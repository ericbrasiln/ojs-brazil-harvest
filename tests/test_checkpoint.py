from __future__ import annotations

import importlib.util
import json
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


def test_save_checkpoint_writes_valid_json_and_leaves_no_temp_files(harvest, tmp_path):
    checkpoint = {
        "phase1_done": True,
        "phase1_portals_processed": ["https://example.org/oai"],
        "phase2_done": False,
        "phase2_isolateds_processed": [],
        "phase3_done": False,
        "phase3_retries_processed": [],
    }

    harvest.save_checkpoint(tmp_path, checkpoint)

    cp_path = tmp_path / "harvest_complete_checkpoint.json"
    assert json.loads(cp_path.read_text()) == checkpoint
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_json_atomic_preserves_existing_file_when_replace_fails(harvest, tmp_path, monkeypatch):
    target = tmp_path / "phase1_results.json"
    target.write_text('[{"status": "old"}]')

    def fail_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(harvest.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        harvest.save_json_atomic(target, [{"status": "new"}])

    assert json.loads(target.read_text()) == [{"status": "old"}]
    assert list(tmp_path.glob("*.tmp")) == []
