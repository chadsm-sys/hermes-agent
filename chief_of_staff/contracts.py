"""Shared schema-version helpers for chief-of-staff contracts."""

from __future__ import annotations

SCHEMA_VERSION = "1.0"


def _major(version: str) -> str:
    return version.split(".", 1)[0]


def check_schema_version(version: str) -> bool:
    """Return True when *version* is compatible with this contract major.

    Mission Control may send additive minor versions (for example ``1.1``).
    Consumers accept matching majors and reject future incompatible majors.
    """

    if not isinstance(version, str) or not version.strip():
        return False
    return _major(version.strip()) == _major(SCHEMA_VERSION)


__all__ = ["SCHEMA_VERSION", "check_schema_version"]
