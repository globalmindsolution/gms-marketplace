"""s04 — routing evals for all 25 skills (paid, E1.2).

Three kinds of probe, 27 in all, covering every skill:

1. Description-trigger (23 model-invocable skills): a natural-language request
   that describes the intent *without naming the skill* must route to that
   skill. A miss is a real finding — the skill's `description` frontmatter
   isn't discriminating that request from its neighbors.

2. Explicit-invocation (the 2 user-only skills `install-hooks` and `update`,
   which set `disable-model-invocation: true`): the explicit `/acs:<skill>`
   command must still route to the skill. The model is forbidden from
   auto-routing to these, so a description probe can't reach them — but the
   explicit path the user types must work.

3. Negative-routing (same 2 user-only skills): a bare description of their
   intent must NOT auto-route to them, proving `disable-model-invocation` is
   honored — the model should pick a different skill or no skill at all.

A description probe is decided by the first `Skill` tool_use the model makes; an
explicit probe is decided by the session's registration list, before any model
turn (the CLI expands a typed slash command into the prompt, so it never reaches
the `Skill` tool at all). Every assertion label states which rule decided it, and
a probe the harness could not measure is never a pass. The session is killed as
soon as a probe is decided, so no skill body runs.
"""

from harness import Sandbox, Check

META = {
    "name": "skill_triggers",
    "tier": "paid",
    "goal": "route",
    "summary": "right skill routes for all 25 (23 by description, 2 user-only by explicit cmd + no-auto-route)",
}

# Description-trigger + explicit-invocation cases.
# (label, init?, request, expected skill).
#   - The 23 model-invocable skills use a request that avoids naming the skill.
#   - The 2 user-only skills (install-hooks, update) set
#     disable-model-invocation, so they can only be reached by the explicit
#     `/acs:<skill>` command — a description would never route to them. Their
#     positive case is therefore the literal explicit invocation; their
#     no-auto-route guarantee is covered by NEGATIVE below.
CASES = [
    ("setup", False,
     "Set up and initialize the acs configuration for this repository.",
     "setup"),
    ("ship", True,
     "Take a CSV-export feature all the way from idea to an open pull request — "
     "drive the whole delivery pipeline end to end.",
     "ship"),
    ("handoff", True,
     "Let's stop here and hand this work off to a fresh session so I can "
     "resume it later without losing state.",
     "handoff"),
    ("create-prd", True,
     "Write the product requirements document — vision, personas, goals and "
     "success metrics — for this product.",
     "create-prd"),
    ("create-requirements", True,
     "Reverse-engineer a living functional and non-functional requirements doc "
     "set for this repo from the source that already exists — one file per "
     "feature, each item cited back to where it lives.",
     "create-requirements"),
    ("create-architecture", True,
     "Generate the architecture documentation: the C4 diagrams and the "
     "high- and low-level design flows for this product.",
     "create-architecture"),
    ("create-project", True,
     "Scaffold the repository skeleton — build config, test framework, CI — "
     "from the approved architecture docs.",
     "create-project"),
    ("create-quality", True,
     "Author and maintain the test-strategy and coverage-policy docs for this "
     "product's quality doc set.",
     "create-quality"),
    ("create-operations", True,
     "Author and maintain the release-process, runbooks, observability, and "
     "incident-response docs for this product's operations doc set.",
     "create-operations"),
    ("create-principles", True,
     "Author and maintain the engineering principles and rationale doc set "
     "for this product.",
     "create-principles"),
    ("create-standards", True,
     "Author and maintain the coding standards and conventions doc set — "
     "style, naming, and the review checklist — for this product's codebase.",
     "create-standards"),
    ("create-docs", True,
     "Bootstrap the quality and the operations doc sets in one parallel "
     "fan-out instead of running one and then the other, each landing as its "
     "own docs-only pull request.",
     "create-docs"),
    ("standardize-project", True,
     "Audit this existing repo against our approved doc set and readiness "
     "tooling, then additively scaffold whatever's missing without ever "
     "touching the source we already have.",
     "standardize-project"),
    ("create-ticket", True,
     "Create a ticket to add a dark mode toggle to the settings page.",
     "create-ticket"),
    ("create-design", True,
     "Settle the system design for ticket EVAL-1, weighing options and "
     "trade-offs, before we start implementing it.",
     "create-design"),
    ("code", True,
     "Implement ticket EVAL-1 from its specs, using TDD on a dedicated branch.",
     "code"),
    ("docs-sync", True,
     "Ticket EVAL-1's implementation is finished and committed but has no "
     "pull request yet — work out from the branch diff which documentation the "
     "change made wrong or missing, and commit the fixes onto that same branch.",
     "docs-sync"),
    ("create-pr", True,
     "Open the pull request for ticket EVAL-1's finished implementation.",
     "create-pr"),
    ("merge-pr", True,
     "Land ticket EVAL-1: merge its pull request and finish the ticket.",
     "merge-pr"),
    ("metrics", True,
     "Show me a dashboard of throughput, cost, coverage and review effort for "
     "this repo, read straight from the workspace state — no external tools.",
     "metrics"),
    ("usage", True,
     "Show me a breakdown of AI spend, token consumption, and average working "
     "time per ticket for this repo — not delivery throughput, just the tool "
     "usage and cost side.",
     "usage"),
    ("test", True,
     "Run the configured test suites for this repo and give me a results "
     "report, opening a regression ticket for anything that broke.",
     "test"),
    ("release", True,
     "Cut a new release — draft the changelog section from what's merged "
     "since the last tag, bump the version in both manifests, and open the "
     "release PR for me to review and merge.",
     "release"),
    # User-only skills: positive case = the explicit command the user types.
    # (A description can't reach them — see NEGATIVE for that guarantee.)
    ("install-hooks", True,
     "/acs:install-hooks",
     "install-hooks"),
    ("update", True,
     "/acs:update",
     "update"),
]

