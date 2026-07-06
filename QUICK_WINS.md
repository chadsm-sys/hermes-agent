# Quick Wins — hermes-agent

**Audit date:** 2026-07-06 · **Commit:** `93b565b`. Every item here is **S-effort (≤ ~4 hours)**, low-risk, and independently shippable — no architectural decisions required. Sorted by payoff. IDs cross-reference `TECH_DEBT_REGISTER.md`. Evidence only — nothing has been changed.

## Bugs you can fix in minutes (found by the audit, still live)

1. **Repeated dict key `"trinity"`** — `hermes_cli/model_normalize.py:63`: the first mapping is silently dead (ruff F601). Decide which mapping wins, delete the other. *(TD-095)*
2. **Registry lookup normalization mismatch** — `agent/image_gen_registry.py:53` stores raw `name` while `get_provider` (:72) looks up `name.strip()`; same in video/web_search/browser registries; tts/transcription lower-case, the rest don't. A provider registered with whitespace or different case is unreachable. One-line normalization at registration per registry. *(TD-090)*
3. **`FOO=on` parses differently per platform** — `gateway/config.py` inline bool parses at :1415, :1527, :1643, :1670, :1686 use `{"true","1","yes"}` (no "on"); :1889 (bluebubbles) accepts "on"; the shared `_coerce_bool` (:25) accepts all four. Point all inline parses at `_coerce_bool`. *(TD-093)*
4. **Non-numeric port env aborts the whole gateway config load** — bare `int(os.getenv(...))` at `gateway/config.py:1826` (wecom) and `:1882` (bluebubbles); every other platform guards with try/except (:1470, :1660, :1679). *(TD-094)*
5. **Emoji dict keys collide** — `gateway/platforms/matrix.py:936-937`: unicode-variant keys hash equal, first entries dead. *(TD-095)*
6. **Phantom test timeouts** — every `pytest.mark.timeout(...)` is a silent no-op: pytest-timeout is not installed anywhere and the "global --timeout=30" cited in `tests/docker/conftest.py:46` doesn't exist. Either add the plugin or delete the marks; add `--strict-markers` to `pyproject.toml:329-336` so this class of bug can't recur. *(TD-099/110)*
7. **Duplicate function shadows its twin in the same file** — `tui_gateway/server.py:3582` vs `:3783` `_content_display_text`, byte-identical 30 lines; delete one. *(TD-044)*
8. **Cleanup swallows Ctrl+C** — `cron/scheduler.py:1940-1957` catches `(Exception, KeyboardInterrupt)` → debug log during teardown. Let `KeyboardInterrupt` propagate. *(TD-098)*

## Delete / rename (near-zero risk)

9. **Rename `agent/curator_backup.py` → `curator_snapshot.py`** — it is live snapshot/rollback code (imported at `agent/curator.py:1450`, `hermes_cli/curator.py:375`) whose current name reads "stale backup copy of curator.py"; it will eventually be deleted by mistake. *(TD-072)*
10. **Delete `hermes-already-has-routines.md`** — 6.3 KB competitive-marketing blog post at repo root. *(TD-074)*
11. **Delete `.plans/` and `plans/`** — all three contained plans (streaming, OpenAI-compatible server, Gemini OAuth) describe features that shipped (`run_agent.py:4085`, `gateway/platforms/api_server.py`, `agent/google_oauth.py`); `docs/plans/` remains the one home. *(TD-074)*
12. **Drop the eager root dep `@streamdown/math`** — `package.json:35`; imported by zero files; desktop deliberately replaced it (`apps/desktop/src/lib/katex-memo.ts:4,246`); installed for every `hermes update` user today. *(TD-077)*
13. **Delete the dead browser-resolution shim once adopted** — even before the full TD-070 refactor, the test-only `_PROVIDER_REGISTRY` legacy shim (`tools/browser_tool.py:423-431` + detector :446-467) and the `FirecrawlProvider` import (:102-104) that exists only to feed it can go with a small test update.
14. **Delete `__main__` demo blocks** — `tools/browser_tool.py:3751-3800`, `tools/skills_tool.py:1493-1533`; and the always-True `check_skills_requirements` (`skills_tool.py:477-479`). *(TD-079)*
15. **Delete the commented-out file-wide skip fossil** — `tests/run_agent/test_413_compression.py:10` (`#pytestmark = pytest.mark.skip…`) — history bait with no issue reference. *(TD-108)*
16. **Delete `tests/tools/test_mcp_stability.py:447`'s `time.sleep(60)`** inside a fake that is never called (inspect-only test) — booby trap for future refactors.
17. **Remove ~45 dead imports/vars flagged by ruff/vulture** — includes the explicitly-noqa'd dead `_canonical_whatsapp_identifier` (`gateway/run.py:1384`), 9 more unused imports in run.py (:19, :41, :54, :1074, :1079, :1347), 4 unused matrix crypto imports (:501-504), 9 unused `say` params in slack.py handlers (:866-912), `web_tools.py:53` unused Firecrawl imports, `hermes_cli/main.py:265`. `ruff check --select F401,F811 --fix` covers most. *(TD-080)*
18. **Move 572 KB of `.wav` samples out of the repo** — `tools/neutts_samples/` ships in every clone; fetch-on-demand or Git LFS. *(TD-081)*
19. **Move the 1.2 MB promo PNG** — `infographic/kanban-db-corruption-defense/infographic.png`, sole content of a top-level dir. *(TD-082)*
20. **Empty `gateway/builtin_hooks/` package + no-op `_register_builtin_hooks`** (`gateway/hooks.py:72-79`, "Currently empty") — replace with a comment at the registration site. *(TD-079)*

