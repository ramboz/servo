# Worked example — spec 046-shaped (scaffold artifact fidelity)

> A committed dogfood fixture for `/servo:spec-oracle`, shaped like jig's
> `046-scaffold-artifact-fidelity`. This is **not** a real servo spec — it is a
> self-contained example the planner runs against (so the dogfood has no
> runtime dependency on the jig repo). See `test_skill_surface.py`.

## Slice 046-01 — scaffold-doc-command-rendering

**Acceptance Criteria:**

1. **Command renders.** The stocktake command works from the scaffold target,
   generated into a tempdir, and exits 0.
2. **Doc links resolve.** Local Markdown links in the generated onboarding docs
   resolve.
3. **Reads naturally.** The generated onboarding prose reads well and is
   appropriately worded for a newcomer.
4. **Version provenance.** The generated `manifest.json` contains the version
   string recorded at scaffold time.
