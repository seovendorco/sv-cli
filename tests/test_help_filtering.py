"""End-to-end check that --help hides irrelevant options per tool+action (points 1/2).

This spawns a real subprocess (rather than calling the Typer app in-process) because
main.py reads the on-disk definitions cache and bakes per-option `hidden` flags in at
module import time - one process per invocation, exactly like real CLI usage. Testing
in-process would be import-order-dependent across the test suite instead.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _run_cli(sv_home: Path, *args: str) -> str:
    cache_dir = sv_home / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = {
        "version": 1,
        "base_url": "https://ai.seovendor.co/api/",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "root": {"seogpt2": {}, "ranklens": {}},
        "tools": {
            "seogpt2": {"tool": "seogpt2", "definition": json.loads((FIXTURES / "seogpt2_definitions.json").read_text())},
            "ranklens": {"tool": "ranklens", "definition": json.loads((FIXTURES / "ranklens_definitions.json").read_text())},
        },
        "warnings": [],
    }
    (cache_dir / "definitions.json").write_text(json.dumps(cache))
    env = dict(os.environ)
    env["SV_HOME"] = str(sv_home)
    env["NO_COLOR"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "sv_cli.main", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return _ANSI_ESCAPE_RE.sub("", result.stdout)


def test_seogpt2_create_task_hides_unrelated_generic_options(tmp_path):
    output = _run_cli(tmp_path, "seogpt2", "create-task", "--help")
    assert "--topic" in output
    assert "--keyword" in output
    assert "--price" not in output
    assert "--theme" not in output
    assert "--entity" not in output  # entity is RankLens/Insight Igniter only


def test_seogpt2_get_task_status_shows_only_task_id(tmp_path):
    output = _run_cli(tmp_path, "seogpt2", "get-task-status", "--help")
    assert "--task-id" in output
    assert "--topic" not in output
    assert "--keyword" not in output


def test_ranklens_rank_shows_entity_not_seogpt2_only_fields(tmp_path):
    output = _run_cli(tmp_path, "ranklens", "rank", "--help")
    assert "--entity" in output
    assert "--topic" not in output
    assert "--price" not in output


def test_tool_help_separates_actions_from_option_lookups(tmp_path):
    output = _run_cli(tmp_path, "seogpt2", "--help")
    assert "Actions" in output
    assert "Option lookups" in output
    actions_section = output.split("Option lookups")[0]
    assert "create-task" in actions_section
    assert "languages" not in actions_section
