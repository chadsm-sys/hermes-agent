# Governance Metadata Schema v2 — Data Minimization

## Minimum-necessary test

A field is included only if removing it would prevent at least one required certification judgment: scenario classification, policy/contract/evidence/authority correctness, malformed-input handling, recommendation classification, uncertainty/calibration, provenance, or deterministic replay.

## Included minimum

| Need | Minimum representation |
|---|---|
| Scenario type | Coarse action class |
| Target risk boundary | Coarse target class |
| Policy outcome/ambiguity | Result plus tri-state conflict |
| Contract integrity | Resolution status |
| Evidence gap | Aggregate sufficiency |
| Authority boundary | Requested tier, available tier, decision |
| Malformed input | Bounded validation status |
| Recommendation | Closed category |
| Calibration | Confidence bucket |
| Uncertainty diagnosis | One bounded primary reason |
| Event binding | Existing opaque event reference |
| Fact integrity | Provenance digest |
| Run reproducibility | Replay digest |

## Excluded

- Message content, prompts, reasoning, rationale text
- Tool names, tool arguments, commands, payloads, outputs
- User, session, chat, thread, platform-message, account, approver, or recipient identities
- Paths, URLs, hostnames, resource IDs, calendar titles, contact data, amounts
- Credentials, tokens, secrets, API keys, entitlements
- Exact policy/contract identifiers or rule text
- Evidence names, values, documents, or sources
- Raw confidence float and model internals
- Human labels from the event stream
- Runtime latency and nondeterministic timestamps

## Why all Required fields remain necessary

- Removing action or target class prevents representative risk sampling.
- Removing policy result/conflict prevents ambiguity and policy-correctness review.
- Removing contract status prevents unknown/failed contract cases.
- Removing evidence sufficiency conflates evidence gaps with policy/authority defects.
- Removing any authority field prevents requested-versus-available comparison or independent result validation.
- Removing schema status hides malformed input behavior.
- Removing recommendation/category/confidence/uncertainty prevents the thing being certified or its calibration from being measured.
- Removing event/provenance/replay identifiers permits substitution and destroys reproducibility.

## Recommended/optional extensions

No extension is included in the minimum v2 record. A future reviewed profile may add a bounded `evidence_gap_category` because it improves remediation, but only after privacy review. Exact evidence types remain prohibited.

## Retention and reporting

- Event-level records: retain only through certification and challenge window.
- Aggregate reports: suppress cells below 5 and omit event references.
- Deletion: use a separately approved reversible-to-final process with manifest confirmation.
- Reuse: prohibited outside governance certification and defect remediation.

## Stop condition

If any required enum cannot be sourced without exporting or persisting prohibited data, leave it `unknown` for design fixtures and block real certification. Do not increase collection granularity to avoid a blocked result.