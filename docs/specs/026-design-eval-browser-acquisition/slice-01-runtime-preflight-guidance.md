---
status: REVIEWED
dependencies: [adr-0031]
last_verified:
frame_review: true
claimed_by: claude/jig-orient-6324de
---

## Slice 026-01 — runtime-preflight-guidance

**Goal:** Make the machine that actually fails say what to do about it — for the
two failure modes that are *cheaply* detectable before launch (node missing,
browser library missing), plus fix the stderr surfacing that currently hides the
remedy for everything else.

**DoR:**
- ✅ [ADR-0031](../../decisions/adr-0031-design-eval-browser-acquisition.md)
  Accepted; this is its Option G.
- ✅ **Failure taxonomy corrected and probe-grounded** (the first frame-critique
  found the original premise wrong). Verified by running the real shapes:
  | failure | branch in `score.py:103-111` | what the adopter sees today |
  |---|---|---|
  | `node` binary absent | `FileNotFoundError` → `EnvError("node/playwright unavailable…")` | the only case that message covers |
  | **library absent** | node starts, **rc 1** → `EnvError("capture failed …: {stderr[:200]}")` | `node:internal/modules/package_json_reader:256 / throw new ERR_MODULE_NOT_FOUND…` — node internals |
  | browser binary absent | node starts, rc≠0 → same branch | Playwright's launch error, head-truncated |
  | app down / selector / setup throw / timeout | node starts, rc≠0 → same branch | head-truncated |
  Probe: a script doing `import { chromium } from 'playwright'` with the library
  absent returns **rc 1, not `FileNotFoundError`**, and `stderr[:200]` is
  entirely node-internals preamble.
- ✅ **`stderr[:200]` is a *head* truncation** (`score.py:111`), so when a tool's
  own remedy text appears later in the message it is cut away.
- ✅ **Fake-scores bypass located:** `score()` skips `capture_app` entirely when
  `SERVO_DESIGN_EVAL_FAKE_SCORES` is set. The preflight must sit inside the
  live-capture arm or every offline/CI run breaks.

**Acceptance criteria:**
1. Before the first capture, `score.py` probes: (a) `shutil.which("node")`;
   (b) library resolvability via a single `node -e "require.resolve('playwright')"`
   spawn. **The probe fails OPEN:** it reports "library absent" *only* when the
   probe's stderr carries the `MODULE_NOT_FOUND` token (probe-confirmed). On any
   other non-zero exit or unrecognised stderr it proceeds to capture and lets
   capture's error be authoritative — because `-e` runs as CommonJS and an
   environment such as `NODE_OPTIONS=--input-type=module` would make `require`
   undefined, which must not be misreported as a missing library on a machine
   where capture would have succeeded.
   **The probe spawns with `cwd=base_dir`**, matching `capture_app`'s own spawn,
   so its CommonJS `module.paths` walk covers the same directory chain as
   `capture.mjs`'s ESM resolution (which walks up from `<target>/.servo/design-eval/`
   to `<target>/node_modules`). Without this the probe could emit a *genuine*
   `MODULE_NOT_FOUND` token on a machine where capture would succeed — a
   token-confirmed false positive that lands in the fail-**closed** branch, the
   one hole fail-open cannot plug.
2. The preflight **performs no browser launch** and adds **at most one extra
   node spawn per run** — and none at all when (a) already failed. (Falsifiable
   restatement of "cheap".)
3. **Browser-binary presence is explicitly NOT preflighted** — detecting it needs
   a real Playwright import or launch, which would cost every success run or turn
   a working-but-slow environment into rc 2. It is covered by AC4 instead.
