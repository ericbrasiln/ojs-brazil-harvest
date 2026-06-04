#!/usr/bin/env python3
"""
retry_ssl.py — Retry de URLs com erro SSL, usando monkey-patch no requests

O ojs-scrape não suporta --no-verify-ssl, então este script:
1. Importa ojs_scrape e monkey-patchea requests.Session.send para verify=False
2. Extrai URLs com erro SSL dos resultados de harvest
3. Roda a coleta para cada URL
4. Salva resultados

Uso:
    python3 scripts/retry_ssl.py [--timeout 300] [--verbose]
"""
import json
import sys
import time
import os
import glob
import re
import logging
import warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from unittest.mock import patch

# Monkey-patch requests to disable SSL verification
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

import requests
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request

from ojs_scrape.oaipmh import OAIPMHClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_LOGS = PROJECT_ROOT / "data" / "logs"


def setup_logging(verbose: bool = False):
    DATA_LOGS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = DATA_LOGS / f"retry_ssl_{ts}.log"
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt,
                        handlers=[logging.FileHandler(log_file), logging.StreamHandler()])
    return logging.getLogger("retry_ssl")


def extract_ssl_urls() -> list[dict]:
    """Extrai URLs com erro SSL de todos os harvest_results."""
    ssl_urls = []
    seen = set()

    # Passada 1 results
    for f in sorted(DATA_RAW.glob("harvest_results_*.json")):
        with open(f) as fh:
            data = json.load(fh)
        for r in data:
            if r['status'] == 'error' and 'SSL' in (r.get('error', '') or ''):
                key = r['oai_url']
                if key not in seen:
                    seen.add(key)
                    ssl_urls.append({
                        'oai_url': r['oai_url'],
                        'repository_name': r.get('repository_name', ''),
                        'is_portal': r.get('is_portal', False),
                        'n_journals': r.get('n_journals', 1),
                        'set_spec': None,
                        'source': 'P1',
                    })

    # Passada 2 results — only top-level portal URLs (not individual sets)
    for f in sorted(DATA_RAW.glob("harvest_by_set_results_*.json")):
        with open(f) as fh:
            data = json.load(fh)
        for r in data:
            if r['status'] == 'error' and 'SSL' in (r.get('error', '') or ''):
                key = r['oai_url']
                if key not in seen:
                    seen.add(key)
                    ssl_urls.append({
                        'oai_url': r['oai_url'],
                        'repository_name': r.get('repository_name', ''),
                        'is_portal': True,
                        'n_journals': r.get('n_journals', 1),
                        'set_spec': None,
                        'source': 'P2',
                    })

    return ssl_urls


def make_output_path(repo_name: str, set_spec: str | None = None) -> Path:
    slug = re.sub(r'[^a-z0-9]+', '_', repo_name.lower()).strip('_')[:60] or "unknown"
    if set_spec:
        set_slug = re.sub(r'[^a-z0-9]+', '_', set_spec.lower()).strip('_')[:30]
        return DATA_RAW / f"{slug}__{set_slug}.json"
    return DATA_RAW / f"{slug}.json"


def harvest_isolated(oai_url: str, output_path: Path, timeout: int,
                     logger: logging.Logger) -> dict:
    """Coleta periódico isolado via ojs-scrape API."""
    start = time.monotonic()
    try:
        with OAIPMHClient(oai_url, timeout=timeout, delay=1.0) as client:
            articles = list(client.list_records(
                metadata_prefix="oai_dc",
                from_date="2000-01-01",
                until_date=f"{datetime.now().year}-12-31",
            ))

        records = [a.to_dict() for a in articles]
        elapsed = time.monotonic() - start

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ {output_path.name} — {len(records)} registros ({elapsed:.1f}s)")
        return {'status': 'ok', 'record_count': len(records), 'elapsed': elapsed}

    except Exception as e:
        elapsed = time.monotonic() - start
        err_type = type(e).__name__
        err_msg = str(e)[:2000]
        logger.warning(f"❌ {oai_url} — {err_type}: {err_msg[:150]}")
        return {'status': 'error', 'error': f"{err_type}: {err_msg}", 'elapsed': elapsed}


