# Olympus Authority Model Proposal V2 — Constitutional Analysis

- **Date (UTC):** 2026-07-18
- **Companion to:** `AUTHORITY-V2-INDEPENDENT-REVIEW.md` (verdict `BLOCKED`)
  and `AUTHORITY-V2-RISK-REGISTER.md`
- **Method:** the constitutional standard below is reconstructed
  independently from durable, repo-resident governance records — not from
  the V2 proposal (unobtainable, review §3–§4) and not from any prior
  review of it (mandate: do not rely on prior reviews).

---

## 1. Sources for the constitutional standard

Read directly for this analysis, all treated as untrusted inputs whose
*principles* were evaluated on their merits:

- `docs/olympus/audit-records/2026-07-17/CURRENT-RELEASE.md`,
  `SUPERSESSION-NOTICE.md`, `AUDIT-RECORD-INDEX.md` and
  `…/2026-07-18/RT02-ARCHIVAL-AND-PREFLIGHT.md`
  (branch `remediation/olympus-audit-records-20260717`)
- `review/schema-v2-independent-review-20260717/LOST-REVIEW-RECORD.md`
  (same branch)
- The Schema V2 / R2 attestation and review chain
  (branches `review/olympus-schema-v2-package-20260717`,
  `design/olympus-schema-v2-r2-20260717`)
- Olympus v1 governance PRs #16–#21 (review-only boundaries, attested
  bases, drift rules)

## 2. The constitutional standard for a founding authority basis

From these records, the estate's own operating constitution is
reconstructable as eight requirements. Any package proposed as the basis
for a *founding* authority decision must satisfy all of them, because the
founding decision is the one act with no upstream authority to correct it.

1. **Identified, sealed subject.** Authority acts bind to exact bytes:
   a directory sealed by `SHA256SUMS`, referenced by manifest digest, or a
   package bound to an exact commit SHA. (RC4 is referenced everywhere by
   `e9b9c0ec…`; the lost review binds to `67cc8a13…`.)
