#!/usr/bin/env python3
"""Valida, deduplica e consolida saídas JSON do OJS Brazil Harvest.

A deduplicação automática usa apenas identificadores fortes: DOI normalizado,
identificador OAI e URL canônica. Similaridade de título, primeiro autor e ano
é registrada como candidata para revisão humana, sem fusão automática.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


CONTROL_PREFIXES = (
    "phase",
    "harvest_",
    "retry_",
    "probe_",
)
CSV_FIELDS = (
    "oai_identifier",
    "doi",
    "url",
    "title",
    "subtitle",
    "creators",
    "publication_date",
    "datestamp",
    "languages",
    "subjects",
    "publishers",
    "types",
    "rights",
    "set_spec",
    "issue_number",
    "section",
    "pages",
    "pdf_url",
    "deleted",
    "provenance_count",
)


def normalize_doi(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", normalized)
    normalized = normalized.rstrip(".,; ")
    return normalized if re.fullmatch(r"10\.\d{4,9}/\S+", normalized) else ""


def canonical_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _doi_from_record(record: dict) -> str:
    doi = normalize_doi(record.get("doi"))
    if doi:
        return doi
    for identifier in record.get("identifiers") or []:
        doi = normalize_doi(identifier)
        if doi:
            return doi
    return ""


def strong_aliases(record: dict) -> list[str]:
    aliases: list[str] = []
    doi = _doi_from_record(record)
    if doi:
        aliases.append(f"doi:{doi}")
    oai_identifier = record.get("oai_identifier")
    if isinstance(oai_identifier, str) and oai_identifier.strip():
        aliases.append(f"oai:{oai_identifier.strip()}")
    url = canonical_url(record.get("url"))
    if url:
        aliases.append(f"url:{url}")
    return aliases


def _fold(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\W+", " ", text.lower()).strip()


def _publication_year(record: dict) -> str:
    values = record.get("dates") or []
    if isinstance(values, list):
        for value in values:
            match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|2100)\b", str(value))
            if match:
                return match.group(1)
    return ""


def weak_candidate_key(record: dict) -> str:
    title = _fold(record.get("title"))
    creators = record.get("creators") or []
    first_creator = _fold(creators[0]) if isinstance(creators, list) and creators else ""
    year = _publication_year(record)
    if not title:
        return ""
    return f"{title}|{first_creator}|{year}"


def discover_article_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.glob("*.json")
        if not path.name.startswith(CONTROL_PREFIXES)
    )


def sha256sum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_record(record: object) -> tuple[bool, list[str]]:
    if not isinstance(record, dict):
        return False, ["record_not_object"]
    warnings: list[str] = []
    if not record.get("title"):
        warnings.append("missing_title")
    if not record.get("creators"):
        warnings.append("missing_creators")
    if not record.get("dates"):
        warnings.append("missing_publication_date")
    if not strong_aliases(record) and not record.get("title"):
        return False, ["missing_identity_and_title"]
    return True, warnings


def _init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE records (
            id INTEGER PRIMARY KEY,
            record_json TEXT NOT NULL,
            weak_key TEXT NOT NULL
        );
        CREATE TABLE aliases (
            alias TEXT PRIMARY KEY,
            record_id INTEGER NOT NULL REFERENCES records(id)
        );
        CREATE TABLE provenance (
            record_id INTEGER NOT NULL REFERENCES records(id),
            source_file TEXT NOT NULL,
            source_index INTEGER NOT NULL,
            source_sha256 TEXT NOT NULL
        );
        CREATE TABLE decisions (
            kept_record_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            source_index INTEGER NOT NULL,
            reason TEXT NOT NULL,
            matched_alias TEXT NOT NULL
        );
        """
    )


def _alias_reason(alias: str) -> str:
    if alias.startswith("doi:"):
        return "doi"
    if alias.startswith("oai:"):
        return "oai_identifier"
    return "url"


