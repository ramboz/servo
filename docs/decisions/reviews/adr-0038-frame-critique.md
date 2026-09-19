---
adr: 0038
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-09-18T17:40:17Z
prompt_source: review.py frame-critique docs/decisions/adr-0038-copilot-third-host.md
---

Frame-critique of ADR-0038 (GitHub Copilot CLI as a third committed host), run
pre-implementation with independent general-purpose reviewers, each grounding its
attack against the live `copilot` CLI (1.0.84→1.0.86) and, in the later rounds,
against jig's **shipped** keystone (`/Users/ramboz/Projects/misc/jig`, ADR-0061 /
spec 113 on `main`). The frame passed on the final pass after five prior
needs-changes rounds, each of which caught a genuine, code-verified flaw:

1. **needs-changes** — the draft asserted jig ADR-0061/spec 113 as a *settled
   keystone servo mirrors* and led its Context with the 2026-09-28 cutover as the
   load-bearing justification. Verified: jig ADR-0061 was then Accepted only on an
   unmerged branch and reframed to "parity-not-deadline." Also: loader-limit
   exposure was grounded on jig's corpus, not servo's; and the Autopilot
   oracle-gated-stop question was left open when the CLI settles it. Fix:
   parity-not-deadline framing; servo's own measured corpus; Autopilot recorded as
   a finding.
2. **needs-changes** — the "servo corpus" grounding measured the *first
   description paragraph* (~726 chars) when Copilot's loader caps the full
   `description:` field; measured directly, 9 of 12 servo skills exceed 1024 —
   exactly the 9 that carry the `servo:` colon (both hazards co-located, not
   "the inverse of jig"). Plus a render-target ambiguity (repo-root `.github/`
   vs a `hosts/copilot/` package). Fix: correct exposure characterization;
   disambiguate the committed artifact.
3. **needs-changes** — the ADR claimed servo's goal driver "never gated
   internally," contradicting ADR-0008's load-bearing invariant (a per-turn
   oracle gate: transcript sentinel + stop-on-pass + meta-judge `Stop`-hook
   block-while-failing). Mapping it to Autopilot's cap-only continuation would
   silently drop the gate. Also: the reused Codex renderer *drops* description
   paragraphs 2+, so "full text preserved in body" was false. Fix: honest
   goal-driver → `agentStop` mapping with a fallback; append-to-body renderer.
   [A fourth reviewer round was interrupted by a worktree recycle and not counted.]

   **jig then SHIPPED its keystone** (ADR-0061 / spec 113 merged to jig `main`,
   with committed `hosts/copilot/` + post-ship bugs 034/035/036). Per owner
   direction, the ADR was re-aligned to mirror jig's *final shipped* layout and
   mechanism (`.github/`-inside-`hosts/copilot/`, legacy `.plugin/plugin.json`
   with component paths, `copilot_hook_adapter.py`, `$SERVO_ROOT` plugin-mode
   rewrite, repo-root `marketplace.json`), reversing the draft's earlier
   `com.github.copilot/`-plugin guess. Two further rounds critiqued the re-aligned
   ADR:

4. **needs-changes** (jig-alignment round) — the `$SERVO_ROOT` mechanism was
   imported verbatim from jig ("publish via a `SessionStart` carrier"), but jig
   can only do that because it is hook-heavy and folds the announcement into an
   *existing* SessionStart hook (`copilot_hook_adapter.py:144`, `merge_root_context`);
   servo ships **zero** plugin hooks, so it has no carrier — and the manifest's
   `hooks` component-path field would dangle. Also: Context-1 still described the
   Codex first-paragraph collapse while the Decision section specified jig's
   word-boundary `loader_safe_description` rule (an internal contradiction). Fix:
   servo's Copilot package is **hook-free** — `$SERVO_ROOT` resolves via the
   standalone `servo_root.py` locator one-liner (jig's own fresh-shell fallback,
   minus the SessionStart convenience), the manifest omits `hooks`, and the oracle
   `agentStop` hook + adapter ship as target-side `oracle-hook` resources;
   Context-1 aligned to the jig loader rule.

## Final verdict: PASS

The frame is sound, internally consistent, and faithful to jig's shipped
solution. Verified against jig's code: servo's `hooks/` is genuinely empty
(`.gitkeep` only); jig's `$JIG_ROOT` publication is genuinely folded into an
existing SessionStart carrier servo cannot have; the standalone locator servo
falls back to is the very fallback jig ships (`jig_root.py`); jig's
`loader_safe_description` (`scaffold.py:1796`) matches the ADR's keep-or-
word-boundary-truncate-and-preserve-in-body rule on both axes and is distinct
from Codex's first-paragraph collapse; and the goal-driver's `agentStop` reliance
is consistent because servo's oracle gate (`oracle-hook/hook.py`) has always been
a target-side install, never a plugin hook. The hook-free-package narrative now
speaks with one voice across the layout diagram, Recommended-Decision bullets,
Invariants, and Assumptions.

## Residual notes (not blocking)

- The ADR cites `copilot` 1.0.84-8 (frame-critique-time grounding); the CLI is now
  1.0.86-2. The leaned-on facts are patch-stable and the ADR already mandates
  re-verification at slice 032-01.
- The adapter port is scoped to its stdin-reshaping half (post-pass edit); servo
  does not wire jig's SessionStart root-publisher half — a 032-04 detail.

Reviewer: independent general-purpose subagents (read-only), 6 rounds
(3 pre-jig-ship + 1 interrupted + 2 jig-alignment).
Prompt built via: review.py frame-critique docs/decisions/adr-0038-copilot-third-host.md
