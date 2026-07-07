"""Chief-of-staff contract surface for Hermes executive-loop integrations.

The package is intentionally import-light: it exposes stable contract helpers
without coupling installed wheels to Hermes runtime services.
"""

from chief_of_staff.contracts import SCHEMA_VERSION, check_schema_version

__all__ = ["SCHEMA_VERSION", "check_schema_version"]
