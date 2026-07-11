# Rollback Plan

No rollback is needed for this mission because production was not changed.

## Branch-only rollback

Close or delete branch `codex/trustworthy-briefing-v1` and remove its worktree. This leaves the runtime and current briefing untouched.

## Future controlled-deployment rollback

Before deployment, create:

- timestamped backup of `/Users/macmini/.hermes/scripts/daily_command_center.py`;
- SHA-256 checksums for old script, new script, and manifest;
- deployment receipt naming the branch commit and paths.

Rollback trigger:

- false GREEN;
- required source omitted or incorrectly fresh;
- unsupported decision/merge recommendation;
- Telegram rendering regression;
- output exceeds the accepted size;
- cron execution error;
- missing legacy capability that the approved deployment contract requires.

Rollback procedure after separate approval:

1. Restore the timestamped prior script atomically.
2. Run the prior script directly with output redirected locally.
3. Confirm no schedule or delivery configuration changed.
4. Do not restart Hermes; the no-agent cron job loads the script on its next invocation.
5. Record rollback checksum and reason.

The V1 manifest and machine reports may remain as inert evidence, but they must not be represented as active after rollback.
