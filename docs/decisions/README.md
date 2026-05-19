# Architectural Decision Records

Servo's ADRs. Each record captures a hard-to-reverse decision and the alternatives considered. Filenames follow `adr-NNNN-<kebab-slug>.md` (lowercase, matching jig's convention); the acronym is uppercase in prose.

| ADR | Status | Title |
|---|---|---|
| [ADR-0001](adr-0001-reuse-jig-test-detector.md) | Accepted | Reuse jig's `tdd.py detect` for test-framework detection when jig is co-installed |
| [ADR-0002](adr-0002-gate-caller-contract.md) | Accepted | Quality-gate caller contract: closed exit codes and versioned JSON schema |
| [ADR-0003](adr-0003-fresh-subagent-roster.md) | Accepted | Why a fresh subagent roster, not reused from jig |
| [ADR-0004](adr-0004-session-state-file-format.md) | Accepted | Session-state file format on disk |

Pending decisions are listed in `docs/architecture.md` under "Decisions pending" until they crystallize.
