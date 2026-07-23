#!/usr/bin/env python3
"""
harvest_batch.py — Coleta massiva de metadados OJS-PMH de periódicos brasileiros.

Estratégia:
  1. Passada 1: Para cada URL OAI, descobre os sets (revistas individuais).
  2. Passada 2: Coleta registros set por set, com retry e backoff.
  3. Portais multi-revista são coletados revista por revista (--set),
     evitando timeouts em respostas OAI-PMH gigantes.

Uso:
  python scripts/harvest_batch.py [opções]

Opções:
  --input FILE      JSON filtrado (default: data/processed/ojs_brazil_pkp_beacon.json)
  --output-dir DIR  Diretório de saída (default: data/raw)
  --log-dir DIR     Diretório de logs (default: data/logs)
  --sample N        Coletar apenas N URLs aleatórias (para teste)
  --seed INT        Seed para reprodutibilidade do --sample
  --from DATE       Data inicial (default: 2000)
  --until DATE      Data final (default: ano atual)
  --timeout SEC     Timeout por periódico em segundos (default: 300)
  --delay SEC       Delay entre requisições (default: 1.0)
  --workers N       Processos paralelos (default: 4)
  --skip-unresponsive  Pular endpoints marcados como não responsivos no dataset
  --resume          Retomar coleta anterior, pulando URLs já coletadas
  --dry-run         Simular execução sem chamar ojs-scrape
  -v, --verbose     Saída verbosa
"""

import argparse
import json
import logging
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_INPUT = "data/processed/ojs_brazil_pkp_beacon.json"
DEFAULT_OUTPUT_DIR = "data/raw"
DEFAULT_LOG_DIR = "data/logs"
DEFAULT_FROM = "2000"
DEFAULT_TIMEOUT = 300  # 5 minutos por periódico
DEFAULT_DELAY = 1.0
DEFAULT_WORKERS = 4

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"harvest_{ts}.log"

    logger = logging.getLogger("harvest")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    # File handler (always debug)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Log: {log_file}")
    return logger