def harvest_portal_by_sets(oai_url: str, repo_name: str, timeout: int,
                           delay: float, logger: logging.Logger) -> list[dict]:
    """Coleta portal por set (descobre sets e coleta cada um)."""
    results = []
    start_total = time.monotonic()

    try:
        with OAIPMHClient(oai_url, timeout=30, delay=delay) as client:
            sets = client.list_sets()
    except Exception as e:
        elapsed = time.monotonic() - start_total
        logger.warning(f"❌ ListSets falhou para {oai_url} — {e}")
        return [{'status': 'error', 'error': f"ListSets: {e}", 'elapsed': elapsed}]

    # Filter top-level sets (no colon = journal, not section)
    top_sets = [s for s in sets if ':' not in s.spec]
    logger.info(f"  {len(sets)} sets total, {len(top_sets)} top-level (journals)")

    for i, oai_set in enumerate(top_sets):
        output_path = make_output_path(repo_name, oai_set.spec)

        if output_path.exists():
            try:
                with open(output_path) as f:
                    existing = json.load(f)
                if isinstance(existing, list) and len(existing) > 0:
                    logger.debug(f"  ⏭ {oai_set.spec} já existe ({len(existing)} rec), pulando")
                    results.append({'status': 'ok', 'record_count': len(existing),
                                    'set_spec': oai_set.spec, 'elapsed': 0, 'skipped': True})
                    continue
            except:
                pass

        logger.info(f"  [{i+1}/{len(top_sets)}] Set: {oai_set.spec} — {oai_set.name}")
        set_start = time.monotonic()
        try:
            with OAIPMHClient(oai_url, timeout=timeout, delay=delay) as client:
                articles = list(client.list_records(
                    metadata_prefix="oai_dc",
                    from_date="2000-01-01",
                    until_date=f"{datetime.now().year}-12-31",
                    set_spec=oai_set.spec,
                ))

            records = [a.to_dict() for a in articles]
            elapsed = time.monotonic() - set_start

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

            logger.info(f"    ✅ {len(records)} registros ({elapsed:.1f}s)")
            results.append({'status': 'ok', 'record_count': len(records),
                            'set_spec': oai_set.spec, 'elapsed': elapsed})

        except Exception as e:
            elapsed = time.monotonic() - set_start
            err_type = type(e).__name__
            logger.warning(f"    ❌ {err_type}: {str(e)[:100]}")
            results.append({'status': 'error', 'error': f"{err_type}: {str(e)[:2000]}",
                            'set_spec': oai_set.spec, 'elapsed': elapsed})

        time.sleep(delay)

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Retry URLs com erro SSL (bypass via monkey-patch)")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout em segundos")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay entre requisições (s)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("SSL bypass ativado (requests.Session.send monkey-patch)")

    ssl_urls = extract_ssl_urls()
    logger.info(f"URLs com erro SSL encontradas: {len(ssl_urls)}")

    all_results = []
    total_ok = 0
    total_records = 0

    for i, target in enumerate(ssl_urls):
        logger.info(f"\n[{i+1}/{len(ssl_urls)}] {target['repository_name'][:50]} — {target['oai_url']}")

        if target['is_portal'] and target['n_journals'] > 1:
            # Portal: collect by set
            logger.info(f"  Portal com {target['n_journals']} journals — coletando por set")
            set_results = harvest_portal_by_sets(
                target['oai_url'], target['repository_name'], args.timeout, args.delay, logger)
            ok_sets = sum(1 for r in set_results if r['status'] == 'ok')
            rec_sets = sum(r.get('record_count', 0) for r in set_results if r['status'] == 'ok')
            logger.info(f"  Portal: {ok_sets}/{len(set_results)} sets OK, {rec_sets:,} registros")
            total_ok += ok_sets
            total_records += rec_sets
            all_results.append({**target, 'phase': 'portal_by_set', 'sets': set_results,
                                'ok_sets': ok_sets, 'total_sets': len(set_results),
                                'record_count': rec_sets})
        else:
            # Isolado: direct collection
            output_path = make_output_path(target['repository_name'])
            if output_path.exists():
                try:
                    with open(output_path) as f:
                        existing = json.load(f)
                    if isinstance(existing, list) and len(existing) > 0:
                        logger.info(f"  ⏭ Já existe com {len(existing)} registros, pulando")
                        all_results.append({**target, 'status': 'ok',
                                            'record_count': len(existing), 'skipped': True})
                        total_ok += 1
                        total_records += len(existing)
                        continue
                except:
                    pass

            res = harvest_isolated(target['oai_url'], output_path, args.timeout, logger)
            all_results.append({**target, **res})
            if res['status'] == 'ok':
                total_ok += 1
                total_records += res.get('record_count', 0)
            time.sleep(args.delay)

    # Save results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = DATA_RAW / f"retry_ssl_results_{ts}.json"
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # Summary
    n_isolados = sum(1 for r in ssl_urls if not r['is_portal'] or r['n_journals'] <= 1)
    n_portais = sum(1 for r in ssl_urls if r['is_portal'] and r['n_journals'] > 1)

    logger.info("=" * 50)
    logger.info("RESULTADO FINAL — SSL Bypass Retry")
    logger.info(f"  URLs SSL: {len(ssl_urls)} ({n_isolados} isolados, {n_portais} portais)")
    logger.info(f"  ✅ Sucesso: {total_ok}")
    logger.info(f"  📊 Registros: {total_records:,}")
    logger.info(f"  Resultados: {results_file}")


if __name__ == "__main__":
    main()