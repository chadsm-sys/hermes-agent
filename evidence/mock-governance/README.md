# Olympus → Hermes Shadow Governance

A local-only, deterministic, contract-driven environment for evaluating what Olympus **would** decide without granting it production authority or executing any real-world effect.

## Run

From this workspace:

```bash
python3 -m shadow_governance.cli run --workspace "$PWD" --events inputs/realistic_hermes_events.jsonl --contracts inputs/contracts.json
```

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Outputs

- `ledger/simulated_actions.jsonl` — complete structured decision ledger
- `reports/execution_timeline.json` — eight-stage event-to-result timeline
- `reports/governance_report.json` / `.md` — metrics and health
- `reports/dashboard.html` — static dashboard
- `reports/human_vs_olympus.json` — matches, disagreements, false approvals/denials
- `replay/replay_manifest.json` — input hash and two deterministic decision digests
- `certification/CERTIFICATION_PACKET.json` / `.md` — readiness, gaps, recommendations

## Safety

- Permanently shadow-only.
- No activation, authority enablement, network, subprocess, Git, cron, launchd, gateway, credential, browser, message, payment, or deployment adapters.
- No writes outside the declared workspace.
- Production mutation proposals can only become simulated ledger entries.

See `docs/ARCHITECTURE.md` and `docs/THREAT_MODEL.md`.
