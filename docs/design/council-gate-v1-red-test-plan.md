# Council Gate V1 — RED Test Plan

Status: Phase 2 design artifact
Purpose: define failing tests before implementation.

## Test files to add

```text
tests/hermes_cli/test_council_models.py
tests/hermes_cli/test_council_artifacts.py
tests/hermes_cli/test_council_adapters.py
tests/hermes_cli/test_council_gate.py
tests/hermes_cli/test_goal_council_integration.py
```

If `tests/hermes_cli/` is not the current convention, use the closest existing goal test directory and keep names explicit.

## RED tests

### Models

1. `test_council_finding_to_dict`
   - Create `CouncilFinding`.
   - Assert fields serialize exactly.

2. `test_council_review_result_defaults`
   - Create minimal result.
   - Assert default reviewer, empty findings, no artifact path.

3. `test_council_review_request_defaults_metadata`
   - Create minimal request.
   - Assert metadata defaults to `{}` and does not share mutable state.

### Artifacts

4. `test_artifact_writer_writes_json_and_markdown`
   - Use `tmp_path`.
   - Write request/result.
   - Assert both files exist.
   - Assert JSON `schema_version` and Markdown title.

5. `test_artifact_writer_sanitizes_session_id`
   - Use session id with slashes/spaces.
   - Assert output remains under artifact dir.

6. `test_artifact_writer_populates_result_artifact_path`
   - Assert returned result includes Markdown or JSON artifact path.

### Adapters

7. `test_mock_adapter_passes_clean_subject`
   - Subject without markers returns `pass`.

8. `test_mock_adapter_holds_on_blocker_marker`
   - Subject containing `COUNCIL_BLOCKER` returns `hold` and blocker finding.

9. `test_manual_adapter_returns_needs_review`
   - Manual default returns configured decision.

10. `test_command_adapter_rejects_empty_argv`
   - Empty command argv raises config error or returns blocking `needs_review` through gate.

11. `test_command_adapter_parses_json_stdout`
   - Use a temporary Python script that echoes valid JSON.
   - Assert decision parsed.

12. `test_command_adapter_timeout_returns_error`
   - Use a script that sleeps past timeout.
   - Assert gate handles timeout safely.

### Gate

13. `test_gate_disabled_returns_skipped`
   - Config `enabled=false`.
   - Assert adapter not called and decision `skipped`.

14. `test_gate_unmatched_trigger_returns_skipped`
   - Enabled but trigger false.
   - Assert skipped.

15. `test_gate_enabled_mock_writes_artifact`
   - Enabled mock mode.
   - Assert artifact exists.

16. `test_gate_blocking_adapter_error_returns_needs_review`
   - Adapter raises.
   - Blocking true returns `needs_review` with finding.

17. `test_gate_nonblocking_adapter_error_returns_skipped`
   - Adapter raises.
   - Blocking false returns `skipped`.

### Goal integration

18. `test_goal_done_pauses_when_council_holds`
   - Monkeypatch `judge_goal` to return `done`.
   - Enable Council mock.
   - Last response contains `COUNCIL_BLOCKER`.
   - `GoalManager.evaluate_after_turn()` returns no continuation and status paused/needs_review.

19. `test_goal_done_preserved_when_council_disabled`
   - Council disabled.
   - Judge done.
   - Existing done behavior remains.

20. `test_goal_done_passes_when_council_passes`
   - Council enabled mock.
   - Clean subject.
   - Goal status done and artifact written.

21. `test_goal_continue_does_not_review_by_default`
   - Judge continue.
   - Council enabled but only `delivery_review` active.
   - Assert no artifact and continuation behavior unchanged.

## Verification commands

Run focused RED tests after adding tests:

```bash
python3 -m pytest tests/hermes_cli/test_council_models.py tests/hermes_cli/test_council_artifacts.py tests/hermes_cli/test_council_adapters.py tests/hermes_cli/test_council_gate.py tests/hermes_cli/test_goal_council_integration.py -q
```

Expected before implementation: import failures or assertion failures proving tests are RED.

After implementation:

```bash
python3 -m pytest tests/hermes_cli/test_council_models.py tests/hermes_cli/test_council_artifacts.py tests/hermes_cli/test_council_adapters.py tests/hermes_cli/test_council_gate.py tests/hermes_cli/test_goal_council_integration.py -q
```

Expected after implementation: all focused tests pass.

Then run existing goal tests:

```bash
python3 -m pytest tests -k 'goal or council' -q
```
