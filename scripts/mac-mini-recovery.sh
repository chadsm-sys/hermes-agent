#!/bin/bash
# ============================================================================
# Hermes Mac mini Recovery Script
# ============================================================================
# One-shot recovery for a Hermes install on macOS that has gone down.
# Safe to re-run: every step is idempotent.
#
# Usage (on the Mac mini):
#   bash scripts/mac-mini-recovery.sh
#
# What it does:
# 1. Finds the hermes CLI (reinstalls Hermes if the CLI is gone)
# 2. Runs `hermes doctor` for a health report
# 3. Starts the gateway via launchd (`hermes gateway start` self-heals a
#    missing or outdated ai.hermes.gateway plist)
# 4. Verifies the launchd job and gateway status, tails logs on failure
# ============================================================================

set -u

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

if [ "$(uname -s)" != "Darwin" ]; then
    echo -e "${RED}✗ This script is for macOS. Run it on the Mac mini itself.${NC}"
    exit 1
fi

echo -e "${CYAN}⚕ Hermes Mac mini recovery${NC}"
echo ""

# ----------------------------------------------------------------------------
# 1. Locate (or reinstall) the hermes CLI
# ----------------------------------------------------------------------------
HERMES=""
for candidate in hermes "$HOME/.local/bin/hermes"; do
    if command -v "$candidate" >/dev/null 2>&1; then
        HERMES="$candidate"
        break
    fi
done

if [ -z "$HERMES" ]; then
    echo -e "${YELLOW}→ hermes CLI not found — reinstalling.${NC}"
    echo -e "  Existing config and data in ~/.hermes (including .env) are preserved."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash || {
        echo -e "${RED}✗ Install failed. Check network access and re-run.${NC}"
        exit 1
    }
    export PATH="$HOME/.local/bin:$PATH"
    HERMES="$HOME/.local/bin/hermes"
fi

echo -e "${GREEN}✓ hermes CLI: $HERMES${NC}"
echo ""

# ----------------------------------------------------------------------------
# 2. Health check (informational — recovery continues regardless)
# ----------------------------------------------------------------------------
echo -e "${CYAN}→ Running hermes doctor...${NC}"
"$HERMES" doctor || true
echo ""

# ----------------------------------------------------------------------------
# 3. Start the gateway service
#    `gateway start` regenerates the launchd plist if missing/outdated,
#    bootstraps it into the gui domain, and kickstarts the job.
# ----------------------------------------------------------------------------
echo -e "${CYAN}→ Starting gateway service...${NC}"
if ! "$HERMES" gateway start; then
    echo -e "${RED}✗ gateway start failed — recent errors:${NC}"
    tail -n 40 "$HOME/.hermes/logs/gateway.error.log" 2>/dev/null || true
    exit 1
fi
echo ""

# ----------------------------------------------------------------------------
# 4. Verify
# ----------------------------------------------------------------------------
sleep 3
echo -e "${CYAN}→ Gateway status:${NC}"
"$HERMES" gateway status || true
echo ""

if launchctl print "gui/$(id -u)/ai.hermes.gateway" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ launchd job ai.hermes.gateway is loaded (RunAtLoad + KeepAlive)${NC}"
else
    echo -e "${YELLOW}⚠ launchd job not visible in gui/$(id -u) — the gateway may be"
    echo -e "  running detached instead. Check: hermes gateway status${NC}"
fi

echo ""
echo -e "${CYAN}Logs:${NC} ~/.hermes/logs/gateway.log  ~/.hermes/logs/gateway.error.log"
echo ""
echo -e "${CYAN}Reboot resilience (LaunchAgents only run while you're logged in):${NC}"
echo "  • System Settings → Users & Groups → enable automatic login for this user"
echo "  • sudo pmset -a autorestart 1    # auto power-on after power loss"
echo "  • System Settings → Energy → 'Start up automatically after a power failure'"
