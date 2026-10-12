# Native frame review, round 1 (2026-10-12)

Source: independent `jig:reviewer` task `native-spec-frame`, generated through
`review.py frame-critique`. This preserves the failed framing, not a fabricated
implementation verdict.

034-04: **pass**. Effective fresh-call/tool restrictions are a live prerequisite;
candidate generation preserves advisory independent review and human per-AC
authority. Not evidence of native implementation.

034-05: **needs-changes**. "Required" decoding controls were undefined. Existing
generic/content defaults include temperature/max_tokens, but complete native help
exposes neither. Define a supported positive native policy rather than delivering
only refusal or silently ignoring frozen controls.

034-06: **needs-changes**. Same decoding issue inherited from text; design defaults
include temperature 0.6/max_tokens 1024. Actual image-sensitive/model-commanded
proof is correctly a separate prerequisite, not established by text success.

034-01 readiness: **needs-changes** because ADR0043 was still Proposed.
034-02 readiness: **needs-changes** because ADR0043 was Proposed and legacy
native state attribution was undefined (the prototype persisted no backend).

Disposition: ADR0043 was accepted after its passing frame critique; 034-02 now
states identifiable native-state refusal and the unmarked version-1 ambiguity.
New ADR0040 defines deliberate frozen native-default decoding, runtime-version
compatibility and explicit rejection of numeric controls. Its independent frame
critique and subsequent 034-05/06 frame verdicts pass; live prerequisites remain.
