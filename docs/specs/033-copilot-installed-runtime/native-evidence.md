# Native evaluation evidence (2026-10-12)

All executed public-dummy probes use Copilot CLI **1.0.96-2**, commanded
**gpt-5.4**, no automatic provider fallback or permission grants. These are
capability/fixture proofs, not production human-approval claims or USD limits.

## Fresh read-only text and authoring

Isolated-home native invocation used a nonempty `--available-tools=view`
whitelist, write/shell denials, disabled built-in MCPs/custom instructions/
automatic updates and bounded subprocess time. Under a requested write attempt,
the model returned `write_succeeded:false`, no tool execution and no marker file.
This is observed behavior plus documented restrictions, not an observed denied
callback or signed decoding proof. An earlier empty whitelist did not establish
restriction and is not counted as such.

The implemented authoring helper expanded the public toy calculator goal and
independently reviewed five candidate criteria in two different fresh sessions.
Platform assistant metadata reported gpt-5.4 for both, runtime1.0.96-2.
Human curation/approval remained pending. After control/telemetry corrections,
the generated `hosts/copilot/.github/skills/eval-authoring/eval_authoring.py`
helper ran that public fixture from a separate isolated-home consumer cwd.
It exited0, produced exactly five `acs`, all `approval_status:proposed`, and
distinct expansion/review sessions under gpt-5.4/runtime1.0.96-2. Both actual
terminal usage objects were retained (premiumRequests1 each, no USD conversion).
No implicit approval or write-tool grant occurred.

## Installed content consumer

Normal native init/freeze/install and vendored scorer ran a real "four matches
four" candidate/reference fixture under an isolated home. No fake-score hook or
fake executable was used. Score **1.0**, configured native-default/gpt-5.4/
exact1.0.96-2; installed ledger transport copilot, `cost_usd:null`.
One sample was used for this minimal transport proof, not as a recommendation
to weaken the existing statistical policy.

## Vision capability and installed design consumer

Raw CLI received two real generated256x256 PNG attachments with neutral
first/second names and no color cues in the prompt. It correctly identified
red versus blue and returned score0, with successful terminal event and
platform gpt-5.4 metadata.

The full installed design consumer subsequently used the existing manual capture
provider, normal explicit fixture approval/freeze/install, real reference/
candidate attachments and native scorer. Score **0.0** for different solid
colors; ledger transport copilot, `cost_usd:null`, unpriced marker
`[design_fidelity]`, manual-capture provenance retained. Fixture self-approval is
labelled fixture consent, not independent production review. No injected score.

## Generic consumer gap and disposition

The original full emitted generic proof reached a real pre-existing
candidate-gather stub and could not score. It was **not** replaced with fake
scores or case.input as output. AcceptedADR0042 defines a bounded native-only,
constraint-free candidate-file acquisition policy; actual-value extraction stays
unsupported and must refuse before models. Actual emitted/frozen/installed
generic proof now passes after that real implementation: normal params/rubric/
dataset/emit/freeze/install, real external toy-calculator output `4`, then
native score **1.0** with no score/actual injection. The installed ledger records
candidate_file `answer.txt`, `component-file-utf8-v1`, one byte, and SHA256
`4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a`.
Actual native usage is captured; USD remains null and the installed component
is marked unpriced. This constraint-free proof does not supply unsupported
actual-value extraction or automatic system-under-test execution.

## Correction / final-proof status

Independent native compliance identified discarded usage, native injection-hook
bypasses and missing generic/packaged proofs. Those corrections and re-review
are implemented and undergoing independent re-review. Actual consumer evidence
does not by itself make slices DONE: required craft/architecture/reconciliation
and final integrated CI remain. Source/test fixtures stay distinct from actual
CLI consumers. New native judge fields are closed to the deliberate policy;
native score/actual injection is rejected before runtime/model/capture selection.
