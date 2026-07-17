# Olympus Decision Quality Reviewer Guide

## Scope
Judge recommendation quality only from each curated packet. Do not seek message content, tool arguments, reasoning, secrets, or any data outside the certified exporter boundary.

## Required workflow
1. Verify `adjudication/corpus.json` and its source-stream hash.
2. Review normalized metadata, evidence, contracts, policies, authority context, confidence inputs, recommendation, and rationale.
3. Choose exactly one: `Agree`, `Disagree`, `Insufficient Evidence`, `Policy Ambiguity`, `Human Error`, `Olympus Error`, or `Needs Governance Revision`.
4. For every `Disagree`, `Human Error`, `Olympus Error`, or `Needs Governance Revision`, provide written justification, root-cause category, reproducibility confirmation, and a regression recommendation when appropriate.
5. Never infer hidden semantic activity from role, source, tool-activity, or opaque identifiers.

## Certification stop rule
The corpus contains only redacted `hermes.activity.message_observed` events mapped to the fixed `read_only_observation` contract. It cannot establish whether underlying activity represented policy evaluation, authority boundary, missing evidence, ambiguity, contract failure, unknown contract, policy conflict, malformed metadata, or expected denial. Mark those judgments `Insufficient Evidence`; do not weaken redaction to resolve them.

## Independence
Reviewer identity/attestation is required before labels count. Unattested or prefilled labels are not human adjudication.
