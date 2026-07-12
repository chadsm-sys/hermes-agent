# Hermes on a Mac mini — Recovery Runbook

How to get a Hermes install on a Mac mini back up after it has gone down
(crash, reboot, power loss, broken upgrade). All commands run on the mini
itself (locally or over SSH with a GUI login session active).

## Quick path (covers most outages)

```bash
hermes doctor           # health report — flags config/service problems
hermes gateway start    # self-heals the launchd plist and starts the service
hermes gateway status   # confirm it's up
```

`hermes gateway start` regenerates `~/Library/LaunchAgents/ai.hermes.gateway.plist`
if it is missing or outdated, loads it into launchd, and kickstarts the job.
The service definition has `RunAtLoad` + `KeepAlive`, so once loaded it
restarts automatically on crashes and starts at every login.

Or run the one-shot script, which also reinstalls the CLI if it's gone:

```bash
bash scripts/mac-mini-recovery.sh
```

## If the `hermes` command is missing

The install lives in `~/.hermes` with the CLI symlinked at `~/.local/bin/hermes`.
If the CLI is gone (or the venv is broken), reinstall — config and data in
`~/.hermes` (including `.env`, cron jobs, memory, sessions) are preserved:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.zshrc          # or ~/.bashrc
hermes gateway start
```

## Diagnosing a gateway that won't stay up

```bash
tail -f ~/.hermes/logs/gateway.error.log     # stderr from the service
tail -f ~/.hermes/logs/gateway.log           # stdout
launchctl print gui/$(id -u)/ai.hermes.gateway   # launchd's view of the job
```

Common causes:

- **Bad or missing API key** — `hermes doctor` flags it; fix with
  `hermes model` or edit `~/.hermes/.env`.
- **Stale plist after an update** — `hermes gateway start` repairs it;
  `hermes gateway install --force` rewrites it from scratch.
- **Another gateway already bound** — `hermes gateway restart` replaces it.

## Surviving reboots unattended

LaunchAgents only run while the user is logged in, so a headless mini needs:

1. **Automatic login**: System Settings → Users & Groups → Automatic login.
2. **Auto power-on after power loss**: System Settings → Energy →
   "Start up automatically after a power failure", or `sudo pmset -a autorestart 1`.
3. Optional: disable sleep — `sudo pmset -a sleep 0 displaysleep 10`.

With those set, the boot chain is: power restored → mac boots → auto-login →
launchd loads `ai.hermes.gateway` (`RunAtLoad`) → gateway up, kept alive.
