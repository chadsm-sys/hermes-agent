"""Contract tests for shipping the chief_of_staff package in built wheels."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_chief_of_staff_package_imports_from_installed_wheel(tmp_path):
    wheel_dir = tmp_path / "wheel"
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir), "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert build.returncode == 0, f"uv build failed:\n{build.stdout}\n{build.stderr}"

    wheels = glob.glob(str(wheel_dir / "*.whl"))
    assert wheels, "no wheel produced"
    wheel = wheels[0]

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    expected_members = {
        "chief_of_staff/__init__.py",
        "chief_of_staff/contracts.py",
        "chief_of_staff/morning_brief.py",
        "chief_of_staff/evening_report.py",
        "chief_of_staff/escalation.py",
    }
    assert expected_members <= names

    probe = """
from chief_of_staff.contracts import SCHEMA_VERSION, check_schema_version
from chief_of_staff.morning_brief import MorningBriefSource, parse_morning_brief
from chief_of_staff.evening_report import EveningReportSource, parse_evening_report
from chief_of_staff.escalation import Decision, classify_escalation
assert SCHEMA_VERSION == "1.0"
assert check_schema_version("1.1") is True
assert check_schema_version("2.0") is False
assert callable(parse_morning_brief)
assert callable(parse_evening_report)
assert Decision.NEEDS_CHAD.value == "NEEDS_CHAD"
assert classify_escalation({"decision": "CONTINUE"}) is Decision.CONTINUE
assert MorningBriefSource
assert EveningReportSource
"""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = wheel
    run = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert run.returncode == 0, f"installed wheel import probe failed:\n{run.stdout}\n{run.stderr}"
