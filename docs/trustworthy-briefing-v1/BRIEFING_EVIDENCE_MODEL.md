# Briefing Evidence Model

## Source assessment

Each manifest source declares purpose, owner, retrieval method, required/optional status, freshness threshold, failure behavior, evidence class, fallback, and authority.

At collection, every source becomes one of:

- `FRESH`: successfully collected inside its threshold.
- `STALE`: collected timestamp exceeds its threshold.
- `MISSING`: no observation exists.
- `UNAVAILABLE`: retrieval failed or content could not be read.
- `UNKNOWN`: timestamp or structure cannot support an assessment.

Any required source not `FRESH` makes the brief RED and makes recommendations untrustworthy. Optional non-fresh sources make a fully covered brief YELLOW and suppress claims dependent on those sources.

## Evidence classes

- `DOCUMENTED`: a document or artifact says something; it is not runtime proof.
- `RUNTIME_OBSERVED`: collected from current runtime/state.
- `TEST_VERIFIED`: established by a current explicit test or readiness gate.
- `PHYSICALLY_VERIFIED`: verified through a recorded physical inspection.
- `INFERRED`: reasoned conclusion from evidence; never presented as direct observation.
- `UNKNOWN`: evidence cannot support a stronger classification.

The renderer never upgrades an evidence class. An artifact PASS remains DOCUMENTED unless a separate runtime source establishes current behavior.

## Item envelope

Every rendered or suppressed item carries in the machine report:

- source name and source location;
- collection timestamp and freshness state;
- evidence class and confidence;
- contradiction flag;
- operator relevance and urgency;
- consequence, recommendation, reversibility, and whether Chad is required;
- autonomy classification;
- owner, age, next checkpoint;
- suppression reason when omitted.

## Contradictions

Only fresh authoritative sources participate in claim comparison. Conflicting values for the same claim are listed verbatim by source. They are never averaged or silently resolved. A contradiction forces RED and `NO TRUSTWORTHY RECOMMENDATION`.

## Recommendation eligibility

A recommendation is trustworthy only when:

1. all required sources are fresh;
2. no fresh authoritative claims contradict;
3. operator readiness does not explicitly report RED/FAIL/BLOCKED; and
4. the proposed gate carries an explicit consequence and recommendation from its source packet.

PR merge advice has an additional invariant: a recommendation containing “merge” is replaced with neutral review guidance unless `merge_evidence_current=true` is present.
