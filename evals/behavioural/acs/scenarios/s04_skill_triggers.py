"""s04 — routing evals for all 32 skills (paid, E1.2).

Three kinds of probe, 38 in all, covering all 32 skill directories. v0.5.0
retired the `test` alias directory, which was the one skill with no probe of
its own, so there are no exclusions left:

1. Description-trigger (26 skills): a natural-language request that describes
   the intent *without naming the skill* must route to that skill. A miss is a
   real finding — the skill's `description` frontmatter isn't discriminating
   that request from its neighbors.

2. Explicit-invocation (the six internal legs: /acs:project's `create-project`
   and `standardize-project`, and /acs:code's four ADR-0095 delivery-path legs
   `code-trivial`, `code-small`, `code-standard`, `code-complex`): the explicit
   `/acs:<skill>` command must still route to the leg, because a user types it
   to resume an interrupted run on the path that run was already judged onto.

3. Negative-routing (the same six legs): a description of the leg's own subject
   must NOT auto-route to it — its entry point should pick it up. What delivers
   that is each leg's description, never a frontmatter flag. The four
   delivery-path negatives deliberately plant the path word itself ("a trivial
   two-line change", "a complex change: several modules, a migration"), because
   the leg is chosen from the ticket's recorded `delivery_path` — judged once
   from the plan — and never from how the request happens to be phrased.

The four doc-set legs /acs:create-docs used to fan out (`create-quality`,
`create-operations`, `create-principles`, `create-standards`) were folded INTO
it (ADR 0094), so they are neither skills nor probes any more: the
create-docs description probe is the one that covers all four sets.

A description probe is decided by the first `Skill` tool_use the model makes; an
explicit probe is decided by the session's registration list, before any model
turn (the CLI expands a typed slash command into the prompt, so it never reaches
the `Skill` tool at all). Every assertion label states which rule decided it, and
a probe the harness could not measure is never a pass. The session is killed as
soon as a probe is decided, so no skill body runs.

The suite-runner probe targets `run-e2e-tests`: the skills-independence
refactor renamed `test` to `run-e2e-tests` and left `test` behind as a
deprecated alias directory. v0.5.0 deleted the alias, so the intent routes to
`run-e2e-tests` and nothing else.

The 32 probed skills are every skill directory on disk. There is no exclusion
list: a skill with no probe is a defect, which
tests/acs/test_eval_trigger_detection.py catches.

Adding a probe moves the measured "all N green" routing-coverage claim the PRD
and roadmap carry, so a newly added probe is UNMEASURED until the next paid
run — it is not a green one. The eight delivery-path probes (four explicit,
four negative) are new with ADR-0095, and the `analyze-requirements` and
`review-code` probes are new with v0.5.0; all ten are in exactly that state.
"""

from harness import Sandbox, Check

META = {
    "name": "skill_triggers",
    "tier": "paid",
    "goal": "route",
    "summary": "right skill routes for all 32 (26 by description, 6 internal legs by explicit cmd + a description that must reach their entry point)",
}

