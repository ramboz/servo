---
status: Accepted
date: 2026-07-01
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-01
---

# ADR-0020: Minimum supported Python is 3.9

## Status

Accepted (2026-07-01)

## Context

Servo is distributed as a Claude Code / Codex plugin, not a pip package. Its
helper scripts (`skills/*/<helper>.py`, `scripts/*.py`, the vendored
scaffold-runtime) are invoked by the host with whatever `python3` is on the
user's PATH. On a default macOS install that is the Command Line Tools
interpreter — **Python 3.9.6**.

CI, however, only ever ran the test matrix on 3.11 and 3.12, and
`pyproject.toml` declared `requires-python = ">=3.11"`. A 3.10+ floor therefore
crept into shipped, adopter-facing helpers unnoticed:

- **PEP 604 `X | None` unions (3.10)** in module-level annotations. On 3.9 the
  union expression is evaluated at *def-time*, so every affected helper raised
  `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` on
  import — before doing any work. Nine shipped files were affected, including
  `scaffold-init/scaffold.py`, `quality-gate/gate.py`,
  `edd-suitability/suitability.py`, `execution-planner/execution_plan.py`, and
  `spec-oracle/oracle_plan.py`.
- **`zip(..., strict=)` (PEP 618, 3.10)** in the agent-loop test suite.

The result: servo's first-touch helpers crashed with an opaque `TypeError` on
the *most common* interpreter our adopters actually run. The breakage was
invisible to us because nothing tested it. This is the same regression class the
sibling plugin jig hit and fixed in its **ADR-0030** (minimum supported Python
is 3.9); this ADR adopts jig's resolution for servo so the two plugins share one
supported-floor policy and one enforcement mechanism.

## Decision

**Python 3.9 is servo's minimum supported runtime.** Concretely:

- **Shipped, adopter-facing code MUST run on 3.9.** This is the code under
  `skills/`, `agents/`, `hooks/`, `templates/`, the plugin manifests, and the
  `scripts/` install helpers that vendor into a target.
- **Convention for PEP 604 unions:** add `from __future__ import annotations`
  (lazy string annotations, valid on 3.9) rather than falling back to
  `typing.Optional`. Reserve `Optional`/`Union` for genuinely
  *runtime-position* unions (type-alias assignments, `Callable[...]`
  subscripts) that the future import does not defer.
- **No 3.10+ runtime APIs in shipped code** (`zip(strict=)`, `match`,
  `sys.stdlib_module_names`, …) without a 3.9-safe shim or an explicit
  version-gate.
- **Tests that need a genuinely-newer API version-gate** (e.g.
  `spec-oracle/test_checks.py` skips its `sys.stdlib_module_names` case below
  3.10) rather than lowering the floor.
- Servo stays **zero-dependency** (stdlib only) — no `tomli`-style backports.

Enforcement is two-layer: a **`3.9` job in the CI matrix** (the load-bearing
guard — it actually executes the floor against the full suite) and **`ruff
target-version = "py39"`** (a static signal that flags 3.10+ syntax before CI
runs). `pyproject.toml`'s `requires-python` is lowered to `>=3.9` to match.

`actions/setup-python` no longer ships the exact 3.9.6 patch for current hosted
runners, so the CI leg pins the **3.9 minor** and resolves the latest 3.9.x —
intra-3.9 patch releases don't change language/stdlib compatibility, and the
`ruff target-version=py39` static check still enforces the syntax floor.

## Consequences

**Positive:**
- The plugin works out-of-the-box on a stock macOS — no adopter or contributor
  has to install a newer interpreter.
- Regressions are caught mechanically: a new bare `X | None` or `zip(strict=)`
  reddens the 3.9 CI leg (and usually ruff) immediately.
- The `from __future__ import annotations` convention keeps modern, readable
  type syntax across the codebase.
- Servo and jig now share one supported-floor policy (jig ADR-0030), so the two
  sibling plugins behave consistently on adopter machines.

**Negative:**
- Contributors must remember the future-import convention and avoid 3.10+
  runtime APIs in shipped code (the CI leg is the backstop when they forget).
- Genuinely-3.10+ APIs must be version-gated rather than used freely.

**Neutral:**
- The 3.9 leg is import-coverage + test-exercised coverage, not full behavior
  coverage: a 3.10+ API on a code path that is both untested *and* invisible to
  ruff's version-aware lints could still slip through. This is the same
  untested-code blind spot that let the original regression ship — a bounded,
  known residual risk, not an implied guarantee. `ruff target-version=py39` is
  the static backstop for some unexercised branches.

## Alternatives considered

- **Declare 3.10/3.11 the floor; tell users to upgrade.** Free use of modern
  syntax and stdlib, but breaks the plugin on the default macOS interpreter —
  pushing setup friction onto users for a tool whose value is *reducing*
  friction. Rejected: it silently regressed once already precisely because no
  one verified the floor. (This was the prior, undeclared-but-real state:
  `requires-python = ">=3.11"`.)
- **Add a third-party backport dependency** (e.g. `tomli`) to run newer-stdlib
  code on 3.9. Rejected: servo is deliberately zero-dependency (stdlib only) —
  one dep is a precedent and a supply-chain surface. No shipped helper needs a
  3.11-only stdlib module anyway.
- **`typing.Optional` everywhere instead of the future import.** Works, but
  churns every annotation and loses the readable PEP 604 syntax. The future
  import defers annotations to strings at zero runtime cost, so it is the
  cheaper, less invasive convention. Rejected in favor of the future import,
  keeping `Optional` only for runtime-position unions.

## Verification

- Root-caused by running the full suite under the machine's default
  `python3` (3.9.6): 6 collection errors, all
  `TypeError: unsupported operand type(s) for |` at module import of the
  PEP-604-annotated helpers.
- Fix applied: `from __future__ import annotations` added to the nine affected
  shipped modules; `zip(strict=False)` dropped in the two agent-loop test call
  sites (the kwarg was the default, so behavior is unchanged).
- Full suite green on **3.9.6** (1114 passed, 1 skipped — the skip is
  `spec-oracle/test_checks.py`'s `sys.stdlib_module_names` case, version-gated
  to 3.10+) and on **3.13** (1115 passed, 13 subtests) — run via a stdlib venv
  + pytest under each interpreter.
- `ruff==0.15.17 ruff check .` clean with `target-version = "py39"`.
- CI matrix now `["3.9", "3.11", "3.12"]`; `requires-python = ">=3.9"`.

## References

- jig **ADR-0030** — Minimum supported Python is 3.9 (the sibling-plugin
  decision this mirrors).
- [ADR-0007](adr-0007-align-release-with-jig.md) — the align-with-jig posture
  this continues.
- Spec 009 (ci-hardening) — the CI matrix + ruff lint gate this amends.
- PEP 563 / `from __future__ import annotations`; PEP 604 (union types);
  PEP 618 (`zip(strict=)`).
