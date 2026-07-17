# Defect Reproduction Report

Date: 2026-07-17
Source candidate: `baf98f1c7faa802aa401c43ff0cd874001790211`
Component baseline: `2b828e3cc20deb7437f89c6c651a2c778e6b6a81`

All reproductions used temporary test databases or stores under the repository test wrapper's isolated temporary home. No live Hermes data or service was read or written by a defect test.

## Memorygraph exclusive claims

The red run covered four independent behaviors and finished with 46 passing tests and four failures:

- Two synchronized `GraphStore` connections both inserted an active exclusive `employer` claim. Expected one create plus one database rejection; observed two creates.
- After two exclusive claims were marked `contradicted`, a later exclusive claim was returned as `created` because conflict discovery queried only `active` rows.
- Given a legacy active exclusive claim beside a contradicted group, `resolve_contradiction()` reactivated its winner without superseding the active claim, leaving two active values.
- Connection policy reported `journal_mode=delete` instead of `wal`.

A separate upgrade reproduction created the legacy duplicate-active state, closed the database, and reopened it. Before the compatibility repair, index creation raised `sqlite3.IntegrityError: UNIQUE constraint failed: claims.entity_id, claims.attribute`.

## Opportunity Scout confidence

The red capture test supplied `confidence=0.77` through a JSON inbox item, then exercised capture, persistence, scoring, and reload. Capture returned `0.30`, the source-type prior, rather than the declared `0.77`. The inbox re-capture dictionary omitted the already-ingested confidence value.

## Morning Brief severity

The red test set producer `overall_health` to `WARN` while a known fleet row provided derived `FAIL` evidence. `build_report()` returned `WARN`, proving producer opinion could mask the worse evidence-supported state.

## Test-first disposition

Each test was observed failing before its implementation change and then passing after the bounded fix. No source-text or snapshot-shape tests were introduced; the new tests execute the public behavior and real local persistence paths.
