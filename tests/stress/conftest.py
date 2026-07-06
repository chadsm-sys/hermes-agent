"""pytest config for the stress/ subdirectory.

These files are __main__-executable stress scripts, not pytest test
modules: they define no ``test_*`` functions and carry top-level
constants tuned for long adversarial runs (30s+, real subprocesses).
Run them directly:

    python tests/stress/test_concurrency.py

pytest must not import them, so the whole directory is excluded from
collection below. (A previous ``--run-stress`` opt-in flag was removed:
with zero collectable test functions it could never run anything — see
tests/test_pytest_guardrails.py for the guard that keeps this honest.)
"""

collect_ignore_glob = [
    # The stress scripts have top-level tuning constants and hard-coded
    # paths; they're meant to run as `python tests/stress/<name>.py`,
    # not as pytest modules.
    "*.py",
]
