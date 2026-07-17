# Olympus Schema V2 Offline Fixture Prototype

Standalone, standard-library-only validation of the approved Schema v2 design using synthetic data.

## Safety boundary

- No Hermes integration
- No exporter modification
- No runtime, policy, contract, or production configuration changes
- No network access, credentials, outbound action, activation, or production authority
- Writes only to the selected generated-artifact directory

## Generate

```bash
cd offline_fixture_prototype
PYTHONPATH=. python3 generate.py
```

Use `--replace` only to regenerate the generated-only output directory.

## Verify

```bash
cd offline_fixture_prototype
PYTHONPATH=. python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 verify_generated.py
```

## Artifact map

- `generated/fixtures/raw/` — exact canonical or adversarial raw inputs
- `generated/fixtures/normalized-ledger.jsonl` — ordered valid/quarantine normalization ledger
- `generated/reports/replay-evidence.*` — deterministic replay results
- `generated/reports/adversarial-validation-report.*` — expected-versus-actual adversarial outcomes
- `generated/reports/digest-verification-report.json` — canonicalization and digest profile evidence
- `generated/reports/fixture-certification-report.*` — offline-only certification and verdict
- `generated/manifests/` — fixture, evidence, source, certification, combined, and root hashes

The fixture certification is intentionally self-excluded from its evidence manifests. Its digest is stored externally in `certification.sha256`, and `manifest-root.json` binds that manifest without attempting a self-hash.
