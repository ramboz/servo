# Installed delivery evidence (2026-10-12)

Executed against generated Servo 0.10.0 with Copilot CLI 1.0.96-2.
No model call was needed for the deterministic consumer workflow.

## Native CLI installation

With a fresh isolated `COPILOT_HOME`, auto-update disabled:

```text
copilot plugin marketplace add <this-worktree-absolute-path>
Marketplace "servo" added successfully.

copilot plugin install servo@servo
Plugin "servo" installed successfully.
Enabled "servo@servo". It is loaded live from <worktree>/hosts/copilot
... nothing was copied.

copilot plugin list
Live Plugins ... servo@servo (v0.10.0) (enabled)
```

This is **actual local marketplace installation/discovery**, not an install-store
copy or a remote default-main install. The CLI explicitly loads local directory
marketplaces live. `file://` marketplace registration was also attempted and
refused as a nonexistent local path; no cloned-store claim follows from it.
The published default-main marketplace cannot contain this PR until it merges.

## Clean consumer execution

From a separate consumer directory with a minimal Node test fixture, unrelated
root environment variables removed and isolated `XDG_STATE_HOME`:

```bash
SERVO_ROOT="$(python3 <known-installed-package>/.github/scripts/servo_root.py)"
python3 "$SERVO_ROOT/skills/scaffold-init/scaffold.py" <consumer>
python3 "$SERVO_ROOT/skills/quality-gate/gate.py" <consumer> --json
```

The locator returned the executing package's `.github` runtime. Scaffold exited
0 and wrote `oracle.sh`, `.servo/install.json`, refinement notes and availability
metadata with `plugin_name: servo`, `source_version: 0.10.0`, and source_path
equal to that actual `.github` runtime. No `.claude` compatibility tree appeared.

The native packaged gate exited **0**:

```json
{"schema_version":1,"exit_code":0,"status":"pass","composite":1.0,"threshold":0.5,"missing":[]}
```

No Claude or Jig helper was required for that workflow. Copied-install layouts,
marketplace names/versions, missing roots, pass/below/env/timeout and unrelated
environment roots are covered by deterministic regression fixtures, not falsely
labelled live CLI install-store observations.

## Regression and release evidence

- Merge-damaged loop fixtures: original ten failures reproduced, mechanical
  class-boundary restoration yielded all 397 historical loop tests passing.
  Production permission-wall diagnosis was preserved.
- New installed-root/gate regressions: ten red failures including subtests,
  then 16 new tests green. After host regeneration, combined builder/scaffold/
  quality-gate/new regressions: **204 passed, 59 subtests passed**.
- New native launch refusal tests: four methods with fifteen subcases witnessed
  red-to-green. Changed legacy native-launch expectations updated intentionally;
  focused changed loop coverage: **20 passed, 15 subtests passed**.
- `validate_manifests.py`: four manifests agree on 0.10.0.
- `build_host_packages.py --check`: all three committed hosts in sync.
- `build_release_zip.py --host <copilot|claude|codex> --version 0.10.0`:
  all archives built and their existing host-specific smoke checks passed.
  These smoke checks are **static**, not live model/hook proofs.

Final synchronized CI passed2255 tests and all established gates; see
ci-evidence.md. These focused delivery results do not imply that deferred native
autonomy or enforcing continuation is complete.
