# Hermes Morning Brief v1

Canonical, deterministic, read-only executive dashboard renderer.

## One command

```bash
python3 scripts/morning_brief_v1.py tests/fixtures/morning_brief/healthy_day.json
```

Machine-readable output for a future dashboard API:

```bash
python3 scripts/morning_brief_v1.py tests/fixtures/morning_brief/healthy_day.json --format json
```

## Architecture

`normalized JSON snapshot -> validation/normalization -> deterministic report model -> Markdown or JSON renderer`

The renderer performs no collection. A future collector may create snapshots from reviewed, read-only adapters, but v1 accepts files only. This prevents the presentation layer from contacting DGX hosts, Hermes runtime, GitHub, schedulers, or the network.

## Contract

- `schema_version` and `as_of` are mandatory.
- Missing values render as `UNKNOWN`; they are never inferred.
- Fleet always contains Mac mini, MacBook Pro, Spark 1, and Spark 2 in canonical order.
- Wins sort newest first; other collections use stable documented keys.
- A claimed PASS is downgraded when failures, stale/unknown evidence, approvals, or fleet warnings exist.
- Source paths, observed timestamps, freshness, and evidence references are retained in both formats.

## Synthetic scenarios

- `healthy_day.json`
- `busy_day.json`
- `failure_day.json`
- `everything_blocked.json`
- `no_work_overnight.json`
- `contradictory_evidence.json`
- `stale_evidence.json`
- `unknown_state.json`

Regenerate fixtures deterministically with:

```bash
python3 tests/fixtures/morning_brief/generate_fixtures.py
```

## v1 boundaries

- No live collectors.
- No notification or scheduling integration.
- No approval execution; recommended buttons are display-only.
- No runtime, launchd/systemd, network, or DGX interaction.
- JSON is the stable integration surface for a future dashboard API.
