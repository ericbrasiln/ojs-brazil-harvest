#!/usr/bin/env python3
"""
harvest_complete.py — Orquestrador da coleta completa de metadados OAI-PMH
de periódicos brasileiros em plataformas OJS.

Executa três fases em sequência, com resumabilidade e checkpoints:
  1. Portais → coleta por set (descobrir sets via ListSets, coletar cada set)
  2. Isolados → coleta integral (sem filtro de set)
  3. Retry → timeout 600s + --no-verify-ssl para falhas das fases 1-2

Uso:
  python3 scripts/harvest_complete.py [opções]

Opções:
  --input FILE        Dataset PKP Beacon filtrado (default: data/processed/ojs_brazil_pkp_beacon.json)
  --output-dir DIR    Diretório de saída (default: data/raw)
  --log-dir DIR       Diretório de logs (default: data/logs)
  --from DATE         Data inicial (default: 2000-01-01)
  --until DATE        Data final (default: {ano atual}-12-31)
  --timeout-set SEC   Timeout por set na Fase 1 (default: 120)
  --timeout-iso SEC   Timeout por isolado na Fase 2 (default: 300)
  --timeout-retry SEC Timeout por retry na Fase 3 (default: 600)
  --delay SEC         Delay entre requisições (default: 1.0)
  --delay-usp SEC     Delay para USP e portais com rate limiting (default: 5.0)
  --skip-unresponsive  Pular endpoints marcados como não responsivos (default: True)
  --resume            Retomar a partir do checkpoint
  --dry-run           Simular sem coletar
  --phase N           Executar apenas a fase N (1, 2 ou 3)
  -v, --verbose       Saída verbosa
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_INPUT = "data/processed/ojs_brazil_pkp_beacon.json"
DEFAULT_OUTPUT_DIR = "data/raw"
DEFAULT_LOG_DIR = "data/logs"
DEFAULT_FROM = "2000-01-01"
DEFAULT_TIMEOUT_SET = 120
DEFAULT_TIMEOUT_ISO = 300
DEFAULT_TIMEOUT_RETRY = 600
DEFAULT_DELAY = 1.0
DEFAULT_DELAY_USP = 5.0

CHECKPOINT_FILE = "data/raw/harvest_complete_checkpoint.json"

# Domínios com rate limiting agressivo
RATE_LIMITED_DOMAINS = ["revistas.usp.br", "scielo.br"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"harvest_complete_{ts}.log"

    logger = logging.getLogger("harvest_complete")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(ch)

    # File (always debug)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Log: {log_file}")
    return logger


# ---------------------------------------------------------------------------
# Pre-flight validation
# ---------------------------------------------------------------------------
def normalize_harvest_date(value: str, is_until: bool = False) -> str:
    if re.fullmatch(r"\d{4}", value):
        return f"{value}-12-31" if is_until else f"{value}-01-01"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Data inválida: {value}. Use YYYY ou YYYY-MM-DD.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Data inválida: {value}. Use uma data real em YYYY-MM-DD.") from exc
    return value


def validate_date_range(from_date: str, until_date: str) -> None:
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(until_date)
    if start > end:
        raise ValueError(f"from ({from_date}) não pode ser posterior a until ({until_date})")


def ensure_ojs_scrape_available() -> None:
    try:
        result = subprocess.run(
            ["ojs-scrape", "--help"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("ojs-scrape não está disponível no PATH") from exc
    help_text = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        raise RuntimeError("ojs-scrape --help falhou; verifique a instalação")
    if "--no-verify-ssl" not in help_text:
        raise RuntimeError("ojs-scrape instalado não suporta --no-verify-ssl; atualize a dependência")


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------
def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    for old, new in [("áàãâ", "a"), ("éèê", "e"), ("íìî", "i"), ("óòõô", "o"), ("úùû", "u"), ("ç", "c")]:
        text = re.sub(f"[{old}]", new, text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:max_len]


def make_output_path(
    output_dir: Path,
    name: str,
    oai_url: str,
    set_spec: str | None = None,
) -> Path:
    slug = slugify(name)
    if not slug or slug == "unknown":
        slug = "unknown_repo"
    identity = f"{oai_url}\0{set_spec or ''}"
    identity_hash = hashlib.sha256(identity.encode()).hexdigest()[:12]
    if set_spec:
        set_slug = slugify(set_spec.split(":")[-1] if ":" in set_spec else set_spec, max_len=30)
        return output_dir / f"{slug}__{set_slug}--{identity_hash}.json"
    return output_dir / f"{slug}--{identity_hash}.json"


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------
def load_checkpoint(output_dir: Path) -> dict:
    cp_path = output_dir / "harvest_complete_checkpoint.json"
    if cp_path.exists():
        with open(cp_path) as f:
            return json.load(f)
    return {
        "phase1_done": False,
        "phase1_portals_processed": [],
        "phase2_done": False,
        "phase2_isolateds_processed": [],
        "phase3_done": False,
        "phase3_retries_processed": [],
    }


def save_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def save_checkpoint(output_dir: Path, checkpoint: dict) -> None:
    save_json_atomic(output_dir / "harvest_complete_checkpoint.json", checkpoint)


def update_checkpoint(output_dir: Path, checkpoint: dict, dry_run: bool) -> None:
    if not dry_run:
        save_checkpoint(output_dir, checkpoint)


# ---------------------------------------------------------------------------
# Descoberta de sets via ListSets (curl, com paginação)
# ---------------------------------------------------------------------------
def discover_sets(oai_url: str, timeout: int = 30, logger=None) -> list[str] | None:
    all_sets: list[str] = []
    url = f"{oai_url}?verb=ListSets"
    page = 0
    max_pages = 50

    try:
        while url and page < max_pages:
            result = subprocess.run(
                ["curl", "-sL", "--max-time", str(timeout), url],
                capture_output=True, text=True, timeout=timeout + 10,
            )
            if result.returncode != 0:
                break
            if "badVerb" in result.stdout or "badArgument" in result.stdout:
                break
            sets = re.findall(r"<setSpec>([^<]+)</setSpec>", result.stdout)
            top_sets = [s for s in sets if ":" not in s]
            all_sets.extend(top_sets)
            token_match = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", result.stdout)
            if token_match and token_match.group(1).strip():
                token = token_match.group(1).strip()
                url = f"{oai_url}?verb=ListSets&resumptionToken={token}"
                page += 1
            else:
                url = None
        return list(dict.fromkeys(all_sets)) if all_sets else None
    except Exception as e:
        if logger:
            logger.debug(f"  discover_sets error: {e}")
        return list(dict.fromkeys(all_sets)) if all_sets else None


# ---------------------------------------------------------------------------
# Coleta de um set ou periódico isolado via ojs-scrape subprocess
# ---------------------------------------------------------------------------
def harvest_one(
    oai_url: str,
    set_spec: str | None,
    output_path: Path,
    from_date: str,
    until_date: str,
    timeout: int,
    delay: float,
    no_verify_ssl: bool = True,
    verbose: bool = False,
) -> dict:
    cmd = ["ojs-scrape", oai_url]
    cmd += ["--from", from_date, "--until", until_date]
    if set_spec:
        cmd += ["--set", set_spec]
    cmd += ["--format", "json", "-o", str(output_path.with_suffix(""))]
    cmd += ["--timeout", str(timeout)]
    cmd += ["--delay", str(delay)]
    if no_verify_ssl:
        cmd.append("--no-verify-ssl")
    if verbose:
        cmd.append("-v")

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 120,
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
            "status": status,
            "record_count": record_count,
            "elapsed": round(elapsed, 1),
            "error": error[:300],
            "output_file": str(output_path),
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return {
            "status": "timeout",
            "record_count": 0,
            "elapsed": round(elapsed, 1),
            "error": f"Process timed out after {timeout + 120}s",
            "output_file": str(output_path),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "status": "error",
            "record_count": 0,
            "elapsed": round(elapsed, 1),
            "error": str(e)[:300],
            "output_file": str(output_path),
        }


# ---------------------------------------------------------------------------
# Fase 1: Portais — coleta por set
# ---------------------------------------------------------------------------
def phase1_portals(
    dataset: list[dict],
    output_dir: Path,
    from_date: str,
    until_date: str,
    timeout: int,
    delay: float,
    delay_usp: float,
    resume: bool,
    dry_run: bool,
    verbose: bool,
    checkpoint: dict,
    logger: logging.Logger,
) -> list[dict]:
    logger.info("=" * 60)
    logger.info("FASE 1: PORTAIS — coleta por set")
    logger.info("=" * 60)

    # Agrupar por URL OAI → portais são URLs compartilhadas por >1 periódico
    url_count: dict[str, int] = {}
    url_to_name: dict[str, str] = {}
    for e in dataset:
        url = e["oai_url"]
        url_count[url] = url_count.get(url, 0) + 1
        if url not in url_to_name:
            url_to_name[url] = e.get("repository_name", "")

    portal_urls = [url for url, c in url_count.items() if c > 1]
    logger.info(f"Portais (URLs com >1 periódico): {len(portal_urls)}")

    processed = set(checkpoint.get("phase1_portals_processed", []))
    all_results: list[dict] = []
    total_records = 0
    total_ok = 0
    total_error = 0
    total_timeout = 0
    total_skip = 0

    for idx, url in enumerate(sorted(portal_urls), 1):
        name = url_to_name.get(url, "?")
        is_rate_limited = any(d in url for d in RATE_LIMITED_DOMAINS)
        actual_delay = delay_usp if is_rate_limited else delay

        if url in processed:
            logger.info(f"[{idx}/{len(portal_urls)}] SKIP (já processado): {name[:50]}")
            total_skip += 1
            continue

        logger.info(f"[{idx}/{len(portal_urls)}] {name[:50]} ({url[:70]})")
        if is_rate_limited:
            logger.info(f"  Rate limiting detectado — delay {actual_delay}s")

        # Descobrir sets
        if dry_run:
            logger.info(f"  DRY RUN: descobrir sets de {url}")
            continue

        sets = discover_sets(url, timeout=30, logger=logger)
        if sets is None:
            logger.warning("  ListSets falhou — pulando")
            total_error += 1
            all_results.append({"oai_url": url, "repository_name": name, "status": "error_listsets", "record_count": 0})
            processed.add(url)
            continue
        if not sets:
            logger.warning("  0 sets encontrados — pulando")
            total_error += 1
            all_results.append({"oai_url": url, "repository_name": name, "status": "empty_listsets", "record_count": 0})
            processed.add(url)
            continue

        logger.info(f"  {len(sets)} sets encontrados — coletando...")

        for set_idx, set_spec in enumerate(sets, 1):
            out_path = make_output_path(output_dir, name, url, set_spec)

            # Resume: pular se arquivo já existe
            if resume and out_path.exists() and out_path.stat().st_size > 100:
                logger.info(f"    [{set_idx}/{len(sets)}] SKIP {set_spec} (já existe)")
                total_skip += 1
                try:
                    with open(out_path) as f:
                        d = json.load(f)
                        recs = len(d) if isinstance(d, list) else 1
                        total_records += recs
                        total_ok += 1
                except Exception:
                    pass
                continue

            logger.info(f"    [{set_idx}/{len(sets)}] {set_spec}")
            result = harvest_one(
                oai_url=url,
                set_spec=set_spec,
                output_path=out_path,
                from_date=from_date,
                until_date=until_date,
                timeout=timeout,
                delay=actual_delay,
                no_verify_ssl=True,
                verbose=verbose,
            )
            result["oai_url"] = url
            result["repository_name"] = name
            result["set_spec"] = set_spec
            all_results.append(result)

            if result["status"] == "ok":
                total_ok += 1
                total_records += result["record_count"]
            elif result["status"] == "timeout":
                total_timeout += 1
            elif result["status"] == "error":
                total_error += 1

            logger.info(
                f"      → {result['status']} | {result['record_count']} records | {result['elapsed']}s"
                + (f" | {result['error'][:60]}" if result["error"] else "")
            )

            time.sleep(actual_delay)

        processed.add(url)
        checkpoint["phase1_portals_processed"] = list(processed)
        update_checkpoint(output_dir, checkpoint, dry_run)

    checkpoint["phase1_done"] = True
    update_checkpoint(output_dir, checkpoint, dry_run)

    logger.info("-" * 40)
    logger.info("FASE 1 CONCLUÍDA")
    logger.info(f"  Portais processados: {len(processed)}")
    logger.info(f"  ✅ OK: {total_ok} | ❌ Erro: {total_error} | ⏱ Timeout: {total_timeout} | ⏭ Skip: {total_skip}")
    logger.info(f"  📊 Registros: {total_records:,}")
    return all_results


# ---------------------------------------------------------------------------
# Fase 2: Isolados — coleta integral
# ---------------------------------------------------------------------------
def phase2_isolateds(
    dataset: list[dict],
    output_dir: Path,
    from_date: str,
    until_date: str,
    timeout: int,
    delay: float,
    resume: bool,
    dry_run: bool,
    verbose: bool,
    checkpoint: dict,
    logger: logging.Logger,
) -> list[dict]:
    logger.info("=" * 60)
    logger.info("FASE 2: ISOLADOS — coleta integral")
    logger.info("=" * 60)

    # URLs únicas com apenas 1 periódico
    url_count: dict[str, int] = {}
    url_to_name: dict[str, str] = {}
    for e in dataset:
        url = e["oai_url"]
        url_count[url] = url_count.get(url, 0) + 1
        if url not in url_to_name:
            url_to_name[url] = e.get("repository_name", "")

    isolated_urls = [url for url, c in url_count.items() if c == 1]
    logger.info(f"Isolados (1 periódico por URL): {len(isolated_urls)}")

    processed = set(checkpoint.get("phase2_isolateds_processed", []))
    all_results: list[dict] = []
    total_records = 0
    total_ok = 0
    total_error = 0
    total_timeout = 0
    total_skip = 0

    for idx, url in enumerate(sorted(isolated_urls), 1):
        name = url_to_name.get(url, "?")

        if url in processed:
            logger.info(f"[{idx}/{len(isolated_urls)}] SKIP (já processado): {name[:50]}")
            total_skip += 1
            continue

        out_path = make_output_path(output_dir, name, url)

        if resume and out_path.exists() and out_path.stat().st_size > 100:
            logger.info(f"[{idx}/{len(isolated_urls)}] SKIP (já existe): {name[:50]}")
            total_skip += 1
            try:
                with open(out_path) as f:
                    d = json.load(f)
                    recs = len(d) if isinstance(d, list) else 1
                    total_records += recs
                    total_ok += 1
            except Exception:
                pass
            continue

        logger.info(f"[{idx}/{len(isolated_urls)}] {name[:50]} ({url[:70]})")

        if dry_run:
            logger.info(f"  DRY RUN: ojs-scrape {url}")
            continue

        result = harvest_one(
            oai_url=url,
            set_spec=None,
            output_path=out_path,
            from_date=from_date,
            until_date=until_date,
            timeout=timeout,
            delay=delay,
            no_verify_ssl=True,
            verbose=verbose,
        )
        result["oai_url"] = url
        result["repository_name"] = name
        all_results.append(result)

        if result["status"] == "ok":
            total_ok += 1
            total_records += result["record_count"]
        elif result["status"] == "timeout":
            total_timeout += 1
        elif result["status"] == "error":
            total_error += 1

        logger.info(
            f"  → {result['status']} | {result['record_count']} records | {result['elapsed']}s"
            + (f" | {result['error'][:60]}" if result["error"] else "")
        )

        processed.add(url)
        if idx % 10 == 0:
            checkpoint["phase2_isolateds_processed"] = list(processed)
            update_checkpoint(output_dir, checkpoint, dry_run)

        time.sleep(delay)

    checkpoint["phase2_isolateds_processed"] = list(processed)
    checkpoint["phase2_done"] = True
    update_checkpoint(output_dir, checkpoint, dry_run)

    logger.info("-" * 40)
    logger.info("FASE 2 CONCLUÍDA")
    logger.info(f"  Isolados processados: {len(processed)}")
    logger.info(f"  ✅ OK: {total_ok} | ❌ Erro: {total_error} | ⏱ Timeout: {total_timeout} | ⏭ Skip: {total_skip}")
    logger.info(f"  📊 Registros: {total_records:,}")
    return all_results


# ---------------------------------------------------------------------------
# Fase 3: Retry — timeout 600s + --no-verify-ssl para falhas
# ---------------------------------------------------------------------------
def phase3_retry(
    output_dir: Path,
    from_date: str,
    until_date: str,
    timeout: int,
    delay: float,
    resume: bool,
    dry_run: bool,
    verbose: bool,
    checkpoint: dict,
    logger: logging.Logger,
) -> list[dict]:
    logger.info("=" * 60)
    logger.info("FASE 3: RETRY — timeout 600s + SSL bypass")
    logger.info("=" * 60)

    # Carregar resultados das fases 1 e 2
    phase1_file = output_dir / "phase1_results.json"
    phase2_file = output_dir / "phase2_results.json"
    all_results: list[dict] = []

    failed: list[dict] = []
    for pf in [phase1_file, phase2_file]:
        if pf.exists():
            with open(pf) as f:
                for r in json.load(f):
                    if r.get("status") in ("timeout", "error") and r.get("set_spec"):
                        failed.append(r)
                    elif r.get("status") in ("timeout", "error") and not r.get("set_spec"):
                        failed.append(r)

    logger.info(f"Targets com falha (timeout/erro) das Fases 1-2: {len(failed)}")

    if not failed:
        logger.info("Nenhuma falha para retry. Encerrando.")
        checkpoint["phase3_done"] = True
        update_checkpoint(output_dir, checkpoint, dry_run)
        return []

    processed = set(checkpoint.get("phase3_retries_processed", []))
    total_ok = 0
    total_error = 0
    total_skip = 0
    total_records = 0

    for idx, target in enumerate(failed, 1):
        url = target["oai_url"]
        name = target.get("repository_name", "?")
        set_spec = target.get("set_spec")
        key = f"{url}::{set_spec or 'iso'}"

        if key in processed:
            total_skip += 1
            continue

        out_path = make_output_path(output_dir, name, url, set_spec)

        if resume and out_path.exists() and out_path.stat().st_size > 100:
            logger.info(f"[{idx}/{len(failed)}] SKIP (já existe): {name[:50]}")
            total_skip += 1
            processed.add(key)
            continue

        label = f"set={set_spec}" if set_spec else "isolado"
        logger.info(f"[{idx}/{len(failed)}] RETRY {label} — {name[:50]} ({url[:60]})")

        if dry_run:
            logger.info(f"  DRY RUN: retry {url} set={set_spec}")
            continue

        result = harvest_one(
            oai_url=url,
            set_spec=set_spec,
            output_path=out_path,
            from_date=from_date,
            until_date=until_date,
            timeout=timeout,
            delay=delay,
            no_verify_ssl=True,
            verbose=verbose,
        )
        result["oai_url"] = url
        result["repository_name"] = name
        result["set_spec"] = set_spec
        result["retry"] = True
        all_results.append(result)

        if result["status"] == "ok":
            total_ok += 1
            total_records += result["record_count"]
        else:
            total_error += 1

        logger.info(
            f"  → {result['status']} | {result['record_count']} records | {result['elapsed']}s"
            + (f" | {result['error'][:60]}" if result["error"] else "")
        )

        processed.add(key)
        if idx % 5 == 0:
            checkpoint["phase3_retries_processed"] = list(processed)
            update_checkpoint(output_dir, checkpoint, dry_run)

        time.sleep(delay)

    checkpoint["phase3_retries_processed"] = list(processed)
    checkpoint["phase3_done"] = True
    update_checkpoint(output_dir, checkpoint, dry_run)

    logger.info("-" * 40)
    logger.info("FASE 3 CONCLUÍDA")
    logger.info(f"  Retries processados: {len(processed)}")
    logger.info(f"  ✅ OK: {total_ok} | ❌ Erro: {total_error} | ⏭ Skip: {total_skip}")
    logger.info(f"  📊 Registros novos: {total_records:,}")
    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orquestrador da coleta completa OAI-PMH de periódicos OJS brasileiros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--from", dest="from_date", default=DEFAULT_FROM)
    parser.add_argument("--until", dest="until_date", default=f"{datetime.now().year}-12-31")
    parser.add_argument("--timeout-set", type=int, default=DEFAULT_TIMEOUT_SET)
    parser.add_argument("--timeout-iso", type=int, default=DEFAULT_TIMEOUT_ISO)
    parser.add_argument("--timeout-retry", type=int, default=DEFAULT_TIMEOUT_RETRY)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--delay-usp", type=float, default=DEFAULT_DELAY_USP)
    parser.add_argument(
        "--skip-unresponsive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pular endpoints marcados como não responsivos (use --no-skip-unresponsive para incluir)",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], help="Executar apenas a fase N")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    input_path = project_root / args.input
    output_dir = project_root / args.output_dir
    log_dir = project_root / args.log_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(log_dir, args.verbose)
    try:
        from_date = normalize_harvest_date(args.from_date)
        until_date = normalize_harvest_date(args.until_date, is_until=True)
        validate_date_range(from_date, until_date)
        if not args.dry_run:
            ensure_ojs_scrape_available()
    except (ValueError, RuntimeError) as exc:
        logger.error(str(exc))
        raise SystemExit(2) from exc

    logger.info(f"harvest_complete.py — {datetime.now().isoformat()}")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"From: {from_date} | Until: {until_date}")
    logger.info(f"Timeouts: set={args.timeout_set}s | iso={args.timeout_iso}s | retry={args.timeout_retry}s")
    logger.info(f"Delay: {args.delay}s (USP: {args.delay_usp}s)")
    logger.info(f"Resume: {args.resume} | Dry run: {args.dry_run}")

    # Carregar dataset
    with open(input_path) as f:
        dataset = json.load(f)
    logger.info(f"Dataset: {len(dataset)} periódicos")

    # Filtrar não responsivos
    if args.skip_unresponsive:
        before = len(dataset)
        dataset = [e for e in dataset if not e.get("unresponsive_endpoint", False)]
        logger.info(f"Filtrados {before - len(dataset)} não responsivos → {len(dataset)} restantes")

    # Carregar checkpoint
    checkpoint = load_checkpoint(output_dir)
    logger.info(f"Checkpoint: F1={'✅' if checkpoint['phase1_done'] else '⏳'} "
                f"F2={'✅' if checkpoint['phase2_done'] else '⏳'} "
                f"F3={'✅' if checkpoint['phase3_done'] else '⏳'}")

    run_phase = args.phase or 0

    # Fase 1: Portais
    if (run_phase == 0 or run_phase == 1) and not checkpoint["phase1_done"]:
        results1 = phase1_portals(
            dataset, output_dir, from_date, until_date,
            args.timeout_set, args.delay, args.delay_usp,
            args.resume, args.dry_run, args.verbose,
            checkpoint, logger,
        )
        if not args.dry_run:
            save_json_atomic(output_dir / "phase1_results.json", results1)
            logger.info(f"Resultados Fase 1: {output_dir / 'phase1_results.json'}")
    elif run_phase == 1 and checkpoint["phase1_done"]:
        logger.info("Fase 1 já concluída. Use --resume para continuar.")
    elif run_phase == 0 and checkpoint["phase1_done"]:
        logger.info("Fase 1 já concluída — pulando.")

    # Fase 2: Isolados
    if (run_phase == 0 or run_phase == 2) and not checkpoint["phase2_done"]:
        results2 = phase2_isolateds(
            dataset, output_dir, from_date, until_date,
            args.timeout_iso, args.delay,
            args.resume, args.dry_run, args.verbose,
            checkpoint, logger,
        )
        if not args.dry_run:
            save_json_atomic(output_dir / "phase2_results.json", results2)
            logger.info(f"Resultados Fase 2: {output_dir / 'phase2_results.json'}")
    elif run_phase == 2 and checkpoint["phase2_done"]:
        logger.info("Fase 2 já concluída.")
    elif run_phase == 0 and checkpoint["phase2_done"]:
        logger.info("Fase 2 já concluída — pulando.")

    # Fase 3: Retry
    if (run_phase == 0 or run_phase == 3) and not checkpoint["phase3_done"]:
        results3 = phase3_retry(
            output_dir, from_date, until_date,
            args.timeout_retry, args.delay,
            args.resume, args.dry_run, args.verbose,
            checkpoint, logger,
        )
        if not args.dry_run:
            save_json_atomic(output_dir / "phase3_results.json", results3)
            logger.info(f"Resultados Fase 3: {output_dir / 'phase3_results.json'}")
    elif run_phase == 3 and checkpoint["phase3_done"]:
        logger.info("Fase 3 já concluída.")
    elif run_phase == 0 and checkpoint["phase3_done"]:
        logger.info("Fase 3 já concluída — pulando.")

    # Resumo final
    logger.info("=" * 60)
    logger.info("RESUMO GERAL")
    logger.info("=" * 60)
    logger.info(f"  Fase 1 (portais): {'✅' if checkpoint['phase1_done'] else '⏳'}")
    logger.info(f"  Fase 2 (isolados): {'✅' if checkpoint['phase2_done'] else '⏳'}")
    logger.info(f"  Fase 3 (retry): {'✅' if checkpoint['phase3_done'] else '⏳'}")
    logger.info(f"  Checkpoint: {output_dir / 'harvest_complete_checkpoint.json'}")

    # Contar arquivos no disco
    json_files = list(output_dir.glob("*.json"))
    json_files = [f for f in json_files if not f.name.startswith("phase") and not f.name.startswith("harvest_complete")]
    total_size = sum(f.stat().st_size for f in json_files)
    logger.info(f"  Arquivos JSON no disco: {len(json_files)} ({total_size / 1e9:.1f} GB)")


if __name__ == "__main__":
    main()