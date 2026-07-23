#!/usr/bin/env python3
"""
retry_isolated.py — Etapa 2a: Retry de periódicos ISOLADOS (não-portais)

Estratégia:
1. Carrega URLs com erro da P1 (exceto SSL, já tratado)
2. Filtra: apenas periódicos ISOLADOS (não-portais, não estão na P2)
3. Probe rápido (15s) com verb=Identify para classificar alive/slow/dead
4. Retry com timeout 600s apenas nos ALIVE + HTTP 102
5. Aplica SSL bypass (monkey-patch)

NÃO coleta portais integralmente — isso duplica dados da P2.
Portais devem ser retried por set (harvest_by_set.py com --resume).
"""

import json
import glob
import time
import os
import sys
import logging
import warnings
from datetime import datetime
from collections import Counter

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


def load_isolated_error_urls():
    """Load error URLs from P1 that are NOT in P2 (isolated journals only)."""
    # P1 results
    files = sorted(glob.glob('data/raw/harvest_results_*.json'))
    with open(files[-1]) as f:
        p1 = json.load(f)

    # P2 results — get portal URLs to exclude
    p2_files = sorted(glob.glob('data/raw/harvest_by_set_results_*.json'))
    p2_portal_urls = set()
    if p2_files:
        with open(p2_files[-1]) as f:
            p2 = json.load(f)
        p2_portal_urls = set(e.get('oai_url', '') for e in p2)

    # P2 progress — also check for portal URLs
    prog_file = 'data/raw/harvest_by_set_progress.json'
    if os.path.exists(prog_file):
        with open(prog_file) as f:
            prog = json.load(f)
        # Progress has portal URLs in different format
        for portal in prog.get('portals', []):
            p2_portal_urls.add(portal.get('oai_url', ''))

    isolated = []
    for r in p1:
        if r.get('record_count', 0) > 0:
            continue  # Already successful

        url = r.get('oai_url', '')
        err = str(r.get('error', '') or '')

        # Skip SSL (already handled)
        if 'SSLError' in err or 'certificate' in err:
            continue
        # Skip DNS/ConnectionError (likely dead)
        if 'Connection' in err and 'Max retries' in err:
            continue
        # Skip portals — they should be retried by set, not integral
        if url in p2_portal_urls:
            continue
        # Skip if is_portal=True
        if r.get('is_portal', False):
            continue

        isolated.append({
            'url': url,
            'name': r.get('repository_name', ''),
            'n_journals': r.get('n_journals', 1),
            'original_error': err[:200],
            'category': _categorize_error(err),
        })

    return isolated


def _categorize_error(err):
    if '102' in err or 'Processing' in err:
        return 'http102'
    elif 'timed out' in err or 'ReadTimeout' in err:
        return 'timeout'
    elif 'ConnectTimeout' in err:
        return 'connect_timeout'
    elif 'XML' in err or 'parse' in err.lower():
        return 'xml_parse'
    else:
        return 'other'


def probe_url(url, timeout=15):
    """Quick probe with verb=Identify."""
    try:
        r = requests.get(url, params={'verb': 'Identify'}, timeout=timeout, verify=False)
        if r.status_code == 200 and '<OAI-PMH' in r.text:
            return 'alive', r.status_code
        elif r.status_code == 200:
            return 'alive_partial', r.status_code
        elif r.status_code in (429, 503):
            return 'rate_limited', r.status_code
        elif r.status_code >= 500:
            return 'server_error', r.status_code
        else:
            return 'http_error', r.status_code
    except requests.exceptions.Timeout:
        return 'slow', 0
    except requests.exceptions.ConnectionError:
        return 'dead', 0
    except Exception as e:
        return 'error', 0


