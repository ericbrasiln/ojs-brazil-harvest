#!/usr/bin/env python3
"""
retry_portals_by_set.py — Etapa 2b: Retry de portais por set

Estratégia:
1. Carrega portais com erro da P1 (excluindo SSL, já tratado na Etapa 1)
2. Identifica quais sets JÁ foram coletados com sucesso na P2 → pula
3. Identifica quais sets falharam na P2 → retry com timeout 300s
4. Portais novos (não na P2): descobre sets e coleta tudo
5. SSL bypass integrado (monkey-patch)
6. Usa OAIPMHClient diretamente (não subprocess ojs-scrape)

NÃO duplica dados: verifica resultados P2 e arquivos existentes antes de coletar.
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

# ─── SSL bypass monkey-patch ───────────────────────────────────────────
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

# ─── Slugify ────────────────────────────────────────────────────────────
def slugify(text, max_len=60):
    text = text.lower().strip()
    for old, new in [('áàãâ','a'),('éèê','e'),('íìî','i'),('óòõô','o'),('úùû','u'),('ç','c')]:
        text = re.sub(f'[{old}]', new, text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text[:max_len]

# ─── Discover sets via requests (not subprocess) ────────────────────────
def discover_sets(oai_url, timeout=30):
    """List top-level sets (no ':') from an OAI-PMH endpoint."""
    all_sets = []
    url = f"{oai_url}?verb=ListSets"
    page = 0
    max_pages = 50

    try:
        while url and page < max_pages:
            r = requests.get(url, timeout=timeout, verify=False)
            if r.status_code != 200:
                break
            if 'badVerb' in r.text or 'badArgument' in r.text:
                break

            sets = re.findall(r'<setSpec>([^<]+)</setSpec>', r.text)
            top_sets = [s for s in sets if ':' not in s]
            all_sets.extend(top_sets)

            match = re.search(r'<resumptionToken[^>]*>([^<]+)</resumptionToken>', r.text)
            if match and match.group(1).strip():
                url = f"{oai_url}?verb=ListSets&resumptionToken={match.group(1).strip()}"
                page += 1
            else:
                url = None
        return list(dict.fromkeys(all_sets)) if all_sets else None

    except Exception as e:
        logger.warning(f"  discover_sets error: {e}")
        return list(dict.fromkeys(all_sets)) if all_sets else None


# ─── Harvest one set ────────────────────────────────────────────────────
def harvest_one_set(oai_url, set_spec, from_date, until_date, timeout=300, delay=1.0):
    """Harvest a single set using OAIPMHClient with SSL bypass."""
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


# ─── Load P2 successful sets → skip these ──────────────────────────────
def load_p2_ok_sets():
    """Load sets already successfully collected in P2."""
    p2_files = sorted(glob.glob('data/raw/harvest_by_set_results_*.json'))
    if not p2_files:
        return {}  # url → set of set_specs

    p2_ok = {}  # url → {set_spec: record_count}
    with open(p2_files[-1]) as f:
        p2 = json.load(f)

    for entry in p2:
        if entry.get('status') == 'ok':
            url = entry.get('oai_url', '')
            spec = entry.get('set_spec', '')
            if url not in p2_ok:
                p2_ok[url] = {}
            p2_ok[url][spec] = entry.get('record_count', 0)

    return p2_ok


# ─── Load P2 error sets → retry these ───────────────────────────────────
def load_p2_error_sets():
    """Load sets that failed in P2 → need retry."""
    p2_files = sorted(glob.glob('data/raw/harvest_by_set_results_*.json'))
    if not p2_files:
        return {}

    p2_err = {}  # url → {set_spec: error}
    with open(p2_files[-1]) as f:
        p2 = json.load(f)

    for entry in p2:
        if entry.get('status') not in ('ok', 'empty'):
            url = entry.get('oai_url', '')
            spec = entry.get('set_spec', '')
            if url not in p2_err:
                p2_err[url] = {}
            p2_err[url][spec] = entry.get('error', '')[:100]

    return p2_err


# ─── Main ────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Etapa 2b: Retry de portais por set')
    parser.add_argument('--timeout', type=int, default=300, help='Timeout por set (s)')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay entre requisições (s)')
    parser.add_argument('--resume', action='store_true', help='Pular sets já coletados')
    parser.add_argument('--dry-run', action='store_true', help='Simular sem coletar')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Load data ────────────────────────────────────────────────────
    p1_file = sorted(glob.glob('data/raw/harvest_results_*.json'))[-1]
    with open(p1_file) as f:
        p1 = json.load(f)

    # P2 successful sets → DO NOT re-collect
    p2_ok = load_p2_ok_sets()
    logger.info(f"P2 OK sets: {sum(len(v) for v in p2_ok.values())} sets em {len(p2_ok)} portais")

    # P2 error sets → RETRY these
    p2_err = load_p2_error_sets()
    logger.info(f"P2 error sets: {sum(len(v) for v in p2_err.values())} sets em {len(p2_err)} portais")

    # ── Build target list ──────────────────────────────────────────────
    ssl_urls = set(r.get('oai_url', '') for r in p1
                   if 'SSLError' in str(r.get('error', '')) or 'certificate' in str(r.get('error', '')))

    # Portals from P1 with errors (excluding SSL)
    p1_portal_errors = {}
    for r in p1:
        if not r.get('is_portal') or r.get('record_count', 0) > 0:
            continue
        url = r.get('oai_url', '')
        if url in ssl_urls:
            continue
        p1_portal_errors[url] = r.get('repository_name', '')

    logger.info(f"P1 portals com erro (excl SSL): {len(p1_portal_errors)}")

    # Combine: portals from P1 errors + portals with P2 error sets
    all_portal_urls = set(p1_portal_errors.keys()) | set(p2_err.keys())
    logger.info(f"Total portais para retry: {len(all_portal_urls)}")

    # ── Progress file ──────────────────────────────────────────────────
    progress_file = 'data/raw/retry_portals_progress.json'
    completed_urls = set()
    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            progress = json.load(f)
        completed_urls = set(progress.get('completed_urls', []))
        logger.info(f"Resume: {len(completed_urls)} portais já processados")

    # ── Harvest ────────────────────────────────────────────────────────
    from_date = "2000-01-01"
    until_date = f"{datetime.now().year}-12-31"

    total_sets_ok = 0
    total_sets_err = 0
    total_sets_skip = 0
    total_records = 0

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    all_results = []

    for idx, url in enumerate(sorted(all_portal_urls), 1):
        if url in completed_urls:
            logger.info(f"\n[{idx}/{len(all_portal_urls)}] SKIP (já processado): {url[:70]}")
            continue

        # Find name
        name = p1_portal_errors.get(url, '')
        if not name:
            _p2f = sorted(glob.glob('data/raw/harvest_by_set_results_*.json'))
            if _p2f:
                with open(_p2f[-1]) as _f:
                    for e in json.load(_f):
                        if e.get('oai_url') == url:
                            name = e.get('repository_name', '')
                            break

        logger.info(f"\n[{idx}/{len(all_portal_urls)}] {name[:50]} ({url[:70]})")

        # Discover sets
        sets = discover_sets(url, timeout=30)
        if sets is None:
            logger.warning(f"  ListSets falhou — pulando")
            all_results.append({
                'oai_url': url, 'repository_name': name,
                'set_spec': None, 'status': 'error_listsets',
                'record_count': 0, 'error': 'ListSets failed',
            })
            continue

        if not sets:
            logger.warning(f"  0 sets — pulando")
            all_results.append({
                'oai_url': url, 'repository_name': name,
                'set_spec': None, 'status': 'empty_listsets',
                'record_count': 0, 'error': '0 sets returned',
            })
            continue

        logger.info(f"  {len(sets)} sets encontrados")

        # Determine which sets to harvest
        ok_sets_for_url = p2_ok.get(url, {})
        err_sets_for_url = p2_err.get(url, {})
        is_known_portal = url in ok_sets_for_url or url in err_sets_for_url

        sets_to_harvest = []
        for spec in sets:
            # Skip if already OK in P2 (unless resume re-checks file size)
            if spec in ok_sets_for_url:
                sets_to_harvest.append((spec, 'skip_ok'))
                continue
            # If error in P2 → retry
            if spec in err_sets_for_url:
                sets_to_harvest.append((spec, 'retry_error'))
                continue
            # New set (not in P2 at all) → harvest
            sets_to_harvest.append((spec, 'new'))

        skip_count = sum(1 for _, action in sets_to_harvest if action == 'skip_ok')
        retry_count = sum(1 for _, action in sets_to_harvest if action == 'retry_error')
        new_count = sum(1 for _, action in sets_to_harvest if action == 'new')

        logger.info(f"  Skip: {skip_count} | Retry: {retry_count} | New: {new_count}")

        portal_ok = 0
        portal_err = 0
        portal_skip = 0
        portal_records = 0

        for set_idx, (spec, action) in enumerate(sets_to_harvest, 1):
            # SKIP: already OK in P2
            if action == 'skip_ok':
                # Also check if file exists (double protection)
                fname = f"{slugify(name)}__{slugify(spec.split(':')[-1] if ':' in spec else spec, max_len=30)}.json"
                fpath = OUTPUT_DIR / fname
                if args.resume and fpath.exists() and fpath.stat().st_size > 100:
                    portal_skip += 1
                    total_sets_skip += 1
                    continue
                # If we got here but P2 says OK, still skip
                portal_skip += 1
                total_sets_skip += 1
                continue

            # If file already exists (resume), check it
            fname = f"{slugify(name)}__{slugify(spec.split(':')[-1] if ':' in spec else spec, max_len=30)}.json"
            fpath = OUTPUT_DIR / fname
            if args.resume and fpath.exists() and fpath.stat().st_size > 100:
                logger.info(f"    [{set_idx}/{len(sets_to_harvest)}] SKIP {spec} (já existe)")
                portal_skip += 1
                total_sets_skip += 1
                # Count records from existing file
                try:
                    with open(fpath) as f:
                        d = json.load(f)
                        recs = len(d) if isinstance(d, list) else 1
                        portal_records += recs
                        total_records += recs
                except:
                    pass
                continue

            if args.dry_run:
                logger.info(f"    [{set_idx}/{len(sets_to_harvest)}] DRY RUN: {spec} ({action})")
                continue

            logger.info(f"    [{set_idx}/{len(sets_to_harvest)}] {spec} ({action})")

            records, error = harvest_one_set(
                url, spec, from_date, until_date,
                timeout=args.timeout, delay=args.delay,
            )

            if records:
                # Save
                with open(fpath, 'w') as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)

                portal_ok += 1
                total_sets_ok += 1
                portal_records += len(records)
                total_records += len(records)
                logger.info(f"      ✅ {len(records):,} registros → {fpath.name}")
                all_results.append({
                    'oai_url': url, 'repository_name': name,
                    'set_spec': spec, 'status': 'ok',
                    'record_count': len(records), 'output_file': str(fpath),
                })
            else:
                portal_err += 1
                total_sets_err += 1
                err_short = error[:80] if error else 'unknown'
                logger.info(f"      ❌ {err_short}")
                all_results.append({
                    'oai_url': url, 'repository_name': name,
                    'set_spec': spec, 'status': 'error',
                    'record_count': 0, 'error': error[:300] if error else '',
                })

            time.sleep(args.delay)

        logger.info(f"  Portal {name[:40]}: {portal_ok} ok, {portal_err} err, {portal_skip} skip, {portal_records:,} records")

        # Save progress
        completed_urls.add(url)
        progress = {
            'timestamp': datetime.now().isoformat(),
            'completed_urls': list(completed_urls),
            'total_sets_ok': total_sets_ok,
            'total_sets_err': total_sets_err,
            'total_sets_skip': total_sets_skip,
            'total_records': total_records,
        }
        with open(progress_file, 'w') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    # ── Final report ──────────────────────────────────────────────────
    result_file = OUTPUT_DIR / f'retry_portals_results_{ts}.json'
    with open(result_file, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    logger.info("\n" + "=" * 50)
    logger.info("RESULTADO FINAL — Retry Portais (por set)")
    logger.info("=" * 50)
    logger.info(f"  Portais processados: {len(completed_urls)}")
    logger.info(f"  Sets OK: {total_sets_ok}")
    logger.info(f"  Sets erro: {total_sets_err}")
    logger.info(f"  Sets skip (já OK): {total_sets_skip}")
    logger.info(f"  📊 Registros novos: {total_records:,}")
    logger.info(f"  Resultados: {result_file}")


if __name__ == '__main__':
    main()