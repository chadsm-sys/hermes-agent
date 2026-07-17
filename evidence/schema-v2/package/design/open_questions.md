# Governance Metadata Schema v2 — Open Questions

These questions must be resolved before implementation approval.

## Source availability and independence

1. Do typed action, target, policy, contract, evidence, and authority facts already exist independently of message content and Olympus?
2. Which component owns each fact, and can it attest the value without exporting prohibited data?
3. Can source facts be frozen before Olympus recommendation generation?
4. How will controlled custody or authenticity be proven without introducing credential/key exposure?

## Taxonomy

5. Are the proposed action and target classes coarse enough for privacy but precise enough for safety adjudication?
6. Should `family_or_calendar_commitment` be merged into `external_system` in event-level records, not only reports?
7. Is Tier 0–3 already a stable independent authority taxonomy, or does it require a versioned mapping?
8. Should policy conflict be tri-state JSON (`true|false|"unknown"`) or an all-string enum for simpler canonicalization?
9. Is one primary uncertainty reason enough, or is a bounded ordered set necessary?

## Privacy and retention

10. What is the event-level retention and challenge-window duration?
11. Who may access action/target/authority combinations?
12. Is minimum aggregate cell size 5 sufficient for this corpus?
13. Must replay/provenance hashes be redacted in external reports?
14. Is event reference reuse across v1/v2 acceptable under current privacy policy?

## Replay and provenance

15. What exact canonicalization profile and validation error order will be normative?
16. Which taxonomy, policy-set, contract-registry, and authority-mapping digests enter provenance?
17. Should provenance authenticity use controlled custody only or a separately designed signature manifest?
18. How are partial batches, retries, and duplicate sidecars represented without timestamps?

## Review workflow

19. Which reviewer qualifications are required for clinical, financial, family, identity, and production-protected classes?
20. Must review be double-blind or dual-review for high-risk classes?
21. What minimum events per class and confidence bucket establish readiness?
22. How are reviewer disagreements adjudicated without revealing source content?

## Compatibility

23. What media type/path names prevent v1/v2 consumer confusion?
24. Is `v2.1` allowed to add fields, or should every field-set change require v3?
25. How long must old v2 profiles remain replayable?

## Stop conditions

Any answer requiring prompts, message content, reasoning, tool arguments, raw identities/targets, credentials, secrets, an execution path, or weakening the v1 boundary makes the proposal `BLOCKED` until a safer alternative is found.