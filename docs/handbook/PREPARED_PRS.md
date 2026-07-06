# Prepared PRs — Unwired Features Remediation

Three PR branches are pushed to this fork, each implementing one group
from [UPSTREAM_PR_PLAN.md](UPSTREAM_PR_PLAN.md). **No PRs have been
opened** — this file holds the ready-to-paste bodies (structured after
the repo's PR template: summary / changes / how to test / checklist
notes). PR D is deliberately not prepared (see bottom).

Pre-flight performed for all three (2026-07-06):
- **Drift check:** `origin/main` (`93b565b`) is byte-identical to the
  audit base — zero commits of drift since the audit and register.
  *Limitation:* only the fork is reachable from this session; a final
  `git fetch` + rebase against `NousResearch/hermes-agent@main` must be
  repeated at open time.
- **Consistency re-check:** every target line re-read on current main
  before editing (all ten claims still present verbatim); every removal
  re-verified against indirect consumption (SDK readers, JS readers,
  `OPTIONAL_ENV_VARS` registry, doc generators, release tooling).
- **Test impact scan:** no test asserts on any changed line
  (`BROWSER_SESSION_TIMEOUT`/`CONTEXT_COMPRESSION_*`/display fallbacks
  greps over `tests/` — zero behavioral references).

---

## PR A — branch `docs/env-example-accuracy` (commit `eae3ffc`)

**Title:** `docs(env): make .env.example match actual behavior`
**Diff:** 1 file, +11/−14 (`.env.example` only)

### What does this PR do?
Fixes five inaccuracies in `.env.example` found by a claim-vs-wiring
audit of all 119 documented variables (methodology: every var swept for
production readers across py/sh/ts/js, with SDK-, plugin-, registry-,
and release-tooling-consumption explicitly ruled out before any
removal):

1. **OpenRouter header** — dropped "All LLM calls go through OpenRouter
   — no direct provider keys needed"; 29 provider profiles ship in
   `plugins/model-providers/` and this same file documents a dozen
   direct keys. Reworded to "simplest way… OpenRouter is optional."
2. **`TERMINAL_TIMEOUT=60`** — shipped uncommented while the real
   default is 180 (`hermes_cli/config.py` `terminal.timeout`;
   `tools/terminal_tool.py` `_parse_env_var("TERMINAL_TIMEOUT","180")`).
   Copying the example silently cut command timeouts to a third. Now
   commented out with the correct default stated.
3. **`BROWSER_SESSION_TIMEOUT=300`** — removed; zero readers anywhere.
4. **SESSION LOGGING** — section claimed session JSON files are written
   automatically; they are opt-in (`sessions.write_json_snapshots`,
   default false) and superseded by `state.db`. Rewritten to say so.
5. **`CONTEXT_COMPRESSION_ENABLED/THRESHOLD`** — removed; zero readers;
   compression is configured only via `config.yaml` `compression:`.

### Why this improves operator trust
`.env.example` is the first file every installer opens. Two of these
lines were live-looking switches connected to nothing, and one live
line silently changed behavior away from the shipped default — the
worst kind of template bug, because the operator's mental model is
formed here.

### Why it is low risk / no behavior change
The file is a copy-me template; no code parses it. The only behavioral
effect is that *new* users who copy the example stop unknowingly
overriding the terminal timeout to 60 s — i.e., they now get the
documented default.

### How to test
`grep -rn "BROWSER_SESSION_TIMEOUT\|CONTEXT_COMPRESSION_ENABLED\|CONTEXT_COMPRESSION_THRESHOLD" --include=*.py --include=*.sh --include=*.ts --include=*.js .`
→ no production reader (pre-existing fact this PR documents).

---

## PR B — branch `fix/cli-default-display-corrections` (commit `aab28f7`)

**Title:** `fix(cli): correct displayed defaults for max_turns and TERMINAL_TIMEOUT`
**Diff:** 2 files, +3/−3 (three display strings)

### What does this PR do?
- `cli.py` `main()` help text: `max_turns … (default: 60)` → `90` — the
  real default everywhere (`hermes_cli/config.py` `agent.max_turns: 90`,
  `cli.py:421`, `:3224`, `:3386-3388`).
- `cli.py` `show_config()` and `tools/terminal_tool.py` debug dump:
  `TERMINAL_TIMEOUT` display fallback `"60"` → `"180"`, matching the
  behavioral fallback (`terminal_tool.py:1172`) and `DEFAULT_CONFIG`.

### Why this improves operator trust
`--help` and `show_config` are exactly where users go to learn the
defaults; both currently disagree with the code by 30-50%.

