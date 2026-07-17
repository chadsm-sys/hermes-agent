# Governance Metadata Schema v2 — Security Review

**Review result:** Design is suitable for independent security review; no implementation authority granted.

## Security properties required

- Descriptive metadata is never an authorization artifact.
- Olympus recommendations remain non-executable.
- No field contains a callback, endpoint, resource path, credential, identity, recipient, amount, command, or tool argument.
- Source facts are frozen before recommendation generation.
- V1 exporter and replay remain unchanged.
- Unknown or invalid values fail closed for certification.

## Trust boundaries

1. **Hermes native governance/audit facts:** future source, if separately approved.
2. **Metadata projection:** future producer; read-only and one-way requirements would need new certification.
3. **Immutable v2 sidecar:** certification input.
4. **Olympus advisory evaluator:** consumes facts and emits non-executable category/confidence/uncertainty.
5. **Human review environment:** reads packets, writes only adjudication artifacts outside Hermes.

No boundary may provide an upstream handle into Hermes.

## Field security assessment

- Action/target classes expose no actionable locator.
- Policy/contract/evidence/authority outcomes expose no rule bodies, credentials, or control-plane interfaces.
- Authority fields must carry a normative warning: **NOT AN AUTHORIZATION TOKEN**.
- Recommendation categories must carry a normative warning: **ADVISORY ONLY — NON-EXECUTABLE**.
- Replay/provenance hashes provide integrity linkage but not authenticity. Authenticity requires controlled custody or a separately reviewed signature manifest.

## Abuse cases and controls

| Abuse | Control |
|---|---|
| Treat `within_boundary` as permission | Schema contract forbids actuator consumption; architecture/lint review must verify no execution consumer |
| Treat `allow_simulation_only` as production approval | Distinct enum and UI warning; production targets remain unavailable |
| Forge policy/authority results | Recompute provenance; pin source/taxonomy digests; separate producer from Olympus |
| Transplant valid metadata to another event | Bind provenance to `event_ref` and source snapshot digest |
| Replay stale authority | Authority class is immutable point-in-time certification evidence, never live authorization |
| Enumerate internal policies/contracts | Export statuses only; identifiers prohibited |
| Inject extra fields | `additionalProperties=false` in any future machine schema; strict validation |
| Abuse unknown values to force approval | Under NEW-1, unknown/indeterminate values never permit `allow_simulation_only` or a definitive correctness label; they may coexist with non-authorizing provisional `continue_read_only_observation` only when every NEW-1 Rule 1 predicate holds, otherwise the canonical fail-closed category is required |
| Hide malformed input by dropping it | Under NEW-2, each raw input contributes either one valid record or one namespace-separated quarantine envelope to provenance and replay; no input is repaired, guessed, or omitted |
| Use hashes as bearer capabilities | No consumer accepts replay/provenance IDs for access or execution |

## Separation of duties

`design/fixture_profile_normative_resolutions.md` is the single normative source for NEW-1 and NEW-2. Security prose must not reinterpret `continue_read_only_observation` as an allow category or treat quarantine identifiers as valid-record identifiers.

- Governance fact producer cannot generate or amend human adjudications.
- Olympus cannot amend governance facts or provenance.
- Reviewers cannot modify source facts or recommendations.
- Certification finalizer validates hashes and completeness but cannot reinterpret enums.

## Security acceptance gate

Implementation remains blocked until a future review proves: no new source query selects prohibited fields; one-way read-only access; immutable publication; strict schema validation; no callback/network/actuator path; independent fact provenance; no production consumer; downgrade rejection; and full regression/replay recertification.