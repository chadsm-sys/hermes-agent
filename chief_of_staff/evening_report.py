"""Evening packet consumer contract for chief-of-staff integrations."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from chief_of_staff.contracts import check_schema_version


class EveningReportSource(Protocol):
    """Source adapter contract for future read-only evening packet wiring."""

    def fetch_latest(self) -> Mapping[str, Any] | None:
        """Return the latest evening report payload, or None when unavailable."""


def parse_evening_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema-major compatibility and return a detached payload copy."""

    version = str(payload.get("contract_version", "1.0"))
    if not check_schema_version(version):
        raise ValueError(f"unsupported evening report contract_version: {version}")
    return dict(payload)


__all__ = ["EveningReportSource", "parse_evening_report"]
