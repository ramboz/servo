---
status: Accepted
date: 2026-06-18
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0013: Servo availability breadcrumb

## Status

Accepted

## Context

Jig wants to nudge a user toward `/servo:scaffold-init` when servo is available
on the machine but the current project has not yet been servo-scaffolded. The
easy part is checking the current project for `.servo/`. The hard part is
detecting whether servo itself is available without depending on a Claude-only
registry, invoking `servo`, running `claude plugin list`, or forcing servo as a
jig dependency.

The existing servo/jig boundary pattern is filesystem-only and writer-owned:
the producer owns the format, and the consumer performs cheap reads. ADR-0004
uses that pattern for loop state, and ADR-0010 uses it for heartbeat triage
state. The availability signal should follow the same rule: servo writes a
small host-neutral marker; jig treats its presence as a hint.

## Decision

Servo writes a user-state availability marker at:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/servo/available.json
```

The marker is JSON with schema version 1:

```json
{
  "schema_version": 1,
  "plugin_name": "servo",
  "source_kind": "scaffold-init",
  "source_path": "/absolute/path/to/servo",
  "source_version": "0.4.0",
  "updated_at": "2026-06-18T12:34:56Z"
}
```

`source_kind` records which servo path refreshed the marker. The initial
writers are:

1. `skills/scaffold-init/scaffold.py` when running from a source or release
   plugin root that has `.claude-plugin/plugin.json`;
2. `scripts/verify_install.py plugin <root>` after a successful plugin-root
   verification, which is the runtime-install confirmation path for local
   checkout users;
3. `scripts/scaffold_runtime.py` when vending servo into a project-local
   `.claude/` tree.

A vendored project-local `scaffold.py` does not refresh the global marker by
itself, because that helper may only be available inside one target project.
`scripts/scaffold_runtime.py` already writes the marker at the moment the
project-local runtime is created, using the source checkout as `source_path`.

The marker is best-effort. Failure to write it emits a warning but does not
fail the install or scaffold operation. Consumers must treat it as a hint:
presence means "servo has been observed here before"; absence or stale content
does not prove servo is unavailable.

## Consequences

**Positive.**

- Jig can detect "servo probably available" with a plain filesystem stat,
  without subprocesses, plugin registries, or host-specific paths.
- Local-clone, release-zip, and project-local scaffold users all have a path to
  write the same marker.
- The marker is inspectable and versioned, so future consumers can parse it
  without guessing.

**Negative.**

- It is a hint, not a capability proof. A user can delete or move the recorded
  `source_path` after the marker is written.
- There is now a tiny user-state artifact outside the target project. It must
  remain best-effort so a locked-down home directory does not break servo
  installs.

**Neutral.**

- This does not make servo a jig dependency.
- This does not change project oracle install state: `.servo/install.json`
  remains the target-local authority for whether a project has been
  servo-scaffolded.

## Alternatives considered

- **Use `~/.claude/` plugin metadata.** Rejected because it is Claude-specific,
  may move under `CLAUDE_CONFIG_DIR`, and misses local-clone installs.
- **Have jig run `claude plugin list` or invoke a servo command.** Rejected
  because the consumer path must stay cheap, read-only, and host-agnostic.
- **Write the marker under each target project's `.servo/`.** Rejected because
  `.servo/` answers a different question: whether that project is already
  scaffolded. Jig needs the inverse signal for unscaffolded projects.
- **Only document manual setup.** Rejected because the whole point of the
  breadcrumb is to make the nudge reliable enough for an automated prepare
  check.

## Verification

Implementation tests cover:

- `/servo:scaffold-init` writes the marker from a source plugin root;
- `scripts/verify_install.py plugin <root>` writes the marker on successful
  plugin-root verification;
- `scripts/scaffold_runtime.py` writes the marker when creating a
  project-local runtime scaffold;
- marker writes use `XDG_STATE_HOME` in tests and do not touch host-specific
  Claude directories;
- the marker payload has schema version 1, `plugin_name: "servo"`,
  `source_kind`, `source_path`, `source_version`, and `updated_at`.

## References

- [ADR-0004](adr-0004-session-state-file-format.md) - writer-owned filesystem
  contract precedent.
- [ADR-0010](adr-0010-triage-inbox-schema.md) - heartbeat state spine and cheap
  read/merge contract.
- [docs/refinement-todo.md](../refinement-todo.md) - original deferred
  breadcrumb item.
