#!/usr/bin/env python3
"""Fail closed unless every required GitHub Actions job succeeded or skipped."""

from __future__ import annotations

import json
import sys
from typing import Iterable


ALLOWED_RESULTS = frozenset({"success", "skipped"})


def unexpected_results(results: Iterable[object]) -> list[object]:
    """Return results that cannot satisfy the required-check aggregate."""
    return [result for result in results if result not in ALLOWED_RESULTS]


def main() -> int:
    results = json.load(sys.stdin)
    if not isinstance(results, list):
        print("::error::required job results must be a JSON array")
        return 1
    unexpected = unexpected_results(results)
    if unexpected:
        print(f"::error::required job result(s) not successful: {unexpected!r}")
        return 1
    print("All required checks passed (or were skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
