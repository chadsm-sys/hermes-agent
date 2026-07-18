# Olympus Authority Model Proposal V2 — Risk Register

- **Date (UTC):** 2026-07-18
- **Companion to:** `AUTHORITY-V2-INDEPENDENT-REVIEW.md` (verdict `BLOCKED`)
- **Scope note:** the V2 package itself was not obtainable in the review
  environment (review §3–§4). Risks below therefore concern the *process
  state as it exists today* — the risks that materialize if a founding
  authority decision proceeds from the current evidence posture. Risks
  internal to the package's design could not be enumerated and are
  explicitly **not covered**; their absence here is not evidence of their
  absence in the package.

Severity: CRITICAL / HIGH / MEDIUM / LOW.
Likelihood: judged for the scenario "a founding decision is attempted
without first meeting the unblock conditions."

---

## R-01 — Founding decision on an unreviewable basis

- **Severity:** CRITICAL · **Likelihood:** certain (in the above scenario)
- **Description:** The proposal that would ground all downstream authority
  exists, for any independent party, only as a narrative claim. A founding
  decision taken now would rest on documents no independent reviewer can
  demonstrate to have read.
- **Mandated-search-target mapping:** implicit authority; missing
  fail-closed behavior.
- **Mitigation:** publish the package to an accessible surface, bound to a
  commit SHA and `SHA256SUMS` manifest, before any decision (review §9).

## R-02 — Self-certification laundering via reported test totals

- **Severity:** CRITICAL · **Likelihood:** high
- **Description:** "34/34 consistency checks PASS, 9/9 negative tests
  PASS" originates inside the proposal lane and is relayed by narration.
  If these totals influence the founding decision, the lane will have
  self-certified — the precise failure mode item 6 of the review scope
  exists to prevent. Passing counts also say nothing about check
  *adequacy*: a package can pass 34/34 of its own checks and still be
  circular.
- **Mapping:** self-certification; circular bootstrap.
- **Mitigation:** ship the validation suite inside the sealed package;
  independent re-execution replaces reported totals.

## R-03 — Package substitution / TOCTOU between review and adoption

- **Severity:** HIGH · **Likelihood:** medium
- **Description:** With no digest binding, nothing ties "the V2 that was
  reviewed" to "the V2 that gets adopted." Any later edit — innocent or
  not — inherits whatever approval the review is remembered as having
  granted.
- **Mapping:** replay attacks; unsigned template promotion; stale
  authority.
- **Mitigation:** digest-bound commissioning (review §9.2); adoption
  records must quote the reviewed digest.

## R-04 — Misuse of this review record as approval

- **Severity:** HIGH · **Likelihood:** medium
- **Description:** Governance lanes accrete records, and records get
  cited. A future operator could cite "the 2026-07-18 independent review"
  as if it had examined the package. The lane's own history shows exactly
  this hazard (the lost Schema V2 review had to be formally recorded as
  `UNESTABLISHED` to stop later quotations being promoted into an original
  artifact).
- **Mapping:** implied authority; authority ambiguity.
- **Mitigation:** the review record states in terminal language that it
  reviewed no package contents and must not be cited as if it had
  (review §9).

## R-05 — "V2" designator collision across the estate

- **Severity:** HIGH · **Likelihood:** high
- **Description:** Three unrelated artifacts now answer to "V2": Schema V2
  (governance metadata schema, `67cc8a13…`), Olympus v2 (reference
  architecture research appendix, 2026-07-07), and the Authority Model
  Proposal V2. Unqualified "V2" references in future records can misdirect
  reviewers, operators, or ceremony tooling to the wrong artifact.
- **Mapping:** conflicting terminology; authority ambiguity.
- **Mitigation:** every future record naming the proposal should use the
  full designator plus package digest, never bare "V2."

## R-06 — Single-machine custody of canonical evidence

- **Severity:** HIGH · **Likelihood:** high (standing condition)
- **Description:** The sealed RC4 evidence, `CURRENT-RELEASE.md` pointer,
  canonical ledger, and (presumably) the V2 package live only on the
  operator's machine; the repository holds digests. Independent review,
  off-box integrity comparison (the still-open W3 step 4 in the adjacent
  GBR lane), and disaster recovery all depend on artifacts one hardware
  failure or one compromise can silently alter or destroy.
- **Mapping:** stale authority; missing fail-closed behavior.
- **Mitigation:** off-box, digest-verified copies of every artifact that a
  founding decision will rely on, established *before* the decision.

## R-07 — Replay / staleness of this review

- **Severity:** MEDIUM · **Likelihood:** medium
- **Description:** If the package is later published, this `BLOCKED`
  verdict describes a superseded world-state. Conversely, if quoted after
  publication it could falsely suggest the package is still missing.
  Reviews, like authority requests, go stale.
- **Mapping:** replay attacks; stale authority.
- **Mitigation:** this register and review are dated and bound to repo
  state `51bb3887…` + the 2026-07-18 branch snapshot; any re-commissioned
  review supersedes them for all purposes.

## R-08 — Commissioning-channel trust

- **Severity:** MEDIUM · **Likelihood:** low
- **Description:** The review mandate itself (including the claim "V2
  proposal package exists") arrived over the same untrusted narrative
  channel the mandate instructs the reviewer to distrust. A forged or
  mistaken commissioning could induce reviews of phantom artifacts or,
  worse, induce "reviews" that legitimize them.
- **Mapping:** self-authentication; implied authority.
- **Mitigation:** treat commissioning statements as claims (this review
  did); require commissioning records to carry artifact digests so the
  claim is testable.

---

## Residual-risk statement

Even after all mitigations above, the *content-level* risks of the V2
authority model (circular bootstrap in its root-of-trust construction,
privilege inheritance in its delegation rules, lifecycle contradictions,
emergency-power abuse paths, etc.) remain **unassessed**. They can only be
retired by the re-commissioned, digest-bound independent review described
in review §9.
