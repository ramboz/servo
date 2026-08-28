# Changelog

## [0.10.0](https://github.com/ramboz/servo/compare/v0.9.0...v0.10.0) (2026-08-28)


### Features

* **design-eval:** enumerate-first catalogue + enforced re-enumerator (028-03) ([936de4e](https://github.com/ramboz/servo/commit/936de4ec78741a83e37cc8516ab0db56fb87a969))
* **design-eval:** freeze surfaces the exclusion list + approval provenance (028-02) ([227c930](https://github.com/ramboz/servo/commit/227c930de052d0c8cb7a4cb6ea9593e7c5d941c6))
* **design-eval:** manual human-supplied capture provider (029-01) ([2247fdb](https://github.com/ramboz/servo/commit/2247fdb0b0aee1b672c8996fcce4e65968ef3baf))
* **design-eval:** structured scoring policy — dimensions + ignore (028-01) ([7d25318](https://github.com/ramboz/servo/commit/7d2531838139921df1db7eb79c2bf7c189cdf434))
* **design-eval:** subagent advisory judge transport (029-02) ([7ccae52](https://github.com/ramboz/servo/commit/7ccae529b6e1ac6e6708c3241fa8c466ed48fa5e))


### Bug Fixes

* **design-eval:** loudly mark fake-scores and within-noise composites ([af51d38](https://github.com/ramboz/servo/commit/af51d38b882a19946b6a7d825e56b90949f0ae28))
* **design-eval:** migrate sibling tests to the v2 schema (CI green) ([44d4ddd](https://github.com/ramboz/servo/commit/44d4ddd6c1f7543257ecd0d0433a1e18f8754ba2))


### Documentation

* **decisions:** accept ADR-0033/0034/0035 (design-eval honesty & reachability) ([793ba1d](https://github.com/ramboz/servo/commit/793ba1d0e36396287e2c6143d117b3ce14aac897))
* **refinement-todo:** capture Mystique agentic-loop pickups (push-as-lock, harvest-&-compact, coordination×evaluation) ([bbd5c3e](https://github.com/ramboz/servo/commit/bbd5c3efa69f86572a347290849035793bc5b916))
* **refinement-todo:** note edd-suitability feasibility-vs-direction risk gap ([9cd28e8](https://github.com/ramboz/servo/commit/9cd28e8a5cf4872b634bb89d515c813d7f5dfc54))
* **refinement-todo:** record design-eval field report, Phase-0 patch, and ADR plan ([fe41a4e](https://github.com/ramboz/servo/commit/fe41a4ee861d50682b3284eab014ded26193ab9a))
* **specs:** draft 028 (policy honesty) + 029 (reachability) for design-eval ([488c212](https://github.com/ramboz/servo/commit/488c21248261099a3f242db7eae2eeeb8e4a6acf))
* **specs:** reserve 028-design-eval-policy-honesty ([31eb15b](https://github.com/ramboz/servo/commit/31eb15b3a5d9300ef98441b0c6d3c60f94e4ce30))
* **specs:** reserve 029-design-eval-reachability ([9b9564e](https://github.com/ramboz/servo/commit/9b9564e4b67d38825fb1ae6f4e1b5a3be0922663))

## [0.9.0](https://github.com/ramboz/servo/compare/v0.8.0...v0.9.0) (2026-08-24)


### Features

* **design-eval:** implement 026-01 runtime preflight + salient stderr surfacing ([d116e5e](https://github.com/ramboz/servo/commit/d116e5e5e2e9dfb8dafa7cfd892ac432290cc288))
* **design-eval:** implement 026-03 ledger browser-identity attestation ([73110b7](https://github.com/ramboz/servo/commit/73110b7de51ab81035d105df4d1ce19665a018c1))
* **design-eval:** platform-agnostic capture (spec 027) — web, command, Android, iOS ([#31](https://github.com/ramboz/servo/issues/31)) ([43418ca](https://github.com/ramboz/servo/commit/43418ca331e8e22c7bf9d5955f9b1c13c8384afd))


### Bug Fixes

* **design-eval:** 026-03 reconciliation findings — untrue DoD ticks corrected ([08b6909](https://github.com/ramboz/servo/commit/08b690901d9226489799a463f5c4623fa2d56c94))
* **design-eval:** address 026-01 compliance + craft review findings ([fb25ac2](https://github.com/ramboz/servo/commit/fb25ac23a0c262421ac67389df8bb16a5f718849))
* **design-eval:** address 026-03 compliance + craft review findings ([f009d55](https://github.com/ramboz/servo/commit/f009d55fe83df20dcdbfc050b9535d68bf48ebf8))
* **design-eval:** address spec 012 compliance + craft review findings ([1cfbf8f](https://github.com/ramboz/servo/commit/1cfbf8fa36e6c14001658d9e38755aa026547509))
* **design-eval:** close 026-01 review nits; add reconciliation artifacts ([3b2eba1](https://github.com/ramboz/servo/commit/3b2eba1a6f1fb4373bc63132c8246138466340ad))


### Documentation

* **decisions:** accept ADR-0031 (design-eval browser acquisition) ([dadf272](https://github.com/ramboz/servo/commit/dadf272bc0e3859ce952994a09f90827dafa2d36))
* **decisions:** add ADR-0032 — pluggable capture providers for design-eval (Proposed) ([#30](https://github.com/ramboz/servo/issues/30)) ([8da8506](https://github.com/ramboz/servo/commit/8da8506aaa12b4b5195cd77611f005b8a4205a77))
* **decisions:** file ADR-0031 (design-eval browser acquisition) — Proposed ([2128502](https://github.com/ramboz/servo/commit/21285025696c878cf30c6a3c7dfc10d63bea3678))
* **decisions:** reserve adr-0031-design-eval-browser-acquisition ([e0d21b3](https://github.com/ramboz/servo/commit/e0d21b323421aee2027bf2bbdceae3a2cc1a22a8))
* **decisions:** revise ADR-0031 through 4-round frame-critique (still Proposed) ([66e1625](https://github.com/ramboz/servo/commit/66e1625d834d8d2a8055fb554491d30f5a3ec812))
* **specs:** 026 — frame-critique round 4/5; 026-02 simplified, not patched ([e6332cc](https://github.com/ramboz/servo/commit/e6332cc550b1bd27792657bccf719647e51a2cec))
* **specs:** 026 slices — frame-critique round 3/4 findings applied ([9bdfc41](https://github.com/ramboz/servo/commit/9bdfc41fc88bc3640865c0a851878c2bb04bae6e))
* **specs:** 026-01 round-7 fixes; drop 026-03 dep on deferred 026-02 ([2d208c8](https://github.com/ramboz/servo/commit/2d208c809f4bbfe1f68c46932dd564efce288f33))
* **specs:** 026-03 — make the labelling claim true; record the SKILL.md residual ([3f1ad82](https://github.com/ramboz/servo/commit/3f1ad820ff457f6382ca77844ae4cfd90d0b43d9))
* **specs:** 026-03 round-6 — testable JS logic, bundled constant, no-stash ([df7eaad](https://github.com/ramboz/servo/commit/df7eaad1fcf0a12975fcbb9b8c72c7e101240c9b))
* **specs:** abandon 026-04, revise 026-01/02/03 after frame-critique round 2 ([a9ce3b5](https://github.com/ramboz/servo/commit/a9ce3b5139f76468827bc5b700f62ffbc2ab2e4e))
* **specs:** defer 026-02 pending A1 probe; apply round-5/6 findings to 026-01/03 ([81910df](https://github.com/ramboz/servo/commit/81910df433431e27dc55e11f25e92b44c3769f17))
* **specs:** draft spec 026 (design-eval browser acquisition) — implements ADR-0031 ([89b7ccb](https://github.com/ramboz/servo/commit/89b7ccbd29517f7a3b849086942bd12414bbc8db))
* **specs:** reserve 026-design-eval-browser-acquisition ([e8ecaa5](https://github.com/ramboz/servo/commit/e8ecaa5c78e1bec065a7624eda44ca1a1eb7be7b))
* **specs:** respec 026 slices after frame-critique (all four needs-changes) ([906a4f2](https://github.com/ramboz/servo/commit/906a4f2064cd069e347f8775a1db0a9e631174b8))

## [0.8.0](https://github.com/ramboz/servo/compare/v0.7.0...v0.8.0) (2026-08-13)


### Features

* **autonomy-readiness:** implement spec 023-02 loop.py readiness preflight ([#27](https://github.com/ramboz/servo/issues/27)) ([adad6b4](https://github.com/ramboz/servo/commit/adad6b423731c5f3cb23ee3ce22fa838e9d01fc1))
* **autonomy-readiness:** land spec 023-01 autonomy-readiness gate ([#24](https://github.com/ramboz/servo/issues/24)) ([ae5218c](https://github.com/ramboz/servo/commit/ae5218c9828c3e2d3595948500ce926383d1f56c))
* **heartbeat:** implement spec 024-01 durable cross-run quarantine (reframe ADR-0030) ([#25](https://github.com/ramboz/servo/issues/25)) ([560ea9d](https://github.com/ramboz/servo/commit/560ea9d61a5a604f5562e09421d806080c0c6344))
* **heartbeat:** implement spec 025-01 lifecycle-aware coordinator ([#26](https://github.com/ramboz/servo/issues/26)) ([4f528f4](https://github.com/ramboz/servo/commit/4f528f4be5e2fa963e20b7c87aea6dc4f4ec3a52))


### Documentation

* **autonomy:** record the long-horizon-autonomy bridge (servo half) — ADR-0029/0030 + specs 023/024/025 ([#20](https://github.com/ramboz/servo/issues/20)) ([f9e4067](https://github.com/ramboz/servo/commit/f9e4067ef40072e7abc48e0335f9c0d67c89a767))

## [0.7.0](https://github.com/ramboz/servo/compare/v0.6.0...v0.7.0) (2026-07-12)


### Features

* **agent-loop:** complete spec 021 headless agent discipline ([b28bc8c](https://github.com/ramboz/servo/commit/b28bc8ca741fd8990944921d34f376f98d5ddbe7))
* **eval-authoring:** implement spec 008 — generic eval-authoring skill (008-01..06) ([#19](https://github.com/ramboz/servo/issues/19)) ([dc6b1e0](https://github.com/ramboz/servo/commit/dc6b1e0a38d87f00f5c023000b9c9336f051963d))
* **execution-planner:** /servo:execution-planner skill surface + compile --json (016-04) ([95be40f](https://github.com/ramboz/servo/commit/95be40f431d0a42ec52b105a65b49200f3c64c17))
* **execution-planner:** clamp-and-review — plan clamp/validate/preserve (016-03) ([56968c1](https://github.com/ramboz/servo/commit/56968c195e6dc37e5d6af294759b9710f4195f35))
* **release:** add dual-host plugin delivery ([97cade5](https://github.com/ramboz/servo/commit/97cade560bf970826c5e61da71d4804676068db2))


### Bug Fixes

* **agent-loop:** goal_unavailable refusal echoes plan-resolved budget ([794eb62](https://github.com/ramboz/servo/commit/794eb62bff091affb7920420f0531c4b08c9dcb6))
* **execution-planner:** dual-path resolve evaluation_model overlay (bug 005) ([c632bff](https://github.com/ramboz/servo/commit/c632bfff864c061789056bc58ee2f7cc8ea3cc02))


### Documentation

* **008:** accept ADR-0026/0027 and activate the eval-authoring spec ([fcab17e](https://github.com/ramboz/servo/commit/fcab17ee31b59934d2abe0d4a0d2659f89e365bf))
* **008:** resolve analyze review findings on the eval-authoring spec ([643c1ee](https://github.com/ramboz/servo/commit/643c1eead64d47277a27cfdccd03b100de499ed2))
* **021:** file headless-agent-investigation spec + ADR-0025 (Proposed) ([cde7a93](https://github.com/ramboz/servo/commit/cde7a93cecf3982402f5293cff8785ce72f50fca))
* **readme:** add logo ([48ee0a1](https://github.com/ramboz/servo/commit/48ee0a19018605695311165950d9f3523b417941))
* **specs:** flesh 016-03 clamp-and-review ACs, amend ADR-0016 (016-03) ([514d90c](https://github.com/ramboz/servo/commit/514d90ce3e08f64a72c61ad6f2da7f118b5833a6))

## [0.6.0](https://github.com/ramboz/servo/compare/v0.5.1...v0.6.0) (2026-07-04)


### Features

* **execution-planner:** run-consume — loop.py --plan reads budget+driver (016-02) ([43d04dd](https://github.com/ramboz/servo/commit/43d04ddf6dc353b7f37287b795dd0e284a1a4147))
* **spec-019:** compile-core-simplification (ADR-0021/0022/0023) ([#15](https://github.com/ramboz/servo/issues/15)) ([0666353](https://github.com/ramboz/servo/commit/0666353f570594e350004c4d241269fd2a1001ec))
* **spec-020:** generalize the frozen-eval harness, ship content-fidelity (ADR-0024) ([#17](https://github.com/ramboz/servo/issues/17)) ([087559c](https://github.com/ramboz/servo/commit/087559caaf4bbd3dc34c647d71af179ed306c5d9))


### Bug Fixes

* **agent-loop:** surface claude -p invocation errors and forward target settings ([4315187](https://github.com/ramboz/servo/commit/4315187b2bba9041281954fa25e3411ee1d14460))
* **spec-oracle:** tolerate bold-label AC preamble; warn on empty AC section ([f272502](https://github.com/ramboz/servo/commit/f272502753e528d614b6d32435e1a87977c54786))


### Documentation

* **bugs:** file bugs 001-003 from external dogfood ([e513aa5](https://github.com/ramboz/servo/commit/e513aa5e9cbaab88b29fd8dde26490d6d015adff))
* **decisions:** propose ADR-0021/0022/0023 from external dogfood ([676549f](https://github.com/ramboz/servo/commit/676549f39944cd39222182f6b345a26215737f1b))
* **specs:** draft spec 019 compile-core-simplification ([b6bb055](https://github.com/ramboz/servo/commit/b6bb055e962cdaf6327c3d8efef6136ab1ab5fcd))

## [0.5.1](https://github.com/ramboz/servo/compare/v0.5.0...v0.5.1) (2026-07-01)


### Bug Fixes

* **python:** baseline servo against Python 3.9 (ADR-0020) ([726e410](https://github.com/ramboz/servo/commit/726e410d9cbc72d513919a105034df24b9dc2ad7))
* **scaffold:** detect Node's built-in test runner (node --test) ([d068b68](https://github.com/ramboz/servo/commit/d068b68524a932f6ce8969e9a8bd21ecbf768553))

## [0.5.0](https://github.com/ramboz/servo/compare/v0.4.0...v0.5.0) (2026-07-01)


### Features

* **docs:** host-native phase-hint contract (013-01) ([3133be3](https://github.com/ramboz/servo/commit/3133be3bcd1cbfcd0995cd119b5d77b27932af9a))
* **execution-planner:** compile ADR-0016 execution plan (016-01) ([e05a4c4](https://github.com/ramboz/servo/commit/e05a4c4069c394bc927e8d211b385361bed06eb4))
* **execution-planner:** surface reasons + missing_evidence at the Compile gate (015-03) ([fe7b8d7](https://github.com/ramboz/servo/commit/fe7b8d728234f85ee5d2a45201ce8c266a8b7442))
* **heartbeat:** add whole-pass run cost ceiling ([d756de8](https://github.com/ramboz/servo/commit/d756de8f06049e52a603608d0bd816dead835d20))
* **heartbeat:** candidate-dispatch — oracle-gated isolated-worktree loop dispatch (011-03) ([d50e152](https://github.com/ramboz/servo/commit/d50e15252ad693467fc8f0a8ef5f73cbdba31c15))
* **heartbeat:** ship heartbeat skill surface ([7c19a69](https://github.com/ramboz/servo/commit/7c19a69e1baa4b712bf856e242d51bb7dce9f7d2))
* **heartbeat:** triage-state-spine — merge, retention, status verb (011-02) ([e194bab](https://github.com/ramboz/servo/commit/e194bab99474bead2cb2bd9d4bd759fba5590f67))
* **scaffold:** add servo availability breadcrumb ([a3425b3](https://github.com/ramboz/servo/commit/a3425b32f96f107807575dbde6031e0cb009d463))
* **suitability:** /servo:edd-suitability skill surface + --json/--explain (015-04) ([db03d46](https://github.com/ramboz/servo/commit/db03d4641b6a563e15620e2be9e318992b575c3e))
* **suitability:** add EDD suitability verdict analyzer (015-01) ([fd542d6](https://github.com/ramboz/servo/commit/fd542d608e6414fb3dd8665d201e52a485c6e761))
* **suitability:** populate missing_evidence with closed-taxonomy items (015-02) ([af57986](https://github.com/ramboz/servo/commit/af57986a0bf3509f77e4e65542d035d966516f69))


### Bug Fixes

* **heartbeat:** code event-disqualified CI runs as ci_non_actionable_event ([e725acb](https://github.com/ramboz/servo/commit/e725acba7447199025c411f513ac13a579f23e33))
* **suitability:** keep edd-suitability host-only, not scaffold-vendored (015-04 follow-up) ([bd03813](https://github.com/ramboz/servo/commit/bd0381347f5db324c1f0f3d6968ffa94f338f3a4))


### Documentation

* **decisions:** accept ADR-0005 (eval as a frozen oracle component) ([#11](https://github.com/ramboz/servo/issues/11)) ([ec438b9](https://github.com/ramboz/servo/commit/ec438b97aaf0d35c2613452fc7ddd92b7c714e1d))
* **decisions:** accept ADR-0011 (host-native phase hints) ([716e2da](https://github.com/ramboz/servo/commit/716e2da815713d69a0c7927494e585948542a138))
* **decisions:** accept ADR-0019 (eval authoring stays entirely servo-owned) ([a908a26](https://github.com/ramboz/servo/commit/a908a264d2c7e83b6c142ea4cd7fbfb04d961294))
* **decisions:** ADR-0017 (Proposed) — conformance scores + trend ledger half ([8fcba7c](https://github.com/ramboz/servo/commit/8fcba7c7a531a4796915928bde7c9bcadb93545d))
* **decisions:** ADR-0018 — suitability gates Compile, not the heartbeat (015-05 spike) ([d7562e0](https://github.com/ramboz/servo/commit/d7562e0fa92be4c467165ed589df65a804140ce9))
* **decisions:** reserve adr-0019-eval-authoring-servo-owned ([316139b](https://github.com/ramboz/servo/commit/316139b62d762c7371ac249839ac9f7279dd15a2))
* **refinement-todo:** track reciprocal servo-available breadcrumb for jig slice-land ([1e3a3ad](https://github.com/ramboz/servo/commit/1e3a3adea11dda71499fbef27577ee3a58b125c5))
* **workflow:** capture host-native phase hint follow-up ([b8503f1](https://github.com/ramboz/servo/commit/b8503f11b24b409d755fe80c2633f4579799baff))

## [0.4.0](https://github.com/ramboz/servo/compare/v0.3.0...v0.4.0) (2026-06-13)


### Features

* **agent-loop:** detach + Routine-ready unattended runs (003-08, closes ADR-0008 rebase) ([4b77a1d](https://github.com/ramboz/servo/commit/4b77a1de96dfdab6591c1a1a0e857c7be8ce89b1))

## [0.3.0](https://github.com/ramboz/servo/compare/v0.2.1...v0.3.0) (2026-06-13)


### Features

* **agent-loop:** add /goal-driven loop driver (003-06) ([61f774d](https://github.com/ramboz/servo/commit/61f774d72a0646472cf6ca9ef5e5945c75173697))
* **agent-loop:** add plateau noise floor δ (ADR-0005 clause 4) ([#9](https://github.com/ramboz/servo/issues/9)) ([01d27bd](https://github.com/ramboz/servo/commit/01d27bd835a3b7c093dd9d643731d1689cb43e58))
* **agent-loop:** portable guardrails — vendor gate.py, dirty-tree refusal, host-scope routing (003-07) ([fb0b62c](https://github.com/ramboz/servo/commit/fb0b62c29b8437f114e8103c6671f59ff0a188f2))
* **design-eval:** add /servo:design-eval skill (spec 012, ADR-0009) ([#8](https://github.com/ramboz/servo/issues/8)) ([028e0a3](https://github.com/ramboz/servo/commit/028e0a334c5366019935680cab3367e552b47eba))
* **heartbeat:** add read-only discovery pass and triage inbox (slice 011-01) ([254acb0](https://github.com/ramboz/servo/commit/254acb0d13e969075ae7620f0a07d0b3f3f18d5a))


### Documentation

* **decisions:** accept ADR-0008 (rebase agent-loop onto autonomy primitives) ([#6](https://github.com/ramboz/servo/issues/6)) ([9fdb8f6](https://github.com/ramboz/servo/commit/9fdb8f6978d835ba2b41a32dcb7c0084be62291f))

## [0.2.1](https://github.com/ramboz/servo/compare/v0.2.0...v0.2.1) (2026-06-12)


### Documentation

* **specs:** mark 010 release-automation DONE — release 0.2.0 verified live ([11ef66e](https://github.com/ramboz/servo/commit/11ef66ea6754a2733fdf714615bf5be693949951))

## [0.2.0](https://github.com/ramboz/servo/compare/v0.1.0...v0.2.0) (2026-06-12)


### Features

* **release:** add automated release pipeline (release-please + conventional-commit gate) ([#2](https://github.com/ramboz/servo/issues/2)) ([d530083](https://github.com/ramboz/servo/commit/d530083f5290dfcb4dec6928424198b68a62bae4))
* spec 001 (scaffold-init) — five slices, end-to-end DONE ([b1855fb](https://github.com/ramboz/servo/commit/b1855fb57dcfcd21399d81de83282042cdb6cc6f))
* spec 002 (quality-gate) — five slices, end-to-end DONE ([d5e7e50](https://github.com/ramboz/servo/commit/d5e7e50b42579b27552a67943c192fce71f25022))
* spec 003 slice 003-01 (invoke-loop) — loop.py + 35 tests ([ea6de43](https://github.com/ramboz/servo/commit/ea6de43d5b88977b7a9011dca122211a6c497117))
* spec 003 slice 003-02 (cost-ceiling) — loop.py + 17 tests ([e4afaff](https://github.com/ramboz/servo/commit/e4afaff9cc389ce9913f3727583e63f42fe8d6c6))
* spec 003 slice 003-03 (context-fill-gate) — loop.py + 31 tests ([02c86d4](https://github.com/ramboz/servo/commit/02c86d48e03b1b3af6ffc6c92f97d94f6d095088))
* spec 003 slice 003-04 (checkpoint-resume) — loop.py + 43 tests ([3df14b0](https://github.com/ramboz/servo/commit/3df14b08783b6a69a818c31bea609ac7846e7a1b))
* spec 003 slice 003-05 (stuck-loop-and-handoff) — closes spec 003 ([3710d4f](https://github.com/ramboz/servo/commit/3710d4f6ffffe7b82214ee2b5514df94f1779773))
* spec 004 slice 004-01 (install-and-judge) — meta-judge Stop-hook installer ([a403835](https://github.com/ramboz/servo/commit/a403835f5ca5b4eb689b1dcab71e6e353bc75954))
* spec 004 slice 004-02 (fail-open-safety) — env-error warnings + ADR-0006 ([94ef3cf](https://github.com/ramboz/servo/commit/94ef3cf69d9a14579dcfb14e17b378b076a11107))
* spec 004 slice 004-03 (idempotent-install-and-backup) — settings.json backup + merge-safe re-install ([3cbbeed](https://github.com/ramboz/servo/commit/3cbbeedd2e706b6e076fd4002e16f54b445668d8))
* spec 004 slice 004-04 (uninstall-and-status) — reverse the install + report state ([9761fab](https://github.com/ramboz/servo/commit/9761fabcd5659d76ce30dff0c316aa14ce67044b))
* spec 004 slice 004-05 (skill-and-dogfood) — /servo:oracle-hook surface + end-to-end dogfood — closes spec 004 ([959ef69](https://github.com/ramboz/servo/commit/959ef69ef7ee7abff1af44bb87b888f814b48f8f))
* spec 006 slice 006-01 (evidence-plan) — spec→evidence planner ([8c38c78](https://github.com/ramboz/servo/commit/8c38c78f88861f630f661a37701fd137e204abf4))
* spec 006 slice 006-02 (check-library) — stdlib check engine + JSONL evidence ([197fcc7](https://github.com/ramboz/servo/commit/197fcc7a09e89ce94d3a2ab0b6cf2f1a38ef3372))
* spec 006 slice 006-03 (oracle-overlay) — install spec checks as an oracle.sh component ([825ea32](https://github.com/ramboz/servo/commit/825ea32b15d63a8a97d52e2ce99de2dbd2202741))
* spec 006 slice 006-04 (freeze-and-controls) — anti-self-grading freeze layer for spec-oracles ([c80d692](https://github.com/ramboz/servo/commit/c80d692f41e89028c5e79607bd558d303bff7740))
* spec 006 slice 006-05 (skill-and-dogfood) — /servo:spec-oracle surface + jig dogfood — closes spec 006 ([0686cad](https://github.com/ramboz/servo/commit/0686cadfaab2fb5e13a41907bb81fde66fe0adda))
* spec 007 install contract and release zip ([36b2217](https://github.com/ramboz/servo/commit/36b2217ac35d23a12bbb34915e0071fe1438acc5))
* spec 007 slice 007-03 (scaffold-runtime) — scaffold_runtime.py + verifier scaffold mode ([f03ea16](https://github.com/ramboz/servo/commit/f03ea16d0cd5cb64a98b04151a4b9b201b2a8bea))
* spec 007 slice 007-04 (scaffold-fidelity) — self-contained vendored helpers + fidelity verifier ([10ebbb7](https://github.com/ramboz/servo/commit/10ebbb72a99306e0847111b0c58b89205969ad0d))
* spec 007 slice 007-05 (docs-and-ci) — install docs + CI verification — closes spec 007 ([85ca033](https://github.com/ramboz/servo/commit/85ca03326ba1e27c4086b9ba49653e81b58c400e))


### Bug Fixes

* deterministic signal tests + skip shellcheck when Docker daemon is down ([d7860d4](https://github.com/ramboz/servo/commit/d7860d417410181a85858c313473851926c41b3e))


### Documentation

* add STATUS markers to slices 003-01 and 003-02 ([7be9280](https://github.com/ramboz/servo/commit/7be92807dc3a2e552556865a9195192a7f02154e))
* align hub docs with jig 1.5.0 conventions ([43eb2c9](https://github.com/ramboz/servo/commit/43eb2c9f0c4ba5dbf4825e895590ea172f249ae5))
* **decisions:** add ADR-0005 — eval as a frozen oracle component ([51cb289](https://github.com/ramboz/servo/commit/51cb28963d1636a36e1e744840ec09675fbe7c5d))
* **decisions:** ADR-0005 — note multimodal eval inputs (design-conformance consumer) ([50cc1b1](https://github.com/ramboz/servo/commit/50cc1b1a53795ef0464bd2c7d4d98ba0941bd52b))
* draft spec 006 spec-oracle ([e65b797](https://github.com/ramboz/servo/commit/e65b797b880a4dfe1df3e2fae31b1475d1e2e013))
* draft spec 007 install surfaces ([cf7c490](https://github.com/ramboz/servo/commit/cf7c490949b9f9e35e4f505338144653e39befae))
* drop curriculum module references from user-facing files ([e910aa3](https://github.com/ramboz/servo/commit/e910aa30259b747a94b75913036fe4f4cedea336))
* name the long-running-session gaps each planned spec closes ([f0a5571](https://github.com/ramboz/servo/commit/f0a55714634c5987878e47fc00eddb69907c8fa3))
* spec 003 (agent-loop) READY_FOR_IMPLEMENTATION + ADR-0003 + ADR-0004 ([72e4d2c](https://github.com/ramboz/servo/commit/72e4d2ccc4aed0165d5b73a13d60c9fd59457781))
* spec 003 pre-spec research spike — Claude Code headless surface ([e354a25](https://github.com/ramboz/servo/commit/e354a250674b0ecc1f40c3c18203d014e7c2dac4))
* **specs:** add DRAFT spec 005 — variant-race (scope capture, parked) ([13a2fcd](https://github.com/ramboz/servo/commit/13a2fcdfbddcd8f3173b3aac6aa368d8c7b1230d))
* **specs:** add DRAFT spec 008 — eval-authoring (scope capture, parked) ([4f1fd17](https://github.com/ramboz/servo/commit/4f1fd17531fe2fb861d89c782cd4859eb77bd64c))
* **specs:** add specs 009 + 010 + ADR-0007 (release/CI alignment) ([1ce7e72](https://github.com/ramboz/servo/commit/1ce7e72389ebe4b3613a99f1f90d20d890bf27ad))
* **specs:** draft spec 011 heartbeat front-end ([#4](https://github.com/ramboz/servo/issues/4)) ([df115d3](https://github.com/ramboz/servo/commit/df115d32ca3e02b0b35d433b01db256c495db1dd))
* **specs:** finalize spec 009 (ci-hardening) → DONE — CI proofs captured ([70be540](https://github.com/ramboz/servo/commit/70be54031e8f89f547b534f809a61fe37b4dbdf5))
