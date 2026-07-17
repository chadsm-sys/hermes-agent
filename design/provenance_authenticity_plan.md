# Schema v2 R2 — Provenance Authenticity Plan

**Status:** Design plan only. Resolves independent-review finding P2-5 by documenting
the required mechanism and its gate position. Nothing here creates keys, signatures,
or custody infrastructure. This plan is **non-blocking for offline fixture design**
and **mandatory before any live implementation** (Phase 3 boundary certification and
beyond).

## 1. Problem statement

Every digest in `design/digest_domain_specification.md` provides integrity linkage:
tampering with a record or manifest changes recomputed hashes. Hashes do not provide
trusted origin: an adversary who controls the pipeline could regenerate a fully
self-consistent forged corpus, manifest included. Authenticity therefore requires an
anchor outside the pipeline that produced the artifacts.

## 2. Required mechanism

A certification run manifest (and each human-adjudication checkpoint digest,
`design/human_adjudication_store.md` §2) must be anchored by **at least one** of the
following, chosen and approved at the Phase 3 boundary review:

### Option A — controlled custody (baseline)

- The completed run manifest is delivered, at S8 close, into an append-only,
  access-controlled custody store operated by a role with no write access to the
  certification pipeline.
- The custody store records the manifest digest, receipt UTC timestamp, and the
  submitting role, and issues a custody receipt referenced by the certification
  record.
- An independent witness copy of the manifest digest is held by the reviewing
  organization; verdict finalization requires custody receipt and witness digest to
  match the recomputed manifest digest.

### Option B — detached dual-signature manifest (preferred for live runs)

- The run manifest is signed with two detached signatures over its canonical bytes:
  one by the fact-producer role key and one by the assembler role key. A single key
  must never hold both roles.
- Proposed primitive: Ed25519 detached signatures; exact primitive, key custody,
  rotation, and revocation procedures are specified and reviewed at Phase 3, not
  here.
- Public verification keys are published in the review environment's key manifest;
  private keys are managed outside Hermes and outside the certification pipeline.
  No key material, key identifier, or signature ever appears inside a v2 record —
  records remain 18 closed-vocabulary fields, and the privacy surface is unchanged.

Both options may be combined. Fixture-only runs (Phase 2) use custody-lite: the
fixture run manifest digest is recorded in the review record that consumes the
fixtures — sufficient for offline work where the threat is pipeline error rather than
adversarial substitution.

## 3. Verification obligations

- A consumer verifying a live corpus must verify the anchor (custody receipt match or
  signature validity) **before** trusting any manifest-derived list during digest
  recomputation. Anchor failure fails the entire run closed; there is no per-record
  salvage from an unanchored manifest.
- Anchor verification is offline-capable: custody receipts and signatures are static
  artifacts; no network call, callback, or live-system query is introduced.

## 4. Threats closed and threats remaining

- Closed once mandatory: whole-corpus regeneration by a compromised pipeline
  (Option A: custody receipt predates forgery; Option B: forger lacks role keys);
  manifest substitution; advisory-set rewrite with matching manifest.
- Remaining and out of scope here: compromise of both role keys or of the custody
  operator (addressed by separation of duties and key custody review at Phase 3);
  correctness of the facts themselves (addressed by source-independence gates, not by
  authenticity).

## 5. Gate placement

- **Phase 2 (fixture-only):** custody-lite recording. This plan imposes no other
  requirement, so fixture design is not blocked.
- **Phase 3 (producer boundary certification):** this plan must be turned into an
  approved concrete design (option choice, key/custody procedures, revocation,
  audit). Automatic blocker: any design that places key material, signatures, or
  custody references inside v2 records, inside Hermes, or inside the exporter.
- **Phase 4 and later:** every published run must carry a verified anchor; an
  unanchored run is `NOT_AVAILABLE` for certification, never implicitly accepted.
