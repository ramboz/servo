# Native candidate frame, round 1 (2026-10-12)

Independent `jig:reviewer` candidate-file-frame returned **needs-changes** for
Proposed0042 and the034-05 supplement. File/base/snapshot/hash scope was sound,
but candidate text does not supply the generic constraint actual-value extractor.
Existing constrained cases obtain actuals only from a fake hook, after judging.

Revised policy explicitly limits native file-v1 to constraint-free scored cases;
unsupported constraints and native fake-actuals injection refuse before model
calls. Do not infer measurements from case.input or conceal the inherited
actual-value residual behind a constraint-free installed proof. No old API
record/hash/behavior amendment is authorized or performed.
