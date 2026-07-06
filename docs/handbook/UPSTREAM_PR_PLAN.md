# Upstream PR Plan — Unwired Features Remediation

Classification and remediation plan for the ten findings in
[UNWIRED_FEATURES_REGISTER.md](UNWIRED_FEATURES_REGISTER.md), packaged
as four small upstream PRs against `NousResearch/hermes-agent`. Plan
only — nothing has been merged, no PRs opened, no code changed.
Behavior is preserved everywhere; no feature is invented to satisfy a
doc claim.

---

## 1. Classification

| # | Finding | Classification |
|---|---|---|
| 1 | Matrix tool suite + `MATRIX_TOOLS_ALLOW_*` (6 documented tools, 5 permission vars, none exist) | **Needs maintainer clarification** (docs-ahead-of-code or reverted feature); interim: documentation correction |
| 2 | `BROWSER_SESSION_TIMEOUT=300` (uncommented, unread) | **Dead configuration removal** |
| 3 | `TERMINAL_TIMEOUT` documented default 60 vs real 180 (+2 stale display fallbacks) | **Code defect** (cosmetic inconsistency) + documentation correction |
| 4 | `CONTEXT_COMPRESSION_ENABLED/THRESHOLD` env toggles (unread) | **Dead configuration removal** |
| 5 | "SESSION LOGGING" claims automatic JSON session files (opt-in, default off) | **Documentation correction only** |
| 6 | `memory_monitor` docstring claims nonexistent `logging.memory_monitor` config; module unwired | **Needs maintainer clarification** (wire vs. leave dormant); interim: documentation correction |
| 7 | "All LLM calls go through OpenRouter" header | **Documentation correction only** (historical claim from the single-provider era) |
| 8 | Suggestion sources `usage`/`integration` described in present tense, no producers | **Intentional forward-looking design**, mislabeled; documentation correction |
| 9 | `cli.py --help`: `max_turns (default: 60)` vs real 90 | **Documentation correction only** (help text in a code file) |
| 10 | Homebrew formula: placeholder sha256, 0.6.0 pin | **Intentional historical artifact** (release-time template; `scripts/release.py:2113` names stable assets "so Homebrew can target them") |

No finding was reclassified as FALSE_POSITIVE. Finding 1 got **worse**
on re-verification: `website/docs/user-guide/messaging/matrix.md:409-423`
names six specific agent tools (`matrix_send_reaction`,
`matrix_redact_message`, `matrix_create_room`, `matrix_invite_user`,
`matrix_fetch_history`, `matrix_set_presence`) — none exists anywhere
in the codebase (`grep -rn` per name: zero non-doc matches).

## 2. Final indirect-consumption verification (pre-removal gate)

Every removal candidate was re-swept across **all file types** (not just
`*.py`/`*.sh`/`*.ts`), plus the four indirect channels:

| Candidate | SDK/dependency | Plugins | Generated config/docs | Release tooling | Verdict |
|---|---|---|---|---|---|
| `BROWSER_SESSION_TIMEOUT` | none (unlike the Azure vars) | none | not in `OPTIONAL_ENV_VARS` registry; not in any JS (unlike `WHATSAPP_DEBUG`) | none | safe to remove |
| `CONTEXT_COMPRESSION_*` | none | none | none | none | safe to remove |
| `MATRIX_TOOLS_ALLOW_*` | not read by mautrix | none | `environment-variables.md` is **hand-maintained** (no generator in `website/scripts/` references it) | none | safe to remove (docs) |
| SESSION LOGGING wording | n/a (wording) | n/a | n/a | n/a | safe to reword |
| Homebrew formula | n/a | n/a | n/a | `release.py` names assets for brew but does **not** template the formula | do NOT remove — clarify |

Known false-positive classes were explicitly checked: env vars read by
dependencies (`AZURE_*` via `azure.identity`), by non-Python code
(`WHATSAPP_DEBUG` via `bridge.js`), and dashboard-registry-only listings
(`OPTIONAL_ENV_VARS`). None applies to any removal candidate.

## 3. PR grouping

### PR A — `.env.example` cleanup (docs-only, single file)
Findings 2, 4, 5, 7, and the example line of 3.
- Delete `BROWSER_SESSION_TIMEOUT=300` + its two comment lines (276-278).
- Delete `CONTEXT_COMPRESSION_ENABLED` / `CONTEXT_COMPRESSION_THRESHOLD`
  lines (394-395); keep the pointer to `config.yaml` `compression:`.
- Rewrite SESSION LOGGING section (306-310): sessions live in
  `~/.hermes/state.db`; JSON snapshots are opt-in via
  `sessions.write_json_snapshots: true`.
- Reword OpenRouter header (lines 1-5): "the simplest way to reach 200+
  models with one key" instead of "All LLM calls go through OpenRouter —
  no direct provider keys needed".
