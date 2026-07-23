from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "process_harvest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("process_harvest", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def process():
    return load_module()


def article(**overrides):
    record = {
        "oai_identifier": "oai:example:article/1",
        "article_id": 1,
        "url": "https://example.org/article/view/1",
        "datestamp": "2025-01-01T00:00:00Z",
        "title": "Example title",
        "creators": ["Silva, Ana"],
        "dates": ["2024-01-01"],
        "doi": "",
        "identifiers": [],
        "deleted": False,
    }
    record.update(overrides)
    return record


def test_normalize_doi_accepts_urls_and_prefixes(process):
    assert process.normalize_doi("https://doi.org/10.1234/ABC.1") == "10.1234/abc.1"
    assert process.normalize_doi("doi: 10.9999/Test") == "10.9999/test"
    assert process.normalize_doi("not a doi") == ""


def test_strong_aliases_include_doi_oai_and_canonical_url(process):
    record = article(doi="https://doi.org/10.1234/ABC.1")

    aliases = process.strong_aliases(record)

    assert "doi:10.1234/abc.1" in aliases
    assert "oai:oai:example:article/1" in aliases
    assert "url:https://example.org/article/view/1" in aliases


def test_weak_key_is_only_a_candidate_signal(process):
    first = article(oai_identifier="oai:a", url="", doi="")
    second = article(oai_identifier="", url="", doi="", article_id=2)

    assert process.weak_candidate_key(first) == process.weak_candidate_key(second)
    assert process.strong_aliases(second) == []


def test_discover_article_files_excludes_control_files(process, tmp_path):
    for name in [
        "journal.json",
        "portal__set.json",
        "phase1_results.json",
        "harvest_complete_checkpoint.json",
        "retry_ssl_results.json",
        "probe_results.json",
    ]:
        (tmp_path / name).write_text("[]")

    found = [path.name for path in process.discover_article_files(tmp_path)]

    assert found == ["journal.json", "portal__set.json"]


def test_bridge_record_merges_previously_separate_strong_aliases(process, tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "derived"
    input_dir.mkdir()

    doi_only = article(doi="10.1234/bridge", oai_identifier="", url="", title="DOI copy")
    oai_only = article(doi="", oai_identifier="oai:bridge", url="", title="OAI copy")
    bridge = article(
        doi="10.1234/bridge",
        oai_identifier="oai:bridge",
        url="",
        title="Bridge copy",
    )
    (input_dir / "a.json").write_text(json.dumps([doi_only]))
    (input_dir / "b.json").write_text(json.dumps([oai_only]))
    (input_dir / "c.json").write_text(json.dumps([bridge]))

    summary = process.process_harvest(input_dir, output_dir)

    assert summary["records_unique"] == 1
    assert summary["duplicates_merged"] == 2
    with (output_dir / "duplicate_decisions.csv").open(newline="") as stream:
        decisions = list(csv.DictReader(stream))
    assert [row["reason"] for row in decisions] == ["alias_bridge", "doi"]


def test_end_to_end_consolidation_preserves_provenance_and_decisions(process, tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "derived"
    input_dir.mkdir()

    record_a = article(doi="10.1234/a", oai_identifier="oai:a", title="Article A")
    record_b = article(
        doi="",
        oai_identifier="oai:b",
        article_id=2,
        url="https://example.org/article/view/2",
        title="Shared title",
    )
    record_c = article(
        doi="",
        oai_identifier="",
        article_id=3,
        url="",
        title="Shared title",
    )
    (input_dir / "a.json").write_text(json.dumps([record_a, record_b, record_c]))

    duplicate_a = article(
        doi="https://doi.org/10.1234/A",
        oai_identifier="oai:a:mirror",
        article_id=99,
        url="https://mirror.example/article/99",
        title="Article A mirror",
    )
    duplicate_b = article(
        doi="",
        oai_identifier="oai:b",
        article_id=2,
        url="https://other.example/article/2",
        title="Shared title",
    )
    (input_dir / "b.json").write_text(json.dumps([duplicate_a, duplicate_b, "invalid"]))

    summary = process.process_harvest(input_dir, output_dir)

    assert summary["files_valid"] == 2
    assert summary["records_seen"] == 6
    assert summary["records_valid"] == 5
    assert summary["records_invalid"] == 1
    assert summary["records_unique"] == 3
    assert summary["duplicates_merged"] == 2
    assert summary["weak_candidate_groups"] == 1

    consolidated = [json.loads(line) for line in (output_dir / "articles.jsonl").read_text().splitlines()]
    assert len(consolidated) == 3
    record_a_out = next(record for record in consolidated if record["doi"] == "10.1234/a")
    record_b_out = next(record for record in consolidated if record["oai_identifier"] == "oai:b")
    assert len(record_a_out["_provenance"]) == 2
    assert len(record_b_out["_provenance"]) == 2

    with (output_dir / "duplicate_decisions.csv").open(newline="") as stream:
        decisions = list(csv.DictReader(stream))
    assert len(decisions) == 2
    assert {row["reason"] for row in decisions} == {"doi", "oai_identifier"}

    candidates = json.loads((output_dir / "duplicate_candidates.json").read_text())
    assert len(candidates) == 1
    assert candidates[0]["record_count"] == 2

    report = json.loads((output_dir / "validation_report.json").read_text())
    assert report["invalid_records"][0]["source_file"] == "b.json"

    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["summary"] == summary
    assert {item["path"] for item in manifest["input_files"]} == {"a.json", "b.json"}

    with (output_dir / "articles.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert "provenance_count" in rows[0]
