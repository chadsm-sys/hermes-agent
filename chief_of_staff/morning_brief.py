"""Morning packet consumer contract for chief-of-staff integrations."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from chief_of_staff.contracts import check_schema_version


class MorningBriefSource(Protocol):
    """Source adapter contract for future read-only morning packet wiring."""

    def fetch_latest(self) -> Mapping[str, Any] | None:
        """Return the latest morning brief payload, or None when unavailable."""


def parse_morning_brief(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema-major compatibility and return a detached payload copy."""

    version = str(payload.get("contract_version", "1.0"))
    if not check_schema_version(version):
        raise ValueError(f"unsupported morning brief contract_version: {version}")
    return dict(payload)


__all__ = ["MorningBriefSource", "parse_morning_brief"]
