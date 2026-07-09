# Refinement TODO

Decisions deferred during servo's own development (not the target-project refinement-todo that 001-04 will scaffold — that one lives in `<target>/.servo/refinement-todo.md`).

Each entry: heading, Deferred reason, Resolution trigger.

---

## ~~Shellcheck verification falls back to skip on dev machines~~ — RESOLVED 2026-05-15

**Resolution:** `scripts/shellcheck.sh` wraps both the local binary (preferred) and the `koalaman/shellcheck:stable` Docker image (fallback), exiting 127 only when neither is available. `ShellcheckTests.test_rendered_oracle_shellcheck_clean` now invokes the wrapper and skips only on exit 127, so on any dev box with Docker the assertion actually runs. Verified: 34/34 tests green with zero skips on this branch even though the local `shellcheck` binary is absent.

---

## ~~Jig-fallback failures are silent~~ — RESOLVED 2026-05-15

**Resolution:** `_jig_tdd_detect` now returns `(framework, status)` where status ∈ `{absent, success, failed, unknown}`. The four non-absent failure modes (timeout, OSError, non-zero exit, JSON decode, missing framework key, out-of-vocab framework) each emit a distinct stderr breadcrumb naming the failure cause. `detect_signals` consumes the status to set the manifest `detector` field to the detector actually *used* (jig only on `success`), not merely "jig present on disk". A silent jig regression is now impossible.

---

## No automated test for the jig-present detector path

**Deferred:** `JigFallbackTests` covers the no-jig branch for all five test frameworks; the jig-present branch is "exercised by manual smoke" per ADR-0001 and not gated. The normalization map (`framework` / `runner` / `name`) and the vocabulary check (`framework in TEST_COMPONENTS`) are untested.

**Resolution trigger:** First time `_jig_tdd_detect` regresses (or when servo gets a CI pipeline that can stand up a fake-jig fixture). Easy fix: write a `tmp/jig/skills/tdd-loop/tdd.py` shim in the test that prints a chosen JSON shape, point CLAUDE_PLUGIN_ROOT at that tmp, assert servo picks up the shim's framework name. Three test cases (one per accepted key, one for the out-of-vocab fall-through) close the gap.

**Surfaced by:** slice 001-03 reviewer pass; ADR-0001 acknowledges this gap explicitly.

---

## ~~Threshold default of 0.5 is arbitrary~~ — RESOLVED 2026-05-15 by slice 001-04

