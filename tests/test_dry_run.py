from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "harvest_complete.py"


def test_dry_run_does_not_write_collection_state(tmp_path):
    input_path = tmp_path / "input.json"
    output_dir = tmp_path / "raw"
    log_dir = tmp_path / "logs"
    input_path.write_text(
        json.dumps(
            [
                {
                    "oai_url": "https://portal.example/index/oai",
                    "repository_name": "Portal",
                    "unresponsive_endpoint": False,
                },
                {
                    "oai_url": "https://portal.example/index/oai",
                    "repository_name": "Portal",
                    "unresponsive_endpoint": False,
                },
                {
                    "oai_url": "https://isolated.example/index/oai",
                    "repository_name": "Revista",
                    "unresponsive_endpoint": False,
                },
            ]
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dry-run",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--log-dir",
            str(log_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert list(output_dir.glob("*")) == []
    assert "Dry run: True" in result.stderr
    assert "Portais (URLs com >1 periódico): 1" in result.stderr
    assert "Isolados (1 periódico por URL): 1" in result.stderr
