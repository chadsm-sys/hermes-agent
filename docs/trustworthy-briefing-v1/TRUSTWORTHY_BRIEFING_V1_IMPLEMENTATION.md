# Trustworthy Briefing v1 Implementation

## Change set

- `scripts/trustworthy_briefing_v1.py`: standalone read-only collector, evidence evaluator, decision consolidator, suppression engine, Markdown renderer, and optional machine-report writer.
- `config/BRIEF_SOURCE_MANIFEST.yaml`: canonical briefing source contract.
- `tests/test_trustworthy_briefing_v1.py`: focused fail-closed and rendering tests.
- `docs/trustworthy-briefing-v1/`: audit, evidence model, rules, examples, test report, rollback, and closeout.

## Why standalone

The production generator is a standalone local script, not a Hermes core module. Packaging V1 as one repository-tracked script is the smallest reviewable change and follows the repository doctrine to avoid a new core model tool. It introduces no daemon, database, plugin, dashboard, scheduler, or delivery path.

## Read-only collection

- Gateway: current loopback HTTP health probe.
- Readiness/cron/action/optional packets: JSON reads.
- Kanban: copies each board DB plus WAL/SHM siblings into a temporary directory, then queries the copy read-only. Production DB files are not opened for mutation.
- Missing and parse failures become structured unavailable observations.

## Outputs

- stdout: Telegram-compatible compact Markdown; no table rendering dependency.
- optional `--report-json`: full source/item/suppression audit envelope.
- no send operation is implemented in the script.

## Proposed controlled deployment (not executed)

After PR review and separate deployment approval:

1. Back up `/Users/macmini/.hermes/scripts/daily_command_center.py` with timestamp and checksum.
2. Copy the reviewed script and manifest to an operator-approved immutable/local config path.
3. Run direct local generation with output redirected to a scratch file.
4. Compare source coverage and output against the acceptance report.
5. Perform one explicitly approved Telegram test-fire through the existing cron job.
6. Do not alter the existing schedule or delivery target.
7. Retain the prior script until the controlled observation window passes.

## Explicit non-changes

No production script, config, schedule, Telegram route, service, launchd item, network/Tailscale setting, Mission Control file, tmux state, or production datum was changed.
