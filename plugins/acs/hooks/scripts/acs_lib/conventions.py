"""acs_lib.conventions — the conventions acs itself relies on, fixed in code.

None of these is a setting. Branch names, commit subjects, PR titles and the
rest of a repo's house style are the model's to follow: it reads CLAUDE.md,
CONTRIBUTING.md and the recent `git log` like any contributor. What is here is
only what a script must be able to parse or produce without asking anyone --
the ticket id in a branch name, the exemptions to the CI ticket-link check, the
label the pipeline's PRs carry, and the templates' names.

templates/ci/check-conventions.py runs in CI with no plugin installed, so it
mirrors the exemption constants; a test keeps the two in step.
"""

#: `<type>/<ticket_id>-<slug>`: ticket detection from a branch name depends on
#: the id being in it.
BRANCH_FORMAT = "{type}/{ticket_id}-{slug}"

#: The subject of a commit a script makes (analyze-requirements' publish).
#: Commits a model makes follow the repo's own style, ticket id first.
COMMIT_SUBJECT = "{ticket_id} {summary}"

#: Branches the CI ticket-link check skips: releases and bot PRs.
EXEMPT_BRANCHES = ("release/*", "dependabot/*", "renovate/*")

#: A PR carrying this label skips the CI ticket-link check.
EXEMPT_LABEL = "acs-exempt"

#: The label /acs:create-pr puts on a pipeline PR and /acs:merge-pr --pr reads
#: to tell it from an exempt one.
PIPELINE_LABEL = "ACS"

#: Built-in templates, by name. A repo's `.acs/templates/<name>.md` of the same
#: name replaces the built-in one (acs_lib.settings.resolve_template).
PR_TEMPLATE = "pr-default"
DESIGN_TEMPLATE = "design-default"
TICKET_TEMPLATES = {"epic": "epic-default", "story": "story-default", "task": "task-default"}

#: An epic's title is tagged; a story's and a task's is the title as given.
TICKET_TITLE_PREFIX = {"epic": "[EPIC] "}


def branch_name(type_, ticket_id, slug):
    return BRANCH_FORMAT.format(type=type_, ticket_id=ticket_id, slug=slug)


def ticket_title(type_, title):
    return TICKET_TITLE_PREFIX.get(type_, "") + title