def _add_record(
    connection: sqlite3.Connection,
    record: dict,
    source_file: str,
    source_index: int,
    source_sha256: str,
) -> int:
    aliases = strong_aliases(record)
    existing: list[tuple[int, str]] = []
    for alias in aliases:
        row = connection.execute(
            "SELECT record_id FROM aliases WHERE alias = ?", (alias,)
        ).fetchone()
        if row:
            existing.append((int(row[0]), alias))

    if existing:
        kept_id = min(record_id for record_id, _alias in existing)
        matched_alias = existing[0][1]
        merged_existing_ids = sorted({record_id for record_id, _alias in existing if record_id != kept_id})
        for duplicate_id in merged_existing_ids:
            bridge_alias = next(alias for record_id, alias in existing if record_id == duplicate_id)
            source_row = connection.execute(
                """
                SELECT source_file, source_index
                FROM provenance
                WHERE record_id = ?
                ORDER BY source_file, source_index
                LIMIT 1
                """,
                (duplicate_id,),
            ).fetchone()
            if source_row:
                connection.execute(
                    "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
                    (
                        kept_id,
                        source_row[0],
                        source_row[1],
                        "alias_bridge",
                        bridge_alias,
                    ),
                )
            connection.execute(
                "UPDATE provenance SET record_id = ? WHERE record_id = ?",
                (kept_id, duplicate_id),
            )
            connection.execute(
                "UPDATE aliases SET record_id = ? WHERE record_id = ?",
                (kept_id, duplicate_id),
            )
            connection.execute(
                "UPDATE decisions SET kept_record_id = ? WHERE kept_record_id = ?",
                (kept_id, duplicate_id),
            )
            connection.execute("DELETE FROM records WHERE id = ?", (duplicate_id,))

        connection.execute(
            "INSERT INTO provenance VALUES (?, ?, ?, ?)",
            (kept_id, source_file, source_index, source_sha256),
        )
        connection.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
            (
                kept_id,
                source_file,
                source_index,
                _alias_reason(matched_alias),
                matched_alias,
            ),
        )
        for alias in aliases:
            connection.execute(
                "INSERT OR IGNORE INTO aliases(alias, record_id) VALUES (?, ?)",
                (alias, kept_id),
            )
        return 1 + len(merged_existing_ids)

    cursor = connection.execute(
        "INSERT INTO records(record_json, weak_key) VALUES (?, ?)",
        (json.dumps(record, ensure_ascii=False), weak_candidate_key(record)),
    )
    assert cursor.lastrowid is not None
    record_id = cursor.lastrowid
    connection.execute(
        "INSERT INTO provenance VALUES (?, ?, ?, ?)",
        (record_id, source_file, source_index, source_sha256),
    )
    for alias in aliases:
        connection.execute(
            "INSERT INTO aliases(alias, record_id) VALUES (?, ?)",
            (alias, record_id),
        )
    return 0


def _provenance(connection: sqlite3.Connection, record_id: int) -> list[dict]:
    rows = connection.execute(
        """
        SELECT source_file, source_index, source_sha256
        FROM provenance WHERE record_id = ?
        ORDER BY source_file, source_index
        """,
        (record_id,),
    )
    return [
        {
            "source_file": row[0],
            "source_index": row[1],
            "source_sha256": row[2],
        }
        for row in rows
    ]


