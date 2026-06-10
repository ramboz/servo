---
status: DONE
dependencies: []
last_verified:
---

## Slice 002-03 — manifest-aware

**Goal:** Refuse to run against a target that lacks `.servo/install.json` (the manifest spec 001 writes). Add a `gate.py audit <target>` subcommand that prints the manifest's `installed_tier`, `signals`, and `components` so callers can introspect the install without running the oracle. End-to-end value: 002-03 closes the contract that "if the gate runs, this is a servo install, not a hand-rolled `oracle.sh`."

**DoR:**
- ✅ Slice 002-02 DONE
- ✅ Manifest schema frozen by spec 001-03 (keys: `servo_version`, `timestamp`, `installed_tier`, `signals`, `components`)
- ✅ Decision: gate refuses on missing manifest; runs on present-but-stale manifest (staleness is a future concern, not a gate concern)

**Acceptance Criteria:**

1. **Refusal on missing manifest.** If `<target>/.servo/install.json` does not exist, `gate.py <target>` exits **2** with a stderr message naming the absent manifest. The user is told to run `/servo:scaffold-init` first.
2. **Refusal on malformed manifest.** If the manifest exists but is not valid JSON, or is missing required keys (`installed_tier`, `components`), `gate.py` exits 2 with a stderr message naming the offending key.
3. **Audit subcommand prints manifest.** `gate.py audit <target>` exits 0 and prints a human-readable summary of the manifest: `tier`, `installed at`, `signals` (one per line), `components` (one per line, with weight). No oracle invocation.
4. **Audit `--json` mode.** `gate.py audit <target> --json` emits the manifest contents verbatim as JSON on stdout.
5. **Audit refusal modes mirror invocation refusal.** Audit also refuses on missing manifest / bad target with rc=2 and the same stderr shape.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _62/62 in `test_gate.py` (up from 39 at 002-02); 40/40 `test_scaffold.py` regression check; total 102 tests green._
- [x] Test coverage per AC: AC1→`MissingManifestTests` (5 tests), AC2→`MalformedManifestTests` (4 tests: bad JSON, non-object, missing `installed_tier`, missing `components`), AC3→`AuditTextOutputTests` (7 tests, including no-oracle-invocation sentinel verification), AC4→`AuditJsonOutputTests` (2 tests: verbatim manifest, no weight enrichment), AC5→`AuditRefusalTests` (5 tests, covers all four refusal reasons + schema_version).
- [x] Reviewer subagent review. _2026-05-18, PASS verdict. Six caveats: two fixed in-flight (one-line audit JSON, lowercase booleans); one logged to `refinement-todo.md` (manifest weights coupling); three documented below._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _New entry: "`gate.py audit` parses component weights from `oracle.sh` (soft template coupling)" — the manifest carries names only; weights live in oracle.sh until a future spec/ADR extends the manifest schema._

### Close-out (post-DONE)

- [ ] If the manifest schema needs a new key for gate's benefit (e.g., `oracle_path` override), record an ADR-candidate in `docs/architecture.md` rather than silently extending it. _Logged in refinement-todo (weights-in-manifest); revisit when spec 003 or a future template-shape change forces the question._

**Anti-horizontal-phasing check:** After this slice, the gate is the front door to *any* servo install introspection. A user with no oracle invocation in mind can still run `gate.py audit <target>` and see what's there. That makes 002 useful even when the project is paused mid-loop.

### Deviation log (after reconciliation)

**Slice 002-03 — implemented 2026-05-18.** 62 tests green in `test_gate.py` (up from 39 at 002-02 close-out); 40/40 scaffold regression intact. End-to-end dogfood: scaffold a tmp project with pytest → `gate.py audit <tmp>` prints `tier-0`, `installed: <ts>`, `signals: tests=true language=python`, `components: pytest (weight 1)`. `gate.py audit <tmp> --json` emits the manifest verbatim. `rm <tmp>/.servo/install.json` then `gate.py <tmp> --json` → `{schema_version: 1, exit_code: 2, status: env_error, reason: manifest_missing}`.

