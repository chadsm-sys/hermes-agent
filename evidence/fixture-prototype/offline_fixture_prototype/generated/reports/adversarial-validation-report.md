# Adversarial Validation Report

**Scope:** Offline synthetic fixtures only; no production authority.

- **Advisory Output Digest:** `advisory-sha256-e6d7512d90005e042a5599afef8e74ea9d8c27d2c3f45020e49a2c3f5485f4bb`
- **Fixture Namespace:** `olympus-fixture-v2-20260717`
- **Item Count:** `28`
- **Quarantine Count:** `14`
- **Replay Identifier:** `replay-397b07d5b47851bba3975c00e42a66a8ecaebd2df039045c99032831510939e5`
- **Valid Count:** `14`
- **Verdict:** `FIXTURE_PROTOTYPE_READY`

| Case | Expected | Actual | Result |
|---|---|---|---|
| `downgrade` | `unknown_version` | `unknown_version` | **PASS** |
| `provenance_spoof` | `invalid_provenance` | `invalid_provenance` | **PASS** |
| `replay_spoof` | `invalid_replay` | `invalid_replay` | **PASS** |
| `duplicate_key` | `duplicate_key` | `duplicate_key` | **PASS** |
| `invalid_utf8` | `invalid_utf8` | `invalid_utf8` | **PASS** |
| `invalid_json` | `invalid_json` | `invalid_json` | **PASS** |
| `extra_field` | `invalid_additional_property` | `invalid_additional_property` | **PASS** |
| `unknown_enum` | `invalid_enum` | `invalid_enum` | **PASS** |
| `invalid_identifier` | `invalid_identifier` | `invalid_identifier` | **PASS** |
| `allow_indeterminate` | `invalid_cross_field` | `invalid_cross_field` | **PASS** |
| `policy_conflict` | `invalid_cross_field` | `invalid_cross_field` | **PASS** |
| `circular_fact_source` | `invalid_additional_property` | `invalid_additional_property` | **PASS** |
| `namespace_spoof` | `invalid_additional_property` | `invalid_additional_property` | **PASS** |
| `invalid_top_level` | `invalid_top_level` | `invalid_top_level` | **PASS** |
