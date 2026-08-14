# LESSONS — auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation — do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 — When an AC requires surfacing a domain timestamp on a non-happy-path branch (e.g. when something was previously done), add that field to the response schema up front — a short-circuit that returns only the enum result silently drops it and nothing catches the omission until spec re-verification.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `api-contracts` · harmful: 0
- features: ticket-platform
- evidence: spec.md GATE-02 / app/api/v1/gate.py:36-37 (api-contracts)
- last seen: 2026-08-14T12:39:42Z

### L-002 — When a spec AC says the user selects from a list of external search results, do not fold the search into the create/submit endpoint and auto-pick the first match — expose a dedicated search/list endpoint so the UI can render a real picker before the create action fires.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `api-design` · harmful: 0
- features: ticket-platform
- evidence: spec.md CATALOG-01 / app/api/v1/events.py:41-53 (api-design)
- last seen: 2026-08-14T12:39:42Z

### L-003 — When a spec AC names a specific HTTP status code for an authorization failure, decide explicitly between role-based denial (403) and ownership/existence-hiding denial (404) per case, and reconcile the spec's wording with whichever is actually safer rather than leaving the two conflated under one status code.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `auth` · harmful: 0
- features: ticket-platform
- evidence: spec.md AUTH-02 / app/api/v1/organizer.py (auth)
- last seen: 2026-08-14T12:39:42Z

### L-004 — When a test tampers a base64url-encoded signature/token to prove verification rejects it, flip a byte in the middle of the payload (or corrupt multiple characters), not just the value's last character — the last base64 group can carry unused padding bits, so a single-character flip there has a measurable chance of leaving the decoded bytes unchanged and producing a flaky false-pass.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `test-design` · harmful: 0
- features: ticket-platform
- evidence: tests/unit/test_security.py:68 test_tampered_token_signature_is_rejected (test-design)
- last seen: 2026-08-14T12:47:08Z

## Quarantined (failed when applied — ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
