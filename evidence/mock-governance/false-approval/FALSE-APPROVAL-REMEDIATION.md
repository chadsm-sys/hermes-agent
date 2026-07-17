# False Approval Remediation

## Smallest defensible correction

1. Added contract-driven policy applicability and allowed mock-target prefixes.
2. Enforced the existing protected-mutation default block through explicit, validated policy-gate evidence.
3. Added general evidence validation for required metadata, duplicate/contradictory IDs, target binding, scope, timestamps, and contract-defined freshness.
4. Added fail-closed handling for malformed contract identity, policy applicability, authority tier, target identity, evidence, and confidence.
5. Kept permanent denials and the simulation-only sink unchanged.

No event ID or target was hard-coded into runtime decision logic. The stricter restart requirements live in the `restart_service` contract and apply to every event of that action kind.

## Regression coverage

- Exact `evt-005` frozen event
- Missing evidence
- Contradictory evidence
- Unknown contract
- Stale evidence
- Malformed authority tier
- Unauthorized target
- Legitimate approval with complete evidence
- Legitimate denial with complete evidence

## Verification

- Original tests: `14/14`
- New regression tests: `9/9`
- Total: `23/23`
- Zero-side-effect controls: `11/11`
- Replay digest: `fde88e2e961fb898cd1617d813d287dd897663392d481df214b48f31be0bca9d`
- Final verdict: `FALSE_APPROVAL_RESOLVED`
