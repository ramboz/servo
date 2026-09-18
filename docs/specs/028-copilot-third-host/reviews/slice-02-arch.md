---
slice: 028-02 — renderer-and-skeleton
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-09-18T18:30:02Z
prompt_source: review.py implementation (arch pass folded in)
---

Independent review (compliance + craft + arch) of slice 028-02 by a fresh
jig:reviewer subagent, reading committed state + jig's shipped renderer for
fidelity. **VERDICT: PASS.**

Faithful port of jig's `build_copilot_plugin.py` + `CopilotScaffoldRenderer` into
servo's function-based builder. ACs 1–5 + 7 directly met with mutation-tested
guards (name-strip/assert, ≤1024 truncate+append-to-body, `$SERVO_ROOT` rewrite,
marketplace source-shape each fail under mutation); AC6 met by a sound,
positively-tested interpretation (servo `scaffold-init` is host-agnostic — jig
bug-034's Claude-default renderer has no servo analogue; oracle Stop→agentStop
deferred to 028-04). Copilot arm cleanly isolated in `_copy_copilot_tree` /
`_write_copilot_manifest`; drift-guarded via `build_all`/`check_drift`;
Claude/Codex byte-unchanged. AC7 live-verified by the orchestrator (`copilot
1.0.86 --plugin-dir` loads all 12 skills).

Non-blocking nits (all correctly scoped elsewhere, none block REVIEWED):
1. `build_release_zip.HOSTS` + release-please `extra-files` don't yet track
   `hosts/copilot/.plugin/plugin.json` → **028-06** (caught loudly by `--check`,
   not silent).
2. The injected `$SERVO_ROOT` shell locator one-liner is tested only via its
   Python `servo_root.resolve()`; a shell-level smoke would harden it (parallels
   AC7's honest live residual).
3. `.github/plugin/marketplace.json` `description`/`owner` are hand-copied and not
   equality-checked by `validate_manifests` — cosmetic, matches servo's existing
   hand-committed Claude/Codex descriptor convention.

Reconciliation: AC6 satisfied by documented interpretation; block-scalar
truncated description (vs jig's inline JSON) is a faithful adaptation for servo's
quote-heavy descriptions; release lockstep/archive deferred to 028-06.
Safe to mark 028-02 REVIEWED → DONE.