## Two-file merges (mechanical dedups)

21. **Merge the diverged test forks** — `tests/test_cli_skin_integration.py` (3 banner tests only here) vs `tests/cli/test_cli_skin_integration.py` (2 voice tests only here); same for the `test_cli_file_drop.py` pair (cli/ is a superset by 4 tests). Merge into `tests/cli/`, delete root copies. *(TD-102)*
22. **`_extract_json_blob` ×3 → `hermes_cli/kanban_common.py`** — byte-identical at `kanban_specify.py:111`, `kanban_decompose.py:145`, `profile_describer.py:138`; take `_profile_author` (×3, already drifted) with it. *(TD-053)*
23. **`_read_skill_name` ×2** — verbatim 20 lines: `tools/skills_sync.py:154-173` == `tools/skill_usage.py:394-413` → `agent/skill_utils.py`. *(TD-054)*
24. **`_diagnostic_key` ×2** — byte-identical 22 lines at `agent/lsp/client.py:911` and `agent/lsp/manager.py:608`; the manager's docstring demands they stay identical — make it one import. *(TD-055)*
25. **STT/TTS quoting helpers** — `tools/transcription_tools.py:386/:418` == `tools/tts_tool.py:625/:656` (48 lines). *(TD-050)*
26. **`_save_config_key` ×2** — identical 17-line closure in two methods of `gateway/slash_commands.py` (:2071, :2278). *(TD-058)*
27. **`format_duration_compact`/`format_token_count_compact`** — `cli.py:105-141` verbatim copies of `agent/usage_pricing.py:874-908` sitting in a lazy-import shim block; convert to imports like their neighbors. *(TD-052)*
28. **`_prepare_anthropic_messages_for_api` / `_prepare_messages_for_non_vision_model`** — `run_agent.py:4462/:4490`; the second's comment admits identical behavior, "naming is historical". *(TD-051)*
29. **`fuzzy.ts` ×2** — `web/src/lib/fuzzy.ts` == `ui-tui/src/lib/fuzzy.ts` (identical header comment) → `apps/shared`. *(TD-059)*
30. **`_ra()` ×6** — identical 2-line lazy-import helper in six agent/ modules (agent_init :62, agent_runtime_helpers :45, chat_completion_helpers :42, conversation_loop :147, system_prompt :47, tool_executor :55). *(TD-060)*
31. **`_coerce_optional_positive_int`** — `gateway/config.py:59` == `hermes_cli/active_sessions.py:24` (34 lines). *(TD-062)*
32. **`_ssrf_redirect_guard` ×2 in one file** — `tools/vision_tools.py:175` and `:1270`. *(TD-063)*
33. **Spotify PKCE pair beside the generic pair** — `hermes_cli/auth.py:2341-2356`: `_spotify_code_verifier/_challenge` duplicate `_oauth_pkce_code_verifier/_challenge` defined 10 lines below. *(TD-063)*
34. **`_extract_code_and_state` ×2** — `skills/productivity/google-workspace/scripts/setup.py:312` == `plugins/platforms/google_chat/oauth.py:474`; same for `display_hermes_home` (`hermes_constants.py:245` == the skill script :34). *(TD-063)*
35. **`_normalize_skill_list`/`_canonical_skills`** — `cron/jobs.py:154` == `tools/cronjob_tools.py:299`. *(TD-063)*
36. **rsa_keypair fixture ×2** — add `tests/plugins/dashboard_auth/conftest.py` (currently duplicated in both provider test files). *(TD-101)*

## Small config/tooling hygiene

37. **Extract the 7 gateway↔TUI parity loaders** into `gateway/config` — admitted manual copies with observed drift (`gateway/run.py:3447-3700` vs `tui_gateway/server.py`; server.py:1734 docstring). ~4h, kills a whole "keep in parity" duty. *(TD-043)*
38. **De-duplicate the release contributor map into `.mailmap`** — `scripts/release.py` (hottest-churn file, 72 ruff findings incl. repeated keys at :159/:241) maintains its own email→name table parallel to root `.mailmap`. *(TD-150)*
39. **Comment or drop the lodash exact-pin** — root `package.json:39` `overrides: {"lodash":"4.18.1"}` with no rationale. *(TD-154)*
40. **Fix root npm scripts drift** — `install:*`/`audit:*` enumerate workspaces by hand; `apps/bootstrap-installer` (in the workspace glob) and `website/` are missing. *(TD-154)*
41. **Adopt `MessageDeduplicator` in the 3 holdouts** — feishu :4356, ntfy :367, photon :441 hand-roll `_is_duplicate` that `helpers.py:27` already provides (and cites feishu as its source). *(TD-049)*
42. **Hoist `import aiohttp` in whatsapp.py** — imported inside 8 separate methods (:439-:955); one lazy-import helper. *(TD-080)*
43. **Add a `helpers.guess_extension`** — 4 divergent copies (wecom :821, feishu :3835, signal :78, simplex :104); pick the superset table. *(TD-063)*
44. **Retire `hermes_cli/claw.py`** — 809-line one-time OpenClaw→Hermes migration, single call site (`main.py:11427`); deprecate with a stub pointing at the last release that carried it. *(TD-073)*
45. **Fix `browser_dialog`'s cloud gate** — change `_browser_cdp_check` (`browser_cdp_tool.py:525-552`) to also pass when a per-session supervisor is live; today Browserbase sessions can show a `must_respond` dialog with no tool offered. Small conditional change; the supervisor plumbing already exists. *(TD-092)*

**Estimated total for this page: ~60–75 hours of work removing ~3,000+ duplicated/dead lines, two whole directories, ~2 MB of binary weight, and eight latent bugs.**
