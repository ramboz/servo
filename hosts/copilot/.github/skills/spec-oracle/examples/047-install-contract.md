# Worked example — spec 047-shaped (install-contract verification)

> A committed dogfood fixture for `/servo:spec-oracle`, shaped like jig's
> `047-install-contract-verification`. This is **not** a real servo spec — it is
> a self-contained example the planner runs against. See `test_skill_surface.py`.

## Slice 047-01 — plugin-release-contract-validator

**Acceptance Criteria:**

1. **Manifest valid.** The `install-contract.json` manifest is valid JSON and
   has the required key `schema_version`.
2. **Archive inventory.** The release zip contains the required entries and
   excludes development-only files.
3. **Executable present.** The verifier script is present and its executable
   bit is set.
4. **Verifier exits zero.** The verifier command runs and exits 0.
