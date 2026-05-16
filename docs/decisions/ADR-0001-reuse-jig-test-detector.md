---
status: Accepted
date: 2026-05-15
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0001 — Reuse jig's `tdd.py detect` for test-framework detection when jig is co-installed

## Context

Servo's slice 001-03 needs to classify a target project's test framework so the scaffolded `oracle.sh` includes the right `score_<framework>` block. The five primary frameworks servo cares about (pytest, vitest, jest, cargo, go) overlap exactly with the set jig's `skills/tdd-loop/tdd.py detect` already discriminates.

Three implementation options:

1. **Reimplement detection in servo.** Walk file signals from scratch in `scaffold.py`.
2. **Hard-depend on jig.** Refuse to scaffold without jig present; always shell out to `tdd.py detect`.
3. **Prefer jig if present, fall back to built-in.** Use `${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py detect` via subprocess when the file exists; otherwise run servo's own minimal detectors.

The product-vision and architecture docs say servo is a *sibling* plugin to jig — independent install/uninstall, no shared Python dependency surface. That rules out option 2. Option 1 duplicates logic that already lives next door. Option 3 keeps servo independently installable while letting users who have jig benefit from its richer (and presumably better-maintained) classifier.

## Decision

**Option 3.** `scaffold.py:_jig_tdd_detect()` looks for `${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py`. If present, it invokes `python3 <path> detect <target>` via `subprocess.run` with a 5-second timeout and parses stdout as JSON, accepting any of `framework` / `runner` / `name` keys (tolerates jig schema drift). If jig is absent, the JSON shape doesn't match, the call times out, or the returned framework name isn't in servo's vocabulary, servo falls through to its own `BUILTIN_DETECTORS` mapping — which covers all five primary frameworks per slice 001-03 AC #4.

Lint detection (eslint, ruff) is **not** routed through jig — jig only classifies test runners. Servo owns its own lint detectors regardless.

## Consequences

**Positive.**
- Independent install: servo with no jig still works; AC #4 in slice 001-03 validates this path.
- Schema-drift tolerant: servo accepts three possible jig output keys and silently falls back on unknown shapes — a jig upgrade can't break servo's scaffolder.
- 5-second timeout caps the worst case if jig's detector hangs (network call, subprocess wedge).
- No shared Python module imports, no `sys.path` mutation — the filesystem-only coupling promised in architecture.md holds.

**Negative.**
- Subprocess overhead per scaffold (one process spawn + JSON parse). Negligible for a one-shot install command, would matter if detection moved into a hot loop.
- Two code paths to keep aligned: jig's mapping and servo's built-in. If jig adds a new framework, servo's normalization vocabulary needs an update.
- jig's `tdd.py detect` is not contractually frozen — schema drift is mitigated by the fall-back, but a wholly incompatible change in jig could silently degrade servo to built-in-only on jig-installed boxes. Acceptable: built-in still works.

**Neutral.**
- The decision binds to a specific filesystem path (`<plugin-root>/jig/skills/tdd-loop/tdd.py`). If the Claude Code plugin layout ever changes, this needs a re-check. Documented in `docs/architecture.md`'s "Signal detection" section.

## Alternatives considered

- **Vendor jig's detector** (copy `tdd.py` into servo). Rejected: doubles maintenance, defeats the "lives next door" framing.
- **Have jig publish a JSON contract first.** Rejected: blocks servo on a jig-side change that may never happen. Falling back to built-in on schema mismatch achieves the same end with no jig changes required.
- **Always use built-in, never delegate.** Rejected: misses the obvious win when jig is already there, and means servo's vocabulary diverges from jig's over time.

## Verification

- `JigFallbackTests` in `skills/scaffold-init/test_scaffold.py` covers the no-jig path for all five test frameworks.
- The jig-present path is exercised by manual smoke against a co-installed jig; not gated in CI because servo's CI shouldn't depend on jig being checked out.

## References

- Slice 001-03 (signal-detection) in `docs/specs/001-scaffold-init/spec.md`.
- `docs/architecture.md` "Signal detection" and "Project vs servo-core split" sections.
- `docs/product-vision.md` "Sibling, not competitor" framing.
