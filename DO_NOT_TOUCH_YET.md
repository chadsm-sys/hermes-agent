# Do Not Touch Yet — hermes-agent debt reduction

**Date:** 2026-07-06 · **Baseline:** `93b565b`. These areas carry known debt (documented in `TECH_DEBT_REGISTER.md`) but must **not** be refactored until their stated unlock condition is met. Touching them early is how a debt-reduction program creates incidents. Each entry: what, why frozen, and the unlock condition.

## 1. OAuth flows — any provider port (TD-034/035, lane O)

**Frozen:** all of `hermes_cli/auth.py`'s per-provider flows, `agent/google_oauth.py`, `tools/mcp_oauth*.py`, `hermes_cli/dashboard_auth/`, `web_server.py:5146-6250`.
**Why:** highest blast radius in the repo — a wrong refresh/quarantine change locks users out of every provider silently, and the audit found the flows are subtly divergent (near-copy terminal-error classifiers at `auth.py:4850` vs `:4867` differ deliberately or accidentally — unknown which). Credential-store formats are undocumented; bit-compatibility must be proven, not assumed.
**Unlock:** a maintainer-reviewed design note (engine API, storage compatibility matrix, per-provider rollback story) + recorded token-lifecycle fixtures for the pilot provider. Until then only two lane-O moves are legal: the `auth.py:2341-2356` PKCE-twin deletion (pure same-file dedup) and *adding* lifecycle tests.

## 2. The self-updater's logic (TD-004)

**Frozen:** everything `_cmd_update_impl` (`hermes_cli/main.py:8410-9925`) *does* — git stash lifecycle, upstream sync, Windows exe quarantine, reboot scheduling, interrupted-install recovery.
**Why:** the updater runs unattended on user machines; a bug bricks installs and — uniquely — a bricked updater can't ship its own fix. It is also the least-testable code in the repo (mutates the running installation).
**Unlock:** verbatim **extraction** to `hermes_cli/updater/` is allowed in lane M (pure motion, `--color-moved` review); any behavioral change waits until the extracted modules have unit seams and a rollback-tested release has shipped.

## 3. `run_conversation`, `GatewayRunner`, `AIAgent`, `HermesCLI` decomposition (TD-001/002/003/006/007/008)

**Frozen:** all four god structures, plus `init_agent` (TD-010) and the `interruptible_*_api_call` fork (TD-037).
**Why:** the hottest paths in the product, guarded today mostly by integration-level tests; the audit's own premise-corrections (e.g. `_handle_message` pipeline, `run_sync` closure) prove that static reading of these files misleads — extraction without characterization coverage risks silent semantic drift. The `_ra()` monkeypatch shim means test coupling is load-bearing in non-obvious ways (88 test files import via the `cli` facade; many patch `run_agent`).
**Unlock:** `FIRST_THREE_PRS.md` PR-3 ratchet in place, lane T mock consolidation underway (so gateway tests are trustworthy), and — for `run_conversation`/`_run_agent` specifically — a characterization suite pinning turn-level behavior (tool-call ordering, retry/fallback activation, compaction triggers) recorded against `93b565b`. Then banner-by-banner extraction only, one banner per PR.

## 4. `yuanbao` platform (~7,979 lines) (TD-130)

