# /acs:create-ticket — Step 2 with no user to ask

Open this at Step 2 when you cannot reach the user (a non-interactive run),
or when the request itself delegates the record's decisions up front. Steps
2-3, User interaction and Finish are SKILL.md's.

If you genuinely cannot reach the user (e.g. a non-interactive run), return
`<handoff skill="create-ticket" ticket-id="<id>" status="needs_input">` with the
open `<questions>` instead of guessing — see Finish.

**A request that delegates the record up front IS the confirmation.** When
the request itself says to decide without waiting — "you decide", "use your
judgement", "no need to confirm", "raise it with sensible defaults" — items
1 and 3-5 are answered by that delegation: record each field you settle
(type, priority, every acceptance criterion, no due date)
with `clarify.py add … --source assumption --rationale "…"`, keep
`docs_only` at `false` (the one value a delegation never sets to `true`),
list the assumptions under the completion report's Findings, and continue
to Step 3. Never return `needs_input` for a question the request already
delegated — a headless run that hands off on "story or task?" after being
told to decide has produced nothing. Item 2, the PRD link, is never
assumed past — a delegation never confirms going beyond the PRD: it can choose
among the PRD's features and requirements, but work no feature PRD describes
still ends the run `failed`, pointing at `/acs:create-prd` (ADR-0144).

The same rule holds for any question User interaction would ask. When you
genuinely cannot reach the user (a non-interactive run): return a `<handoff
... status="needs_input">` with `<questions>` instead of guessing. A request
that delegates the decisions up front is not such a case — it is answered, by
assumption entries, per Step 2's delegation rule.
