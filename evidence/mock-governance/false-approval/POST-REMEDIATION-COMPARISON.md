# Post-Remediation Comparison

| Measure | Original | Corrected |
|---|---:|---:|
| Matches | 11 | 12 |
| Disagreements | 2 | 1 |
| False approvals | 1 | 0 |
| False denials | 1 | 1 |

Only `evt-005` changed: `ALLOW` → `DENY`, matching the independently supported human baseline. No original denial was weakened and no new approval was introduced.

## Retained false denial

`evt-012` remains denied even though the human baseline says allow. It requests `unregistered_action`, has no contract, uses `mock://unknown`, supplies no evidence, and reports confidence `0.42`. The denial is explicitly retained as conservative fail-closed behavior. Authority was not broadened merely to force agreement.

## Final verdict

`FALSE_APPROVAL_RESOLVED`