**Resolution:** Slice 001-04 emits a `Threshold` decision into every scaffolded `<target>/.servo/refinement-todo.md`, pinning `DEFAULT_THRESHOLD = 0.5` as a constant in `scaffold.py` (kept in sync with the template's static `0.5`) and quoting it back to the user along with a resolution trigger ("first time the oracle gate misfires"). The arbitrariness is now surfaced explicitly at the install site, not buried in servo's own dev notes.

---

## `DEFAULT_THRESHOLD` is duplicated between `scaffold.py` and the oracle template

**Deferred:** `scaffold.py:DEFAULT_THRESHOLD = 0.5` and `templates/oracle.sh.template:THRESHOLD="${THRESHOLD:-0.5}"` are two sources of truth. The refinement-todo quotes back the Python constant; the runtime oracle uses the bash literal. If either is ever changed without the other, the scaffolded install will quote a value back to the user that disagrees with what the script actually defaults to.

**Resolution trigger:** First proposal to change the default threshold, OR the next template refactor that touches the substitution markers. Introduce a `{{THRESHOLD_DEFAULT}}` placeholder in the template and have `_render_oracle` substitute `str(DEFAULT_THRESHOLD)` at scaffold time. Add a test that asserts the rendered oracle's literal default matches the constant.

**Surfaced by:** slice 001-04 reviewer pass.

---

## "Custom signals" deferral category not emitted

**Deferred:** Slice 001-04's goal text named four deferred-decision categories (weights, threshold, ambiguous, **custom signals**), but no AC required the fourth and the implementation only emits the first three. The user's path to "add your own signal" today is the `# SEED:` block convention surfaced in the template's comment header and `README.md` — not the refinement-todo.

**Resolution trigger:** First user feedback that `refinement-todo.md` should explicitly invite custom signals (especially in the no-signals case, where the current refinement-todo has only Threshold). When that lands, add a `## Custom signals` block citing the `# SEED:` convention and `README.md#adding-a-component`. Emit unconditionally, or gate on `len(components) == 0`.

**Surfaced by:** slice 001-04 reviewer pass.

---

## Env-error test bypasses production code path

**Deferred:** Slice 001-02 AC #3 ("env error distinguishable from below-threshold") is tested by `EnvErrorDistinguishableTests`, which **patches the scaffolded `oracle.sh`** to inject a component returning `rc=2`. That's a fair structural test of the driver's exit-2 propagation, but the *shipped* `placeholder` component never returns 2 — so no naturally-scaffolded output exercises the env-error path today. Acceptable here because no real components exist yet (signal detection is 001-03), but the gap should close when real components land.

**Partial resolution (2026-05-15, slice 001-03):** Real shipped components now exist (pytest, vitest, jest, cargo, go, eslint, ruff) and each documents a `return 2` path on missing tool. `JigFallbackTests` exercises the natural detection path but does not execute the scoring functions, so the env-error exit-2 contract is still verified only by the patched-template test in `EnvErrorDistinguishableTests`. Leaving the entry open: closure requires an integration test that scaffolds a target with (say) pytest detected, runs the oracle with `PATH` stripped, and asserts exit 2 + a stderr mention of the component name.

**Resolution trigger:** Next time the env-error path regresses, OR opportunistically when servo gets a CI pipeline that can cheaply isolate `PATH`. The patched-template test stays as a driver-mechanics check; the new test would close the production-code-path gap.

**Surfaced by:** slice 001-02 reviewer pass.

---

## SKILL.md anti-greediness tests have soft negative-trigger checks

**Deferred:** `DescriptionBoundsTests.test_negative_triggers_in_description` only asserts that the strings "oracle" and "score this code" *appear somewhere* in the description and that some exclusion word ("do not" / "don't" / "skip") is present. A future broadening that added "review my code" or "score tests" as a *positive* trigger would still pass — the test never enforces that those phrases live inside a do-not block specifically.

**Resolution trigger:** Next time SKILL.md gets edited, OR when servo grows a second skill with its own surface tests. Tighten the assertion to: split the description into "fire" and "do not fire" sections by marker, assert positive phrases appear in the fire section only, assert negative phrases appear in the do-not section only.

**Surfaced by:** slice 001-05 reviewer pass.

---

## SKILL.md body tests check substrings globally, not by section

**Deferred:** `QAQuestionsTests`, `SkippabilityTests`, and `RefusalSurfacingTests` lowercase the entire SKILL.md and check for substring presence anywhere — so a SKILL.md with the right keywords in the wrong sections (Q&A options dumped in a comment, trigger phrases in the body instead of the description) could still pass. Only `DescriptionBoundsTests` correctly isolates the YAML frontmatter via regex.

**Resolution trigger:** Same as above. Extract a `_section(text, heading)` helper that scopes substring checks to the named section, then refactor the three body tests to use it.

**Surfaced by:** slice 001-05 reviewer pass.

---

## `test_signal_killed_remapped_to_two` assertion is platform-loose

**Deferred:** `UnexpectedExitTests.test_signal_killed_remapped_to_two` asserts `"unexpected code"` in stderr but doesn't pin the exact code (143 on Linux/macOS via `128 + signo`, but could be negative on platforms where Python reports `-signo` for signal-killed children). The reliance on the substring match is defensible — the gate's contract is "rc=2 with some unexpected-code message" — but two parallel assertions (one for positive `128 + signo`, one tolerating negative returncode) would be a stricter cross-platform guarantee.

**Resolution trigger:** First CI run on a platform where Python reports a negative returncode for signal-killed children, OR the next time the test is touched for any reason.

**Surfaced by:** slice 002-01 reviewer pass (`jig:reviewer`, PASS verdict).

---

## `gate.py` does not guard against non-regular-file `oracle.sh`

**Deferred:** `gate.py` checks `oracle.exists()` and `os.access(oracle, os.X_OK)` but does not verify the path is a regular file. A target with `oracle.sh` as a directory, FIFO, device file, or dangling symlink would pass the existence check, fail at subprocess.run, and surface an OSError message (caught by the generic `_refuse` handler — so rc=2 with `"failed to invoke oracle.sh: ..."`).

End-state behavior is still rc=2, which is the contract — but the error message is less actionable than the dedicated chmod-hint refusal. Adding `oracle.is_file()` would surface a clearer "oracle.sh is not a regular file" message.

**Resolution trigger:** First report of a confused user staring at "failed to invoke oracle.sh: ..." stderr because their `oracle.sh` is somehow a directory. Cheap fix when it lands.

**Surfaced by:** slice 002-01 reviewer pass (`jig:reviewer`, PASS verdict).

---

## Quality-gate surface tests inherit loose-substring pattern from scaffold-init

**Deferred:** `skills/quality-gate/test_skill_surface.py` uses the same loose-substring assertions as `skills/scaffold-init/test_skill_surface.py` (`test_recovery_pointers_present` asserts `"longer"` for the timeout recovery hint; positive triggers checked as substrings; etc.). A future docs reword could break the test without changing behavior. Also: surface tests only assert 6 of the 11 `reason` codes (`manifest_missing`, `oracle_missing`, `oracle_not_executable`, `timeout`, `unparseable_oracle_output`, `unexpected_exit`) — the remaining 5 (`target_missing`, `target_not_directory`, `manifest_malformed`, `manifest_invalid_key`, `invocation_failed`) are documented in SKILL.md but not test-asserted.

**Resolution trigger:** Same family as the pre-existing 001-05 entries above ("SKILL.md anti-greediness tests have soft negative-trigger checks" + "SKILL.md body tests check substrings globally"). Bundle the fix: extract a `_section(text, heading)` helper and a tighter trigger-assertion pattern, then update both `scaffold-init/test_skill_surface.py` and `quality-gate/test_skill_surface.py` together. Broader reason-code coverage is a separate one-line addition to `test_reason_field_documented`'s tuple.

**Surfaced by:** slice 002-05 reviewer pass (`jig:reviewer`, PASS verdict).

---

## Spec 003 spike open questions (Q1, Q2, Q5, Q6) await live-claude verification

**Deferred:** The pre-spec research [spike](specs/003-agent-loop/spike.md) flagged six open questions; Q3 and Q4 were resolved in the spec body. Q1, Q2, Q5, Q6 were tagged "await empirical verification at their respective slices" — but every slice 003-01..05 test uses a mock-claude harness via PATH injection (the AC8 contract), so no slice has actually exercised a live `claude -p` invocation against the spike's predictions.

The four still-open questions:

- **Q1: `terminal_reason` taxonomy from `claude -p` JSON output.** Spike captured `terminal_reason="completed"`. Other plausible values: `budget_exceeded`, `error`, `interrupted`, `timeout`. Slice 003-02's cost-ceiling logic assumes the mock harness's `"completed"`; an unexpected real-world value falls into the loop's "claude-terminal-reason-pass-through" branch (per-iter JSON emits whatever claude says) but doesn't drive halt logic — the cumulative tracking is the brake.
- **Q2: `stop_reason` taxonomy.** Spike captured `stop_reason="end_turn"`. Other Anthropic-API-named values: `max_tokens`, `tool_use`, `stop_sequence`, `pause_turn`. Less load-bearing than Q1; the loop doesn't branch on `stop_reason` today.
- **Q5: `--max-budget-usd` halt granularity.** Does `claude -p --max-budget-usd X` clean-halt before the next API call would exceed budget, or partway through with a partial response? Slice 003-02's cumulative tracking handles either case (the per-iter cost is summed regardless), but the per-iter `--max-budget-usd` defense-in-depth floor (`MIN_BUDGET_FLOOR_USD=0.01`) was picked conservatively without empirical data.
- **Q6: `--agent <name>` + permissions inheritance.** When `loop.py` invokes `claude --agent runner -p "..."`, does the agent's own `tools:` frontmatter authoritatively narrow the toolset, or does the parent invocation's `--allowedTools` / `--disallowedTools` (if any) intersect with the frontmatter? Slice 003-05's `runner.md` and `judge.md` declare their own `tools:` frontmatter and the loop does NOT pass parent-level `--allowedTools`; the assumption is "frontmatter authoritative." Untested against live `claude -p`.

**Resolution trigger:** First live `claude -p` invocation against a real servo target — either (a) a user runs `/servo:agent-loop` and reports an unexpected behavior, or (b) dogfooding for spec 004 / 005 surfaces a difference. When triggered, update the relevant slice's deviation log and either keep the spike's assumption documented or amend `loop.py` to match observed reality. **A note:** the spec text at `docs/specs/003-agent-loop/spec.md` mentions "all five open questions from spike.md 'Open questions' are either resolved..." — the count is six (Q1–Q6); Q3 / Q4 resolved in spec; Q1, Q2, Q5, Q6 deferred here.

**Surfaced by:** Slice 003-05 reconciliation review (`jig:reviewer`, 2026-05-20). The reviewer flagged that no slice empirically verified the spike's spike-shape predictions, despite the spike's "verification at the slice" promise. Deferring rather than blocking close-out because the entire spec was built on the mock-harness assumption and the spike's central question ("loop driver subprocesses claude, parses JSON, decides") was validated in vitro across 5 slices.

---

## Scaffold-init does not write `<target>/.gitignore`

**Deferred:** Slice 003-04 (checkpoint-resume) ships per-run state at `<target>/.servo/runs/<run-id>/state.json`. The spec's close-out item asks: "`.gitignore` updated to ensure `<target>/.servo/runs/` is ignored on the target — confirm spec 001's scaffold already adds this; if not, file a refinement-todo." `skills/scaffold-init/scaffold.py` does not currently touch `<target>/.gitignore`, so a target that runs `/servo:scaffold-init` followed by `/servo:agent-loop` will start checking in `<target>/.servo/runs/*/state.json` (and any future race / hook artifacts) unless the user manually adds the line.

`docs/architecture.md` "Runtime artifacts" already states the paths "are reserved (in `.gitignore`)" — that statement is aspirational, not enforced by the scaffolder.

**Resolution trigger:** First user report that servo's runtime artifacts polluted their commits, OR opportunistically when the scaffolder grows another out-of-band artifact (e.g., spec 005's `.servo/races/`). The shape of the fix: extend `scaffold.py:_write_artifacts` to append a `.servo/runs/`, `.servo/races/`, `.servo/refinement-todo.md`, `.servo/install.json` block to `<target>/.gitignore` — idempotent (skip if the block already exists), no-op if `<target>/.gitignore` doesn't exist (target's choice not to track gitignore is the target's call). Add a test under `test_scaffold.py` that asserts the block lands.

