from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import urllib.error
from email.message import Message
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "prepare_beacon_dataset.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_beacon_dataset", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prepare():
    return load_module()


def write_source(path: Path) -> None:
    fields = [
        "oai_url",
        "application",
        "version",
        "admin_email",
        "earliest_datestamp",
        "repository_name",
        "set_spec",
        "context_name",
        "total_record_count",
        "issn",
        "country_consolidated",
        "last_oai_response",
        "unresponsive_endpoint",
        "unresponsive_context",
        "record_count_2020",
        "record_count_2021",
        "record_count_2022",
        "record_count_2023",
        "record_count_2024",
        "record_count_2025",
        "region",
    ]
    rows = [
        {
            "oai_url": "https://example.org/index/oai",
            "application": "ojs",
            "version": "3.4.0.8",
            "admin_email": "private@example.org",
            "earliest_datestamp": "2020-01-01 00:00:00",
            "repository_name": "Portal",
            "set_spec": "revista",
            "context_name": "Revista",
            "total_record_count": "12",
            "issn": "1234-5678\\n8765-4321",
            "country_consolidated": "BR",
            "last_oai_response": "2025-01-01 00:00:00",
            "unresponsive_endpoint": "0",
            "unresponsive_context": "1",
            "record_count_2020": "2",
            "record_count_2021": "",
            "record_count_2022": "0",
            "record_count_2023": "3",
            "record_count_2024": "4",
            "record_count_2025": "3",
            "region": "Latin America & Caribbean ",
        },
        {
            "oai_url": "https://foreign.example/oai",
            "application": "ojs",
            "country_consolidated": "PT",
        },
        {
            "oai_url": "https://books.example/oai",
            "application": "omp",
            "country_consolidated": "BR",
        },
    ]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_build_brazil_dataset_filters_and_removes_contact_email(prepare, tmp_path):
    source = tmp_path / "beacon.tab"
    write_source(source)

    records = prepare.build_brazil_dataset(source)

    assert len(records) == 1
    record = records[0]
    assert record["oai_url"] == "https://example.org/index/oai"
    assert record["base_url"] == "https://example.org/index"
    assert record["issn"] == "1234-5678; 8765-4321"
    assert record["total_record_count"] == 12
    assert record["record_count_2021"] == 0
    assert record["unresponsive_endpoint"] is False
    assert record["unresponsive_context"] is True
    assert record["region"] == "Latin America & Caribbean"
    assert "admin_email" not in record


def test_download_source_uses_dataverse_compatible_user_agent(prepare, tmp_path, monkeypatch):
    payload = b"oai_url\tapplication\n"
    expected = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(prepare, "BEACON_V6_TABULAR_SHA256", expected)

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_urlopen(request, timeout):
        assert request.get_header("User-agent").startswith("Mozilla/5.0")
        assert timeout == 120
        return Response(payload)

    monkeypatch.setattr(prepare.urllib.request, "urlopen", fake_urlopen)
    output = tmp_path / "beacon.tab"

    prepare.download_source(output)

    assert output.read_bytes() == payload


def test_download_source_falls_back_to_curl_on_dataverse_403(prepare, tmp_path, monkeypatch):
    payload = b"oai_url\tapplication\n"
    expected = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(prepare, "BEACON_V6_TABULAR_SHA256", expected)

    def fail_urllib(output):
        raise urllib.error.HTTPError("url", 403, "Forbidden", Message(), None)

    def fake_curl(output):
        output.write_bytes(payload)

    monkeypatch.setattr(prepare, "_download_with_urllib", fail_urllib)
    monkeypatch.setattr(prepare, "_download_with_curl", fake_curl)
    output = tmp_path / "beacon.tab"

    prepare.download_source(output)

    assert output.read_bytes() == payload


def test_write_dataset_produces_reproducible_json(prepare, tmp_path):
    output = tmp_path / "processed.json"
    records = [{"oai_url": "https://example.org/oai", "total_record_count": 1}]

    prepare.write_dataset(output, records)

    assert json.loads(output.read_text()) == records