### Why it is low risk / no behavior change
This is the one "cosmetic code" PR. All three literals were verified to
sit in print/help paths only: `show_config()` renders a status panel,
`terminal_tool.py:2621` is a debug `print`, and the docstring is fire's
help source. The behavioral fallback (`_parse_env_var`, line 1172) is
untouched. `python -m py_compile` passes on both files.

### How to test
`hermes --help | grep max_turns` shows 90; `grep -n "TERMINAL_TIMEOUT" tools/terminal_tool.py` shows the display fallback now equals the
behavioral fallback three lines apart.

---

## PR C — branch `docs/docstring-runtime-sync` (commit pushed on branch)

**Title:** `docs(code): sync docstrings and packaging comments with actual wiring`
**Diff:** 3 files, +14/−6 (comments/docstrings only; zero executable lines)

### What does this PR do?
- `gateway/memory_monitor.py` — docstring claimed a
  `logging.memory_monitor` config key that exists nowhere
  (`hermes_cli/config.py`, `cli-config.yaml.example`, website docs) and
  the module has no production caller. Now states plainly that it is
  not wired and documents the manual `start_memory_monitoring()` path.
  (Wiring it behind a real key is left as a separate maintainer
  decision — this PR deliberately does not invent that feature.)
- `cron/suggestions.py` — the `usage` and `integration` suggestion
  sources were described in present tense; repo-wide, `add_suggestion()`
  is called only by the blueprint installer and the catalog seeder.
  Both sources now marked "RESERVED, no producer yet."
- `packaging/homebrew/hermes-agent.rb` — header note that the formula
  is a release-time template (stale 0.6.0 pin + placeholder sha256) and
  not installable as committed; `scripts/release.py` names the assets
  it should point at.

### Why this improves operator trust
Each of these is a claim a reader acts on: grepping for a `[MEMORY]`
series that never appears, waiting for usage-based automation proposals
that cannot arrive, or running `brew install` against a template.

### Why it is low risk / no behavior change
Comments and docstrings only — the diff contains no executable line.
Verified: `python -m py_compile` on both modules;
`tests/gateway/test_memory_monitor.py` + `tests/cron/test_suggestions.py`
run against the branch: **28 passed**.

### How to test
Run the two test files; read the diff — every hunk is inside a string
or comment.

---

## PR D — NOT prepared (blocked on maintainer question M1)

The Matrix findings (six documented agent tools + five permission env
vars, none existing) may be abandoned or future work — intent cannot be
determined locally (squashed history). Per plan, PR D opens only after
asking upstream:

> The Matrix user guide (`website/docs/user-guide/messaging/matrix.md`,
> "Matrix Tools and Controls") documents six agent tools
> (`matrix_send_reaction`, `matrix_redact_message`, `matrix_create_room`,
> `matrix_invite_user`, `matrix_fetch_history`, `matrix_set_presence`)
> and five `MATRIX_TOOLS_ALLOW_*` permission variables. None of these
> exists in the codebase (no tool registrations; no env reads — the
> wired siblings `MATRIX_ALLOW_PUBLIC_ROOMS` /
> `MATRIX_APPROVAL_REQUIRE_SENDER` show what wiring looks like). Were
> these reverted, or documented ahead of an unmerged branch? Happy to
> either remove the section + env rows + docstring entries, or mark
> them "planned — not yet shipped," whichever matches your intent.

If the project prefers acting without the question, the fallback is the
"planned/reserved" marking (matches the convention this fork's PR C
uses for the suggestion sources), which is safe under either answer.

---

## Final summary

**Expected maintainer review effort.**
- PR A: ~5 minutes — one template file, five self-contained hunks, each
  justified by a one-line grep the reviewer can rerun.
- PR B: ~2 minutes — three one-token changes; the only work is
  confirming the call sites are display-only (the PR body names them).
- PR C: ~5 minutes — comment-only diff plus two test files to run.
- Total: one sitting; no cross-PR context needed.

**Potential areas of disagreement.**
- PR A: whether to *remove* `BROWSER_SESSION_TIMEOUT` /
  `CONTEXT_COMPRESSION_*` vs. wire them (a maintainer may prefer making
  the docs true by implementing the vars — our scope rule chose docs).
- PR A: rewording the OpenRouter header touches marketing tone; the
  maintainer may want their own phrasing (content, not substance).
- PR C: the memory-monitor docstring fix invites the obvious rejoinder
  "why not just wire it?" — the body pre-empts this by scoping wiring
  as a separate decision (question M2).
- PR B: essentially none.

**Submission order.** PR B first — smallest, most obviously correct,
and it establishes the audit's credibility with a 2-minute review.
Then PR A (highest operator value), then PR C. PR D waits for the M1
answer.

**Independence.** A, B, and C touch disjoint files and share no hunks —
they can merge in any order or combination with no conflicts. D is
independent of all three.

---

PRS_READY_TO_OPEN