2. **Externally rooted legitimacy.** Every grant of authority must trace
   to a root outside the thing being authorized — in this estate, the
   explicit human operator. Narrative, chat transcripts, and certification
   prose are expressly *not* authority ("Certification and chat narrative
   are not ceremony authority," `CURRENT-RELEASE.md`).
3. **Independence of review from authorship.** Review verdicts count only
   when produced organizationally outside the lane that produced the
   artifact; a review that cannot be established is recorded as
   `UNESTABLISHED` and redone, never reconstructed from the authoring
   side's memory (`LOST-REVIEW-RECORD.md`).
4. **Stage separation.** Evidence, review, certification, release,
   adoption, and activation are distinct records with distinct authority
   bases; possession of one confers none of the others ("A VERIFIED
   WebAuthn receipt is approval evidence only — it is not GBR adoption and
   grants no REB, PCE, EER, activation-window… authority").
5. **Fail-closed defaults.** Ambiguity, residue, or unverifiable state
   halts the process (RC4 preflight fail-closing on a stale `/tmp`
   request; NOT-GO until off-box comparison and explicit authorization).
6. **Anti-replay and expiry.** Requests expire; expired artifacts are
   archived under explicit authority with tombstones and must never be
   reused; replay stores are append-only and byte-checked.
7. **Explicit supersession.** Old candidates are never silently retired —
   they are enumerated, marked SUPERSEDED/FORBIDDEN, and preserved
   unchanged as history.
8. **Single control plane.** Exactly one authorized path may perform a
   governed act; parallel or historical paths are forbidden by name
   (RT-15 resolution).

This standard is itself the correct yardstick for the twelve scope
questions: a V2 authority model that satisfies all eight cannot contain
circular bootstrap, self-certification, implied authority, or fail-open
defaults.

## 3. Application to the present state

### 3.1 The threshold question is dispositive

Requirement 1 fails at the threshold: **there is no identified, sealed
subject.** No commit, branch, PR, manifest, or digest names the V2
package; the review environment contains no bytes to seal a conclusion to.
Requirements 2–8 cannot even be tested against the package, because
testing them requires reading it.

Constitutionally, this is not a gap the reviewer may bridge with
diligence-by-narration. Under requirement 2, treating the commissioning
statement's description of V2 ("eliminates circular authority", "34/34
PASS") as evidence would convert narrative into authority — the exact
self-authentication pathway the scope forbids. Under requirement 5, the
only lawful disposition is to fail closed.

### 3.2 The internal-validation claim, examined constitutionally

Even taken at face value, "34/34 consistency checks PASS, 9/9 negative
tests PASS" could not carry a founding decision:

- It is *internal* validation — requirement 3 makes it non-probative for
  certification purposes regardless of its truth.
- Consistency checks verify a package against itself. A perfectly
  self-consistent authority model can still be circular; circularity is a
  property proved against *external* roots (requirement 2), which no
  internal check can establish.
- Negative tests demonstrate the checker rejects nine known-bad inputs.
  They bound nothing about unknown-bad inputs, and the checker itself is
  part of the untrusted package.

### 3.3 The founding decision as constitutional singularity

A founding authority decision is the one point where requirement 2 cannot
be satisfied by prior authority, because none exists yet. The estate's
records already model the correct resolution: legitimacy at the root comes
from (a) the explicit, identified human operator, and (b) maximal
*evidentiary* discipline substituting for the missing *authoritative*
chain — sealed bytes, independent review bound to those bytes, off-box
verification, explicit written authorization scoped to the single act.
The current V2 posture inverts this: at exactly the point demanding the
most evidence, the package is the least evidenced artifact in the estate —
less evidenced than RC4, less than Schema V2, less even than the rejected
RC3, all of which have manifests and repo-resident records.

### 3.4 Ambient constitutional observations (independent of the package)

Two conditions in the surrounding state would undermine even a perfect V2
and should be resolved before any founding decision:

- **Designator ambiguity.** "V2" is now overloaded across three artifacts
  (risk R-05). Founding-decision records must use fully qualified names
  plus digests, or future operators inherit an ambiguity about *which
  constitution they adopted*.
- **Single-custody evidence.** All canonical artifacts live on one
  machine (risk R-06). A founding decision whose basis can be silently
  altered post-hoc fails requirement 6 (anti-replay) prospectively: there
  would be no independent way to prove, later, what was adopted.

## 4. Answers to the twelve scope questions, stated constitutionally

| # | Question | Constitutional answer |
|---|---|---|
| 1 | Circular authority eliminated? | Unprovable without the package; the only *available* authority chain for V2 (its own reported validation) is itself circular. |
| 2 | Only legitimate constitutional roots? | Unprovable; the standard requires roots outside the package (§2.2), and no root is currently in evidence. |
| 3 | Privilege escalation prevented? | Not establishable. |
| 4 | Self-authentication prevented? | Not establishable for the package; the *commissioning posture* invites self-authentication by narration (§3.1) and was refused. |
| 5 | Self-appointment prevented? | Not establishable. |
| 6 | Self-certification prevented? | Not establishable for the package; the surrounding process is presently *relying* on self-certification (§3.2). |
| 7 | Implied authority prevented? | Not establishable; this review record itself is written to prevent one known implied-authority path (risk R-04). |
| 8 | Stage separation preserved? | Not establishable; the standard it must meet is §2.4. |
| 9 | Replay/expiry/revocation/supersession/delegation/emergency handled? | Not establishable; the standard is §2.6–§2.7, and the adjacent lane demonstrates compliant handling the package must match. |
| 10 | Internal consistency across documents? | Not establishable — the document set could not be enumerated. |
| 11 | Hidden governance ambiguity introduced? | One ambiguity exists *around* the package already: the V2 designator collision (§3.4). |
| 12 | Safe interpretation without unwritten assumptions? | **No, as currently evidenced** — today, *everything* about V2 is an unwritten assumption from the standpoint of any future operator reading the durable record. |

## 5. Constitutional conclusion

The proposal was to be assumed incorrect until proven otherwise. Proof
requires evidence; evidence requires access; access does not exist. The
eight-requirement standard in §2 is not satisfiable in the current
posture, and requirements 2, 3, and 5 affirmatively forbid the available
substitutes (narrated contents, internal test totals, benefit of the
doubt).

The verdict `BLOCKED` recorded in `AUTHORITY-V2-INDEPENDENT-REVIEW.md`
follows necessarily. It is a statement about the evidence posture, not
about the package's merits, and it dissolves — in favor of a fresh,
digest-bound review — the moment the unblock conditions (review §9) are
met.

This analysis authorizes nothing, certifies nothing, and must not be
cited as an assessment of the V2 package's contents.