# Description-trigger + explicit-invocation cases.
# (label, init?, request, expected skill).
#   - 26 skills are probed by description, with a request that avoids naming
#     the skill. Every shipped skill is model-invocable, so that is the
#     default; no skill sets disable-model-invocation.
#   - The 6 internal legs — /acs:project's two, /acs:code's four delivery-path
#     legs — are probed by the explicit `/acs:<skill>` command instead, because
#     that command must keep resolving: a user invokes a leg directly to resume
#     an interrupted run, which is what its argument-hint offers. What a leg
#     must NOT do is pick up a description of its own subject — its entry point
#     should — and that is covered by NEGATIVE below.
CASES = [
    ("setup", False,
     "Set up and initialize the acs configuration for this repository.",
     "setup"),
    ("ship", True,
     "Drive ticket EVAL-1 all the way through the delivery pipeline end to "
     "end, from where it left off up to an open pull request.",
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
     "/acs:create-project",
     "create-project"),
    ("create-docs", True,
     "Bootstrap the quality and the operations doc sets from their templates, "
     "tailored to our architecture, each landing as its own docs-only pull "
     "request.",
     "create-docs"),
    ("standardize-project", True,
     "/acs:standardize-project",
     "standardize-project"),
    ("code-trivial", True,
     "/acs:code-trivial",
     "code-trivial"),
    ("code-small", True,
     "/acs:code-small",
     "code-small"),
    ("code-standard", True,
     "/acs:code-standard",
     "code-standard"),
    ("code-complex", True,
     "/acs:code-complex",
     "code-complex"),
    ("create-ticket", True,
     "Create a ticket to add a dark mode toggle to the settings page.",
     "create-ticket"),
    ("create-design", True,
     "Settle the system design for ticket EVAL-1, weighing options and "
     "trade-offs, before we start implementing it.",
     "create-design"),
    ("code", True,
     "Implement ticket EVAL-1 from its approved plan, using TDD on a dedicated "
     "branch.",
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
    ("run-e2e-tests", True,
     "Run the configured test suites for this repo and give me a results "
     "report, opening a regression ticket for anything that broke.",
     "run-e2e-tests"),
    ("release", True,
     "Cut a new release — draft the changelog section from what's merged "
     "since the last tag, bump the version in both manifests, and open the "
     "release PR for me to review and merge.",
     "release"),
    ("analyze-requirements", True,
     "Before we plan anything for EVAL-1, work out what it really asks for: "
     "what breaks, what is unclear, and what we are assuming.",
     "analyze-requirements"),
    ("review-code", True,
     "The branch for EVAL-1 is implemented and committed. Review the whole "
     "changeset against what it was supposed to deliver before we open a PR.",
     "review-code"),
    ("create-impl-plan", True,
     "EVAL-1 has been analysed and the questions are answered. Work out the "
     "file-by-file approach the implementation should follow.",
     "create-impl-plan"),
    ("create-api-contract", True,
     "The plan for EVAL-1 adds two new endpoints. Pin down their request and "
     "response shapes, the error codes and the compatibility story before "
     "anything is built.",
     "create-api-contract"),
    ("create-test-docs", True,
     "Work out the test cases EVAL-1 needs from its acceptance criteria, and "
     "say which suite each one belongs in.",
     "create-test-docs"),
    ("create-e2e-tests", True,
     "EVAL-1's test plan has three end-to-end cases and none of them exist "
     "yet. Write those suites on the ticket branch.",
     "create-e2e-tests"),
    ("project", True,
     "This repository has no build or test tooling yet. Set up its structure "
     "so work can start.",
     "project"),
    # install-hooks and update are model-invocable like any other skill, so
    # they are probed by description like any other skill. They used to carry
    # disable-model-invocation and be probed by explicit command instead;
    # these two prompts are the ones that were their NEGATIVE cases, which is
    # exactly what a description probe should say.
    ("install-hooks", True,
     "Set up the local git hooks for this clone so our configured commit-message "
     "and branch-name conventions are enforced before anything gets pushed.",
     "install-hooks"),
    ("update", True,
     "Check whether there's a newer version of the acs plugin available and "
     "summarize what changed since the version I have installed.",
     "update"),
]

# Negative-routing cases for the two internal legs: a bare description of a
# leg's intent must NOT route to the leg, because its entry point
# (/acs:project) is the documented front door and is what
# should pick it up. PASS when the model picks anything other than the
# forbidden skill — the entry point, another skill, or no skill at all (None).
#
# What enforces this is the leg's DESCRIPTION ("Internal leg of /acs:<entry>,
# not a user-facing command ... run /acs:<entry> instead"), not a frontmatter
# flag. The legs used to set disable-model-invocation, which the CLI enforces
# by refusing the Skill call — and since each entry point dispatches its legs
# with a real `Skill(acs:<leg>)` call, that flag broke both folds outright.
# The property below is the one that was actually wanted, and a description is
# what delivers it.
# (label, init?, request, forbidden skill)
NEGATIVE = [
    ("create-project", True,
     "Scaffold the repository skeleton — build config, test framework, CI — "
     "from the approved architecture docs.",
     "create-project"),
    ("standardize-project", True,
     "Audit this existing repo against our approved doc set and readiness "
     "tooling, then additively scaffold whatever's missing without ever "
     "touching the source we already have.",
     "standardize-project"),
    ("code-trivial", True,
     "TKT-1's plan is approved and it is a trivial two-line change. "
     "Implement it.",
     "code-trivial"),
    ("code-small", True,
     "TKT-1's plan is approved — a small change, one module and a handful of "
     "tests. Implement it.",
     "code-small"),
    ("code-standard", True,
     "TKT-1's plan is approved. It is a standard-sized change across a few "
     "modules. Implement it.",
     "code-standard"),
    ("code-complex", True,
     "TKT-1's plan is approved and it is a complex change: several modules, a "
     "migration, and a public API. Implement it.",
     "code-complex"),
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
