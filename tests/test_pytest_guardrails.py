"""Guardrail meta-tests for the pytest configuration.

Proves that ``--strict-markers`` catches the failure mode this suite
actually had: ``pytest.mark.timeout(...)`` marks were applied for years
while pytest-timeout was never a dependency, so every timeout mark was a
silent no-op (the comments even referenced a global ``--timeout=30``
that did not exist). With ``--strict-markers``, an unregistered marker
is a collection error instead of a silent lie.

Each test shells out to a fresh pytest with the repo's own
``pyproject.toml`` config (``-c``), so the assertions exercise the real
configuration, not a synthetic one.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _run_pytest_collect(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-c",
            str(PYPROJECT),
            *args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_unregistered_marker_is_a_collection_error(tmp_path):
    """The prior failure mode — a mark for an uninstalled plugin — now fails loudly.

    ``timeout`` is exactly the marker this suite carried as a silent
    no-op before --strict-markers landed.
    """
    test_file = tmp_path / "test_phantom_marker.py"
    test_file.write_text(
        textwrap.dedent(
            """
            import pytest

            @pytest.mark.timeout(300)
            def test_something():
                pass
            """
        )
    )
    result = _run_pytest_collect(str(test_file))
    assert result.returncode != 0, (
        "collection unexpectedly succeeded — --strict-markers is not active:\n"
        + result.stdout
        + result.stderr
    )
    combined = result.stdout + result.stderr
    assert "'timeout' not found in `markers` configuration option" in combined, combined


def test_registered_markers_still_collect(tmp_path):
    """Every custom marker the suite legitimately uses passes strict collection."""
    test_file = tmp_path / "test_registered_markers.py"
    test_file.write_text(
        textwrap.dedent(
            """
            import pytest

            pytestmark = pytest.mark.xdist_group("guardrail_demo")

            @pytest.mark.integration
            @pytest.mark.ssh
            @pytest.mark.real_concurrent_gate
            def test_something():
                pass
            """
        )
    )
    result = _run_pytest_collect(str(test_file))
    combined = result.stdout + result.stderr
    # Exit 0 (collected) or 5 (collected then deselected by `-m 'not
    # integration'`) are both fine; a marker error is exit 2.
    assert result.returncode in (0, 5), combined
    assert "not found in `markers`" not in combined, combined


def test_stress_scripts_are_not_collected():
    """tests/stress/ holds __main__ scripts with zero test functions.

    They must stay excluded from collection (conftest collect_ignore_glob)
    rather than pretend to be an opt-in suite: the removed --run-stress
    flag could never run anything.
    """
    result = _run_pytest_collect("tests/stress")
    combined = result.stdout + result.stderr
    # Exit 5 == pytest collected nothing, which is the honest state here.
    assert result.returncode == 5, combined
    assert "no tests collected" in combined or "no tests ran" in combined, combined
