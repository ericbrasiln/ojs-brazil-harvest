#!/usr/bin/env python3
"""
retry_p2_errors.py — Etapa 3: Retry de sets P2 e 2b com erro (não-vazios)

Estratégia:
1. Carrega P2 e 2b results
2. Filtra: remove noRecordsMatch (vazio), USP, permanent 500
3. Deduplica: pula sets já OK em P2 ou 2b, e arquivos já no disco
4. Retry com SSL bypass + timeout 600s
5. Usa OAIPMHClient diretamente

NÃO duplica dados: triple check (P2 ok + 2b ok + arquivo existe).
"""

import json
import glob
import time
import os
import sys
import logging
import warnings
import re
from datetime import datetime
from collections import Counter
from pathlib import Path

warnings.filterwarnings('ignore')

# ─── SSL bypass ─────────────────────────────────────────────────────────
import requests
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request
# ────────────────────────────────────────────────────────────────────────

from ojs_scrape.oaipmh import OAIPMHClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path('data/raw')

def slugify(text, max_len=60):
    text = text.lower().strip()
    for old, new in [('áàãâ','a'),('éèê','e'),('íìî','i'),('óòõô','o'),('úùû','u'),('ç','c')]:
        text = re.sub(f'[{old}]', new, text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text[:max_len]


def harvest_one_set(oai_url, set_spec, from_date, until_date, timeout=600, delay=1.5):
    try:
        with OAIPMHClient(oai_url, timeout=timeout, delay=delay) as client:
            articles = list(client.list_records(
                metadata_prefix="oai_dc",
                set_spec=set_spec,
                from_date=from_date,
                until_date=until_date,
            ))
            return [a.to_dict() for a in articles], None
    except Exception as e:
        return [], str(e)[:300]


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Etapa 3: Retry P2/2b error sets')
    parser.add_argument('--timeout', type=int, default=600, help='Timeout por set (s)')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay entre requisições (s)')
    parser.add_argument('--resume', action='store_true', help='Pular sets já processados')
    parser.add_argument('--dry-run', action='store_true', help='Simular sem coletar')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    from_date = "2000-01-01"
    until_date = f"{datetime.now().year}-12-31"

    # ── Load results ──────────────────────────────────────────────────
    p2_file = sorted(glob.glob('data/raw/harvest_by_set_results_*.json'))[-1]
    with open(p2_file) as f:
        p2 = json.load(f)

    r2b_files = sorted(glob.glob('data/raw/retry_portals_results_*.json'))
    r2b = []
    if r2b_files:
        with open(r2b_files[-1]) as f:
            r2b = json.load(f)

    # ── Build sets already OK (triple dedup) ─────────────────────────
    ok_sets = set()  # (url, set_spec) already collected
    for r in p2:
        if r.get('status') == 'ok' and r.get('record_count', 0) > 0:
            ok_sets.add((r.get('oai_url', ''), r.get('set_spec', '')))
    for r in r2b:
        if r.get('status') == 'ok' and r.get('record_count', 0) > 0:
            ok_sets.add((r.get('oai_url', ''), r.get('set_spec', '')))

    # ── Also check files on disk ─────────────────────────────────────
    disk_sets = set()
    for fp in glob.glob('data/raw/*__*.json'):
        if os.path.getsize(fp) > 100:
            bname = os.path.basename(fp).replace('.json', '')
            disk_sets.add(bname.lower())
    logger.info(f"Sets já OK (P2+2b): {len(ok_sets)} | Arquivos no disco: {len(disk_sets)}")

    # ── Build retry targets ──────────────────────────────────────────
    # From P2: errors that are NOT noRecordsMatch, NOT USP, NOT permanent 500
    retry_targets = []  # (url, set_spec, portal_name, error, source)
    seen = set()

    for r in p2:
        if r.get('status') in ('ok', 'empty'):
            continue
        url, spec = r.get('oai_url', ''), r.get('set_spec', '')
        err = r.get('error', '')

        # Skip if already OK
        if (url, spec) in ok_sets:
            continue
        # Skip USP
        if 'usp.br' in url:
            continue
        # Skip noRecordsMatch (empty set)
        if 'noRecordsMatch' in err:
            continue
        # Skip permanent 500 on ListRecords (not timeout)
        if '500 Server Error' in err and 'timed out' not in err.lower():
            continue

        key = (url, spec)
        if key not in seen:
            seen.add(key)
            retry_targets.append((url, spec, r.get('repository_name', ''), err[:80], 'P2'))

    # From 2b: errors NOT noRecordsMatch
    for r in r2b:
        if r.get('status') in ('ok', 'empty'):
            continue
        url, spec = r.get('oai_url', ''), r.get('set_spec', '')
        err = r.get('error', '')

        # Skip if already OK
        if (url, spec) in ok_sets:
            continue
        # Skip noRecordsMatch
        if 'noRecordsMatch' in err:
            continue
        # Skip permanent server errors
        if 'ListSets failed' in err:
            continue

        key = (url, spec)
        if key not in seen:
            seen.add(key)
            retry_targets.append((url, spec, r.get('repository_name', ''), err[:80], '2b'))

    logger.info(f"Retry targets: {len(retry_targets)} sets")
    logger.info(f"  From P2: {sum(1 for t in retry_targets if t[4] == 'P2')}")
    logger.info(f"  From 2b: {sum(1 for t in retry_targets if t[4] == '2b')}")

    # ── Progress file ────────────────────────────────────────────────
    progress_file = 'data/raw/retry_p2_errors_progress.json'
    completed = set()
    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            progress = json.load(f)
        completed = set((e[0], e[1]) for e in progress.get('completed', []))
        logger.info(f"Resume: {len(completed)} sets já processados")

    # ── Harvest ────────────────────────────────────────────────────────
    total_ok = 0
    total_err = 0
    total_skip = 0
    total_records = 0

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    all_results = []

    for idx, (url, spec, name, err, source) in enumerate(retry_targets, 1):
        if (url, spec) in completed:
            total_skip += 1
            continue

        # Triple dedup: also check file on disk
        fname = f"{slugify(name)}__{slugify(spec.split(':')[-1] if ':' in spec else spec, max_len=30)}.json"
        fpath = OUTPUT_DIR / fname
        if fpath.exists() and fpath.stat().st_size > 100:
            logger.info(f"[{idx}/{len(retry_targets)}] SKIP (file exists): {spec} @ {url[:50]}")
            total_skip += 1
            completed.add((url, spec))
            continue

        logger.info(f"\n[{idx}/{len(retry_targets)}] ({source}) {spec} @ {name[:40]}")
        logger.info(f"  Original error: {err}")

        if args.dry_run:
            continue

        records, error = harvest_one_set(url, spec, from_date, until_date, timeout=args.timeout, delay=args.delay)

        if records:
            with open(fpath, 'w') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            total_ok += 1
            total_records += len(records)
            logger.info(f"  ✅ {len(records):,} registros → {fname}")
            all_results.append({
                'oai_url': url, 'repository_name': name, 'set_spec': spec,
                'status': 'ok', 'record_count': len(records),
                'output_file': str(fpath), 'source': source,
            })
        else:
            total_err += 1
            logger.info(f"  ❌ {error[:80] if error else 'unknown'}")
            all_results.append({
                'oai_url': url, 'repository_name': name, 'set_spec': spec,
                'status': 'error', 'record_count': 0, 'error': error[:300] if error else '',
                'source': source,
            })

        completed.add((url, spec))

        # Save progress every 5 sets
        if idx % 5 == 0:
            progress = {
                'timestamp': datetime.now().isoformat(),
                'completed': [[c[0], c[1]] for c in completed],
                'total_ok': total_ok, 'total_err': total_err,
                'total_skip': total_skip, 'total_records': total_records,
            }
            with open(progress_file, 'w') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)

        time.sleep(args.delay)

    # ── Final report ──────────────────────────────────────────────────
    result_file = OUTPUT_DIR / f'retry_p2_errors_results_{ts}.json'
    with open(result_file, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    logger.info("\n" + "=" * 50)
    logger.info("RESULTADO FINAL — Retry P2 Errors")
    logger.info("=" * 50)
    logger.info(f"  Sets processados: {len(completed)}")
    logger.info(f"  OK: {total_ok}")
    logger.info(f"  Erro: {total_err}")
    logger.info(f"  Skip: {total_skip}")
    logger.info(f"  📊 Registros novos: {total_records:,}")
    logger.info(f"  Resultados: {result_file}")


if __name__ == '__main__':
    main()