def _csv_value(record: dict, field: str, provenance_count: int) -> object:
    if field == "provenance_count":
        return provenance_count
    if field == "publication_date":
        values = record.get("dates") or []
        return values[0] if isinstance(values, list) and values else ""
    value = record.get(field, "")
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _write_outputs(
    connection: sqlite3.Connection,
    output_dir: Path,
    summary: dict,
    input_files: list[dict],
    invalid_files: list[dict],
    invalid_records: list[dict],
    warning_counts: dict[str, int],
) -> None:
    provenance_by_record: dict[int, list[dict]] = {}
    for record_id, source_file, source_index, source_sha256 in connection.execute(
        """
        SELECT record_id, source_file, source_index, source_sha256
        FROM provenance
        ORDER BY record_id, source_file, source_index
        """
    ):
        provenance_by_record.setdefault(int(record_id), []).append(
            {
                "source_file": source_file,
                "source_index": source_index,
                "source_sha256": source_sha256,
            }
        )

    jsonl_path = output_dir / "articles.jsonl"
    csv_path = output_dir / "articles.csv"
    with jsonl_path.open("w", encoding="utf-8") as jsonl, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as csv_stream:
        writer = csv.DictWriter(csv_stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record_id, record_json in connection.execute(
            "SELECT id, record_json FROM records ORDER BY id"
        ):
            record = json.loads(record_json)
            provenance = provenance_by_record.get(int(record_id), [])
            enriched = {**record, "_provenance": provenance}
            jsonl.write(json.dumps(enriched, ensure_ascii=False) + "\n")
            writer.writerow(
                {
                    field: _csv_value(record, field, len(provenance))
                    for field in CSV_FIELDS
                }
            )

    with (output_dir / "duplicate_decisions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        fields = ("kept_record_id", "source_file", "source_index", "reason", "matched_alias")
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(
            connection.execute(
                "SELECT kept_record_id, source_file, source_index, reason, matched_alias "
                "FROM decisions ORDER BY source_file, source_index"
            )
        )

    candidates = []
    for weak_key, count, ids in connection.execute(
        """
        SELECT weak_key, COUNT(*) AS record_count, GROUP_CONCAT(id) AS record_ids
        FROM records
        WHERE weak_key != ''
        GROUP BY weak_key
        HAVING COUNT(*) > 1
        ORDER BY weak_key
        """
    ):
        candidates.append(
            {
                "candidate_key": weak_key,
                "record_count": count,
                "record_ids": [int(item) for item in ids.split(",")],
            }
        )
    (output_dir / "duplicate_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    validation = {
        "summary": summary,
        "invalid_files": invalid_files,
        "invalid_records": invalid_records,
        "warning_counts": warning_counts,
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(summary["input_directory"]),
        "output_directory": str(summary["output_directory"]),
        "deduplication": {
            "automatic_keys": ["doi", "oai_identifier", "canonical_url"],
            "candidate_only_key": "normalized_title + first_creator + publication_year",
            "record_selection": "first valid record in lexicographic file order",
        },
        "input_files": input_files,
        "outputs": {
            "articles_jsonl": "articles.jsonl",
            "articles_csv": "articles.csv",
            "duplicate_decisions": "duplicate_decisions.csv",
            "duplicate_candidates": "duplicate_candidates.json",
            "validation_report": "validation_report.json",
        },
        "summary": summary,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def process_harvest(input_dir: Path, output_dir: Path) -> dict:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    database = output_dir / ".process_harvest.sqlite"
    database.unlink(missing_ok=True)

    files = discover_article_files(input_dir)
    summary = {
        "input_directory": str(input_dir),
        "output_directory": str(output_dir),
        "files_discovered": len(files),
        "files_valid": 0,
        "files_invalid": 0,
        "records_seen": 0,
        "records_valid": 0,
        "records_invalid": 0,
        "records_unique": 0,
        "duplicates_merged": 0,
        "weak_candidate_groups": 0,
    }
    input_files: list[dict] = []
    invalid_files: list[dict] = []
    invalid_records: list[dict] = []
    warning_counts: dict[str, int] = {}

    connection = sqlite3.connect(database)
    try:
        _init_db(connection)
        for path in files:
            raw = path.read_bytes()
            digest = sha256sum(raw)
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                summary["files_invalid"] += 1
                invalid_files.append({"path": path.name, "error": str(exc)})
                continue
            if not isinstance(data, list):
                summary["files_invalid"] += 1
                invalid_files.append({"path": path.name, "error": "top_level_not_list"})
                continue

            summary["files_valid"] += 1
            input_files.append(
                {"path": path.name, "sha256": digest, "bytes": len(raw), "records": len(data)}
            )
            for index, record in enumerate(data):
                summary["records_seen"] += 1
                valid, warnings = validate_record(record)
                if not valid:
                    summary["records_invalid"] += 1
                    invalid_records.append(
                        {
                            "source_file": path.name,
                            "source_index": index,
                            "errors": warnings,
                        }
                    )
                    continue
                summary["records_valid"] += 1
                for warning in warnings:
                    warning_counts[warning] = warning_counts.get(warning, 0) + 1
                duplicate_count = _add_record(
                    connection,
                    record,
                    path.name,
                    index,
                    digest,
                )
                summary["duplicates_merged"] += duplicate_count
            connection.commit()

        summary["records_unique"] = int(
            connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        )
        summary["weak_candidate_groups"] = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT weak_key FROM records WHERE weak_key != ''
                    GROUP BY weak_key HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
        )
        _write_outputs(
            connection,
            output_dir,
            summary,
            input_files,
            invalid_files,
            invalid_records,
            warning_counts,
        )
    finally:
        connection.close()
        database.unlink(missing_ok=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/derived"))
    args = parser.parse_args()

    summary = process_harvest(args.input_dir, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
