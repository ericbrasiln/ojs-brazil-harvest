#!/usr/bin/env python3
"""Baixa e prepara o recorte brasileiro do PKP Beacon v6.

O arquivo bruto contém o universo global do Beacon e campos de contato que não
são necessários à coleta. Este script gera apenas os campos metodologicamente
necessários para periódicos OJS classificados como brasileiros.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


BEACON_V6_FILE_ID = 13173372
BEACON_V6_TABULAR_URL = (
    f"https://dataverse.harvard.edu/api/access/datafile/{BEACON_V6_FILE_ID}"
)
BEACON_DOWNLOAD_USER_AGENT = "Mozilla/5.0"
BEACON_V6_TABULAR_SHA256 = (
    "3f594d706d8832de6d696be74b9d30085833d6404ec3227e29871985fd4be3b0"
)

STRING_FIELDS = (
    "repository_name",
    "context_name",
    "version",
    "issn",
    "earliest_datestamp",
    "last_oai_response",
    "country_consolidated",
    "region",
    "set_spec",
)
INTEGER_FIELDS = (
    "total_record_count",
    "record_count_2020",
    "record_count_2021",
    "record_count_2022",
    "record_count_2023",
    "record_count_2024",
    "record_count_2025",
)
BOOLEAN_FIELDS = ("unresponsive_endpoint", "unresponsive_context")


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_with_urllib(output: Path) -> None:
    request = urllib.request.Request(
        BEACON_V6_TABULAR_URL,
        headers={"User-Agent": BEACON_DOWNLOAD_USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        output.write_bytes(response.read())


def _download_with_curl(output: Path) -> None:
    subprocess.run(
        [
            "curl",
            "-fsSL",
            "-A",
            BEACON_DOWNLOAD_USER_AGENT,
            BEACON_V6_TABULAR_URL,
            "-o",
            str(output),
        ],
        check=True,
        timeout=180,
    )


def download_source(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        _download_with_urllib(output)
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        _download_with_curl(output)
    actual = sha256sum(output)
    if actual != BEACON_V6_TABULAR_SHA256:
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum inesperado para PKP Beacon v6: {actual}; "
            f"esperado {BEACON_V6_TABULAR_SHA256}"
        )


def _integer(value: str | None) -> int:
    return int((value or "").strip() or 0)


def build_brazil_dataset(source: Path) -> list[dict]:
    records: list[dict] = []
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            if (row.get("application") or "").strip() != "ojs":
                continue
            if (row.get("country_consolidated") or "").strip() != "BR":
                continue

            oai_url = (row.get("oai_url") or "").strip()
            record: dict = {
                "oai_url": oai_url,
                "base_url": oai_url.removesuffix("/oai"),
            }
            for field in STRING_FIELDS:
                value = (row.get(field) or "").strip()
                record[field] = value.replace("\\n", "; ") if field == "issn" else value
            for field in INTEGER_FIELDS:
                record[field] = _integer(row.get(field))
            for field in BOOLEAN_FIELDS:
                record[field] = (row.get(field) or "").strip() == "1"

            ordered = {
                "oai_url": record["oai_url"],
                "base_url": record["base_url"],
                "repository_name": record["repository_name"],
                "context_name": record["context_name"],
                "version": record["version"],
                "issn": record["issn"],
                "total_record_count": record["total_record_count"],
                "unresponsive_endpoint": record["unresponsive_endpoint"],
                "unresponsive_context": record["unresponsive_context"],
                "earliest_datestamp": record["earliest_datestamp"],
                "last_oai_response": record["last_oai_response"],
                "record_count_2020": record["record_count_2020"],
                "record_count_2021": record["record_count_2021"],
                "record_count_2022": record["record_count_2022"],
                "record_count_2023": record["record_count_2023"],
                "record_count_2024": record["record_count_2024"],
                "record_count_2025": record["record_count_2025"],
                "country_consolidated": record["country_consolidated"],
                "region": record["region"],
                "set_spec": record["set_spec"],
            }
            records.append(ordered)
    return records


def write_dataset(output: Path, records: list[dict]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/raw/beacon.tab"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/ojs_brazil_pkp_beacon.json"),
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Baixar a exportação tabular oficial do PKP Beacon v6 antes de processar",
    )
    args = parser.parse_args()

    if args.download:
        download_source(args.source)
    elif not args.source.exists():
        parser.error("arquivo fonte ausente; use --download ou informe --source")

    records = build_brazil_dataset(args.source)
    write_dataset(args.output, records)
    print(f"Registros OJS Brasil: {len(records)}")
    print(f"Saída: {args.output}")


if __name__ == "__main__":
    main()
