# Hermes Engineering Handbook

The definitive engineering reference for this repository —
`chadsm-sys/hermes-agent`, Chad's fork of NousResearch's Hermes Agent
framework carrying his personal Chief of Staff layer.

| Document | Contents |
|---|---|
| [ENGINEERING_HANDBOOK.md](ENGINEERING_HANDBOOK.md) | The front door: what Hermes is, how the pieces fit, how to work in this repo, governance rules for Chad's layer |
| [ARCHITECTURE_REFERENCE.md](ARCHITECTURE_REFERENCE.md) | System architecture: agent core, gateway, plugin system, memory, Mission Control integration, routing, providers — with diagrams |
| [MODULE_REFERENCE.md](MODULE_REFERENCE.md) | Per-module reference: purpose, dependencies, public interfaces, failure modes, testing, future improvements for every subsystem |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Test-suite map, how to run tests, CI gates, conventions, determinism enforcement |
| [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) | Observability, logging, failure recovery, common failure modes and how to diagnose them |
| [MEMORY_MONITOR_VERIFICATION.md](MEMORY_MONITOR_VERIFICATION.md) | Verified finding: `gateway/memory_monitor.py` is unused in production (TRUE_UNUSED) |

Documentation only — nothing in this directory changes runtime behavior.
Where these documents conflict with `docs/chief-of-staff/MISSION.md`,
MISSION.md wins.
