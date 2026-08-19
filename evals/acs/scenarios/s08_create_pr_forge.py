"""s08 -- create-pr forge scenario (forge, G8+G9).

Drives the real acs pipeline through `/acs:create-pr` against the
`ForgeSandbox` target repo on an ephemeral run branch, then asserts -- via the
GitHub API/CLI only, never the model's prose (this harness's established
convention, s07_fanout_tracker_sync.py:1-22) -- that the resulting PR exists
with the configured title, the required label, and the required body
sections. Teardown reuses `ForgeSandbox`'s own best-effort teardown.

The pipeline is seeded deterministically for free (mint a ticket, seed one
trivial file+branch, fast-forward both the `code` and `docs-sync` gate halves
`gate_create_pr` requires) so exactly ONE paid session is spent, told only the
ticket id, to run `/acs:create-pr` itself -- the same "seed for free, one paid
session" pattern `s03_resume_and_verify.py` proves.

Only runs its real assertions when a forge target is configured
(`evals.forge_repo` / `ACS_FORGE_REPO`); otherwise it skips with one
documented reason and never constructs a `ForgeSandbox` at all.
"""

import json
import os

from harness import Check, ForgeConfigError, ForgeSandbox, resolve_forge_target

META = {
    "name": "create_pr_forge",
    "tier": "forge",
    "goal": "G8+G9",
    "summary": "/acs:create-pr opens a real, GitHub-API-verified PR against the forge target",
}

TICKET_TITLE = "Forge smoke: trivial doc touch"
SEED_FILE = "FORGE-SEED.md"
SEED_CONTENT = "seed content for the create_pr_forge scenario\n"

DEFAULT_PR_TITLE_TEMPLATE = "[{ticket_id}] {title}"
DEFAULT_REQUIRE_LABEL = "ACS"
DEFAULT_SECTIONS = ["Summary", "Ticket", "Changes", "Test plan"]


def _skip_label(err):
    """The single skipped result recorded when no forge target is configured."""
    return (
        "skipped: no forge target configured -- set evals.forge_repo in "
        ".acs/settings.json or the ACS_FORGE_REPO env var to run this "
        "scenario's real create-pr assertions (%s)" % err
    )


def _prompt(tid):
    """The one paid instruction: drive create-pr for the already-seeded ticket."""
    return (
        "Run the /acs:create-pr skill for ticket %s. Treat everything as "
        "already confirmed; do not ask me anything." % tid
    )


def _run_script_ok(sb, script, *args, stdin=None):
    """Run one installed helper CLI and raise with its stderr on failure."""
    out = sb.run_script(script, *args, stdin=stdin)
    if out.returncode != 0:
        raise AssertionError("%s failed: %s" % (script, out.stderr))
    return out


def _seed_ticket(sb):
    """Mint the ticket this run's PR will be opened for, for free."""
    out = _run_script_ok(sb, "new-ticket.py", "--title", TICKET_TITLE, "--type", "task")
    return json.loads(out.stdout)["ticket_id"]


def _code_result(branch):
    """The minimal code-state.json result that opens gate_create_pr's code half."""
    return {
        "status": "completed",
        "states": {
            "branch": branch,
            "verifier_passed": True,
            "tests": {"passed": 1, "failed": 0, "coverage_percent": 100, "coverage_target": 90},
            "specs_implemented": [SEED_FILE],
            "docs_updated": [],
            "review": {"iterations": 1, "findings_open": 0},
        },
    }


def _seed_code_and_docs_sync(sb, tid, branch):
    """Fast-forward both gate_create_pr halves (R-6) without spending claude."""
    _run_script_ok(sb, "skill-start.py", "--skill", "code", "--ticket", tid)
    _run_script_ok(sb, "post-code.py", "--ticket", tid,
                   stdin=json.dumps(_code_result(branch)))
    _run_script_ok(sb, "skill-start.py", "--skill", "docs-sync", "--ticket", tid)
    _run_script_ok(sb, "post-docs-sync.py", "--ticket", tid,
                   stdin=json.dumps({"status": "completed",
                                     "states": {"docs_updated": [SEED_FILE]}}))


def _read_settings(sb):
    """The forge checkout's own committed .acs/settings.json, best-effort."""
    path = os.path.join(sb.repo, ".acs", "settings.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _rendered_title(sb, tid, settings):
    """The expected PR title, produced by the same shipped renderer the skill uses."""
    template = (settings.get("formats") or {}).get("pr_title") or DEFAULT_PR_TITLE_TEMPLATE
    out = _run_script_ok(
        sb, "pr-conventions.py", "render-title",
        "--template", template, "--ticket-id", tid, "--type", "task",
        "--title", TICKET_TITLE, "--summary", "", "--external-key", "", "--provider", "",
    )
    return out.stdout.strip()


def _require_label(settings):
    return (settings.get("enforcement") or {}).get("require_label") or DEFAULT_REQUIRE_LABEL


def _required_sections(settings):
    return (settings.get("enforcement") or {}).get("pr_description_sections") or DEFAULT_SECTIONS


def _assert_pr_facts(check, sb, tid, pr):
    """Every PR fact asserted here comes from `pr` (a gh_json read), never session prose."""
    settings = _read_settings(sb)
    check.eq("PR title matches the configured renderer",
             pr.get("title"), _rendered_title(sb, tid, settings))

    label = _require_label(settings)
    labels = [entry.get("name") for entry in (pr.get("labels") or [])]
    check.ok("PR carries the required label (%s)" % label, label in labels, labels)

    body = pr.get("body") or ""
    for section in _required_sections(settings):
        check.ok("PR body has the '## %s' section" % section, ("## %s" % section) in body)


def run():
    check = Check(META["name"])

    try:
        resolve_forge_target()
    except ForgeConfigError as err:
        check.ok(_skip_label(err), True)
        return check

    with ForgeSandbox() as sb:
        tid = _seed_ticket(sb)
        branch = "task/%s-forge-smoke" % tid
        sb.commit_file(SEED_FILE, SEED_CONTENT, "%s seed trivial doc touch" % tid, branch=branch)
        _seed_code_and_docs_sync(sb, tid, branch)

        r = sb.run_skill(_prompt(tid))
        check.cost = r.get("cost_usd")
        session_ok = check.ok(
            "claude create-pr session completed without error", r["ok"],
            (r.get("stderr") or r.get("raw") or "")[:200])

        if session_ok:
            pr = sb.gh_json("pr", "view", branch, "--repo", sb.owner_name,
                            "--json", "number,title,body,labels,state,headRefName,baseRefName")
            if check.ok("gh pr view returned a parseable PR", pr is not None):
                _assert_pr_facts(check, sb, tid, pr)

    check.ok("teardown left no errors", not sb.teardown_errors, sb.teardown_errors)
    return check
