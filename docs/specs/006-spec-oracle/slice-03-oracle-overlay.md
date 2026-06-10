---
status: DONE
dependencies: []
last_verified: 2026-06-10
---

## Slice 006-03 — oracle-overlay

**Goal:** Compile a checked plan into an installable oracle overlay:
`oracle.sh.fragment` plus generated `checks.py`, with a score function
that can be added to the target's `oracle.sh` as a normal servo
component.

**DoR:**
- ✅ Slice 006-02 DONE.
- ✅ Spec 002 `gate.py` contract remains unchanged.
- ✅ `# SEED:` component convention from spec 001 is still the install
  mechanism.

**Acceptance Criteria:**

1. **Fragment generation.** The helper writes an `oracle.sh.fragment`
   containing a valid `# SEED:start spec_oracle_<id>` /
   `# SEED:end spec_oracle_<id>` block.
2. **Install command.** An explicit install mode adds the generated
   component to `oracle.sh` without disturbing existing baseline
   components.
3. **Score semantics.** The generated score is the check summary score;
   any env-error check returns oracle component rc=2.
4. **Ledger entries.** Each oracle run appends check evidence to
   `.servo/spec-oracles/<spec-id>/ledger.jsonl`.
5. **Gate compatibility.** `gate.py <target> --json` sees the overlay as
   an ordinary oracle component; no `gate.py` special case is required.
6. **Uninstall or disable path.** Users can remove or disable the
   overlay component without deleting the plan/check artifacts.

**DoD:**
- [x] All ACs pass; full test suite green.
- [x] Tests install the overlay into a temp servo-scaffolded target and
      verify `gate.py --json` pass/fail/env-error paths.
- [x] Reviewed by `reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.

### Close-out (post-DONE)

- [x] `docs/architecture.md` documents spec-oracle artifacts.
- [x] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, `/servo:agent-loop`
can optimize against spec-specific AC evidence using the existing gate
contract.

### Deviation log (after reconciliation)

Original ACs above are preserved; this records what changed during
implementation. Implemented 2026-06-10; 25 tests in
`skills/spec-oracle/test_oracle_overlay.py` (+6 engine tests in
`test_checks.py`); full suite 591 passed, 1 skipped (the skip is the
pre-existing shellcheck/Docker-daemon skip, unrelated to 006-03).

- **Engine extended in place (006-02 file), as forward-declared.** This slice
  added two things to `skills/spec-oracle/checks.py`: a `--score-only` mode and
  a per-row `ts` on `--ledger`. `--score-only` prints just the composite score
  and exits `2` iff any check env-errored, else `0` — **never `1`** — so the
  generated `score_spec_oracle_<id>` obeys the `oracle.sh` component contract
  (the THRESHOLD gate, not the component, decides pass/fail; rc=2 marks the
  component missing → oracle exits 2). Both were anticipated by 006-02's own
  deviation log ("`--ledger` are forward seams (used in 006-03)"). The default
  CLI behaviour (evidence JSONL + summary, exit 2/1/0) is unchanged.
- **`oracle_overlay.py` is the compiler/installer.** `generate` writes
  `oracle.sh.fragment` (the SEED block) and copies the engine to
  `.servo/spec-oracles/<id>/checks.py`; `install` splices the SEED block before
  the driver loop and registers `spec_oracle_<id>:<weight>` in `COMPONENTS`
  (idempotent — re-install replaces the block and refreshes the weight);
  `uninstall` removes both but keeps the artifacts (AC6).
- **Self-contained engine copy (drift seam → 006-04).** `generate` copies the
  engine into the target on every install so the overlay survives servo being
  uninstalled (project-owned artifact). Until slice 006-04 freezes and hashes
  these files, the copy can drift from the plugin's engine; the code comments
  flag this and 006-04 owns the freeze.
- **Component registered in `oracle.sh` only, not `install.json`.** The overlay
  adds itself to the oracle's `COMPONENTS` array but does not touch the manifest.
  `gate.py` never cross-validates the manifest's `components` against
  `oracle.sh`, so the unregistered component scores cleanly (AC5 needed no
  `gate.py` change). Consequence: `gate.py audit` lists the overlay's *weight*
  (parsed from `oracle.sh`) but not its *name* (the manifest is the name source).
  Manifest schema extension is the pre-existing deferred 002 item, not this slice.
- **Shell-safe component names + spec-id validation.** Hyphens in the spec id
  collapse to underscores for the shell function / `COMPONENTS` name
  (`006-spec-oracle` → `spec_oracle_006_spec_oracle`) while the
  `.servo/spec-oracles/<id>/` path keeps the original id. `spec_id` is validated
  against `^[A-Za-z0-9._-]+$` and must contain an alphanumeric, so it can never
  inject into the generated bash fragment or escape the spec-oracle directory
  (`.`/`..`/all-punctuation ids are rejected — review-driven hardening).
  *Known limitation:* the sanitiser could in theory collide two distinct ids
  (`a-b` and `a_b` → same component name); negligible for date-prefixed spec
  slugs, noted for a future guard.
- **Splice safety.** `install`/`uninstall` operate by regex on `oracle.sh` using
  lambda replacements (so the bash fragment's `\` line-continuations are never
  misread as `re.sub` escapes); the anchors are spec 001's template shape
  (`^weighted_sum="0"`, `COMPONENTS=\(`). Every install/uninstall path is
  asserted to leave valid bash via `bash -n`.

**Reconciliation review (inline):** deviation log checked against the diff
(faithful — no source-spec ACs or DoD rewritten); the two new files live under
`skills/spec-oracle/`, the engine edits are additive and forward-declared, and
the doc edits are scoped to this slice (the `architecture.md` spec-oracle line,
the board, and this deviation log). Scope to 006-04 (approval/freeze, source-spec
hash, artifact hashes, negative controls) is respected. Independent
`jig:reviewer` pass returned **PASS** on all six ACs with no blocking issues; its
non-blocking suggestions (reject traversal spec-ids, add a `generate` CLI test,
clarify the COMPONENTS-insert comment) were applied.

---