4. `capture_app`'s error surfacing changes from `stderr[:200]` (a blind head
   slice) to **salience-RANKED line selection** — explicitly *not* positional at
   any stage, since two positional heuristics have now been falsified here
   (head, then "first 2 + last 2"):
   - **Drop, as a BLOCK rule — not per-line predicates.** Node's uncaught-
     exception preamble is a three-line *block*: frame header / echoed source /
     caret. A frame header — `^(file://|node:internal/|/).*:\d+$` — drops
     **itself and every following line through the caret line or the next blank
     line, whichever comes first**. Per-line predicates are provably insufficient
     here: probed, the AC's earlier per-line form left
     `throw new ERR_MODULE_NOT_FOUND(packageName, …)` as the first survivor, and
     the rank rule then promotes the first survivor to *the cause* — so the
     adopter's headline would have been node internals, the very defect this AC
     removes. Additionally drop stack frames (`^\s+at `), the trailing
     `Node.js vX.Y.Z` banner, the `{ code: … }` object, and box-drawing/
     padding-only lines. Strip box-drawing characters before measuring — **and the emitted line is that
     box-stripped, whitespace-trimmed form**, not the raw one (otherwise a
     compliant implementation could emit `║     npx playwright install    ║`
     verbatim, which the rank-1 exact-match tests would not catch since all three
     fixtures' cause lines fall outside the box).
   - **Rank** the survivors: the cause (first survivor) first, then remedy lines
     matched by **command shape** — `^\s*(npx|npm|yarn|pnpm|pip|python -m pip|
     brew|apt|apt-get)\b` after box-stripping — then the rest. **Intra-tier
     order is command-shape-first, explicitly, not document order.** A bare
     `install` substring is *not* used: it matches explanatory prose such as
     Playwright's "…was just installed or updated", which sits *above* the real
     command in its box, so document-order tie-breaking would rank the prose
     ahead of the runnable command and can exhaust the budget before reaching it
     — telling an adopter whose symptom is *Playwright is unusable* that it was
     recently installed.
   - **The budget is 400 characters** — stated, because the number decides
     whether the mechanism works. Fixture (ii)'s cause
     (`browserType.launch: Executable doesn't exist at /Users/…/ms-playwright/…`,
     ≈140 chars and longer under a CI `$HOME`) plus its remedy
     (`npx playwright install`, 22) needs ≈165+, so a budget of 150 would make
     the skip-whole-line rule below discard the remedy **silently** — no error,
     no truncation, just absence, the exact outcome this AC exists to prevent.
     400 leaves headroom for the box case; today's 200 does not. Fixture (ii)'s
     test asserts the remedy survives **at 400**, not at whatever value the test
     happens to pass under.
   - **Budget boundaries are defined, not left to the implementer:** never emit a
     partial remedy (a truncated `npx playwright inst` is exactly the failure
     this AC exists to prevent) — skip a line that does not fit and try the next,
     and elide the **middle** of an over-long line (long cache paths are the only
     reason the budget binds) rather than its tail — elision is **per-line**, and
     applies only when a single line exceeds the budget, never to the assembled
     output. **Zero-survivor floor:** if
     the drop stage removes every line, fall back to today's head slice rather
     than emitting an empty diagnostic — a strict regression otherwise.
   Ranking rather than slicing is what makes this robust: Playwright's
   browsers-not-downloaded message puts `npx playwright install` in a
   **positionally central** drawn box, so any first-N/last-N reduction discards
   exactly the remedy while keeping box corners.
   **Grounding, stated honestly — including where it was insufficient.** The
   filter was run against the *real* captured `ERR_MODULE_NOT_FOUND` stderr
   (cause survives, all noise dropped) and against a *reconstruction* of
   Playwright's box (cause and remedy ranked 1st and 2nd). But the reconstruction
   passed only because the prototype used a word-bounded `\binstall\b` while the
   AC text said a bare `install` — i.e. the implementation was stricter than the
   spec, and the box's prose line would have out-ranked the command under the AC
   as written. That divergence is why the rank rule above is now specified by
   **command shape** rather than substring, and it is recorded here as a caution:
   a reconstruction can pass while the specified rule fails.

4a. **The filter is a shared helper, applied only to node-produced stderr.** It
   lives in `skills/_common/fidelity_eval.py` (the ADR-0024 home `score.py`
   already imports through) as a named function, because
   `stderr.strip()[:200]` is not local to the line AC4 replaces — enumerated:
   **5 call sites across 3 skills**.
   **This slice applies it to `capture_app` only.** An earlier draft also wired
   it to `design-eval/score.py:157` (the `claude -p` judge path) on
   same-file/consistency grounds; that was wrong. Every drop predicate in AC4 is
   a parser for **node's uncaught-exception grammar** (frame header / echoed
   source / caret, `^\s+at `, `Node.js vX.Y.Z`, `{ code: … }`), and the `claude`
   CLI is a different producer with a different grammar for which this slice has
   **no fixture**. The block rule is the sharpest hazard: `^/.*:\d+$` matches a
   bare path line such as `/Users/x/.claude/settings.json:12`, and with no caret
   following it would eat forward to the next blank — taking the explanation with
   it and making the judge path **worse** than today's `[:200]`, on exactly the
   remedy-bearing failures (auth expiry, rate limit) that motivated including it.
   Consistency is not urgent enough to outrun evidence: the judge path,
   `content-fidelity`, and `eval-authoring` call sites are **deferred together**
   to a named refinement-todo owner, to be done when a recorded real `claude -p`
   failure fixture exists (or the helper is parameterised by producer).
