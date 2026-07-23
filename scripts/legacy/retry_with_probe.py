#!/usr/bin/env python3
"""
retry_with_probe.py — Etapa 2: probe + retry inteligente

Estratégia:
1. Probe rápido (15s) com verb=Identify nas 63 ReadTimeout + 8 Other URLs
2. Classificar: ALIVE, SLOW, DEAD
3. Probe HTTP 102 URLs (34) — servidor aceitou conexão, provavelmente vivo
4. Retry com timeout 600s nas ALIVE + HTTP 102
5. Skip DEAD, marcar SLOW para tentativa futura

Também aplica SSL bypass (monkey-patch em requests.Session.request).
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
from urllib.parse import urlparse

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
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def load_error_urls():
    """Load error URLs from P1 results, excluding SSL (already handled) and DNS."""
    # Find latest P1 results
    files = sorted(glob.glob('data/raw/harvest_results_*.json'))
    if not files:
        logger.error("No harvest_results files found")
        return [], []
    
    with open(files[-1]) as f:
        p1 = json.load(f)
    
    timeout_urls = []  # ReadTimeout
    other_urls = []    # Other/unclassified
    http102_urls = []  # HTTP 102 Processing
    
    for r in p1:
        if r.get('record_count', 0) > 0:
            continue
        
        err = r.get('error', '') or ''
        url = r.get('oai_url', '')
        
        # Skip SSL (already handled)
        if 'SSLError' in err or 'certificate' in err:
            continue
        # Skip DNS/ConnectionError (likely dead)
        if 'Connection' in err and 'Max retries' in err:
            continue
        
        entry = {
            'url': url,
            'name': r.get('repository_name', ''),
            'n_journals': r.get('n_journals', 1),
            'is_portal': r.get('is_portal', False),
            'original_error': err[:200],
        }
        
        if '102' in err:
            http102_urls.append(entry)
        elif 'timed out' in err:
            timeout_urls.append(entry)
        elif 'XML' in err or 'parse' in err.lower():
            # XML/Parse — server responded, include in probe
            timeout_urls.append(entry)
        else:
            other_urls.append(entry)
    
    return timeout_urls + other_urls, http102_urls


def probe_url(url, timeout=15):
    """Quick probe with verb=Identify to check if server is alive."""
    try:
        r = requests.get(url, params={'verb': 'Identify'}, timeout=timeout, verify=False)
        if r.status_code == 200 and '<OAI-PMH' in r.text:
            return 'alive', r.status_code, r.text[:500]
        elif r.status_code == 200:
            return 'alive_partial', r.status_code, r.text[:200]
        elif r.status_code in (503, 429):
            return 'rate_limited', r.status_code, ''
        elif r.status_code in (500, 502, 503, 504):
            return 'server_error', r.status_code, ''
        else:
            return 'http_error', r.status_code, ''
    except requests.exceptions.SSLError:
        return 'ssl_error', 0, ''
    except requests.exceptions.Timeout:
        return 'slow', 0, ''
    except requests.exceptions.ConnectionError:
        return 'dead', 0, ''
    except Exception as e:
        return 'error', 0, str(e)[:100]


def harvest_url(url, timeout=600, set_spec=None):
    """Harvest a single URL using ojs-scrape with extended timeout."""
    try:
        with OAIPMHClient(url, timeout=timeout, delay=1.0) as client:
            if set_spec:
                articles = list(client.list_records(
                    metadata_prefix="oai_dc",
                    from_date="2000-01-01",
                    until_date=f"{datetime.now().year}-12-31",
                    set_spec=set_spec
                ))
            else:
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
    parser = argparse.ArgumentParser(description='Etapa 2: probe + retry inteligente')
    parser.add_argument('--timeout-harvest', type=int, default=600, help='Timeout para harvest em segundos')
    parser.add_argument('--timeout-probe', type=int, default=15, help='Timeout para probe em segundos')
    parser.add_argument('--skip-probe', action='store_true', help='Pular probe e ir direto para harvest')
    parser.add_argument('--only-probe', action='store_true', help='Fazer apenas o probe, sem harvest')
    parser.add_argument('--resume', action='store_true', help='Retomar de progresso anterior')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # ─── Load URLs ────────────────────────────────────────────────────
    timeout_and_other_urls, http102_urls = load_error_urls()
    logger.info(f"URLs para probe: {len(timeout_and_other_urls)} (timeout/other)")
    logger.info(f"URLs HTTP 102 (retry direto): {len(http102_urls)}")
    
    # ─── Phase 1: Probe ──────────────────────────────────────────────
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    probe_file = f'data/raw/probe_results_{ts}.json'
    progress_file = 'data/raw/retry_probe_progress.json'
    
    # Load previous progress if resuming
    probe_results = {}
    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            progress = json.load(f)
        probe_results = progress.get('probe_results', {})
        logger.info(f"Retomando com {len(probe_results)} resultados de probe anteriores")
    
    if not args.skip_probe:
        logger.info("=" * 50)
        logger.info("FASE 1: PROBE — verb=Identify (15s timeout)")
        logger.info("=" * 50)
        
        probed = 0
        for i, entry in enumerate(timeout_and_other_urls, 1):
            url = entry['url']
            if url in probe_results:
                logger.info(f"[{i}/{len(timeout_and_other_urls)}] ⏭ Já probed: {url}")
                continue
            
            logger.info(f"\n[{i}/{len(timeout_and_other_urls)}] {entry.get('name', '')[:50]}")
            logger.info(f"  {url}")
            status, code, detail = probe_url(url, timeout=args.timeout_probe)
            
            probe_results[url] = {
                'name': entry.get('name', ''),
                'n_journals': entry.get('n_journals', 1),
                'is_portal': entry.get('is_portal', False),
                'original_error': entry.get('original_error', ''),
                'probe_status': status,
                'probe_code': code,
                'probe_detail': detail[:200] if detail else '',
            }
            
            emoji = {'alive': '✅', 'alive_partial': '✅', 'rate_limited': '🚫', 
                      'server_error': '❌', 'http_error': '❌', 'slow': '⏳', 
                      'dead': '💀', 'ssl_error': '🔒', 'error': '❓'}.get(status, '❓')
            logger.info(f"  {emoji} {status} (HTTP {code})")
            
            probed += 1
            
            # Save progress every 10 probes
            if probed % 10 == 0:
                with open(progress_file, 'w') as f:
                    json.dump({'probe_results': probe_results, 'phase': 'probe'}, f, indent=2)
            
            time.sleep(0.5)  # Be polite between probes
        
        # Save final probe results
        with open(probe_file, 'w') as f:
            json.dump(probe_results, f, indent=2, ensure_ascii=False)
        logger.info(f"\nProbing concluído. Resultados em {probe_file}")
    
    # ─── Classify probe results ──────────────────────────────────────
    probe_stats = Counter(v['probe_status'] for v in probe_results.values())
    logger.info("\n" + "=" * 50)
    logger.info("CLASSIFICAÇÃO DO PROBE")
    logger.info("=" * 50)
    for status, count in probe_stats.most_common():
        logger.info(f"  {status}: {count}")
    
    alive_urls = [url for url, v in probe_results.items() if v['probe_status'] in ('alive', 'alive_partial')]
    slow_urls = [url for url, v in probe_results.items() if v['probe_status'] == 'slow']
    dead_urls = [url for url, v in probe_results.items() if v['probe_status'] in ('dead', 'server_error', 'http_error', 'rate_limited')]
    
    logger.info(f"\nALIVE (retry com timeout 600s): {len(alive_urls)}")
    logger.info(f"SLOW (retry em outro horário): {len(slow_urls)}")
    logger.info(f"DEAD (skip): {len(dead_urls)}")
    
    if args.only_probe:
        logger.info("\n--only-probe: parando após probe.")
        return
    
    # ─── Phase 2: Harvest ALIVE + HTTP 102 URLs ──────────────────────
    harvest_targets = []
    
    # Add ALIVE URLs from probe
    for url in alive_urls:
        v = probe_results[url]
        harvest_targets.append({
            'url': url,
            'name': v['name'],
            'n_journals': v.get('n_journals', 1),
            'is_portal': v.get('is_portal', False),
            'source': 'probe_alive',
        })
    
    # Add HTTP 102 URLs (skip probe — server accepted connection)
    for entry in http102_urls:
        if entry['url'] not in probe_results:  # Don't double if already probed
            harvest_targets.append({
                'url': entry['url'],
                'name': entry['name'],
                'n_journals': entry.get('n_journals', 1),
                'is_portal': entry.get('is_portal', False),
                'source': 'http102',
            })
    
    # Also try SLOW URLs — they might work with longer timeout
    for url in slow_urls:
        v = probe_results[url]
        harvest_targets.append({
            'url': url,
            'name': v['name'],
            'n_journals': v.get('n_journals', 1),
            'is_portal': v.get('is_portal', False),
            'source': 'probe_slow',
        })
    
    logger.info(f"\nTotal URLs para harvest: {len(harvest_targets)}")
    logger.info(f"  ALIVE: {len(alive_urls)}")
    logger.info(f"  HTTP 102: {len(http102_urls)}")
    logger.info(f"  SLOW (tentativa): {len(slow_urls)}")
    
    # Load previous harvest results if resuming
    harvest_results = {}
    if args.resume and os.path.exists(progress_file):
        with open(progress_file) as f:
            progress = json.load(f)
        harvest_results = progress.get('harvest_results', {})
    
    # ─── Harvest ──────────────────────────────────────────────────────
    logger.info("\n" + "=" * 50)
    logger.info("FASE 2: HARVEST — timeout 600s")
    logger.info("=" * 50)
    
    total_records = 0
    ok_count = 0
    err_count = 0
    
    for i, target in enumerate(harvest_targets, 1):
        url = target['url']
        
        if url in harvest_results:
            logger.info(f"\n[{i}/{len(harvest_targets)}] ⏭ Já coletado: {target.get('name', '')[:50]}")
            continue
        
        logger.info(f"\n[{i}/{len(harvest_targets)}] {target.get('name', '')[:50]} — source: {target['source']}")
        logger.info(f"  {url}")
        
        start = time.monotonic()
        try:
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
                    'status': 'ok',
                    'record_count': len(records),
                    'elapsed': round(elapsed, 1),
                    'output_file': outfile,
                    'source': target['source'],
                }
            else:
                err_count += 1
                logger.info(f"  ❌ {error[:120]} ({elapsed:.1f}s)")
                harvest_results[url] = {
                    'status': 'error',
                    'error': error[:300],
                    'elapsed': round(elapsed, 1),
                    'source': target['source'],
                }
        except Exception as e:
            err_count += 1
            logger.info(f"  ❌ Exception: {str(e)[:120]}")
            harvest_results[url] = {
                'status': 'error',
                'error': str(e)[:300],
                'source': target['source'],
            }
        
        # Save progress after each URL
        with open(progress_file, 'w') as f:
            json.dump({
                'probe_results': probe_results,
                'harvest_results': harvest_results,
                'phase': 'harvest',
            }, f, indent=2)
        
        time.sleep(1.0)
    
    # ─── Final report ─────────────────────────────────────────────────
    ts2 = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = f'data/raw/retry_probe_results_{ts2}.json'
    
    final = {
        'timestamp': ts2,
        'probe_stats': dict(probe_stats),
        'alive_urls': len(alive_urls),
        'slow_urls': len(slow_urls),
        'dead_urls': len(dead_urls),
        'http102_urls': len(http102_urls),
        'harvest_targets': len(harvest_targets),
        'harvest_ok': ok_count,
        'harvest_error': err_count,
        'total_records': total_records,
        'results': harvest_results,
    }
    with open(result_file, 'w') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    
    logger.info("\n" + "=" * 50)
    logger.info("RESULTADO FINAL — Probe + Retry")
    logger.info("=" * 50)
    logger.info(f"  Probe: {len(probe_results)} URLs testadas")
    logger.info(f"    ALIVE: {len(alive_urls)}")
    logger.info(f"    SLOW: {len(slow_urls)}")
    logger.info(f"    DEAD: {len(dead_urls)}")
    logger.info(f"  HTTP 102 (direto para harvest): {len(http102_urls)}")
    logger.info(f"  Harvest: {len(harvest_targets)} URLs tentadas")
    logger.info(f"    ✅ Sucesso: {ok_count}")
    logger.info(f"    ❌ Erro: {err_count}")
    logger.info(f"    📊 Registros: {total_records:,}")
    logger.info(f"  Resultados: {result_file}")


if __name__ == '__main__':
    main()