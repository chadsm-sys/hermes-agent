# CLAUDE.md — Cloud Context for chadsm-sys/hermes-agent

## What this repo is

Chad's fork of NousResearch/hermes-agent (the upstream Hermes Agent
framework), carrying his personal **Chief of Staff layer** on top of it.
The live Hermes instance runs on Chad's Mac mini; this repo is the source
of truth for its code, not the running deployment. Cloud sessions here
work on code and docs only.

## Operating model (current, 2026-07)

- **Hermes is the active operating system.** It is the Executive
  Assistant: execution, conversation, escalation, ranking.
- **Mission Control is the Executive Brain** (separate repo,
  `mission-control-v0` — NOT in this repo): state of the world, plans,
  bottlenecks, reports.
- **Chad is the Executive**: judgment, authority, values, final word.
- **Life OS and the Executive Decision Packet are historical only.** Do
  not treat any Life OS governance, packet formats, or rituals as active.
  The current constitution is `docs/chief-of-staff/MISSION.md` and the
  six documents it maps.

## Key files

| Path | Role |
|---|---|
| `docs/chief-of-staff/MISSION.md` | Constitution — wins all conflicts |
| `docs/chief-of-staff/*.md` | Philosophy, decision/bottleneck/compound engines, coach, HUMAN_FIRST boundaries |
| `docs/executive-operating-loop-contract.md` | M21 Hermes↔Mission Control seams — **contract only, nothing wired** |
| `plugins/opportunity_scout/` | Merged. Deterministic 0–100 scoring; never pursues autonomously |
| `plugins/memory/memorygraph/` | Merged. Governed knowledge-graph memory (candidate/established/core tiers) |
| `chief_of_staff/` | **Does not exist on main.** Lives in open PR #5 (interface-only); do not assume it is importable |

## Rules for cloud sessions

1. **No deploys, no production changes, no secret changes.** The Mac
   mini deployment is out of reach and out of scope from here.
2. **Governed merges.** PRs are merged by Chad's explicit approval only.
   Open PRs (#1 council gate, #3 review fixes, #5 chief-of-staff) stay
   open until he says otherwise.
3. **Wiring is milestone-gated.** The executive-loop contract's roadmap
   (section 11) enumerates the allowed next steps; each is a separate,
   Chad-approved milestone. Do not wire seams opportunistically.
4. **Invariants** (contract section 9): evidence or silence; determinism
   over cleverness (no model calls in ranking/escalation/status);
   mutation boundaries (each engine writes only its own store);
   attention economy (four interrupt classes, one question max); never
   chase opportunities autonomously.
5. Upstream docs (`README.md`, `AGENTS.md`, `CONTRIBUTING.md`) describe
   the generic Hermes framework — follow them for code conventions, but
   Chad's layer above overrides them on governance.
