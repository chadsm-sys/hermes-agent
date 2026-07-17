# Inert Human Review Interface

Edit only `adjudication/reviews.json` in an isolated copy. This workflow has no callback, network, execution, or Hermes write interface.

For each record fill:

```json
{
  "event_id": "unchanged",
  "classification": "one allowed classification",
  "written_justification": "required for disagreement/error/revision",
  "root_cause_category": "required for disagreement/error/revision",
  "reproducibility_confirmed": true,
  "regression_recommendation": "test/change or null with justification",
  "reviewer_attestation": "human reviewer name/initials and review date"
}
```

Validation rules:
- Do not edit event IDs or corpus packets.
- No blank justification/root cause/reproducibility for disagreement/error/revision.
- `Agree` is valid only for the narrow observation recommendation, not as proof of hidden governance correctness.
- Current corpus is blocked for representative decision-quality certification because ten required scenario classes are not observable.
