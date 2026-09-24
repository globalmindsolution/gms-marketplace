"""setup_wizard_commands — the one-time `gh` calls and the next steps that
`setup_wizard.py commands` renders (split from setup_wizard.py to hold the
800-line budget).

Everything here is output for the skill to show or run, rendered and quoted:
the branch-protection call, the label calls, and the pipeline the summary
hands the user. setup_wizard re-exports every name, so callers are unchanged.
"""

import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


#: The two labels the convention gate relies on: one marks a pipeline PR, the
#: other exempts a legitimate non-ticket one.
SETUP_LABELS = (
    ("ACS", "Created/validated by the acs pipeline"),
    ("acs-exempt", "Skip acs convention checks for this PR"),
)


def render_protect(slug, branch, contexts):
    """The exact `gh api` call that makes the CI workflows a merge gate.

    Rendered here, with shlex quoting, rather than written out in a SKILL.md:
    the prose form used bare `<slug>`/`<branch>` placeholders inside an
    executable bash block, which bash parses as REDIRECTIONS -- the command
    lost its path argument and still exited 0."""
    argv = ["gh", "api", "-X", "PUT",
            "repos/%s/branches/%s/protection" % (slug, branch),
            "-f", "required_status_checks[strict]=true"]
    for context in contexts:
        argv += ["-f", "required_status_checks[contexts][]=%s" % context]
    return " ".join(shlex.quote(a) for a in argv)


#: The design phase, in order, before the delivery workflow takes over. Entry
#: points only: `project` is the design-phase umbrella, and `create-project`
#: is one of the two internal legs it dispatches to -- a user runs the entry
#: point, never the leg.
PIPELINE_ORDER = ("create-prd", "create-architecture", "project",
                  "create-ticket", "create-design")


def delivery_steps(root=None):
    """The delivery pipeline's steps as this repo resolves them: its own
    `.acs/workflows/ship.yaml` override, else the plugin's. Read, not copied:
    a hand-kept list here went on naming `/acs:test` after that skill was
    gone, and never learned `review-code`. An unreadable workflow yields none
    rather than a crash -- `acs.py workflow validate` is the place to say why."""
    try:
        return lib.workflow.steps_of(lib.workflow.resolve_workflow(root)["workflow"])
    except Exception:  # noqa: BLE001 - next steps are advisory output
        return []


def render_next_steps(greenfield, root=None):
    """The next-steps list. Derived, because `git ls-files` decides it -- the
    skill should not be re-deriving a branch it can be handed."""
    steps = ["/acs:create-prd", "/acs:create-architecture"]
    if greenfield:
        # The entry point, not its `create-project` leg: /acs:project reads the
        # same greenfield evidence off disk (acs_lib.project_mode) and
        # dispatches to that leg itself.
        steps.append("/acs:project")
    return {
        "kind": "greenfield" if greenfield else "brownfield",
        "first": steps,
        "then": "/acs:ship <prompt>, or step by step from /acs:create-ticket <prompt>",
        "pipeline": ["/acs:%s" % name
                     for name in PIPELINE_ORDER + tuple(delivery_steps(root)) + ("merge-pr",)],
        "note": ("merge each PR with /acs:merge-pr <ticket-id> after review; on a "
                 "solo-maintainer repo that skill cannot merge (it requires an "
                 "APPROVED review and GitHub forbids self-approval) -- merge in "
                 "the GitHub UI instead"),
    }


def render_labels():
    """The label-create calls, quoted. Idempotent by construction."""
    return [
        "%s 2>/dev/null || true" % " ".join(
            shlex.quote(a) for a in
            ["gh", "label", "create", name, "--description", description])
        for name, description in SETUP_LABELS
    ]
