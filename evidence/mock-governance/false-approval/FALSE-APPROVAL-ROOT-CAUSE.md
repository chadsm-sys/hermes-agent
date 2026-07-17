# False Approval Root Cause

**Final classification:** implementation defect plus an overly permissive contract schema and missing fail-closed conditions.

## Exact decision

- Event: `evt-005`
- Action: `restart_service`
- Target: `mock://launchd/ai.hermes.gateway`
- Original Olympus result: `ALLOW` / `SIMULATED_WOULD_EXECUTE`
- Human baseline: `DENY`
- Deterministic reproduction: `TRUE`
- Original digest: `b6d466a3ee4b97d2ece7bd053dae21a6a9e6859d539093a2804461e17f909eaa`

## Proven decision path

The original v1 engine recognized the `restart_service` contract, accepted Tier 3, found all three required evidence IDs with `verified=true`, found no event-supplied policy conflict, and produced no denial reason. Its fallback was `allowed = not reasons`, so it approved. Confidence `0.93` was clamped but did not gate or override anything.

That path was defective because it did not enforce the already-declared `protected_mutations_default_blocked=true` policy and treated bare evidence-ID presence as verification. The operator approval had no issuer, scope, target binding, or freshness; the health receipt had no target or freshness; the rollback plan had no target or plan identity.

## Human baseline review

The baseline was not accepted on authority alone. It is supported by the declared protected-mutation default-deny policy and the frozen event's unverifiable evidence. Olympus was not correct under a defensible fail-closed interpretation.

## Root-cause boundaries

- Authority mapping was correct: Tier 3 supplied, Tier 3 required.
- Contract identity was present but its v1 schema was insufficient.
- Target was mock-only and is authorized after explicit contract-prefix validation.
- The defect did not involve side-effect interception; execution remained simulated.
