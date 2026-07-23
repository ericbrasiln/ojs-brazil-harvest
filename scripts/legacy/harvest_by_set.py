#!/usr/bin/env python3
"""
harvest_by_set.py — 2ª passada: coleta set por set (revista por revista) dos
portais que falharam com timeout na 1ª passada.

Estratégia:
  1. Carrega o harvest_results da 1ª passada
  2. Filtra portais/URLs com status 'timeout'
  3. Para cada URL, descobre os sets via ListSets
  4. Coleta cada set individualmente com ojs-scrape --set
  5. Salva resultados consolidados

Uso:
  python scripts/harvest_by_set.py [opções]

Opções:
  --input FILE          JSON com resultados da 1ª passada (default: data/raw/harvest_results_*.json mais recente)
  --results FILE        Arquivo harvest_results a processar (auto-detectado se omitido)
  --output-dir DIR      Diretório de saída (default: data/raw)
  --log-dir DIR         Diretório de logs (default: data/logs)
  --from DATE           Data inicial (default: 2000)
  --until DATE          Data final (default: ano atual)
  --timeout SEC         Timeout por set em segundos (default: 120)
  --delay SEC           Delay entre requisições (default: 1.0)
  --skip-unresponsive   Pular endpoints não responsivos
  --only-portals        Processar apenas portais (is_portal=True)
  --all-timeouts        Processar TODOS os timeouts, não só portais
  --resume              Retomar, pulando sets já coletados
  --dry-run             Simular sem chamar ojs-scrape
  -v, --verbose         Saída verbosa
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = "data/raw"
DEFAULT_LOG_DIR = "data/logs"
DEFAULT_FROM = "2000"
DEFAULT_TIMEOUT = 120  # 2 min por set (menor que portal inteiro)
DEFAULT_DELAY = 1.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"harvest_by_set_{ts}.log"

    logger = logging.getLogger("harvest_by_set")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Log: {log_file}")
    return logger


# ---------------------------------------------------------------------------
# Descoberta de sets via ListSets
# ---------------------------------------------------------------------------
def discover_sets(oai_url: str, timeout: int = 30, logger=None) -> list[str] | None:
    """Lista sets de topo (revistas) num endpoint OAI-PMH via curl.
    
    Pagina via resumptionToken e filtra apenas sets de nível superior
    (sem ':' no setSpec), que correspondem a revistas individuais.
    Sets com ':' são sub-seções editoriais (ART, EDI, ABS etc.).
    """
    import re
    all_top_sets = []
    url = f"{oai_url}?verb=ListSets"
    page = 0
    max_pages = 50  # limite de segurança contra loops

    try:
        while url and page < max_pages:
            result = subprocess.run(
                ["curl", "-sL", "--max-time", str(timeout), url],
                capture_output=True, text=True, timeout=timeout + 10,
            )
            if result.returncode != 0:
                if logger:
                    logger.debug(f"  ListSets failed (curl rc={result.returncode}) at page {page}")
                return all_top_sets if all_top_sets else None

            # Verificar erro OAI-PMH
            if 'badVerb' in result.stdout or 'badArgument' in result.stdout:
                if logger:
                    logger.debug(f"  ListSets: badVerb/badArgument em {oai_url}")
                return None

            # Extrair sets — filtrar apenas top-level (sem ':')
            sets = re.findall(r'<setSpec>([^<]+)</setSpec>', result.stdout)
            top_sets = [s for s in sets if ':' not in s]
            all_top_sets.extend(top_sets)

            # Verificar resumptionToken para próxima página
            token_match = re.search(r'<resumptionToken[^>]*>([^<]+)</resumptionToken>', result.stdout)
            if token_match and token_match.group(1).strip():
                token = token_match.group(1).strip()
                url = f"{oai_url}?verb=ListSets&resumptionToken={token}"
                page += 1
            else:
                url = None

            if logger and page == 0:
                logger.debug(f"  ListSets page 0: {len(sets)} total, {len(top_sets)} top-level sets")

        if logger:
            logger.debug(f"  ListSets: {len(all_top_sets)} top-level sets across {page + 1} pages")

        if not all_top_sets:
            if logger:
                logger.debug(f"  ListSets: 0 top-level sets em {oai_url}")
            return None

        return all_top_sets

    except subprocess.TimeoutExpired:
        if logger:
            logger.debug(f"  ListSets: timeout em {oai_url}")
        # Retornar o que já foi descoberto antes do timeout
        return all_top_sets if all_top_sets else None
    except Exception as e:
        if logger:
            logger.debug(f"  ListSets: erro em {oai_url}: {e}")
        return all_top_sets if all_top_sets else None


# ---------------------------------------------------------------------------
# Coleta de um set individual
# ---------------------------------------------------------------------------
def harvest_one_set(
    oai_url: str,
    repository_name: str,
    set_spec: str,
    output_path: Path,
    from_date: str,
    until_date: str,
    timeout: int,
    delay: float,
    verbose: bool = False,
) -> dict:
    """Roda ojs-scrape para um set individual dentro de um portal."""
    cmd = ["ojs-scrape", oai_url]
    cmd += ["--from", from_date, "--until", until_date]
    cmd += ["--set", set_spec]
    cmd += ["--format", "json", "-o", str(output_path.with_suffix(""))]
    cmd += ["--timeout", str(timeout)]
    cmd += ["--delay", str(delay)]
    if verbose:
        cmd.append("-v")

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 60,
        )
        elapsed = time.time() - start

        record_count = 0
        if output_path.exists():
            try:
                with open(output_path) as f:
                    data = json.load(f)
                    record_count = len(data) if isinstance(data, list) else 1
            except (json.JSONDecodeError, OSError):
                pass

        status = "ok" if result.returncode == 0 else "error"
        error = ""
        if result.returncode != 0:
            error = (result.stderr or result.stdout)[-500:]
        elif record_count == 0 and result.stdout:
            if "0 artigos" in result.stdout or "Records collected: 0" in result.stdout:
                status = "empty"

        return {
            "oai_url": oai_url,
            "repository_name": repository_name,
            "set_spec": set_spec,
            "status": status,
            "record_count": record_count,
            "elapsed": round(elapsed, 1),
            "error": error[:300],
            "output_file": str(output_path),
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return {
            "oai_url": oai_url,
            "repository_name": repository_name,
            "set_spec": set_spec,
            "status": "timeout",
            "record_count": 0,
            "elapsed": round(elapsed, 1),
            "error": f"Process timed out after {timeout + 60}s",
            "output_file": str(output_path),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "oai_url": oai_url,
            "repository_name": repository_name,
            "set_spec": set_spec,
            "status": "error",
            "record_count": 0,
            "elapsed": round(elapsed, 1),
            "error": str(e)[:300],
            "output_file": str(output_path),
        }


def slugify(text: str, max_len: int = 60) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[áàãâ]', 'a', text)
    text = re.sub(r'[éèê]', 'e', text)
    text = re.sub(r'[íìî]', 'i', text)
    text = re.sub(r'[óòõô]', 'o', text)
    text = re.sub(r'[úùû]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text[:max_len]


def make_set_output_path(output_dir: Path, portal_name: str, set_spec: str) -> Path:
    """Gera caminho de saída para set individual."""
    name = slugify(portal_name or 'unknown')
    set_slug = slugify(set_spec.split(':')[-1] if ':' in set_spec else set_spec, max_len=30)
    return output_dir / f"{name}__{set_slug}.json"


# ---------------------------------------------------------------------------
# Progress file para o cronjob ler
# ---------------------------------------------------------------------------
PROGRESS_FILE = Path("data/raw/harvest_by_set_progress.json")

def save_progress(portal_idx: int, portal_total: int, portal_name: str,
                  sets_done: int, sets_total: int, ok_count: int,
                  error_count: int, timeout_count: int, total_records: int,
                  status: str = "running"):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "portal_idx": portal_idx,
        "portal_total": portal_total,
        "portal_name": portal_name,
        "sets_done": sets_done,
        "sets_total": sets_total,
        "ok_count": ok_count,
        "error_count": error_count,
        "timeout_count": timeout_count,
        "total_records": total_records,
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="2ª passada: coleta set por set dos portais com timeout",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--results", default=None, help="Arquivo harvest_results a processar (auto-detectado)")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--from", dest="from_date", default=DEFAULT_FROM)
    parser.add_argument("--until", dest="until_date", default=str(datetime.now().year))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--only-portals", action="store_true", help="Processar apenas portais")
    parser.add_argument("--all-timeouts", action="store_true", help="Processar todos os timeouts, não só portais")
    parser.add_argument("--resume", action="store_true", help="Pular sets já coletados")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / args.output_dir
    log_dir = project_root / args.log_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(log_dir, args.verbose)
    logger.info(f"harvest_by_set.py iniciado — {datetime.now().isoformat()}")

    # Encontrar harvest_results mais recente
    results_files = sorted(project_root.glob("data/raw/harvest_results_*.json"))
    if not results_files:
        logger.error("Nenhum arquivo harvest_results encontrado em data/raw/")
        sys.exit(1)

    if args.results:
        results_file = Path(args.results)
    else:
        results_file = results_files[-1]
        logger.info(f"Usando resultados: {results_file}")

    # Carregar resultados da 1ª passada
    with open(results_file) as f:
        first_pass = json.load(f)
    logger.info(f"1ª passada: {len(first_pass)} entradas")

    # Filtrar timeouts
    if args.all_timeouts:
        candidates = [r for r in first_pass if r['status'] == 'timeout']
        logger.info(f"Modo: todos os timeouts ({len(candidates)})")
    elif args.only_portals:
        candidates = [r for r in first_pass if r['status'] == 'timeout' and r.get('is_portal')]
        logger.info(f"Modo: apenas portais com timeout ({len(candidates)})")
    else:
        # Default: todos os timeouts
        candidates = [r for r in first_pass if r['status'] == 'timeout']
        logger.info(f"Modo: todos os timeouts ({len(candidates)})")

    if not candidates:
        logger.info("Nenhum candidato. Encerrando.")
        return

    # Resume: pular sets já coletados
    existing_sets = set()
    if args.resume:
        existing_files = {f.name for f in output_dir.glob("*.json") if not f.name.startswith("harvest_results") and not f.name.startswith("harvest_by_set")}
        logger.info(f"Resume: {len(existing_files)} arquivos já existentes")

    # Estatísticas gerais
    total_ok = 0
    total_error = 0
    total_timeout = 0
    total_empty = 0
    total_records = 0
    total_sets_discovered = 0
    total_sets_harvested = 0
    all_results = []
    portals_no_sets = 0
    portals_error = 0

    for portal_idx, portal in enumerate(candidates, 1):
        oai_url = portal['oai_url']
        portal_name = portal.get('repository_name', '') or '(sem nome)'
        n_journals = portal.get('n_journals', 1)

        logger.info(f"[{portal_idx}/{len(candidates)}] {portal_name[:50]} ({n_journals} journals) — {oai_url}")

        # Descobrir sets
        sets = discover_sets(oai_url, timeout=30, logger=logger)

        if sets is None:
            logger.warning(f"  ListSets falhou — pulando portal")
            portals_error += 1
            all_results.append({
                "oai_url": oai_url,
                "repository_name": portal_name,
                "set_spec": None,
                "status": "error_listsets",
                "record_count": 0,
                "elapsed": 0,
                "error": "ListSets failed or returned no sets",
                "output_file": "",
                "phase": "discovery",
            })
            save_progress(portal_idx, len(candidates), portal_name,
                         0, 0, total_ok, total_error + 1, total_timeout, total_records)
            continue

        if not sets:
            logger.warning(f"  0 sets encontrados — pulando portal")
            portals_no_sets += 1
            all_results.append({
                "oai_url": oai_url,
                "repository_name": portal_name,
                "set_spec": None,
                "status": "empty_listsets",
                "record_count": 0,
                "elapsed": 0,
                "error": "0 sets returned",
                "output_file": "",
                "phase": "discovery",
            })
            save_progress(portal_idx, len(candidates), portal_name,
                         0, 0, total_ok, total_error + 1, total_timeout, total_records)
            continue

        total_sets_discovered += len(sets)
        logger.info(f"  {len(sets)} sets encontrados — coletando...")

        # Coletar set por set
        sets_ok = 0
        sets_error = 0
        sets_timeout = 0
        portal_records = 0

        for set_idx, set_spec in enumerate(sets, 1):
            output_path = make_set_output_path(output_dir, portal_name, set_spec)

            # Resume: pular se já existe
            if args.resume and output_path.exists():
                existing_size = output_path.stat().st_size
                if existing_size > 100:
                    logger.info(f"    [{set_idx}/{len(sets)}] SKIP {set_spec} (já existe: {existing_size} bytes)")
                    # Contar registros do arquivo existente
                    try:
                        with open(output_path) as f:
                            d = json.load(f)
                            recs = len(d) if isinstance(d, list) else 1
                            sets_ok += 1
                            portal_records += recs
                            total_records += recs
                    except:
                        pass
                    continue

            if args.dry_run:
                logger.info(f"    [{set_idx}/{len(sets)}] DRY RUN: ojs-scrape {oai_url} --set {set_spec}")
                continue

            logger.info(f"    [{set_idx}/{len(sets)}] {set_spec}")
            result = harvest_one_set(
                oai_url=oai_url,
                repository_name=portal_name,
                set_spec=set_spec,
                output_path=output_path,
                from_date=args.from_date,
                until_date=args.until_date,
                timeout=args.timeout,
                delay=args.delay,
                verbose=args.verbose,
            )
            result['phase'] = 'set_collection'
            all_results.append(result)

            status = result['status']
            if status == 'ok':
                sets_ok += 1
                total_ok += 1
                portal_records += result['record_count']
                total_records += result['record_count']
            elif status == 'timeout':
                sets_timeout += 1
                total_timeout += 1
            elif status == 'empty':
                total_empty += 1
            else:
                sets_error += 1
                total_error += 1

            total_sets_harvested += 1
            logger.info(f"      → {status} | {result['record_count']} records | {result['elapsed']}s"
                        + (f" | {result['error'][:60]}" if result['error'] else ""))

            save_progress(portal_idx, len(candidates), portal_name,
                         set_idx, len(sets), total_ok, total_error, total_timeout, total_records)

        logger.info(f"  Portal {portal_name[:40]}: {sets_ok} ok, {sets_error} err, {sets_timeout} timeout, {portal_records} records")

    # ---- Salvar resultados consolidados ----
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"harvest_by_set_results_{ts}.json"
    with open(results_path, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # ---- Resumo ----
    logger.info("=" * 60)
    logger.info("RESUMO DA COLETA POR SET")
    logger.info(f"  Portais processados: {len(candidates)}")
    logger.info(f"  ListSets falhou: {portals_error}")
    logger.info(f"  ListSets vazio: {portals_no_sets}")
    logger.info(f"  Sets descobertos: {total_sets_discovered}")
    logger.info(f"  Sets coletados: {total_sets_harvested}")
    logger.info(f"  ✅ Sucesso: {total_ok}")
    logger.info(f"  📭 Vazio: {total_empty}")
    logger.info(f"  ⏱ Timeout: {total_timeout}")
    logger.info(f"  ❌ Erro: {total_error}")
    logger.info(f"  Total de registros: {total_records:,}")
    logger.info(f"  Resultados: {results_path}")

    # Salvar progresso final
    save_progress(len(candidates), len(candidates), "(concluído)",
                  total_sets_discovered, total_sets_discovered,
                  total_ok, total_error, total_timeout, total_records, status="done")

    return all_results


if __name__ == "__main__":
    main()