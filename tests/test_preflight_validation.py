from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "harvest_complete.py"


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


@pytest.mark.parametrize(
    ("value", "is_until", "expected"),
    [
        ("2024", False, "2024-01-01"),
        ("2024", True, "2024-12-31"),
        ("2024-06-15", False, "2024-06-15"),
    ],
)
def test_normalize_harvest_date_accepts_year_or_full_date(harvest, value, is_until, expected):
    assert harvest.normalize_harvest_date(value, is_until=is_until) == expected


@pytest.mark.parametrize("value", ["24", "2024-6-1", "2024-13-01", "not-a-date"])
def test_normalize_harvest_date_rejects_invalid_dates(harvest, value):
    with pytest.raises(ValueError):
        harvest.normalize_harvest_date(value)


def test_validate_date_range_rejects_from_after_until(harvest):
    with pytest.raises(ValueError, match="from.*until"):
        harvest.validate_date_range("2025-01-01", "2024-12-31")


def test_ensure_ojs_scrape_available_checks_cli_flag(harvest, monkeypatch):
    class Result:
        returncode = 0
        stdout = "usage: ojs-scrape [--no-verify-ssl] url"
        stderr = ""

    monkeypatch.setattr(harvest.subprocess, "run", lambda *a, **k: Result())

    harvest.ensure_ojs_scrape_available()


def test_ensure_ojs_scrape_available_rejects_missing_ssl_flag(harvest, monkeypatch):
    class Result:
        returncode = 0
        stdout = "usage: ojs-scrape url"
        stderr = ""

    monkeypatch.setattr(harvest.subprocess, "run", lambda *a, **k: Result())

    with pytest.raises(RuntimeError, match="--no-verify-ssl"):
        harvest.ensure_ojs_scrape_available()