def harvest_url(url, timeout=600):
    """Harvest a single isolated URL with extended timeout."""
    try:
        with OAIPMHClient(url, timeout=timeout, delay=1.0) as client:
            articles = list(client.list_records(
                metadata_prefix="oai_dc",
                from_date="2000-01-01",
                until_date=f"{datetime.now().year}-12-31",
            ))
            return [a.to_dict() for a in articles], None
    except Exception as e:
        return [], str(e)[:300]


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Etapa 2a: Retry de periódicos ISOLADOS')
    parser.add_argument('--timeout-harvest', type=int, default=600)
    parser.add_argument('--timeout-probe', type=int, default=15)
    parser.add_argument('--skip-probe', action='store_true')
    parser.add_argument('--only-probe', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ─── Load isolated error URLs ────────────────────────────────────
    isolated = load_isolated_error_urls()
    logger.info(f"URLs isoladas com erro (não-portais): {len(isolated)}")

    cats = Counter(e['category'] for e in isolated)
    for cat, n in cats.most_common():
        logger.info(f"  {n}x {cat}")

    # ─── Phase 1: Probe ──────────────────────────────────────────────
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    progress_file = 'data/raw/retry_isolated_progress.json'
    probe_results = {}

    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            progress = json.load(f)
        probe_results = progress.get('probe_results', {})
        logger.info(f"Retomando com {len(probe_results)} resultados de probe")

    if not args.skip_probe:
        logger.info("=" * 50)
        logger.info("FASE 1: PROBE — verb=Identify")
        logger.info("=" * 50)

        probed = 0
        for i, entry in enumerate(isolated, 1):
            url = entry['url']
            if url in probe_results:
                continue

            logger.info(f"\n[{i}/{len(isolated)}] {entry.get('name', '')[:50]} ({entry['category']})")
            logger.info(f"  {url}")

            status, code = probe_url(url, timeout=args.timeout_probe)
            probe_results[url] = {
                'name': entry.get('name', ''),
                'category': entry['category'],
                'n_journals': entry.get('n_journals', 1),
                'probe_status': status,
                'probe_code': code,
            }

            emoji = {'alive': '✅', 'alive_partial': '✅', 'slow': '⏳',
                      'dead': '💀', 'server_error': '❌', 'http_error': '❌',
                      'rate_limited': '🚫', 'error': '❓'}.get(status, '❓')
            logger.info(f"  {emoji} {status} (HTTP {code})")

            probed += 1
            if probed % 10 == 0:
                with open(progress_file, 'w') as f:
                    json.dump({'probe_results': probe_results, 'phase': 'probe'}, f, indent=2)

            time.sleep(0.5)

        probe_stats = Counter(v['probe_status'] for v in probe_results.values())
        logger.info("\n" + "=" * 50)
        logger.info("CLASSIFICAÇÃO DO PROBE")
        logger.info("=" * 50)
        for s, c in probe_stats.most_common():
            logger.info(f"  {s}: {c}")

    if args.only_probe:
        logger.info("\n--only-probe: parando após probe.")
        with open(progress_file, 'w') as f:
            json.dump({'probe_results': probe_results, 'phase': 'probe_done'}, f, indent=2)
        return

    # ─── Phase 2: Harvest ALIVE + HTTP 102 ───────────────────────────
    alive_urls = [url for url, v in probe_results.items()
                  if v['probe_status'] in ('alive', 'alive_partial')]
    http102_urls = [e['url'] for e in isolated if e['category'] == 'http102'
                   and e['url'] not in probe_results]

    # Also try SLOW with longer probe first
    slow_urls = [url for url, v in probe_results.items()
                 if v['probe_status'] == 'slow']

    harvest_targets = []
    for url in alive_urls:
        v = probe_results[url]
        harvest_targets.append({'url': url, 'name': v.get('name', ''), 'source': 'probe_alive'})
    for url in http102_urls:
        harvest_targets.append({'url': url, 'name': '', 'source': 'http102'})
    # Try slow URLs too — they might work with longer timeout
    for url in slow_urls:
        v = probe_results[url]
        harvest_targets.append({'url': url, 'name': v.get('name', ''), 'source': 'probe_slow'})

    logger.info(f"\nTargets para harvest: {len(harvest_targets)}")
    logger.info(f"  ALIVE: {len(alive_urls)}")
    logger.info(f"  HTTP 102: {len(http102_urls)}")
    logger.info(f"  SLOW: {len(slow_urls)}")

    # Load previous results if resuming
    harvest_results = {}
    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            progress = json.load(f)
        harvest_results = progress.get('harvest_results', {})

    logger.info("\n" + "=" * 50)
    logger.info("FASE 2: HARVEST — timeout 600s (apenas isolados)")
    logger.info("=" * 50)

    total_records = 0
    ok_count = 0
    err_count = 0

    for i, target in enumerate(harvest_targets, 1):
        url = target['url']

        if url in harvest_results:
            logger.info(f"\n[{i}/{len(harvest_targets)}] ⏭ Já processado: {target.get('name', '')[:50]}")
            continue

        logger.info(f"\n[{i}/{len(harvest_targets)}] {target.get('name', '')[:50]} ({target['source']})")
        logger.info(f"  {url}")

        start = time.monotonic()
        records, error = harvest_url(url, timeout=args.timeout_harvest)
        elapsed = time.monotonic() - start

        if records:
            slug = target.get('name', 'unknown').lower().replace(' ', '_')
            slug = ''.join(c for c in slug if c.isalnum() or c == '_')[:60]
            outfile = f"data/raw/{slug}.json"
            with open(outfile, 'w') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

            total_records += len(records)
            ok_count += 1
            logger.info(f"  ✅ {len(records):,} registros ({elapsed:.1f}s) → {outfile}")
            harvest_results[url] = {
                'status': 'ok', 'record_count': len(records),
                'elapsed': round(elapsed, 1), 'output_file': outfile,
                'source': target['source'],
            }
        else:
            err_count += 1
            logger.info(f"  ❌ {error[:120]} ({elapsed:.1f}s)")
            harvest_results[url] = {
                'status': 'error', 'error': error[:300],
                'elapsed': round(elapsed, 1), 'source': target['source'],
            }

        # Save progress
        with open(progress_file, 'w') as f:
            json.dump({
                'probe_results': probe_results,
                'harvest_results': harvest_results,
                'phase': 'harvest',
            }, f, indent=2)

        time.sleep(1.0)

    # ─── Final report ─────────────────────────────────────────────────
    ts2 = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = f'data/raw/retry_isolated_results_{ts2}.json'

    probe_stats = Counter(v['probe_status'] for v in probe_results.values())
    final = {
        'timestamp': ts2,
        'type': 'isolated_only',
        'probe_stats': dict(probe_stats),
        'harvest_ok': ok_count,
        'harvest_error': err_count,
        'total_records': total_records,
        'results': harvest_results,
    }
    with open(result_file, 'w') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    logger.info("\n" + "=" * 50)
    logger.info("RESULTADO FINAL — Retry Isolados")
    logger.info("=" * 50)
    logger.info(f"  Probe: {len(probe_results)} URLs — {dict(probe_stats)}")
    logger.info(f"  Harvest: {ok_count} ok, {err_count} erro")
    logger.info(f"  📊 Registros: {total_records:,}")
    logger.info(f"  Resultados: {result_file}")


if __name__ == '__main__':
    main()