---
slice: 042-04 — host-driven verified-wrapped
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T05:45:35Z
prompt_source: review.py frame-critique docs/specs/042-campaign-orchestration/spec.md 042-04 skills/agent-loop/loop.py skills/heartbeat/campaign.py skills/heartbeat/SKILL.md docs/architecture.md docs/specs/042-campaign-orchestration/slice-04-host-driven-verified-wrapped.md (round 2)
---

VERDICT: pass (round 2)

ROUND 1 — needs-changes. The single highest-risk load-bearing premise was that
verified-wrapped "cryptographically binds provenance against an adversarial worker
who controls the worktree" — the slice's stated reason to exist (closing the
042-03 advisory gap). That premise was FALSE as framed: `_verify_wrapped` reads the
halt fingerprint, start HEAD, allow_dirty and rendered outcome from the
worker-controlled `<worktree>/.servo/runs/<run_id>/state.json`; `_content_fingerprint`
is a public sha256 with no servo-held secret; and the base sha is disclosed in the
brief. So a worker can fabricate a self-consistent state.json without running
loop.py, pass verification, and launder chosen cost into enforced spend. Host-driven
mode holds no servo-side anchor to prevent this. The secondary finding: a forgery
produces a verification PASS, so the ~80%-verify kill criterion is blind to it.

ROUND 2 — pass. Resolution was path (1): RETRACT the "cryptographic/adversarial"
language and honestly re-scope 042-04 to the honest-worker (ADR-0049 A5) threat
model. The mechanism is unchanged; the claims were corrected at all sites
(campaign.py `_recheck_oracle` + `_verify_wrapped` + CLI_TIERS comment;
architecture.md; SKILL.md; slice-04 Assumptions + anti-horizontal-phasing). The
adversarial-forgery residual is disclosed as equivalent to the already-shipped
advisory tier's residual and tied to ADR-0049 A5; "verified, not declared" is
redefined as "verified against the loop's recorded state under A5, not
cryptographically against an adversary"; the adversarial anchor is correctly
located in servo-driven mode (042-02). The honest-worker value still justifies the
slice: for a compliant worker it catches post-halt edits (AC5), commit-before-record
(AC3) and dirty/off-base starts (AC2), re-renders metered result/cost from the
loop's state (AC4) rather than the self-reported line, and counts it as enforced
spend (which advisory never does) — and the motivating runaway is a property of the
loop's own execution under an honest worker, so metering it is a real bound. The
frame survives the strongest attack.