- Comment out `TERMINAL_TIMEOUT` and correct its comment to
  "(default: 180)".
**Risk: zero** — the file is a template; no code parses it.

### PR B — CLI help/default corrections (3 lines, display-only)
Findings 9 and 3's code side.
- `cli.py:13525`: `(default: 60)` → `(default: 90)`.
- `cli.py:5733` and `tools/terminal_tool.py:2621`: display fallbacks
  `"60"` → `"180"` to match `DEFAULT_CONFIG` (`config.py:939`) and the
  real behavioral fallback (`terminal_tool.py:1172`). Both call sites
  are print/`show_config` paths — verified display-only, zero behavior
  change.
**Risk: zero** — help text and status prints only.

### PR C — docstring/runtime synchronization (comment-only code edits)
Findings 6, 8, 10.
- `gateway/memory_monitor.py:27-28`: replace the false
  `logging.memory_monitor` config claim with "Not wired into gateway
  startup yet; call `start_memory_monitoring()` explicitly." (Keep the
  module and tests — see maintainer question M2.)
- `cron/suggestions.py` docstring: tag `usage` and `integration`
  sources "(reserved — no producer emits this source yet)".
- `packaging/homebrew/hermes-agent.rb`: header comment stating it is a
  release-time template whose `url`/`sha256` are filled per release.
**Risk: zero** — comments/docstrings only; no executable line changes.

### PR D — remove or clarify the unwired Matrix tool claims (docs-only, blocked on M1)
Finding 1.
- `website/docs/user-guide/messaging/matrix.md`: remove (or mark
  "planned — not yet shipped") the "Matrix Tools and Controls" section
  (six tool names + two-tier permission scheme).
- `website/docs/reference/environment-variables.md:428-432`: remove the
  five `MATRIX_TOOLS_ALLOW_*` rows.
- `gateway/platforms/matrix.py:33-37`: remove the three
  `MATRIX_TOOLS_ALLOW_*` docstring entries (keep the wired
  `MATRIX_ALLOW_PUBLIC_ROOMS` / `MATRIX_APPROVAL_REQUIRE_SENDER`).
**Risk: zero for code; requires maintainer answer to M1 to choose
"remove" vs "mark planned".** Default proposal if no answer: remove —
docs must describe the shipped system.

Suggested landing order: A → B → C independently (no ordering
constraints); D after M1 is answered.

## 4. Maintainer questions

- **M1 (blocks PR D wording only):** Were the Matrix agent tools
  (`matrix_redact_message` et al.) reverted, or documented ahead of an
  unmerged branch? If they're coming, the docs section should be marked
  "planned" instead of deleted; the env-var rows should move to that
  branch. Squashed fork history prevents answering this locally.
- **M2 (informs PR C, does not block it):** Is `memory_monitor`
  intended to be wired behind a real `logging.memory_monitor` key
  (one-line call in `gateway/run.py::start_gateway` + defaults-block
  entry)? The module and tests are ready; we deliberately did NOT wire
  it (scope rule: don't invent features to match docs). If yes, that is
  a separate, tiny, testable PR.

## 5. Maintainer-facing summary

**Why these changes reduce operator confusion.** Nine of ten findings
are claims an operator acts on during setup or debugging: four sit in
`.env.example` — the first file every installer opens — where two dead
toggles (`BROWSER_SESSION_TIMEOUT`, `CONTEXT_COMPRESSION_*`) silently
do nothing, one live value (`TERMINAL_TIMEOUT=60`) silently *changes*
behavior away from the shipped default, and one section promises
debug artifacts (`session_*.json`) that never appear. The Matrix docs
promise six admin tools and a two-tier permission model that don't
exist — an operator "hardening" Matrix is configuring a security
control connected to nothing. Each fix replaces a wrong expectation
with the actual behavior at exactly the place the expectation is
formed.

**Why they are low risk.** PRs A and D touch only documentation and
example files that no code parses. PR B changes three display strings
(one `--help` number, two status-print fallbacks) verified against the
real defaults in `DEFAULT_CONFIG` and `terminal_tool.py`. PR C changes
only docstrings/comments. Nothing alters a code path, a default, a
schema, or a test; every removal candidate passed a final
indirect-consumption check covering SDK-read vars, JS-side readers,
dashboard registry listings, generated docs, and release tooling —
the three classes that produced false positives during the audit are
each explicitly ruled out per candidate.

**Why they improve trust in the documentation.** The audit's headline
result is that Hermes docs are unusually honest: out of 119
`.env.example` vars and ~544 website-documented tokens, only ten claims
failed verification, and they cluster in one file and one platform
guide. Fixing them (and recording the ~40 verified-wired negative
results in the register) moves the docs from "mostly right" to
"checkable": every env var in the example is read by something, every
documented default matches `DEFAULT_CONFIG`, and every documented tool
exists. That is the property that lets operators debug from the docs
instead of around them.

---

PR_PLAN_READY
