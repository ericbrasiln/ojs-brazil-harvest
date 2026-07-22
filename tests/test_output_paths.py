from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "harvest_complete.py"
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "ojs_brazil_pkp_beacon.json"


def load_harvest_module():
    spec = importlib.util.spec_from_file_location("harvest_complete", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harvest():
    return load_harvest_module()


def test_output_path_distinguishes_same_name_on_different_urls(harvest, tmp_path):
    first = harvest.make_output_path(
        tmp_path,
        "Open Journal Systems",
        "https://first.example/index/oai",
    )
    second = harvest.make_output_path(
        tmp_path,
        "Open Journal Systems",
        "https://second.example/index/oai",
    )

    assert first != second
    assert first.name.startswith("open_journal_systems--")
    assert second.name.startswith("open_journal_systems--")


def test_output_path_distinguishes_set_specs_with_same_slug(harvest, tmp_path):
    first = harvest.make_output_path(
        tmp_path,
        "Portal",
        "https://portal.example/index/oai",
        "revista/a",
    )
    second = harvest.make_output_path(
        tmp_path,
        "Portal",
        "https://portal.example/index/oai",
        "revista-a",
    )

    assert first != second


def test_output_path_is_deterministic(harvest, tmp_path):
    args = (
        tmp_path,
        "Revista de História",
        "https://example.org/index/oai",
        "artigos",
    )

    assert harvest.make_output_path(*args) == harvest.make_output_path(*args)


def test_output_path_hash_uses_endpoint_and_set_identity(harvest, tmp_path):
    url = "https://example.org/index/oai"
    set_spec = "artigos"
    expected_hash = hashlib.sha256(f"{url}\0{set_spec}".encode()).hexdigest()[:12]

    path = harvest.make_output_path(tmp_path, "Revista", url, set_spec)

    assert expected_hash in path.name


def test_all_responsive_dataset_destinations_are_unique(harvest, tmp_path):
    dataset = json.loads(DATASET_PATH.read_text())
    responsive = [item for item in dataset if not item.get("unresponsive_endpoint", False)]
    counts: dict[str, int] = {}
    for item in responsive:
        url = item["oai_url"]
        counts[url] = counts.get(url, 0) + 1

    isolated = [item for item in responsive if counts[item["oai_url"]] == 1]
    paths = [
        harvest.make_output_path(
            tmp_path,
            item.get("repository_name", ""),
            item["oai_url"],
        )
        for item in isolated
    ]

    assert len(paths) == 1439
    assert len(set(paths)) == len(paths)
