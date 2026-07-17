# Shadow Governance Post-Remediation Certification

## Final verdict

**FALSE_APPROVAL_RESOLVED**

Certified only for isolated, frozen-event, mock shadow evaluation. Production authority, activation, deployment, service control, cron changes, outbound integrations, and live configuration remain denied and outside scope.

## Acceptance evidence

- Exact original false approval: `evt-005` (`restart_service` → `mock://launchd/ai.hermes.gateway`)
- Original result reproduced from the archived v1 engine and contracts: `ALLOW`
- Archived and reproduced original decision digests match: `b6d466a3ee4b97d2ece7bd053dae21a6a9e6859d539093a2804461e17f909eaa`
- Corrected result: `DENY` / `SIMULATED_BLOCKED`
- Corrected event digest: `93a895c1b691fe0af69085fb88e231ab5dad92b0701dd4d3126f7e27cfb23cad`
- Human comparison: `12` matches, `1` documented conservative false denial, `0` false approvals
- Original tests: `14/14 PASS`
- New regression tests: `9/9 PASS`
- Total tests: `23/23 PASS`
- Zero-side-effect controls: `11/11 PASS`
- Two clean deterministic replays: `PASS`
- Matching replay digest: `fde88e2e961fb898cd1617d813d287dd897663392d481df214b48f31be0bca9d`
- All targets: `mock://`
- All outcomes: `SIMULATED_WOULD_EXECUTE` or `SIMULATED_BLOCKED`
- Olympus activation: `DENIED`
- Production authority: `DENIED`
- Runtime network/HTTP/subprocess/SSH/deployment/production-control imports: none detected

## Root cause

The v1 engine treated required evidence ID presence plus `verified=true` as sufficient and did not enforce the declared `protected_mutations_default_blocked=true` policy. `evt-005` therefore fell through to `allowed = not reasons` despite approval, health, and rollback evidence lacking target binding, provenance/scope, and freshness metadata.

The authority mapping itself was correct: Tier 3 supplied and Tier 3 required. The human denial is supported independently by the declared default-deny protected-mutation policy and unverifiable frozen evidence; it was not accepted merely because it was human-labeled.

## Retained conservative false denial

`evt-012` remains denied because `unregistered_action` has no contract, uses an unknown target identity, supplies no evidence, and has confidence `0.42`. This is explicitly retained as fail-closed behavior; authority was not broadened to force agreement with the human baseline.

## Evidence index

- `reports/FALSE-APPROVAL-ROOT-CAUSE.md`
- `reports/FALSE-APPROVAL-DECISION-TRACE.json`
- `reports/FALSE-APPROVAL-REMEDIATION.md`
- `reports/POST-REMEDIATION-COMPARISON.md`
- `certification/post-remediation-verification.json`
- `certification/post-remediation-test-results.txt`
- `replay/post-remediation-replay-manifest.json`
- `certification/artifact-manifest.json`
- `certification/artifact-manifest.sha256`
- `reports/dashboard.html`
- `ledger/simulated_actions.jsonl`

This certification authorizes no activation, merge, push, deployment, restart, outbound action, or production mutation.

## Live Read-Only Shadow Observation Gate

- Verdict: **LIVE_SHADOW_READY**
- Events observed from live Hermes metadata: **100**
- Export stream: `exporter/live_events.jsonl` (`14320e946a082159ad99c993362a8c5df1c36a6d89d5fc9279ea302c1de881af`)
- Canonical replay ledger: `ledger/live_shadow_decisions.jsonl` (`fe90963d8696e1f8c6934eeecaf5b13b72dc04f9cadc4fd948f7ae7133632730`)
- Two clean replay ledgers byte-identical: **True**
- Unsafe/actionable false approvals: **0**
- Source mutation capability: **none**
- Olympus activation: **DENIED**
- Production authority: **DENIED**

This certification permits only one-way, redacted, read-only observation of Hermes activity metadata into the isolated mock evaluator. It does not certify live governance authority, an autonomous service, direct production observation by Olympus, callbacks, actions, deployment, configuration changes, cron, GitHub access, outbound access, or any upstream influence.

## Olympus Advisory Mode

- Verdict: **ADVISORY_MODE_READY**
- Recommendations: **100**
- Recommendation ledger: `ledger/advisory_recommendations.jsonl` (`177956438fe3c5401eea2f1ed123bd8cfae51e6592c00c5dc75c46c80a1c58ad`)
- Two clean advisory replays byte-identical: **True**
- Human-adjudicated comparisons: **0**; calibration remains explicitly pending
- False approvals introduced: **0**
- Execution capability: **none**
- Callback interface: **none**
- Olympus activation: **DENIED**
- Production authority: **DENIED**

This certification covers recommendation-only processing of the previously certified immutable live-shadow stream. It does not authorize activation, production authority, execution, callback, write access to Hermes, merge, push, deployment, restart, GitHub actions, network actions, configuration changes, cron changes, or runtime behavior changes.

## Decision Quality Certification (Human Adjudication)

- Verdict: **BLOCKED**
- Corpus: **50 unchanged exported events**
- Required scenario classes observable: **1/11** (`expected observations` only)
- Independent human labels: **0**
- Agreement/disagreement/calibration: **unavailable; not fabricated**
- Full regression suite: **49/49 PASS**
- Decision-quality tests: **8/8 PASS**
- Shadow verification: **11/11 PASS**
- Exporter and immutable-stream hashes: **unchanged**
- Two clean corpus replays: **byte-identical**
- Olympus activation: **DENIED**
- Production authority: **DENIED**

The exporter exposes only redacted `hermes.activity.message_observed` metadata under the fixed `read_only_observation` contract. It cannot establish policy evaluation, authority boundary, evidence sufficiency, contract failure, unknown contract, policy conflict, malformed metadata, ambiguity, or expected denial. Redaction was not weakened. This decision-quality blocker does not revoke the prior shadow, live-shadow, or advisory certifications.

Decision-quality artifacts:

- `adjudication/corpus.json`
- `adjudication/reviewer_guide.md`
- `adjudication/review_interface.md`
- `adjudication/reviews.json`
- `reports/decision_quality_dashboard.html`
- `reports/agreement_analysis.md`
- `reports/disagreement_analysis.md`
- `reports/evidence_gap_analysis.md`
- `reports/policy_ambiguity_analysis.md`
- `certification/decision_quality_verification.json`
- `certification/exporter_boundary_audit.md`
- `certification/prior_certifications_summary.md`
- `replay/decision_quality_manifest.json`