5. The preflight runs **only** in the live-capture path: with
   `SERVO_DESIGN_EVAL_FAKE_SCORES` set, scoring still succeeds with node absent.
6. Contract unchanged: failures stay `EnvError` → rc 2, stdout empty. The
   preflight introduces **no new failing case** — guaranteed by AC1's fail-open
   rule, not merely asserted: the only conditions that halt are node-absent and a
   token-confirmed missing library, both of which would have failed at capture
   anyway. Every ambiguous probe outcome proceeds to capture.
7. Non-interactive: never prompts, never reads stdin, never installs.

**DoD:**
- [ ] Preflight implemented inside the live-capture arm of `score()`.
- [ ] Tests: node-missing, library-missing, all-clear, and **fake-scores-with-node-absent still passes** (AC5 regression guard).
- [ ] Test: stdout empty + rc 2 on every preflight failure.
- [ ] **Fixtures committed with provenance**, not merely "tests run against real
      stderr" — fixtures (ii) and (iii) require a machine *with* Playwright
      installed, which this repo is not, so the acquisition path is named rather
      than left to an implementer who would otherwise skip the case (leaving the
      highest-value row untested) or hand-write it (which this DoD forbids):
      record once on a Playwright-equipped machine, commit under the test tree as
      **verbatim captured stderr** with a provenance comment (node version,
      Playwright version, OS, exact command).
- [ ] Tests: the salience filter against those fixtures for all three shapes —
      (i) library absent, (ii) browsers not downloaded, (iii) app down —
      asserting **by exact match that the emitted FIRST line equals the expected
      cause line** (not merely that it "survives" somewhere, which cannot detect a
      rank-1 corruption) and that, where the tool emits one, the runnable remedy
      is present.
- [ ] Test: the helper lives in `_common/fidelity_eval.py`, `capture_app` calls
      it, **and `score.py`'s judge path (`:157`) is UNCHANGED** — a guard against
      re-wiring the node-grammar filter to the `claude -p` producer before a real
      fixture for it exists. (An earlier DoD line required the opposite; it
      contradicted AC4a, and the DoD is what an implementer ticks.)
- [ ] `docs/refinement-todo.md` entry written for the deferred call sites
      (judge path, `content-fidelity`, `eval-authoring`) with a named owner and
      the trigger "a recorded real `claude -p` failure fixture exists, or the
      helper is parameterised by producer".
- [ ] **Prototype-parity test (mechanical, not an exhortation).** Three defects
      here came from code being stricter than its own AC, and a checkbox reading
      "the suite matches the prose" cannot fail — an implementer who writes
      `\binstall\b` where the AC says `install` ticks it in good faith. So it
      gets an artifact: the filter's regexes are named module constants quoted
      **verbatim** from AC4, and a test reads this slice file and asserts the
      constants match the literals in the AC. Precedent exists in-repo —
      `test_skill_surface.py` already parses named sections out of `SKILL.md`
      and asserts on their content — so this needs no new machinery.
- [ ] Test: zero-survivor input falls back to the head slice (no empty diagnostic).
- [ ] Test: a remedy line that would not fit is skipped whole, never truncated.
- [ ] Test: the probe's spawn kwargs carry `cwd=base_dir` (AC1's false-positive
      guard).
- [ ] Test: an ambiguous probe failure (non-zero exit **without** a
      `MODULE_NOT_FOUND` token) does **not** halt — capture still runs (AC1/AC6
      fail-open guard).
- [ ] Test asserts no browser launch occurs during preflight (AC2/AC3).
- [ ] `SKILL.md` Prerequisites references the runtime guidance.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Out of scope (stated, not implied):** transport awareness (026-02 owned it, but
is now **DEFERRED** pending the A1 package probe, so `'playwright'` is the
specifier for the foreseeable future — this
slice probes today's single bundled specifier, preserving its "no config surface"
verticality claim); app-down / selector / timeout failures, which no pre-launch
probe can detect and which AC4 improves only by surfacing.

