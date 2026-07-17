# Olympus → Hermes Shadow Governance Mock Workspace

**Boundary:** `/Users/macmini/Hermes-Handoff/mock-workspaces/olympus-shadow-governance-20260717`

This directory is the only writable scope for this mock execution project.

## Hard prohibitions

- No Olympus activation or production authority.
- No writes to Hermes, Olympus, Mission Control, Ledger, profile, service, cron, Git, or runtime paths.
- No network, subprocess, shell, launchd, gateway, messaging, email, calendar, payment, browser, deployment, push, merge, or restart effects.
- No import of production modules that perform initialization writes.
- Inputs are immutable JSON/JSONL snapshots copied or generated inside this workspace.
- Every proposed external effect is routed through `SimulationSink`, which only appends structured records beneath this workspace.

`mode` is permanently `shadow`; configuration validation rejects every other value.