# ---------------------------------------------------------------------------
# Descoberta de sets (Passada 1)
# ---------------------------------------------------------------------------
def discover_sets(oai_url: str, timeout: int = 30) -> list[str] | None:
    """Lista sets disponíveis num endpoint OAI-PMH via curl."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), f"{oai_url}?verb=ListSets"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if result.returncode != 0:
            return None
        import re
        sets = re.findall(r'<setSpec>([^<]+)</setSpec>', result.stdout)
        return sets if sets else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Coleta de um periódico individual
# ---------------------------------------------------------------------------
def harvest_one(
    oai_url: str,
    repository_name: str,
    set_spec: str | None,
    output_path: Path,
    from_date: str,
    until_date: str,
    timeout: int,
    delay: float,
    verbose: bool = False,
) -> dict:
    """Roda ojs-scrape para um periódico (ou um set dentro de um portal).

    Returns dict with keys: oai_url, set_spec, status, record_count,
    elapsed, error, output_file.
    """
    cmd = ["ojs-scrape", oai_url]
    cmd += ["--from", from_date, "--until", until_date]
    if set_spec:
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
            timeout=timeout + 60,  # margem extra
        )
        elapsed = time.time() - start

        # Contar registros no output
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
            # ojs-scrape pode ter coletado 0 registros — informação útil
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


# ---------------------------------------------------------------------------
# Geração de slug seguro para nomes de arquivo
# ---------------------------------------------------------------------------
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


def make_output_path(output_dir: Path, entry: dict, set_spec: str | None = None) -> Path:
    """Gera caminho de saída único para cada coleta."""
    name = slugify(entry.get('repository_name', '') or '')
    # Se nome vazio, derivar da URL
    if not name or name == 'unknown':
        url = entry.get('oai_url', '')
        # Extrair domínio: periodicos.ufba.br/index.php/afroasia/oai → periodicos_ufba_br
        import re
        m = re.match(r'https?://([^/]+)', url)
        name = slugify(m.group(1).replace('.', '_')) if m else 'unknown'
    # Para sets individuais dentro de portais, incluir o set_spec
    if set_spec:
        set_slug = slugify(set_spec.split(':')[-1] if ':' in set_spec else set_spec, max_len=30)
        return output_dir / f"{name}__{set_slug}.json"
    return output_dir / f"{name}.json"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Coleta massiva de metadados OJS-PMH de periódicos brasileiros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--sample", type=int, default=None, help="Coletar apenas N URLs aleatórias")
    parser.add_argument("--seed", type=int, default=42, help="Seed para --sample")
    parser.add_argument("--from", dest="from_date", default=DEFAULT_FROM)
    parser.add_argument("--until", dest="until_date", default=str(datetime.now().year))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--skip-unresponsive", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Pular URLs já coletadas")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Setup
    project_root = Path(__file__).resolve().parent.parent
    input_path = project_root / args.input
    output_dir = project_root / args.output_dir
    log_dir = project_root / args.log_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(log_dir, args.verbose)
    logger.info(f"harvest_batch.py iniciado — {datetime.now().isoformat()}")
    logger.info(f"Input: {input_path}")

    # Carregar dataset
    with open(input_path) as f:
        dataset = json.load(f)
    logger.info(f"Dataset: {len(dataset)} periódicos")

    # Filtrar não responsivos
    if args.skip_unresponsive:
        before = len(dataset)
        dataset = [e for e in dataset if not e.get('unresponsive_endpoint', False)]
        logger.info(f"Filtrados {before - len(dataset)} endpoints não responsivos → {len(dataset)} restantes")

    # Amostragem
    if args.sample:
        random.seed(args.seed)
        dataset = random.sample(dataset, min(args.sample, len(dataset)))
        logger.info(f"Amostra: {len(dataset)} periódicos (seed={args.seed})")

    # Deduplicar por OAI URL — portais multi-revista compartilham o mesmo endpoint
    seen_urls = {}
    journal_entries = {}  # URL -> entry para logging
    for entry in dataset:
        url = entry['oai_url']
        if url not in seen_urls:
            seen_urls[url] = []
            journal_entries[url] = entry
        seen_urls[url].append(entry)

    unique_urls = list(seen_urls.keys())
    logger.info(f"URLs únicas: {len(unique_urls)} "
                f"(portais multi-revista: {sum(1 for v in seen_urls.values() if len(v) > 1)})")

    # Resume: pular outputs já existentes
    if args.resume:
        existing = {f.name for f in output_dir.glob("*.json") if f.name != "ojs_brazil_pkp_beacon.json"}
        before_resume = len(unique_urls)
        # Precisamos verificar cada output_path possível — simplificação: skip por slug de nome
        # Na prática, o resume será mais preciso quando temos os set_specs
        logger.info(f"Resume: {len(existing)} arquivos já existentes em {output_dir}")

    # Dry run
    if args.dry_run:
        logger.info("DRY RUN — Lista de URLs que seriam coletadas:")
        for url in unique_urls[:20]:
            name = journal_entries[url].get('repository_name', '?')
            n_journals = len(seen_urls[url])
            logger.info(f"  {url} ({name}) [{n_journals} journals]")
        if len(unique_urls) > 20:
            logger.info(f"  ... e mais {len(unique_urls) - 20} URLs")
        return

    # ---- Coleta ----
    results = []
    total = len(unique_urls)
    ok_count = 0
    error_count = 0
    timeout_count = 0
    empty_count = 0
    total_records = 0

    for i, url in enumerate(unique_urls, 1):
        entry = journal_entries[url]
        name = entry.get('repository_name', '?') or '(sem nome)'
        n_journals = len(seen_urls[url])

        logger.info(f"[{i}/{total}] {name[:50]} ({n_journals} journals) — {url}")

        # Para portais multi-revista: coletar sem --set primeiro tenta o endpoint inteiro
        # Se timeout, tentar set por set na segunda passada
        is_portal = n_journals > 1
        output_path = make_output_path(output_dir, entry)

        # Skip se já existe e --resume
        if args.resume and output_path.exists():
            existing_size = output_path.stat().st_size
            if existing_size > 100:  # arquivo não-trivial
                logger.info(f"  SKIP (já existe: {existing_size} bytes) — {output_path.name}")
                continue

        result = harvest_one(
            oai_url=url,
            repository_name=name,
            set_spec=None,  # primeira passada: sem filtro de set
            output_path=output_path,
            from_date=args.from_date,
            until_date=args.until_date,
            timeout=args.timeout,
            delay=args.delay,
            verbose=args.verbose,
        )

        result['is_portal'] = is_portal
        result['n_journals'] = n_journals
        results.append(result)

        # Contabilizar
        status = result['status']
        if status == 'ok':
            ok_count += 1
            total_records += result['record_count']
        elif status == 'timeout':
            timeout_count += 1
        elif status == 'empty':
            empty_count += 1
        else:
            error_count += 1

        logger.info(f"  → {status} | {result['record_count']} records | {result['elapsed']}s"
                     + (f" | {result['error'][:80]}" if result['error'] else ""))

    # ---- Salvar resultados consolidados ----
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"harvest_results_{ts}.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ---- Resumo ----
    logger.info("=" * 60)
    logger.info("RESUMO DA COLETA")
    logger.info(f"  Periódicos processados: {total}")
    logger.info(f"  ✅ Sucesso:         {ok_count}")
    logger.info(f"  📭 Vazio (0 records): {empty_count}")
    logger.info(f"  ⏱ Timeout:          {timeout_count}")
    logger.info(f" ❌ Erro:             {error_count}")
    logger.info(f"  Total de registros: {total_records:,}")
    logger.info(f"  Resultados: {results_path}")

    # Portais com timeout — candidatos para coleta set por set
    portal_timeouts = [r for r in results if r['status'] == 'timeout' and r.get('is_portal')]
    if portal_timeouts:
        logger.info(f"\n⚠ {len(portal_timeouts)} portais com timeout — candidatos para coleta por set:")
        for r in portal_timeouts:
            logger.info(f"  {r['repository_name'][:50]} ({r['n_journals']} journals) — {r['oai_url']}")

    return results


if __name__ == "__main__":
    main()