**Inherited obligation for 026-02 — DORMANT while 026-02 is DEFERRED** (recorded
so it is a handoff rather than a rediscovery if that slice re-opens): this
slice hardcodes the probe specifier `'playwright'`. When 026-02 changes what
`capture.mjs` imports/launches (e.g. `playwright-core` + `channel:'chrome'`), it
**must** update the preflight specifier alongside it — or derive it from the
resolved transport — otherwise the preflight demands a package the chosen
transport does not need (a new false failure) or passes while the real import
fails.

**Vertical?** Yes — an adopter whose run fails gets an actionable remedy at the
point of failure, with no config surface and no dependency on later slices.

### Deviation log

- **A shipped defect, found by review, not by my tests.** AC4's middle-elision
  branch was arithmetically dead: `half = (budget-5)//2` produced a `budget-1`
  line while the fit check charged a separator the first line does not need, so
  every over-long line was skipped whole — and a **sole** over-long survivor
  returned `""`, an empty diagnostic and a strict regression on the `[:200]` it
  replaces. Both reviewers found it independently; I reproduced it (521-char
  cause → `''`) before fixing. My own test could not have: it used a 380-char
  line against a 400 budget, so it never entered the branch it appeared to guard,
  and both its assertions were tautological.
- **The parity control had a hole in exactly its own subject matter.** It pinned
  3 of 6 literals and missed the one that had drifted (`^\s+at\s` vs AC4's
  `^\s+at `), plus an undeclared `re.I`. Corrected; both now mutation-verified.
- **Fixtures — the DoD's acquisition path was only partly satisfiable here.**
  Fixture (i) library-absent is genuinely recorded real, verbatim with
  provenance. Fixture (ii) browsers-not-downloaded is a **labelled
  reconstruction** — Playwright is not installable in this repo. Fixture (iii)
  app-down: the node run and stderr bytes are real, but the **error shape was
  constructed** by hand to mimic Playwright's `ECONNREFUSED` + `Call log:` form;
  it was initially mislabelled "RECORDED REAL" and is now labelled honestly, with
  an upgrade note. Given this slice's own history — *a reconstruction can pass
  while the specified rule fails* — the label mattered more than the coverage.
- **AC4a scope honored, not widened.** The filter is wired to `capture_app` only;
  `score.py`'s `claude -p` judge path deliberately keeps `[:200]`, guarded by a
  test. Deferred call sites recorded in `docs/refinement-todo.md` with a trigger.
- **DoD literal deviation:** the refinement-todo owner is role-based ("whoever
  next touches the judge path") rather than a named person — consistent with the
  rest of that file, but not literally what the DoD asked.
- **Not refactored under review (agreed with the craft reviewer):** the
  three-way line normalization and the value-dedup in the rank stage are
  documented in comments rather than restructured. The caret regex remains a
  local literal outside the parity control — the one acknowledged hole.

### Reconciliation sweep

| Artifact | Disposition |
|---|---|
| `skills/_common/fidelity_eval.py` (`salient_stderr` + SALIENT_* constants) | **updated** — ADR-0024 shared home; elision arithmetic fixed; constants aligned to AC4 literals. |
| `skills/design-eval/score.py` (`preflight_capture`, `capture_app`, `score()`) | **updated** — preflight in the `fake is None` block; helper re-exported; judge path deliberately untouched. |
| `skills/design-eval/test_design_eval.py` | **updated** — +19 tests (preflight, salience, regression, parity, exit contract). |
| `skills/design-eval/fixtures/` | **added** — (i) recorded real; (iii) constructed-input, labelled. |
| `skills/design-eval/SKILL.md` | **updated** — Prerequisites now points at the runtime preflight. |
| `docs/refinement-todo.md` | **updated** — deferred `[:200]` call sites with owner + trigger. |
| `hosts/claude`, `hosts/codex` | **updated** — regenerated by `build_host_packages.py`; drift check clean. |
| `content-fidelity`, `eval-authoring` | **no-op** — deliberately out of scope (AC4a). |
| ADR-0031 | **no-op** — implementation matches the accepted decision; no amendment needed. |
| `docs/architecture.md` | **no-op** — no module boundary or public contract changed. |
