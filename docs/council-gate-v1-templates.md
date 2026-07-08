# Council Gate V1 Templates

Council Gate V1 is a disabled-by-default, mock-safe review layer for high-risk Hermes workflow gates. These templates are instructions/examples only; they do not permit live model calls, external contact, spending, provider/auth/db/cron behavior changes, or file edits by reviewers.

## 1. Host-to-Council instructions

Use this shape when the host asks a Council adapter to review a frozen plan, scope, delivery, commit/merge readiness, cron resume, public release, outbound/spend, or provider/auth/db/cron change.

```text
You are a Council reviewer. Review the frozen request only.

Hard limits:
- Do not execute commands.
- Do not edit files.
- Do not contact users or third parties.
- Do not spend money.
- Do not request or expose secrets.
- Do not override tests, secret scans, branch protection, deterministic checks, or Chad's approval.
- Do not expand scope beyond the requested gate.

Return JSON only:
{
  "verdict": "APPROVE|REVISE|BLOCK",
  "confidence": "LOW|MEDIUM|HIGH",
  "primary_risks": [],
  "evidence_gaps": [],
  "scope_creep_detected": false,
  "safety_concerns": [],
  "distribution_or_monetization_concerns": [],
  "required_fixes": [],
  "optional_suggestions": [],
  "final_recommendation": "one concise recommendation"
}
```

## 2. Council-to-Host reviewer instructions

The host must treat Council output as advisory below deterministic safety checks.

Host enforcement:
- malformed reviewer output => `BLOCK` or `REVISE`, never `APPROVE`
- failed deterministic checks => final outcome `BLOCKED`, even if Council says `APPROVE`
- command adapter disabled unless explicitly configured with an argv allowlist
- live model calls disabled by default
- request payload redacted before adapter invocation
- artifacts written for auditability

## 3. Build scope review example

```json
{
  "gate_type": "BUILD_SCOPE",
  "host_summary": "Review whether this build scope is bounded to Council Gate V1 runtime behavior.",
  "frozen_plan_or_delivery": "Implement models, adapters, gate runner, config, and narrow GoalManager hook only.",
  "allowed_actions": ["edit Council files", "run local tests"],
  "forbidden_actions": ["commit", "push", "merge", "live model calls", "broad refactors"],
  "reviewer_questions": ["Is scope narrow?", "Are safety gates preserved?"]
}
```

Expected Council result: `APPROVE` if bounded; `REVISE` if scope or tests are unclear; `BLOCK` if it requires live calls or weakens safety.

## 4. AppLab candidate review example

Question: Should AppLab require product wedge + distribution wedge + monetization wedge before exact teardown or build?

Expected Council result: `APPROVE` for requiring all three wedges as a pre-build gate; `REVISE` if evidence fields are missing; `BLOCK` if it would trigger outbound, spend, or the full AppLab money-loop patch without approval.

## 5. Commit/merge review example

```json
{
  "gate_type": "COMMIT_READY",
  "deterministic_checks": {
    "git_diff_check": "PASS",
    "targeted_tests": "PASS",
    "secret_scan": "PASS"
  },
  "forbidden_actions": ["push", "merge", "rebase main", "cron resume"]
}
```

Council cannot override failed deterministic checks. A failed test or secret scan forces host outcome `BLOCKED`.

## 6. Cron resume review example

```json
{
  "gate_type": "CRON_RESUME",
  "host_summary": "Review whether it is safe to resume a paused autonomous job.",
  "deterministic_checks": {
    "job_prompt_self_contained": "PASS",
    "delivery_target_verified": "PASS",
    "failure_visibility": "PASS",
    "no_recursive_scheduling": "PASS"
  },
  "forbidden_actions": ["resume cron without Chad approval", "contact users", "spend money"]
}
```

Expected Council result: `APPROVE` only when deterministic checks pass and Chad approval is still required for actual resume.