Deviations from spec text:

- **Component weights are parsed from `oracle.sh`'s `COMPONENTS=( "name:weight" )` array** (reviewer-noted, refinement-todo logged). The manifest stops at component names; AC #3 requires "components (one per line, with weight)". `_parse_component_weights` reads oracle.sh as a best-effort enrichment for text mode. Returns `{}` silently on any parse failure — audit then prints the component name with no weight, which is still useful. The clean long-term fix is to extend the manifest schema, but that touches the frozen 001-03 contract and warrants its own ADR. Tracked in `docs/refinement-todo.md` as "audit parses weights from oracle.sh (soft template coupling)".
- **Audit `--json` mode is one-line (not pretty-printed)** (reviewer-noted, fixed in-flight). First implementation used `json.dumps(manifest, indent=2)` — multi-line. Reviewer flagged the shape divergence from invocation `--json` (one-line per 002-02 AC #2) and from audit refusal-mode JSON (one-line via `_emit_summary`). Changed to `json.dumps(manifest)` (one-line) so the contract is uniform: every `--json` payload from the gate is one parseable line.
- **Signal booleans render lowercase in text mode** (reviewer-noted, fixed in-flight). First implementation interpolated booleans via f-string, yielding Python repr `True`/`False`. Reviewer noted the divergence from JSON's `true`/`false`. Fixed: text mode now emits `tests=true lint=false` etc. The dedicated f-string formatter (`'true' if v is True else 'false' if v is False else v`) only normalizes booleans; other types stringify unchanged.
- **Hand-rolled subcommand dispatch** (reviewer-confirmed clean). `main()` checks `argv[0] == "audit"` and dispatches to a separate argparse parser; otherwise the default gate parser handles bare `gate.py <target>`. Mirrors `scaffold.py`'s `detect` shape. The bare-positional form remains valid because argparse subparsers aren't introduced.
- **Manifest precondition fires between target validation and oracle existence check** (reviewer-confirmed). Order: target exists → is_dir → manifest exists → manifest parseable → oracle exists → oracle executable → invoke. A target with no manifest is rejected before the oracle is even consulted, which matches the AC #1 "this is a servo install, not a hand-rolled oracle.sh" framing.
- **Test setUps pre-seed a manifest** (reviewer-confirmed clean). The 002-01/02 test classes that exercise oracle invocation (`PassthroughTests`, `MissingOracleTests`, `UnexpectedExitTests`, `NonExecutableOracleTests`, `SummaryLineTests`, `JsonOutputTests`, `VerboseTests`, `UnparseableOracleTests`) all added `_make_manifest(self.target)` in setUp. This isolates each test class to its target failure mode (`MissingOracleTests` now tests oracle-missing with a valid manifest, not missing-everything).
- **Three new refusal reasons** (`manifest_missing`, `manifest_malformed`, `manifest_invalid_key`) round out the closed `reason` taxonomy first sketched in slice 002-02's deviation log. Both text and JSON modes carry these consistently.

**Reviewer caveats not addressed in-flight** (logged here for traceability):
- `test_stderr_directs_user_to_scaffold` (and equivalents) assert `scaffold-init` (no slash) rather than the full `/servo:scaffold-init`. Same loose-substring pattern flagged by 002-01 reviewer (already in `refinement-todo.md`). Not regressed by this slice; not blocking.
- `AuditTextOutputTests.test_components_show_weight_when_oracle_present` asserts `"1.5"` substring. Python's `{:g}` formatter would render `1.0` as `1` (no decimal). If a test ever lands a weight of exactly `1.0`, the substring assertion may pick up incidental matches. Defensible — production weights are tunable floats — but worth tightening if it bites.
- Pre-existing 002-01 / 002-02 entries in `docs/refinement-todo.md` still apply.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-18). All 5 ACs met with observable subprocess-driven tests; manifest schema producer/consumer agree; no regressions in `test_scaffold.py`; deviation log captures both the soft coupling and the two in-flight fixes.

---

