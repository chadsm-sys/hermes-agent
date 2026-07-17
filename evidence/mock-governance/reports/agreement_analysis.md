# Agreement Analysis

**Status: BLOCKED**

Agreement and disagreement rates are `null`: zero events have a valid independent human outcome, and the exported stream does not reveal the governance decision being evaluated. Treating agreement with `CONTINUE_READ_ONLY_OBSERVATION` as governance correctness would be circular.

## Information missing
- Requested governance action/decision class (needed to distinguish observation from denial, policy, authority, and contract cases).
- Policy evaluation result and conflict indicators (needed to identify applicable/conflicting policies and ambiguity).
- Contract resolution status, including unknown/failed contract indicators (needed to judge contract recommendations).
- Evidence sufficiency outcome or typed missing-evidence indicators (needed to assess evidence gaps without viewing payloads).
- Authority requirement versus supplied authority and boundary-result indicator (needed to assess authority disagreements).
- Metadata/schema validation outcome (needed to identify malformed metadata).
- Human operator disposition or independently curated expected outcome (needed for agreement and calibration).

No recommendation is made to expose message content, tool arguments, reasoning, secrets, or identifiers.