Target-side .gitignore is the target's concern, not servo's, but the scaffolder is the natural place to suggest the additions — same shape as jig's scaffold-init nudging `.claude/` paths.

**Surfaced by:** Slice 003-04 reconciliation review (`jig:reviewer`, 2026-05-20). The spec close-out item explicitly contemplated this path.

---

## `DEFAULT_CONTEXT_FILL_THRESHOLD = 0.75` is a guess

**Deferred:** `loop.py`'s context-fill refusal threshold defaults to 0.75 (75%) — picked as the midpoint of the spike's observed 60–75% range across mixed iteration loads, with no real-world tuning data. A loop running short, focused turns may reasonably tolerate fills above 0.75 before output degrades; a loop with heavy tool use that produces long agent responses may degrade well below 0.75. Without empirical data, 0.75 could be 20 percentage points too generous (false-negatives: garbage output sneaks through) or too tight (false-positives: legitimate iterations refused).

The `--context-fill-threshold` flag is the user's escape hatch (`0` disables; any value in [0.0, 1.0] tunes). But the default ships in the slice 003-03 contract and downstream slices/callers inherit it.

**Resolution trigger:** First real-world iteration data — either (a) a user reports that 0.75 produced degraded output on the iteration before the gate fired, or (b) servo's own dogfood (slice 003-05 + spec-level end-to-end) shows a different right-sized default. When triggered, either tune the default (and document in `docs/architecture.md` "Project vs servo-core split") OR add the threshold to the `<target>/.servo/refinement-todo.md` deferred-decision set so each scaffolded install gets a chance to override based on the target's workload shape.

**Surfaced by:** Slice 003-03 implementation (`/jig:spec-workflow`, 2026-05-19). DoR's "Decision: threshold default 0.75. **Flagged in `docs/refinement-todo.md` for tuning** once real-world iteration data accumulates." pre-committed to landing this entry alongside the slice.

---

## `DEFAULT_PER_ITER_BUDGET_USD = 1.00` is a guess

**Deferred:** `loop.py`'s per-invocation `--max-budget-usd` fallback when `--cost-ceiling 0` disables cumulative tracking defaults to $1.00. The value is a "sane upper bound for one agentic turn" picked without real-world data — analogous to the `DEFAULT_CLAUDE_TIMEOUT_SECONDS = 1800` guess below. A simple iteration may burn $0.05; a complex one with heavy tool use may approach $1.00 or beyond. Without empirical data, $1.00 could be 10x too generous (one runaway turn still burns $1) or 2x too tight (false-positive `budget_exceeded` on legitimate heavy iterations).

The flag is the user's escape hatch (`--cost-ceiling N` with N > 0 then sets the per-iter cap to remaining budget). But the `--cost-ceiling 0` mode is where the fallback ships and downstream slices/callers will inherit it.

**Resolution trigger:** First real-world iteration cost data — either (a) a user reports that $1/iter isn't enough for their workflow, or (b) servo's own dogfood (slice 003-05 + spec-level end-to-end) shows a different right-sized default. When triggered, either tune the default (and document in `docs/architecture.md` "Project vs servo-core split") OR introduce a `--per-iter-budget` CLI flag if a single fixed default proves insufficient.

**Surfaced by:** Independent reviewer pass on slice 003-02 (`jig:reviewer` subagent, 2026-05-19). The reviewer flagged it as a non-blocking caveat alongside the existing `DEFAULT_CLAUDE_TIMEOUT_SECONDS` entry — both are "best guess" defaults waiting on tuning data.

---

## `DEFAULT_CLAUDE_TIMEOUT_SECONDS = 1800` is a guess

**Deferred:** `loop.py`'s per-invocation `claude -p` timeout defaults to 1800s (30 min). The value was picked without real-world iteration data — it's a generous upper bound chosen to be "long enough for substantial agentic turns with tool use, short enough that an unattended loop won't hang for days if claude wedges." A real-world loop running on a complex target may regularly take 5–20 minutes per iteration (compile cycles, test runs, large code edits); a simple target may finish in seconds. Without data, 1800s could be 10x too generous (wasteful when claude wedges in CI) or 5x too tight (false-positive timeouts on heavy iterations).

The `SERVO_CLAUDE_TIMEOUT` env var is the user's escape hatch today; `0` disables the bound entirely. But the default ships in the slice 003-01 contract and downstream slices (003-02 cost ceiling, 003-04 state file) inherit it.

**Resolution trigger:** First real-world iteration data — either (a) a user reports that 1800s isn't enough for their workflow, or (b) servo's own dogfood (slice 003-05 + spec-level end-to-end) shows a different right-sized default. When triggered, either lower the default to a tighter value (and document the tradeoff in `docs/architecture.md` "Project vs servo-core split") OR introduce a `--claude-timeout` CLI flag if env-var-only proves insufficient.

**Surfaced by:** PR-review pass on slice 003-01 (multi-perspective `pr-review` skill, 2026-05-19). The reviewer flagged "no timeout on `claude -p` subprocess" as a Should-Fix reliability gap; slice 003-01 closed the gap by landing the timeout, but the picked default needs tuning data.

---

## ~~`SERVO_VERSION` constant is dead code in `gate.py`~~ — RESOLVED 2026-05-19

**Resolution:** Removed in the pre-003-03 cleanup pass. `skills/quality-gate/gate.py` no longer declares `SERVO_VERSION`; the constant lives only in `skills/scaffold-init/scaffold.py` where it's actually used (manifest write). 75/75 `test_gate.py` still green post-removal.

---

## ~~ADR-0004 run-id precision: prose says "millisecond" but example uses seconds~~ — RESOLVED 2026-05-19

**Resolution:** Picked path (a) from the original entry — keep seconds-precision in the implementation (matches the example and the test regex) and amend ADR-0004's prose to match. Three spots in `docs/decisions/adr-0004-session-state-file-format.md` were updated: the "Run-id format" sentence, the collision-policy paragraph, and the Neutral consequence bullet. A new sentence at the end of the collision-policy paragraph names millisecond precision as the documented escape hatch if spec 005's parallel-variant fan-out ever surfaces a real collision rate the seconds window can't absorb — so future bumps don't need a new ADR. Slice 003-04 inherits the frozen seconds-precision format with no further reconciliation work.

---

## `gate.py audit` parses component weights from `oracle.sh` (soft template coupling)

