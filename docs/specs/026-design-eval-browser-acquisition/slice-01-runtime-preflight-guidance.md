---
status: DRAFT
dependencies: [adr-0031]
last_verified:
frame_review: true
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
   (b) library resolvability via a single `node -e "require.resolve('<specifier>')"`
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
     padding-only lines. Strip box-drawing characters before measuring.
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

4a. **The filter is a shared helper, not an inline fix.** It lives in
   `skills/_common/fidelity_eval.py` (the ADR-0024 home `score.py` already imports
   through) as a named function — because `stderr.strip()[:200]` is **not** local
   to the line AC4 replaces. Verified by enumeration: **5 call sites across 3
   skills**, including `design-eval/score.py:157` (the `cli` judge path, 46 lines
   below the target, whose failures — auth expiry, rate limit, model unavailable —
   are all remedy-bearing) and `content-fidelity/score.py:157,224`, a sibling that
   drives the same capture pattern its docstring says it mirrors exactly. Writing
   it inline would leave identical truncation in the same file and diverge two
   skills' message quality for the same failure; and since `hosts/` regenerates
   from `skills/`, a copy-paste multiplies into three divergent copies.
   **Scope decision, stated rather than left silent:** this slice applies the
   helper to `capture_app` (its own path) **and** to `design-eval/score.py:157`
   (same file, zero extra risk). `content-fidelity` and `eval-authoring` call
   sites are **deferred with a named owner** — a refinement-todo entry — because
   they belong to other skills whose tests this slice does not own.
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
- [ ] Test: the helper lives in `_common/fidelity_eval.py` and both `capture_app`
      and `design-eval/score.py`'s judge path call it (no second inline copy).
- [ ] **Prototype-parity check:** the test suite exercises the filter exactly as
      the AC specifies it — no stricter predicate in code than in prose. Three
      defects in this slice came from a prototype being stricter than its own AC.
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

**Out of scope (stated, not implied):** transport awareness (026-02 owns it — this
slice probes today's single bundled specifier, preserving its "no config surface"
verticality claim); app-down / selector / timeout failures, which no pre-launch
probe can detect and which AC4 improves only by surfacing.

**Inherited obligation for 026-02 (so it is a handoff, not a discovery):** this
slice hardcodes the probe specifier `'playwright'`. When 026-02 changes what
`capture.mjs` imports/launches (e.g. `playwright-core` + `channel:'chrome'`), it
**must** update the preflight specifier alongside it — or derive it from the
resolved transport — otherwise the preflight demands a package the chosen
transport does not need (a new false failure) or passes while the real import
fails.

**Vertical?** Yes — an adopter whose run fails gets an actionable remedy at the
point of failure, with no config surface and no dependency on later slices.
