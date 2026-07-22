from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "harvest_complete.py"


def write_dataset(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "oai_url": "https://alive.example/index/oai",
                    "repository_name": "Alive",
                    "unresponsive_endpoint": False,
                },
                {
                    "oai_url": "https://dead.example/index/oai",
                    "repository_name": "Dead",
                    "unresponsive_endpoint": True,
                },
            ]
        )
    )


def run_harvest(args, tmp_path):
    input_path = tmp_path / "input.json"
    output_dir = tmp_path / "raw"
    log_dir = tmp_path / "logs"
    write_dataset(input_path)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dry-run",
            "--phase",
            "2",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--log-dir",
            str(log_dir),
            *args,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_unresponsive_endpoints_are_skipped_by_default(tmp_path):
    result = run_harvest([], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Filtrados 1 não responsivos → 1 restantes" in result.stderr
    assert "Isolados (1 periódico por URL): 1" in result.stderr


def test_no_skip_unresponsive_includes_flagged_endpoints(tmp_path):
    result = run_harvest(["--no-skip-unresponsive"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Filtrados" not in result.stderr
    assert "Isolados (1 periódico por URL): 2" in result.stderr