**Deferred:** The manifest written by `scaffold.py` carries component names but not weights (the per-component weight lives only in the scaffolded `oracle.sh`'s `COMPONENTS=( "name:weight" )` array). `gate.py audit` enriches the text-mode component listing with weights by parsing oracle.sh via `_ORACLE_COMPONENT_ENTRY_RE`. This is a best-effort coupling — if `templates/oracle.sh.template` ever changes its COMPONENTS array shape, audit will silently fall back to no-weight rendering (the function returns `{}` on any parse failure).

The clean fix is to extend the manifest schema to carry weights directly (`{"components": [{"name": "pytest", "weight": 1.0}, ...]}`). That requires touching spec 001 (the manifest contract was frozen at 001-03) and probably warrants an ADR ("Quality-gate extends manifest schema to include component weights"). Deferred until the coupling actually breaks or a future spec wants weights for another reason (e.g., spec 003 agent-loop wanting to log per-component scores per iteration).

**Resolution trigger:** Either (a) a future template-shape change exposes the coupling, or (b) spec 003+ requires manifest-readable weights. When triggered, write the ADR and amend `_install_manifest()` in `scaffold.py` to emit the richer shape; the gate's `_parse_component_weights` becomes dead code and can be deleted.

**Surfaced by:** slice 002-03 reviewer pass (`jig:reviewer`, PASS verdict). Implementer also flagged the coupling in `_parse_component_weights` docstring.

---

## spec-oracle family classification is a heuristic first pass

**Deferred:** Slice 006-01's `oracle_plan.py` classifies each AC into a check family with a deterministic, ordered keyword/regex rule set (`_classify_family`). This is intentional for v1 — the dogfood fixtures (AC6) need stable, offline behaviour, and the spec's principle is "deterministic checks remain the source of truth." Two known gaps follow from that choice: (a) the spec's non-goal anticipates a **model-assisted classification/candidate-generation pass** that is not built; (b) on real specs the keyword table under-covers — dogfooding the classifier on servo's own (meta) spec 006 lands only ~26% of ACs in deterministic families, and prose that *enumerates* family names (e.g. an AC that lists "…archive inventory…") false-positives on that family. The generated `plan.md` is explicitly **reviewable**, so a human corrects misclassifications; perfect first-pass accuracy is not the v1 bar.

**Resolution trigger:** When 006-02..006-05 dogfood the planner on jig 046/047 and the residual/false-positive rate is high enough to slow review, OR when an EDD spec (ADR-0005) needs a model-assisted candidate pass. Then either grow the ordered rule table (the documented extension point) and/or add an optional model-assist layer behind a flag, keeping the deterministic rules as the source of truth. Add fixtures for the family-name-enumeration false-positive and any new heuristics.

**Surfaced by:** slice 006-01 implementer (model-assist deferral) + `jig:reviewer` PASS verdict (heuristic coverage / docstring-claim accuracy).

---

## spec-oracle AC extraction has two structural blind spots

**Deferred:** `extract_acs` in `oracle_plan.py` (slice 006-01) finds numbered ACs inside an "Acceptance Criteria" section and joins their continuation lines into the full statement. Two Markdown shapes are mishandled: (a) a continuation line that *begins* with bold (`**Note:** …`) matches the bold-pseudo-heading terminator and would close the section early, dropping the rest of that AC; (b) a nested numbered sub-list inside an AC item (`   1. sub-point`) matches the numbered-item regex and is miscounted as a sibling AC. Neither shape appears in the AC6 fixtures or in any current servo spec, so this is latent.

**Resolution trigger:** First real spec whose ACs use either shape (or a reviewer/dogfood run that mis-extracts). Fix options: restrict the bold-terminator to a known label set (`DoD`/`DoR`/`Goal`/`Anti-`/`Close-out`) while an AC is open; and/or only treat top-level (unindented) numbered items as new ACs. Add a fixture per shape.

**Surfaced by:** slice 006-01 `jig:reviewer` pass (tagged `[nit]`, non-blocking).

---

## spec-oracle `markdown_links` resolves only inline links

**Deferred:** Slice 006-02's `markdown_links` primitive in `checks.py` parses
only inline `[text](target)` links (`_MD_LINK_RE`). Reference-style links —
`[text][ref]` with a separate `[ref]: target` definition — are not collected,
so a broken reference-style local link would not be caught (it is silently
treated as having no link target). No AC6 fixture and no current servo doc uses
reference-style links, so this is latent.

**Resolution trigger:** First spec/doc whose generated-artifact links use the
reference style, OR a dogfood run that misses a broken reference link. Fix:
add a second pass that harvests `^\[ref\]:\s*target` definitions and resolves
the `[text][ref]` usages against them; add a fixture with both a resolving and
a broken reference-style local link.

**Surfaced by:** slice 006-02 `jig:reviewer` pass (PASS verdict; flagged as a
disclosed known-limitation, non-blocking).

---

## spec-oracle approval does not require a negative control per check

**Deferred:** Slice 006-04's `approve` (in `oracle_overlay.py`) runs a check's
negative control only when the check carries a `negative_control` **dict**; a
check with no control, or with `negative_control: "not_applicable"`, is approved
without a falsifiability proof. The parent spec's guardrail is stronger — "the
first version can mark `negative_control: not_applicable` for command checks that
already invoke an existing suite, but **new generated invariants need controls**"
— so a new `text_invariant` / `file_presence` / `json_contract` invariant with no
control can currently be frozen `approved` while being vacuously un-failable.
Two coupled gaps: (a) the planner (006-01) does not yet auto-generate negative
controls, so controls are hand-authored or absent; (b) `approve` does not
distinguish "command wrapping an existing suite" (legitimately `not_applicable`)
from "new invariant with no control" (should be blocked).

**Resolution trigger:** When 006-05 dogfoods real jig 046/047 plans and an
un-falsifiable invariant slips through, OR when the planner gains a
control-generation pass. Fix: teach `approve` to require a `negative_control`
(dict) for non-`command` families, allowing explicit `not_applicable` only with a
recorded reason; and/or have the planner emit candidate controls. Add fixtures
for "new invariant missing control → approval refused".

**Surfaced by:** slice 006-04 `jig:reviewer` pass (needs-changes → resolved):
the `checks.json`-integrity gap was hardened in-slice with an
`approved_content_hash` tripwire; this negative-control leniency was dispositioned
as spec-sanctioned v1 behaviour and deferred here.

---

## meta-judge below-threshold hint lacks per-component failing-score evidence

**Deferred:** Slice 004-01's meta-judge hint (`templates/meta-judge.sh.template`)
names `composite` + `threshold` on a below-threshold block, plus any `missing`
components. But `gate.py --json` exposes only `composite` / `threshold` /
`missing`, and the stock `oracle.sh.template` emits `missing` **only on its
env-error (exit-2) path** (it `exit 2`s before computing the composite). So on a
real below-threshold (exit-1) nudge, `missing` is always empty and the hint
cannot name *which* components scored low — the agent is told "0.42 < 0.50" but
not where to look.

**Resolution trigger:** When dogfood (004-05) or real interactive use shows the
bare composite/threshold hint is too thin to steer the agent. Fix lives in
spec 002, not 004: have `gate.py --json` surface per-component scores (e.g. a
`components: [{name, score, weight}]` array), and the oracle template print
per-component scores on the pass/below path; then the meta-judge names the
lowest-scoring components. Slice 004-01 already amended AC4 to match today's
reality and added a defensive test for the `missing`-present case.

**Surfaced by:** slice 004-01 `jig:reviewer` pass (blocker #1): the original AC4
promised "failing/missing components" but the test masked the gap with a gate
payload (`status=below_threshold` + `missing=[…]`) the stock oracle never emits
on exit 1.

---

## `install` does not refresh an already-installed `meta-judge.sh` on a servo upgrade

**Deferred:** Slice 004-03 made `hook.py install` write the meta-judge script
**only when absent** — so a user-customized `meta-judge.sh` survives re-install
(the slice's non-destructive promise; spec.md calls the script
"user-customizable") and a deleted script self-heals. The trade-off: when servo
ships a newer `templates/meta-judge.sh.template`, re-running `install` over an
existing (servo-written) script will **not** refresh it — the stale script keeps
running. The interim upgrade path is `uninstall` (004-04) then `install`.

**Resolution trigger:** When 004-04 lands `uninstall` (making the
`uninstall` + `install` upgrade path real and documentable), or the first time a
`meta-judge.sh.template` change actually needs to reach already-installed
targets. Cheap options when triggered: an explicit `install --refresh-script`
flag, or stamping the template with a version the installer compares (and offers
to bump) — distinguishing a servo-pristine script (safe to overwrite) from a
user-edited one (must not clobber).

**Surfaced by:** slice 004-03 implementation (write-if-absent decision) and its
`jig:reviewer` pass (decision #2 dispositioned in-scope, trade-off flagged for a
future upgrade slice).

---

## ~~`actionable_reason` mis-codes an event-disqualified CI run as `ci_non_default_branch`~~ — RESOLVED 2026-06-15

**Resolution:** Added `REASON_CI_NON_ACTIONABLE_EVENT = "ci_non_actionable_event"` and reordered `_classify_ci` to check the event gate **first** — a non-`{push, schedule}` run (e.g. `pull_request`) now returns `ci_non_actionable_event` regardless of branch, so the reason names the real disqualifier. The branch gates run only for actionable events, yielding a clean non-overlapping taxonomy: `ci_non_actionable_event` / `ci_default_branch_unknown` / `ci_non_default_branch` / `ci_default_branch`. ADR-0010's `actionable_reason` vocabulary line extended with the new code. `test_ci_pull_request_event_not_actionable` now asserts `ci_non_actionable_event`, and a new `test_ci_non_actionable_event_takes_precedence_over_branch` pins the event-first precedence when both gates fail. 112/112 heartbeat tests green; ruff clean. Closed ahead of the 011-03 dispatch consumer (first half of the resolution trigger).

**Surfaced by:** slice 011-02 craft review (`jig:reviewer`, `[nit]`, PASS verdict).

---

## Triage by-status tally is computed in two places

**Deferred:** Slice 011-02's `_status_counts` (consumed by the `inbox.md` markdown view) and the inline by-status tally in `_summarize_inbox` (the `status` verb) compute the same status histogram independently. A future status-value change must touch both or they drift.

**Resolution trigger:** Next time either read surface's status tally changes, or a fifth `status` value is added. Extract a shared `_tally_by_status(records)` helper both consume.

**Surfaced by:** slice 011-02 craft review (`jig:reviewer`, `[nit]`, PASS verdict).

---

## `heartbeat.py status` best-effort-skips torn JSONL lines (no strict mode)

**Deferred:** The `status` read path tolerates an unparseable `inbox.jsonl` line by skipping it (never gates — closed `{0,2}`), a deliberately friendly read for a hand-editable artifact. There is no strict-read mode that would rc=2 on any torn line.

**Resolution trigger:** First time a silently-skipped torn line masks a real corruption a human needed to see, OR when a consumer (011-03/011-04) needs a guaranteed-complete read. Add an opt-in `--strict` that refuses rc=2 on any unparseable line.

**Surfaced by:** slice 011-02 implementation (deliberate friendly-read choice, flagged for revisit).

---

## No fixture for a mixed file of two *known* versions (e.g. v1 + v2)

**Deferred:** `SchemaMigrationTests` covers the higher-unknown refusal (`schema_version_unsupported`, e.g. v2+v3) and the lower-only warn-and-display, but the `schema_version_mixed` rc=2 path for two *known* ≤current versions (v1+v2 on the `status` read path) has no dedicated fixture — the higher-unknown branch happens to satisfy the AC1 mixed assertion.

**Resolution trigger:** First `schema_version` bump beyond 2 that makes a mixed-known file plausible, OR opportunistically when `SchemaMigrationTests` is next touched. Add a v1+v2 fixture asserting `schema_version_mixed` rc=2.

**Surfaced by:** slice 011-02 implementation + compliance review (`jig:reviewer`, PASS verdict).

---

## ~~Reciprocal "servo-available" breadcrumb for jig's `slice-land` pull-hint~~ — RESOLVED 2026-06-18

~~**Deferred:** jig's `slice-land prepare` wants to nudge a user toward `/servo:scaffold-init` when servo is available on the machine but the *current project* is not yet servo-scaffolded (no `.servo/`). jig cannot reliably detect the servo **plugin** itself: jig's spike (jig spec 072-03) found no signal that is at once documented/supported, install-method-robust, host-agnostic, subprocess-free, and non-forcing — `~/.claude/plugins/installed_plugins.json` is an undocumented internal that misses local-clone installs (including this maintainer's own servo clone, which appears in no registry), `claude plugin list` is a subprocess, and a `plugin.json` dependency would force servo onto every jig user. The agreed direction (human, 2026-06-15) is a **reciprocal servo-side breadcrumb**: servo writes a small, host-agnostic "servo is available here" marker at install/scaffold time that jig reads with a plain filesystem `stat` (no subprocess, no servo invocation). servo owns the contract — mirroring [ADR-0004](decisions/adr-0004-session-state-file-format.md)'s "the writer owns the cross-plugin format" precedent (ADR-0004 already documents jig reading `.servo/runs/*/state.json`).~~

**Resolution trigger:** Write a reciprocal servo-side ADR defining the breadcrumb's exact path + format, then emit it from servo's install/scaffold path. Constraints: (a) host-agnostic location — NOT under `~/.claude/` (Claude-Code-specific and `CLAUDE_CONFIG_DIR`-relocatable); (b) written for a **local-clone** servo user too, not only marketplace installs (the exact gap that sank jig's plugin auto-detection); (c) cheap + read-only for the consumer. Once defined + emitted, jig spec 072-02 (reshaped, currently blocked on this) consumes it: servo-available AND no project `.servo/` → nudge.

**Surfaced by:** jig spec 072 — 072-01 shipped the present-`.servo/` pull-hint (jig `land.py prepare`); 072-03 spike found plugin auto-detection NO-GO; 072-02 was reshaped onto this breadcrumb and is blocked on this servo-side work. Cross-refs: jig ADR-0022 Scope ("a reciprocal servo-side ADR — servo's call"), jig `docs/inbox.md` 2026-06-15.

**Resolved by:** [ADR-0013: Servo availability breadcrumb](decisions/adr-0013-servo-available-breadcrumb.md).

---

## Worktree retention / GC for `.servo/dispatch/` is unbounded

**Deferred:** slice 011-03 dispatch creates a fresh linked worktree per candidate at `<target>/.servo/dispatch/<finding_id>/` and **retains** it (v1) so a `passed` candidate's proposed fix is inspectable/landable and its `outcome.run_id` correlates. Nothing bounds the number of retained worktrees + branches, so a long-lived scheduled target accumulates `.servo/dispatch/*` (and `servo/heartbeat/*` branches) without limit. A `tried`/`passed` finding is never re-dispatched, so a given finding's worktree is created once — but distinct findings across many heartbeats grow the set unboundedly.

**Resolution trigger:** First target where `.servo/dispatch/` growth is a disk/clutter problem, OR when 011-04's `run` verb lands (natural place to add a retention knob). Options to weigh: GC-on-completion (lose inspectability), retain-only-on-`passed` (keep the landable ones, prune `tried`/`env_error`), or a `--keep-last N` / age bound. A `heartbeat.py gc <target>` verb or a `--prune` flag on `dispatch`/`run` would `git worktree remove` + delete the branch for evicted entries.

**Surfaced by:** slice 011-03 (Out-of-scope + Open questions: "Worktree + result lifecycle"); DoD-required follow-up.

---

## Does the dispatched loop commit its fix? (landable branch vs working-tree diff)

**Deferred:** 011-03 dispatches `loop.py` into the worktree on branch `servo/heartbeat/<finding_id>` but does not decide whether the loop **commits** its fix. If the loop commits, the branch is directly landable (cherry-pick / merge / PR); if it leaves a dirty working tree, a human reconstructs the fix from the worktree diff. The dispatch contract deliberately does not depend on either (it records `outcome.run_id` and retains the worktree regardless), but landing ergonomics do.

**Resolution trigger:** Resolve against a **live** `loop.py` dispatch (the same live-`claude -p` gap the 003 spike open-questions note records) — observe whether a real loop run commits. If it does not and landability matters, either have dispatch commit the worktree's result on a `passed` outcome, or document the working-tree-diff reconstruction in the 011-05 skill. Pairs with the worktree-retention decision above.

**Surfaced by:** slice 011-03 (Assumptions A3 + Open questions: "Does the dispatched loop commit its fix?"); DoD-required follow-up.

---

## Dispatch holds the inbox advisory lock across the whole pass

**Deferred:** unlike `discover` (which holds the `fcntl.flock` only around the fast read-merge-write, explicitly *not* across the slow `gh`/`git` enumeration), `dispatch` acquires the lock once up front and **holds it across the entire pass** — including every slow `loop.py` subprocess. This guarantees no *completed* loop outcome is ever lost to mid-pass contention (each outcome is written atomically under the held lock) and is the model AC8's `LOCK_EX | LOCK_NB` + "backs off (exit 0)" wording most directly supports. The trade-off: a concurrent `discover` (or a second `dispatch`) finds the lock contended and backs off (exit 0) for the *whole* dispatch duration, so that tick's discovery is skipped (self-correcting on the next Routine tick; rare outside a double-fire, and a non-issue for 011-04's single-process `run` = discover-then-dispatch).

**Resolution trigger:** First time the "a long dispatch starves discovery" trade-off bites a real schedule (e.g. discovery cadence matters and dispatch passes run long). Alternative to weigh: a lock-per-outcome-write model (release during loops, re-acquire briefly per write) — but that must block-and-retry rather than back off, to avoid losing a just-completed loop's outcome, which diverges from `discover`'s non-blocking back-off. Revisit alongside 011-04's ceiling accounting.

**Surfaced by:** slice 011-03 implementation (deliberate design choice; deviation log).

---

## A dispatch env-error leaves the finding `tried` — no auto-retry for *transient* env-errors

**Deferred:** a per-candidate dispatch env-error (non-git target, worktree-create failure, worktree oracle unverified, or a `loop.py` that emitted no parseable summary) records `attempts += 1`, `outcome.oracle_status = "env_error"`, and `status = "tried"` (AC7's unconditional "passed iff pass, else tried"). The one-attempt-in-v1 rule (ADR-0010) then prevents re-dispatch — correct for a *non-transient* env-error (a non-git target fails identically forever), but a *transient* one (a flaky `git`, a momentarily-busy worktree path) is also frozen at `tried` and won't retry without a human reopening it (and v1 has no machine "reopen" — `skipped` is human-only and `open` is not auto-restored).

**Resolution trigger:** First time a transient dispatch env-error wrongly parks a still-fixable finding. Options: distinguish transient vs permanent env-errors (leave transient ones `open` with a bounded retry counter on `attempts`), or add a `heartbeat.py reopen <finding_id>` verb / `--retry-env-errors` flag. Pairs with ADR-0010's deferred "retry-with-backoff for `tried`". **Coupled with `_remove_worktree_if_present`:** today a retained worktree is force-removed on re-dispatch only for a finding that stayed `open` (never looped) — safe precisely because a looped finding is `tried`/`passed` and leaves the candidate set. If transient env-errors start staying `open` for retry, that teardown would begin clobbering a worktree whose prior loop *did* run; resolve this entry and the worktree-GC/retention entry together.

**Surfaced by:** slice 011-03 implementation (AC6/AC7 env-error status interpretation; deviation log) + arch review (`jig:reviewer`, PASS-WITH-NITS).

---

## Dispatch leaves `inbox.md` stale; uncommitted-`oracle.sh` edits env-error the candidate

**Deferred:** two small disclosed limitations of 011-03 dispatch. (1) `dispatch` updates only `inbox.jsonl` (the spine); the generated `inbox.md` human view is **not** regenerated, so after a dispatch pass it shows pre-dispatch statuses until the next `discover` rewrites it (the accurate read-back is `heartbeat.py status`, which reads the jsonl). (2) Provisioning copies the **live** `<target>/oracle.sh` over the worktree's HEAD checkout; if the target has an **uncommitted** `oracle.sh` edit, the worktree's tracked `oracle.sh` then differs from its HEAD → `loop.py`'s dirty-tree preflight refuses (`dirty_tree`) → the candidate is recorded as an env-error. v1 deliberately does **not** pass `--allow-dirty` on the unattended path (don't loosen a guardrail without a spec mandate).

**Resolution trigger:** (1) First time a stale `inbox.md` confuses a reviewer — have `dispatch` regenerate `inbox.md` (needs a small `_render_markdown` tweak for a non-discovery "Updated at" header, since dispatch has no per-source discovery health to report). (2) First time a legitimately-edited-but-uncommitted oracle should be scored — decide whether dispatch passes `--allow-dirty` for the worktree it provisioned (the dirt is its own intentional provisioning) or requires a committed oracle.

**Surfaced by:** slice 011-03 implementation (deviation log).

---

## `workflow.py status-board`'s deferred-slice trigger extractor mis-handles this repo's prose

**Deferred:** `docs/specs/README.md`'s `## Deferred slices` table sources its
"Resolution trigger" column from slice-file prose, and the extractor has two
distinct failure modes against servo's actual slice files: (1) it only matches
the literal `**Resolution trigger:**` label — several 016-execution-planner
slices (016-02/03/04) use `**DEFERRED — resolution trigger:**` instead, so a
regen silently **blanks** those cells; (2) even with a matching label, it
appears to capture only the **first physical line** of a wrapped multi-line
paragraph — 013-02 and 013-03's trigger prose wraps across 3 lines each and
was found **truncated mid-sentence** in committed `README.md` (predating this
session, so a prior regen already hit this). Same root symptom (the Deferred
table is not a faithful copy of the source prose) as the already-known
Notes-column pipe-dropping bug, but on a different table and via two different
mechanisms (label mismatch vs. line-wrap truncation).

**Resolution trigger:** First time this bites someone who doesn't notice the
blank/truncated cells before committing (this session caught and hand-restored
both — see slice 013-01's deviation log). Fix options: normalize all servo
slice files onto the plain single-paragraph `**Resolution trigger:**` label
(no line wraps), or fix the jig-side extractor to match both label phrasings
and join wrapped lines.

**Surfaced by:** slice 013-01 implementation (`workflow.py status-board .`
regen during reconciliation, 2026-07-01). Reproduced **twice** in the same
session — a second `status-board` run re-blanked the same cells after the
first hand-fix, confirming this is deterministic, not a fluke. **Reproduced a
third time** in a separate session the same day, SPIDR-splitting spec 008's
deferred slices (008-01..04): the same regen re-blanked 016-02/03/04's cells
*again* (label mismatch) and re-truncated 013-02/03's (line-wrap), plus left
008's own new rows blank (same label-mismatch cause — 008's slice files use
the same `**DEFERRED — resolution trigger:**` phrasing). Hand-restored all
of it a third time.

---

## `workflow.py`'s spec-status rollup ignores a `DEFERRED` sibling's human intent

**Deferred:** Per `spec-workflow`'s documented rule, a spec's frontmatter
`status:` derives to `DONE` when *every non-`DEFERRED`* slice is `DONE` —
`DEFERRED` slices are excluded from the computation. For an umbrella spec
where only the first slice has landed and the rest are deliberately parked
behind a grounding consumer (specs **013** and **016**, both hit this in the
same session), that derivation is mechanically correct but reads as false:
`transition <slice> DONE` and `status-board` both silently flip the *spec's*
`status:` frontmatter to `DONE` even though the spec's own prose banner says
"DRAFT — N-01 DONE, N-02..NN DEFERRED" and the spec is nowhere near closed.
Reproduced deterministically — reverting the frontmatter by hand does not
stick; the next `transition` or `status-board` run re-flips it.

**Resolution trigger:** First time someone reads `status: DONE` on a
mostly-parked umbrella spec's frontmatter and takes it at face value (e.g. a
dependency-gate check, or a human skimming `spec.md` without reading the
prose banner). Current workaround (specs 013, 016): keep a hand-written
`> **Status: DRAFT — ...**` banner immediately under the H1 as the
authoritative human-readable statement, and re-revert the frontmatter to
`DRAFT` after every `transition`/`status-board` run that touches that spec.
Real fix needs a jig-side decision: either add a slice-level opt-out (e.g. a
`rollup: false` spec frontmatter flag) or change the derivation to require
*all* slices (including `DEFERRED` ones) to be `DONE`/`DEFERRED`-with-no-
further-work before rolling up — TBD, not decided here.

**Surfaced by:** slice 013-01 reconciliation review (2026-07-01) — first
caught on spec 016 by an independent reconciliation-review pass, then
confirmed to also hit spec 013 itself when 013-01 transitioned to `DONE`.

---

## `adr.py index` regenerates worse descriptions than this repo's hand-curated ones

**Deferred:** `docs/decisions/README.md`'s `## Index` section is hand-curated —
each bullet is a carefully written one-sentence summary of the ADR's actual
decision. `adr.py index` regenerates that entire section by extracting the
first paragraph of each ADR's `## Context` (truncated at the first
sentence-ending punctuation). For ADRs whose Context opens with scene-setting
prose rather than a self-contained summary sentence, this produces a strictly
worse description than what was already there — several came back
`(untitled)` / `((unknown))` (title/date extraction failing entirely), others
came back a technically-accurate but decision-free opening sentence (e.g.
ADR-0012 → "Spec 011 turns servo into a scheduled front-end: ..." instead of
the existing "`heartbeat.py run` applies one heartbeat-level budget ...").
Same root cause as the status-board Deferred-table bug above: an automated
regenerator whose extraction heuristic doesn't match this repo's actual
hand-authored content shape, and blindly overwrites curated prose that was
better than what it produces.

**Resolution trigger:** First time someone runs `adr.py index` expecting only
a new bullet to be appended, and doesn't diff the result carefully before
committing — this session (2026-07-01, adding ADR-0019) caught it only via a
full `git diff` review and reverted, hand-inserting the one new bullet
instead. Fix options: don't run `adr.py index` on a repo with pre-existing
hand-curated entries (append by hand instead, as done here going forward);
or fix the jig-side extractor to prefer an existing bullet's description over
its own Context-paragraph extraction when one is already present for that
ADR number.

**Surfaced by:** this session, ADR-0019 authoring (`adr.py index
docs/decisions`, 2026-07-01) — full-index diff showed 17 of 18 pre-existing
entries degraded, one to a completely different unrelated description.

---

## Silent permission denial has no detection signal (agent-loop can't distinguish it from a genuine plateau)

**Deferred:** Bugs 001/002/004 (all DONE) closed the two *detectable* symptoms
ADR-0021 named — a hard auth/API error envelope (`is_error`/`api_error_status`)
and an unforwarded target `.claude/settings.json` — for both the loop driver
and the goal driver. But a third case remains structurally undetectable: when
a target declares **no** `.claude/settings.json` and the host's default
(prompt-on-tool) policy silently denies edits, the spawned `claude -p` turn
can complete "successfully" (`is_error: false`, real turns, real cost) with
**zero file changes** — there is no error envelope to inspect. Direct grep
across `loop.py`, the three bug records, and ADR-0021 confirms no env var,
parent-process signal, or other mechanism exists to positively detect "I am
nested inside a permission-restricted host" ex ante; ADR-0021's own
Alternatives Considered explicitly rejects trying to defeat the host's safety
classifier. This case degrades to the existing `oracle_plateau` terminal
reason — the ADR's accepted fallback for a genuinely-stuck (vs.
structurally-blocked) run — so an operator sees a plateau and cannot tell
from the loop's output alone whether the model is stuck or whether it was
never allowed to write.

**Resolution trigger:** A future Claude Code release documents a
nesting/restriction signal (an env var, a parent-process marker, or an API
that reports the effective permission mode) that `loop.py` could inspect
before or after an iteration. When that lands, add a dedicated `REASON_*`
(e.g. `edits_denied` or `permission_restricted`) distinct from
`oracle_plateau`, with a regression test mirroring `ClaudeErrorEnvelopeTests`
/ `LoopForwardsTargetSettingsTests`. Until then, inventing a heuristic (e.g.
sniffing an undocumented env var) would be speculative, not grounded, and is
deliberately out of scope.

**Surfaced by:** spec 019 slice 019-04 DoR/Assumption A1 (oracle-as-a-service
docs) — the slice's grounded doc-gap review found no detection signal exists
after Bugs 001/002/004 closed the two detectable cases; recorded here rather
than papered over.

---

## execution-planner's evaluation_model still reads the pre-ADR-0023 spec-oracle path

**RESOLVED (2026-07-08 — [bug 005](bugs/005-evaluation-model-stale-overlay-path.md)):**
`_load_evaluation_model` now takes `spec_dir` and resolves the colocated
`<spec-dir>/oracle/<spec-id>/checks.json` first, legacy
`.servo/spec-oracles/<spec-id>/checks.json` as fallback (dual-path logic
duplicated locally, not imported — per the dependency-free-skill invariant), with
two regression tests on the new layout (`test_evaluation_model_from_colocated_overlay`
+ `test_evaluation_model_colocated_wins_over_legacy`). Fixed via the `jig:bug-fix`
ceremony (standard tier; bug-review + craft PASS). Original deferral write-up
preserved below.

**Deferred:** Slice 019-02 (ADR-0023) moved a spec-oracle's durable artifacts
from `<target>/.servo/spec-oracles/<spec-id>/` to the spec's own
`<spec-dir>/oracle/<spec-id>/`, funneling every in-skill call site through one
shared `oracle_overlay.py::oracle_dir_for_spec` helper (with a soft
read-fallback to the legacy location for pre-019-02 installs). `skills/
execution-planner/execution_plan.py::_load_evaluation_model`
(spec 016, DONE) independently hardcodes the **old** path
(`target / ".servo" / "spec-oracles" / spec_id / "checks.json"`) and was not
swept — it wasn't named in 019-02's original grounding research (only
`oracle_overlay.py` and `oracle_plan.py` were flagged as call sites).

**Effect:** a spec-oracle planned *after* 019-02 (living at the new location)
will not be found by `execution_plan.py`, so its `evaluation_model` block
silently degrades to `null` — the same as a baseline-oracle-only target. This
is not a hard failure (the function already treats a present-but-unreadable
overlay as optional enrichment, and the full execution-planner suite still
passes, since its fixtures fabricate the old path directly), but it is a real
loss of the `evaluation_model` enrichment for any spec-oracle installed via
the new (now-default) layout.

**Why not fixed inline in 019-02:** `execution_plan.py`'s own file header
documents a deliberate "dependency-free skill" invariant (it duplicates
`loop.py`'s budget constants rather than importing them, mirroring
`heartbeat.py`) — `skills/execution-planner/` and `skills/spec-oracle/` are
different skill directories, so importing `oracle_dir_for_spec` across that
boundary would be a new kind of coupling this skill has so far avoided. The
correct fix is more likely to **duplicate** the new-path-plus-fallback logic
locally (matching the existing constant-duplication convention) than to
import it — a design call that belongs to spec 016, with its own tests, not
bolted onto spec 019's slice.

**Resolution trigger:** the next time spec 016 (execution-planner) is
touched, or the first time a real target hits this gap (an
`evaluation_model: null` where a colocated spec-oracle overlay is actually
installed) — update `_load_evaluation_model` to resolve both the new and
legacy locations (duplicating, not importing, `oracle_dir_for_spec`'s logic),
with a regression test using the new (post-019-02) artifact layout.

**Surfaced by:** spec 019 slice 019-02 (colocate-artifacts, ADR-0023)
implementation — flagged by the implementer as an out-of-declared-scope
third call site, confirmed by direct read of `execution_plan.py:222-244`.

---

## Referenced (unvendored) checks.py is not covered by the freeze/approval hash

**Deferred:** ADR-0023 / slice 019-02 made "reference, don't copy" the
default for `checks.py` (`oracle_overlay.py::render_fragment` points the
generated fragment at the shared plugin-sibling `checks.py` by absolute
path, `--vendor-engine` opt-in restores the old copy-and-hash behavior).
`approve()` (`oracle_overlay.py`) only hashes `checks.py` into
`approved_artifacts` **when vendored** — the referenced (default) engine is
never hashed, so a subsequent servo plugin upgrade that changes
`checks.py`'s behavior silently changes what an *already-approved* oracle
runs, invisible to the `--enforce-freeze` gate (006-04 / 019-01). This is a
real, if narrow, version-skew gap in the freeze's threat-model coverage —
distinct from the artifact/plan tripwires the freeze already covers.

**Resolution trigger:** if this ever causes a real incident (an oracle's
behavior changing across a servo upgrade without re-approval), or as part of
a future spec-oracle freeze hardening pass — options include hashing the
referenced engine's content at approval time too (even though it isn't
copied), or pinning to a specific servo version string recorded in
`checks.json`.

**Surfaced by:** spec 019 slice 019-02's arch-review pass — a designed,
disclosed trade-off of ADR-0023's reference-not-copy default, not a slice
defect; flagged for future hardening rather than blocking this slice.

---

## Copied shared-eval-harness module has no re-sync / staleness signal

**Deferred:** ADR-0024 / spec 020 (content-fidelity-eval) extracts
design-eval's freeze/hash/aggregate/ledger primitives into
`skills/_common/fidelity_eval.py`, but design-eval's runtime stays
copy-based (the inverse default from ADR-0023's `checks.py`): `score.py` /
`capture.mjs`, and now `fidelity_eval.py`, are `shutil.copyfile`d into an
arbitrary target's `.servo/design-eval/` (or `.servo/content-fidelity/`) at
install time. Once installed, a target's copy has no version stamp or
staleness check — a later bug fix to the shared module in
`skills/_common/` never reaches an already-initialized target until it
re-runs `install`. This pre-dates the extraction (`score.py`/`capture.mjs`
already have this property today) but the extraction widens its blast
radius from one skill to every consumer of the shared module. A checked-in
vendored fallback (if the two-candidate import-resolution mechanism in
020-01 proves unsound) does **not** close this gap either — it only
relocates it (source-tree drift instead of install-time drift), confirmed
by direct read of ADR-0023's `--vendor-engine` mechanism, which itself only
hashes a vendored file once at freeze time (drift-from-snapshot detection),
never against the live canonical source.

**Resolution trigger:** if a real drift incident occurs (a shared-module fix
silently not reaching an installed target), or as part of a future
freeze/install hardening pass — options include a hash-comment stamped into
the copied file at install time plus a `--check-stale` verb on the
authoring CLI, or adopting ADR-0023's reference-by-absolute-path model for
`fidelity_eval.py` specifically (even though `score.py`/`capture.mjs` stay
copied) since it has no legitimate reason to be vendored per-skill the way
skill-specific runtime code does.

**Surfaced by:** ADR-0024's frame-critique pass (rounds 1-2, 2026-07-03) —
a named, disclosed, out-of-scope risk, not a slice defect; the extraction's
core value proposition (one edited canonical file instead of N
hand-duplicated ones) holds regardless of which reach-the-target mechanism
is used.

---

## `content-fidelity`'s `command`-backed cases have no structural cross-run determinism requirement

**Deferred:** spec 020 (content-fidelity-eval), slice 020-02. Design-eval
structurally requires every case to supply a `setups/<id>.mjs` that seeds
deterministic app state before capture — no equivalent exists for
`content-fidelity`'s `command` artifact-gathering mechanism (AC6), which may
wrap a non-deterministic (e.g. LLM-backed) generator. Slice 020-02's AC3
guarantees the artifact is gathered once per scoring run and reused across
all `n` judge samples (so a single `score()` call's n-sample lower bound
measures judge noise only, per ADR-0005 clause 3) — but that guarantee does
not extend **across** runs. ADR-0005 clause 4's plateau noise floor `δ` is
calibrated to judge stderr, not to generator output drift, so a
non-deterministic `command` case can produce a composite delta `δ` was
never sized to absorb: `loop.py` may read generator drift as false progress
or a false plateau. The noise-floor mechanism itself is not broken — `δ` is
just not scoped for this input class.

**Resolution trigger:** if a real consumer hits this (a `command`-backed
case producing visibly noisy plateau/progress signal across loop
iterations), or as part of a future content-fidelity hardening pass. The
cheapest identified candidate: cache the gathered artifact keyed by its
content hash across a loop's plateau window, so a `command` case naturally
behaves like a stable `file` case once generated once, without requiring
the generator itself to be deterministic. Until then, the skill's
authoring guidance steers projects toward `file`-backed cases for anything
gating a loop's plateau detection.

**Surfaced by:** slice 020-02's frame-critique pass (rounds 2-3,
2026-07-03) — a named, disclosed risk, not a slice defect; `file`-backed
cases are unaffected.

---

## `content-fidelity`'s file-or-command config shape is unvalidated against a real consumer

**Deferred:** spec 020 (content-fidelity-eval), slice 020-02, Assumption A1
(the narrower half — distinct from the cross-run-determinism entry above,
which A1's second half covers). Design-eval's screen/mockup config shape was
de-risked by a real throwaway spike (012's spike-findings) before it
shipped; content-fidelity's two-mechanism artifact-gathering config (`file`
read vs. `command` exec) shipped without an equivalent spike or a committed
first consumer, on the reasoning that it is the smallest shape covering
ADR-0005's dataset-is-a-hashed-artifact framing. It may not cover every real
shape a text-fidelity project needs (e.g. a multi-step pipeline, or an
artifact that needs post-processing before judging).

**Resolution trigger:** the first real content-fidelity consumer (mirroring
design-eval's 012-05 "first consumer wiring" pattern) — extend the config
shape then, informed by what that project actually needs, rather than
guessing further shapes now.

**Surfaced by:** slice 020-02's frame-critique pass (round 1, 2026-07-03) and
its compliance review (2026-07-03) — a disclosed, non-blocking scope
question, not a defect; the shipped `file`/`command` shape is fully
functional for both of its own documented use cases.
