# Olympus Governance Metadata Schema v2 Package Attestation

## Package identity

- Source workspace: `/Users/macmini/Hermes-Handoff/mock-workspaces/olympus-shadow-governance-20260717`
- Destination repository: `https://github.com/chadsm-sys/hermes-agent.git`
- Branch: `review/olympus-schema-v2-package-20260717`
- Base commit: `51bb38871a8159da18ab8c3df603e6be6cbd4798`
- Package commit: **SELF** — the Git commit containing this attestation. Resolve after checkout with `git rev-parse HEAD`. A literal self-referential commit SHA cannot be embedded in the commit whose SHA it determines; the published commit SHA is recorded in the delivery report and remote branch ref.
- Attested UTC: `2026-07-17T19:15:26Z`

## Source and destination verification

All 12 source artifacts existed before copying. Each destination artifact was copied without rewriting, normalization, regeneration, or content improvement. `cmp -s` returned success for every source/destination pair.

| Relative path | Source SHA-256 | Destination SHA-256 | Byte comparison |
|---|---|---|---|
| `design/abuse_replay_review.md` | `b9c41c6f759128596697e91891f6dc3ccce13a1ed33ec057c18a0ca1e9410374` | `b9c41c6f759128596697e91891f6dc3ccce13a1ed33ec057c18a0ca1e9410374` | PASS |
| `design/backward_compatibility.md` | `ef31a32455fa1bb62d0b1726a4662aaacf75bff131f0763a4104924c69cd3e82` | `ef31a32455fa1bb62d0b1726a4662aaacf75bff131f0763a4104924c69cd3e82` | PASS |
| `design/certification_rationale.md` | `53107472f2bcd06b2b1201adc6fcc00bc650bd424ca6f5afff4efaa4c47b5d75` | `53107472f2bcd06b2b1201adc6fcc00bc650bd424ca6f5afff4efaa4c47b5d75` | PASS |
| `design/data_minimization.md` | `dc4d6f4c3dc212166f74cecf585ce0f6f3bb7ce83e21b40e130b144f24907beb` | `dc4d6f4c3dc212166f74cecf585ce0f6f3bb7ce83e21b40e130b144f24907beb` | PASS |
| `design/governance_metadata_schema_v2.md` | `de539baca478b885b518cc42e8d6c161494391888561e3b90fe89629c9a85ee5` | `de539baca478b885b518cc42e8d6c161494391888561e3b90fe89629c9a85ee5` | PASS |
| `design/open_questions.md` | `5cd54c513a5ff2ca26c4a5d61e65ca899e7a29291517b09bc4f763b89f9c251f` | `5cd54c513a5ff2ca26c4a5d61e65ca899e7a29291517b09bc4f763b89f9c251f` | PASS |
| `design/privacy_review.md` | `4f43c5c8b3c2b090650622bd17be177008c4e8c30616ed42e299813c8153401a` | `4f43c5c8b3c2b090650622bd17be177008c4e8c30616ed42e299813c8153401a` | PASS |
| `design/schema_diff_v1_to_v2.md` | `0418a2a4dfa42f2109f8b946d1347c7b38a01e641744f5718aa361ed91dffd62` | `0418a2a4dfa42f2109f8b946d1347c7b38a01e641744f5718aa361ed91dffd62` | PASS |
| `design/security_review.md` | `b9c2897a75c63048d790e5bbdf63399925c0d838873e615714d988b6581863f9` | `b9c2897a75c63048d790e5bbdf63399925c0d838873e615714d988b6581863f9` | PASS |
| `design/threat_model.md` | `b92efb6345d30d31105f95bca9dc9fdcf262003d5c06091e190ead0abd058660` | `b92efb6345d30d31105f95bca9dc9fdcf262003d5c06091e190ead0abd058660` | PASS |
| `review/approval_gate.md` | `48833c93d8094924c098d266b0058caa0cb71dc57bf247ac3e3c8d06acd8eb1d` | `48833c93d8094924c098d266b0058caa0cb71dc57bf247ac3e3c8d06acd8eb1d` | PASS |
| `review/reviewer_checklist.md` | `b5647fefe0fc80280a3bdb1016c1533f641c63083c9e3df0258b49ca23fe03f3` | `b5647fefe0fc80280a3bdb1016c1533f641c63083c9e3df0258b49ca23fe03f3` | PASS |

The destination manifest validates with:

```bash
shasum -a 256 -c review/schema-v2-file-manifest.sha256
```

## Manifest and combined ledger

Canonical manifest-generation command:

```bash
(
  cd "$PACKAGE_ROOT"
  shasum -a 256 \
    design/abuse_replay_review.md \
    design/backward_compatibility.md \
    design/certification_rationale.md \
    design/data_minimization.md \
    design/governance_metadata_schema_v2.md \
    design/open_questions.md \
    design/privacy_review.md \
    design/schema_diff_v1_to_v2.md \
    design/security_review.md \
    design/threat_model.md \
    review/approval_gate.md \
    review/reviewer_checklist.md \
  | LC_ALL=C sort -k2,2
) > review/schema-v2-file-manifest.sha256
```

Combined-ledger verification command:

```bash
shasum -a 256 review/schema-v2-file-manifest.sha256
```

Result: `83fb892ce28354ec32a7899d8f1ae9885cd01a21add0e823feae1ff276c6b3ff` — **REPRODUCED**.

The earlier report described an "ordered deliverable ledger" but did not document the exact generation command. Compatibility was verified against the displayed lexicographic path order and conventional `shasum` ledger serialization; the canonical command above reproduces the reported combined hash. This attestation does not claim that the command itself was previously documented.

## Discrepancies and path drift

- Path drift: **none**. All 12 source-relative paths were preserved at the repository root.
- Byte discrepancies: **none**.
- Hash-report discrepancy: the earlier human-readable report showed `review/approval_gate.md` as `48833c93d8094924c098d266b0058caa0cb71dc57bf247ac3e3c8d06acd8eb1`, which is only 63 hexadecimal characters. The immutable source file and reproduced combined ledger establish the valid SHA-256 as `48833c93d8094924c098d266b0058caa0cb71dc57bf247ac3e3c8d06acd8eb1d`. No source or destination artifact was altered to resolve this reporting typo.

## Validation-gate result

- Twelve-file existence check: **PASS**.
- Manifest verification: **PASS** (`12/12`).
- Source/destination byte comparison: **PASS** (`12/12`).
- Ordered combined-ledger reproduction: **PASS**.
- Changed-path scope check: **PASS** (`14/14` authorized paths only).
- `git diff --cached --check`: **FAIL**. Git reports 16 pre-existing trailing-whitespace findings in three immutable source artifacts: `design/governance_metadata_schema_v2.md` (2), `design/threat_model.md` (11), and `review/approval_gate.md` (3).

The files were not normalized or corrected because doing so would violate the immutable-source and byte-identity requirements. Because every validation gate did not pass, remote publication is withheld even though repository authentication is available.

## Scope attestation

The branch adds only:

1. The 12 immutable design/review artifacts.
2. `review/schema-v2-file-manifest.sha256`.
3. This attestation.

No exporter, Hermes runtime, policy, contract, production, replay, implementation, authority, activation, deployment, or dependency files are changed. No dependencies were installed. Olympus remains inactive and no production authority is granted.