**Frozen:** `gateway/platforms/yuanbao*.py`, its config block, skill, and 6 test files.
**Why:** single-drop code (one commit `40699c3`, zero follow-up), no identifiable owner, niche platform. It is *live and tested* — not deletable — but any refactor (including lane A batching adoption for its siblings) should skip it until someone owns the verification.
**Unlock:** an owner is named, or a deprecation decision is made. Lane A explicitly excludes yuanbao from the adapter rollout list until then (it doesn't carry the batching trio anyway — feishu variant is the closest cousin).

## 5. The `hermes-ink` fork and frontend unification (TD-042/078/121, program P4)

**Frozen:** `ui-tui/packages/hermes-ink/` (68k lines incl. hand-ported yoga), the three chat frontends' structure, `apps/shared` expansion.
**Why:** the largest number in the audit but requires a product decision first (which frontends live, upstream-vs-freeze for the Ink fork) and consumes enormous review bandwidth that waves 1–3 need elsewhere. The three frontends are frozen at the 2026-06-15 squash — divergence is currently static, so there is no bleeding to stop.
**Unlock:** maintainer decision on P4 scope. Legal early moves: the `fuzzy.ts` two-file merge (lane Q, TD-059) and dead-dependency removal in the frontend manifests (TD-077) — neither prejudges the architecture.

## 6. `hermes_state.py` schema, migrations, and corruption repair (TD-021/083)

**Frozen:** `SessionDB` schema init/migration/repair paths (`hermes_state.py:210-655, 973-1279, 4526-4572`) and the legacy-DB heuristics (:37, :595, :1085, :2036).
**Why:** user data. The repair/migration code encodes years of observed corruption modes (WAL fallback, column reconciliation); "cleaning it up" without a corpus of real legacy DB fixtures risks destroying sessions on upgrade.
**Unlock:** a migration test rig with fixture DBs at each historical schema version. The Telegram-topics/handoff **extraction** (TD-021, lane M) is allowed earlier because it moves query methods, not schema code — but it must not touch DDL.

## 7. `kanban_db.py` migrations (TD-020)

**Frozen:** the "racy-idempotent ALTER TABLE" migration block (:1478-1856).
**Why:** same class as #6 — the raciness is documented as deliberate (concurrent CLI/gateway/dashboard writers); a naive tidy-up reintroduces the races it papers over.
**Unlock:** the 4-way module split may proceed around it; migrations move last, verbatim, after a concurrent-writers test exists.

## 8. `migrate_config`'s 13 version gates (TD-016) — semantic content

**Frozen:** the *meaning* of each `if current_ver <` gate (`hermes_cli/config.py:4386-4813`).
**Why:** each gate is a fossilized promise to users upgrading from that era; collapsing or "simplifying" gates can corrupt configs mid-ladder.
**Unlock:** the mechanical MIGRATIONS-table restructure (lane M) is fine — one load/save, gates moved verbatim into list entries. Deleting or merging gates requires a supported-upgrade-window policy decision first.

## 9. Big-bang `sys.modules` cleanup in tests (TD-100)

**Frozen:** any attempt to remove the per-file subprocess CI isolation or sweep all 178 `sys.modules` mutations at once.
**Why:** the subprocess model is currently the only thing making CI deterministic; removing it before the mutations are gone reintroduces the original flake storm. The audit is explicit that this was institutionalized for cause.
**Unlock:** never big-bang. Directory-by-directory burn-down (lane T, wave 3+), each directory proven under a shared-interpreter smoke run before the next starts. The CI architecture itself changes only after the counter hits zero.

## 10. Packaging, entry points, and taxonomy decisions (TD-124/125/126, P11)

**Frozen:** `setup.py`/`MANIFEST.in`/nix/packaging consolidation; the `hermes`/`hermes-agent`/`cli.py` entry-point merge; the root `package.json` workspace split; `skills/` vs `optional-skills/` taxonomy merge.
**Why:** each changes what users install or where files land — product/distribution decisions, not refactors; several have install-base migration costs (Termux fast paths, wheel data_files).
**Unlock:** explicit maintainer decisions per item. Reading list is ready in `LONG_TERM_SIMPLIFICATIONS.md` P11 / register TD-124–126.

## 11. i18n systems and translated READMEs (TD-123)

**Frozen:** consolidation of the five i18n systems; the `README.zh-CN.md`/`README.ur-pk.md` drift.
**Why:** requires translation workflow/ownership decisions; low bug risk today (frontends frozen).
**Unlock:** P11 scheduling. A CI **parity check** (key-count comparison, no content changes) is allowed anytime — it's observability, not refactor.

## 12. Behavior-adjacent "cleanups" that look like quick wins but aren't

Explicitly **not** in lane Q despite appearing trivial:
- **`hermes_cli/model_normalize.py:63` repeated `"trinity"` key (TD-095)** — fixing it *changes which mapping wins*; needs a one-line decision from whoever owns model normalization + a test. Ship as BEHAVIOR-FIX with that context, not in a sweep.
- **`gateway/config.py` bool/int parsing (TD-093/094)** — behavior changes; gated behind the golden-snapshot test (PR-3).
- **Registry key normalization (TD-090)** — behavior change; lane R with its test.
- **`cron/scheduler.py:1940-1957` KeyboardInterrupt swallowing (TD-098)** — plausibly deliberate shutdown hardening; needs a maintainer ruling on intended Ctrl+C semantics during cron teardown before "fixing".
- **Deleting `hermes_cli/claw.py` (TD-073)** — needs a deprecation window decision (users may still be migrating from OpenClaw).
- **`package.json` lodash exact-pin (TD-154)** — investigate the reason (likely CVE) before loosening; the quick win is *documenting* it, not changing it.

---

**Summary rule of thumb:** in waves 1–2, if a change (a) alters any observable behavior, (b) touches credentials, updater, schema, or migrations, or (c) requires a product decision — it is on this list, and the only legal early actions are *adding tests*, *verbatim extraction*, and *documentation*.

**Terminal state: ROADMAP_READY**
