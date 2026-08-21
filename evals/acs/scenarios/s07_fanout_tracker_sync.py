"""s07 — epic fan-out tracker sync (forge, G11).

Runs two real `claude -p` sessions against the SAME sandbox: (1)
`/acs:create-ticket` creates an epic with an approved-design precondition
already confirmed and asserts its creation run ends with `children == []`
(the invariant MAR-78 ships — epic creation no longer mints children); then
(2) a second, separate `/acs:create-ticket <epic-id> --fan-out` invocation
mints the epic's >=2 confirmed children under `tracker.provider: github`.
Assertions run on workspace state (never the model's prose, per this
harness's established convention, s02_create_ticket_artifacts.py:7): every
fanned-out child's `ticket.json` must end with a non-null `external`
carrying `provider == "github"` and a non-empty `key` (MAR-84 AC-2/AC-6),
and the epic's own `external.key` must be identical before and after the
fan-out run (an unchanged tracker sync — a duplicate-issue regression would
show up here as a changed key).

Tier `forge` (evals/README.md:61 — "needs a GitHub remote ... Not yet
populated") is the correct, already-established classification for this
scenario: it needs real `gh` access against a live GitHub repo/project, which
`--paid` alone does not guarantee. This is a GUARDED scenario (MAR-84 decision
C-7): `forge` has no populated runtime convention yet (no
credentialing/sandbox-repo helper exists in harness.py for it), and this spec
does not invent one. So this scenario runs the real fan-out assertion ONLY
when `ACS_EVAL_GH_PROJECT` (the owner/project-number pair `gh` itself needs)
is set in the environment; otherwise it SKIPS with a clear, documented
reason — it never fakes green and never asserts a non-null `external` under
the default `tracker.provider: local` sandbox (which has no real `gh` to push
to).
"""

import os

from harness import Sandbox, Check

META = {
    "name": "fanout_tracker_sync",
    "tier": "forge",
    "goal": "G11",
    "summary": "/acs:create-ticket syncs every epic fan-out child's external via GitHub",
}

PROMPT_CREATE = (
    'Run the /acs:create-ticket skill with this request: '
    'Create an EPIC called "Wishlist" (needs_design TRUE, already confirmed). '
    'Create ONLY the epic itself in this run -- propose NO child breakdown and '
    'mint NO children now. Treat all of this as already confirmed and DO NOT '
    'ask me anything. Complete the full skill including its reflection cycle '
    'and the tracker-sync step.'
)

PROMPT_FAN_OUT = (
    'Run the /acs:create-ticket skill with this request: '
    '/acs:create-ticket EVAL-1 --fan-out. Fan out epic EVAL-1 into exactly 2 '
    'confirmed child STORY tickets: "Wishlist API" and "Wishlist UI" (both '
    'needs_design FALSE, already confirmed). This epic has no approved '
    'design.md yet -- proceeding without one is already confirmed, so do not '
    'ask about it. Treat all of this as already confirmed and DO NOT ask me '
    'anything. Complete the full skill including its reflection cycle and the '
    'tracker-sync step.'
)


def run():
    check = Check(META["name"])

    gh_project = os.environ.get("ACS_EVAL_GH_PROJECT")
    if not gh_project:
        check.ok(
            "skipped: no real GitHub test project configured — set "
            "ACS_EVAL_GH_PROJECT (plus gh auth) to run the real fan-out "
            "assertion; this scenario never fakes green or asserts external "
            "under the default tracker=local sandbox",
            True,
        )
        return check

    with Sandbox(prefix="EVAL", slug="wishlist", init=True, tracker="github") as sb:
        r1 = sb.run_skill(PROMPT_CREATE)
        cost1 = r1.get("cost_usd")
        check.cost = cost1 or 0
        if not check.ok("creation session completed without error", r1["ok"],
                        (r1.get("stderr") or r1.get("raw") or "")[:200]):
            return check  # nothing to assert on if the session died

        epic_id = "EVAL-1"  # first allocation under prefix EVAL
        epic_before = sb.ticket_json(epic_id, "ticket.json")
        check.ok("epic creation run ends with children == []",
                 epic_before.get("children") == [], epic_before.get("children"))
        epic_external_before = epic_before.get("external")

        r2 = sb.run_skill(PROMPT_FAN_OUT)
        cost2 = r2.get("cost_usd")
        check.cost = (cost1 or 0) + (cost2 or 0)
        if not check.ok("fan-out session completed without error", r2["ok"],
                        (r2.get("stderr") or r2.get("raw") or "")[:200]):
            return check  # nothing to assert on if the session died

        epic_after = sb.ticket_json(epic_id, "ticket.json")
        children = epic_after.get("children", [])
        check.ok("epic has at least 2 fanned-out children", len(children) >= 2,
                 children)
        check.eq("epic external.key is unchanged across the two runs",
                 (epic_after.get("external") or {}).get("key"),
                 (epic_external_before or {}).get("key"))

        for child_id in children:
            child = sb.ticket_json(child_id, "ticket.json")
            external = child.get("external")
            check.ok("child %s has non-null external" % child_id,
                     external is not None, external)
            if external:
                check.eq("child %s external.provider is github" % child_id,
                         external.get("provider"), "github")
                check.ok("child %s external.key is non-empty" % child_id,
                         bool(external.get("key")), external)

    return check