# Negative-routing cases for the two user-only skills: a bare description of
# their intent must NOT auto-route to them (disable-model-invocation is
# honored). PASS when the model picks anything other than the forbidden skill
# — a different skill, or no skill at all (None).
# (label, init?, request, forbidden skill)
NEGATIVE = [
    ("install-hooks", True,
     "Set up the local git hooks for this clone so our configured commit-message "
     "and branch-name conventions are enforced before anything gets pushed.",
     "install-hooks"),
    ("update", True,
     "Check whether there's a newer version of the acs plugin available and "
     "summarize what changed since the version I have installed.",
     "update"),
]


def run():
    check = Check(META["name"])

    def _norm(skill):
        # The Skill tool_use may report the skill name bare ("setup") or
        # namespaced ("acs:setup") depending on the runtime; compare on the
        # bare name so the assertion is independent of that.
        return skill.split(":", 1)[-1] if isinstance(skill, str) else skill

    for label, init, request, expected in CASES:
        want = "acs:" + expected
        with Sandbox(prefix="EVAL", slug="trig", init=init) as sb:
            # Model routing is mildly non-deterministic; re-probe up to twice
            # before calling it a miss. Cheap (~5s/probe) and contained to the
            # flaky case — no whole-suite retry needed. An explicit probe is
            # decided by the registration list, so re-probing it proves nothing.
            got, how = sb.trigger_detail(request)
            for _ in range(2):
                if _norm(got) == expected or how != "skill_tool_use":
                    break
                got, how = sb.trigger_detail(request)
        check.ok("%-20s -> %s [%s]" % (label, want, how), _norm(got) == expected,
                 "got=%r" % got)

    # Negative routing: a bare description must NOT auto-invoke a user-only
    # skill. One probe is enough — a single auto-route is already a failure;
    # re-probing could only mask a real disable-model-invocation regression.
    for label, init, request, forbidden in NEGATIVE:
        with Sandbox(prefix="EVAL", slug="trig", init=init) as sb:
            got, how = sb.trigger_detail(request)
        check.ok("%-20s -/> %s (no auto-route) [%s]" % (label, "acs:" + forbidden, how),
                 _norm(got) != forbidden, "got=%r" % got)
    return check
