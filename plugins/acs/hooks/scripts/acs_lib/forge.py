"""acs_lib.forge — the deterministic half of PR-metadata fill and tracker sync (MAR-525).

`create-pr/SKILL.md` spent about 95 lines walking the model through label,
assignee, reviewer and Project-field writes; `create-ticket/SKILL.md` about 125
on the same shape for tracker sync. Every one of those steps is mechanical: a
`gh` call, a case-insensitive name match against a board's own field list, and
one finding when the board does not define the field. None of it is a judgement,
and all of it was being re-derived on every run.

What lives here is that machinery: the field/option resolvers (pure), a `gh`
runner that captures every call, and the two flows built on them. What stays in
the skills is the part with no single right answer -- whether the PR is ready,
what to tell the user, which tickets belong in a batch.

Two failure policies, both from the skills and both preserved exactly:

  * PR metadata fill is **non-critical throughout**. A failed call becomes one
    `info` finding carrying the command and the error plus a replayable block,
    and the flow continues to the next sub-step. The PR is already created; no
    metadata write is worth failing it.
  * Tracker sync is **critical per ticket, soft per batch**. A failed `gh issue
    create` for one ticket is an `error` finding naming that ticket, its error
    and the canonical `gh_failure_hint`, `replayable: false` -- and the batch
    continues, leaving that ticket's `external` null so it can be retried alone.

The runner is injectable, so every arm below is exercised from recorded `gh`
output rather than a live forge.
"""

import json
import os
import shlex
import subprocess

from ._common import read_json  # noqa: F401  (re-exported for callers' convenience)
from .repo import gh_failure_hint

#: The Status option a PR moves to, in preference order (case-insensitive).
PR_STATUS_OPTIONS = ("In Review", "Review")
#: The Status option a freshly synced ticket moves to.
TICKET_STATUS_OPTIONS = ("In Progress", "Todo", "Backlog")

#: ticket field -> the board field names that may carry it, in preference
#: order. Boards name these differently and none of the alternatives is more
#: correct than another, so the table is the whole rule.
GROUP_B_FIELDS = (
    ("priority", ("Priority",)),
    ("story_points", ("Story Points", "Points", "Estimate")),
    ("parent", ("Parent", "Epic")),
)

#: How the `Type` single-select is spelled for each ticket type.
TYPE_OPTIONS = {"epic": "Epic", "story": "Story", "task": "Task"}


class Gh(object):
    """Runs `gh` and records every call, so a flow can be replayed and audited.

    `responses` (tests) maps a command PREFIX -- the argv joined by spaces --
    to a (returncode, stdout, stderr) triple; the longest matching prefix wins,
    so a fixture can answer `gh project field-list` once and still distinguish
    `gh pr edit --add-label` from `gh pr edit --add-assignee`.
    """

    def __init__(self, responses=None, cwd=None):
        self.responses = dict(responses or {})
        self.cwd = cwd
        self.calls = []

    def __call__(self, argv):
        line = " ".join(str(a) for a in argv)
        self.calls.append(line)
        if self.responses:
            match = max((k for k in self.responses if line.startswith(k)),
                        key=len, default=None)
            if match is not None:
                code, out, err = self.responses[match]
                return code, out, err
            return 1, "", "no recorded response for %r" % line
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, cwd=self.cwd)
        except FileNotFoundError:
            return 127, "", "gh is not on PATH"
        return proc.returncode, proc.stdout, proc.stderr


def finding(severity, area, message, command=None, error=None, replayable=None,
            hint=None):
    """The finding shape both skills already document.

    `hint` is the classification ADR-0088 requires every degraded gh call to
    carry. It was the one documented key the shipped shape omitted, and its
    absence had a concrete cost: a 403 "GitHub access is not enabled for this
    session" -- the one failure with a specific remedy -- came out
    indistinguishable from a mistyped label name. It is derived from `error`
    when the caller does not pass one, so no call site can forget it."""
    out = {"severity": severity, "area": area, "message": message}
    if command is not None:
        out["command"] = command
    if error is not None:
        out["error"] = error
    if hint is None and error:
        hint = gh_failure_hint(error)
    if hint is not None:
        out["hint"] = hint
    if replayable is not None:
        out["replayable"] = replayable
    return out


def _render_command(argv):
    """A replayable command line, SHELL-QUOTED.

    The finding carries `replayable: true` and the skills tell the operator it
    is "ready to re-run", so this string is executed by a human sooner or
    later. A bare join made that unsafe with any tracker-controlled value: a
    milestone of `Q3 2026; rm -rf /tmp/x` rendered a command that runs the
    `rm` when replayed, and an ordinary multi-word value rendered one that is
    simply wrong. The EXECUTED calls were always safe (argv, no shell=True);
    only this rendering was not."""
    return " ".join(shlex.quote(str(a)) for a in argv)


def _guarded(gh, argv, area, findings, what):
    """Run a non-critical `gh` call: (ok, stdout). A failure is one info finding
    plus the command, ready to re-run -- never an abort."""
    code, out, err = gh(argv)
    if code != 0:
        findings.append(finding(
            "info", area, "%s failed" % what, command=_render_command(argv),
            error=(err or out or "").strip(), replayable=True))
        return False, out
    return True, out


def _json_or_none(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Project field / option resolution (pure)
# ---------------------------------------------------------------------------

def project_fields(payload):
    """The field list out of `gh project field-list --format json`.

    gh has shipped both a bare list and a {"fields": [...]} envelope; accepting
    both is cheaper than pinning a gh version in a comment nobody updates."""
    if isinstance(payload, dict):
        payload = payload.get("fields")
    return [f for f in (payload or []) if isinstance(f, dict)]


def match_field(fields, names):
    """The first field whose name case-insensitively equals one of `names`,
    trying `names` in order -- the board's spelling wins, our preference
    decides between two spellings it happens to define."""
    by_name = {}
    for field in fields:
        key = str(field.get("name") or "").strip().lower()
        by_name.setdefault(key, field)
    for name in names:
        found = by_name.get(name.strip().lower())
        if found is not None:
            return found
    return None


def match_option(field, value):
    """The option whose name case-insensitively equals `value`."""
    if value is None:
        return None
    wanted = str(value).strip().lower()
    for option in (field or {}).get("options") or []:
        if isinstance(option, dict) and str(option.get("name") or "").strip().lower() == wanted:
            return option
    return None


def first_matching_option(field, values):
    for value in values:
        option = match_option(field, value)
        if option is not None:
            return option
    return None


def project_items(payload):
    if isinstance(payload, dict):
        payload = payload.get("items")
    return [i for i in (payload or []) if isinstance(i, dict)]


def find_item_for_url(items, url):
    """The Project item whose content is `url`. `gh project item-add` without
    `--format json` prints nothing usable, so the id is resolved by looking."""
    for item in items:
        content = item.get("content")
        candidate = content.get("url") if isinstance(content, dict) else item.get("url")
        if candidate and str(candidate).rstrip("/") == str(url).rstrip("/"):
            return item
    return None


# ---------------------------------------------------------------------------
# The two flows
# ---------------------------------------------------------------------------

def _set_single_select(gh, project_id, item_id, field, option, area, findings, what):
    return _guarded(gh, ["gh", "project", "item-edit", "--project-id", project_id,
                         "--id", item_id, "--field-id", field["id"],
                         "--single-select-option-id", option["id"]],
                    area, findings, what)


def _undefined_field(area, findings, label, names):
    findings.append(finding(
        "info", area,
        "the Project defines no %s field (looked for %s); left unset"
        % (label, ", ".join(names))))


def fill_group_b(gh, project_id, item_id, fields, ticket, area, findings):
    """Priority / Story Points / Parent, each by the board's own field list.

    A board that defines none of a field's accepted names, or defines it with a
    dataType the value cannot be written to, gets ONE info finding naming what
    was skipped -- never a wrong-type write."""
    for key, names in GROUP_B_FIELDS:
        value = ticket.get(key)
        if key == "parent":
            value = ((ticket.get("external_parent") or {}).get("key")
                     if isinstance(ticket.get("external_parent"), dict) else ticket.get("parent"))
        if value in (None, "", []):
            continue
        field = match_field(fields, names)
        if field is None:
            _undefined_field(area, findings, key.replace("_", " "), names)
            continue
        data_type = str(field.get("dataType") or field.get("type") or "").upper()
        if data_type == "SINGLE_SELECT":
            option = match_option(field, value)
            if option is None:
                findings.append(finding(
                    "info", area, "the Project's %s field defines no option %r; left unset"
                    % (field.get("name"), value)))
                continue
            _set_single_select(gh, project_id, item_id, field, option, area, findings,
                               "setting %s" % field.get("name"))
        elif data_type == "NUMBER" and isinstance(value, (int, float)):
            _guarded(gh, ["gh", "project", "item-edit", "--project-id", project_id,
                          "--id", item_id, "--field-id", field["id"],
                          "--number", str(value)], area, findings,
                     "setting %s" % field.get("name"))
        elif data_type == "TEXT":
            _guarded(gh, ["gh", "project", "item-edit", "--project-id", project_id,
                          "--id", item_id, "--field-id", field["id"],
                          "--text", str(value)], area, findings,
                     "setting %s" % field.get("name"))
        else:
            findings.append(finding(
                "info", area, "the Project's %s field is %s, which %r cannot be written to; "
                "left unset" % (field.get("name"), data_type or "an unknown type", value)))


def project_fill(gh, settings, ticket, url, status_options, area, findings,
                 item_add_json=False):
    """Add `url` to the configured Project and set Status plus the Group-B fields.

    Returns the item id, or None when the Project is not configured or the item
    could not be resolved -- both of which are reported, never raised."""
    tracker = ((settings or {}).get("tracker") or {}).get("github") or {}
    number, owner = tracker.get("project_number"), tracker.get("owner")
    if not number or not owner:
        return None
    add = ["gh", "project", "item-add", str(number), "--owner", owner, "--url", url]
    if item_add_json:
        add += ["--format", "json"]
    ok, _out = _guarded(gh, add, area, findings, "adding the item to the Project")
    if not ok:
        return None

    ok, listed = _guarded(gh, ["gh", "project", "item-list", str(number), "--owner", owner,
                               "--format", "json", "--limit", "500"],
                          area, findings, "listing the Project's items")
    if not ok:
        return None
    item = find_item_for_url(project_items(_json_or_none(listed)), url)
    if item is None:
        findings.append(finding("info", area,
                                "the Project lists no item for %s; fields left unset" % url))
        return None

    ok, raw_fields = _guarded(gh, ["gh", "project", "field-list", str(number),
                                   "--owner", owner, "--format", "json"],
                              area, findings, "listing the Project's fields")
    if not ok:
        return item.get("id")
    fields = project_fields(_json_or_none(raw_fields))
    project_id = item.get("projectId") or item.get("project_id") or str(number)

    status = match_field(fields, ("Status",))
    if status is None:
        _undefined_field(area, findings, "Status", ("Status",))
    else:
        option = first_matching_option(status, status_options)
        if option is None:
            findings.append(finding(
                "info", area,
                "the Project's Status field defines none of %s; Status left unchanged. "
                "Single-select options cannot be created through the gh CLI -- add one "
                "in the Project UI or via the GraphQL API." % ", ".join(status_options)))
        else:
            _set_single_select(gh, project_id, item["id"], status, option, area, findings,
                               "setting Status")

    type_field = match_field(fields, ("Type",))
    wanted_type = TYPE_OPTIONS.get(ticket.get("type"))
    if type_field is not None and wanted_type:
        option = match_option(type_field, wanted_type)
        if option is None:
            findings.append(finding("info", area,
                                    "the Project's Type field defines no option %r; left unset"
                                    % wanted_type))
        else:
            _set_single_select(gh, project_id, item["id"], type_field, option, area,
                               findings, "setting Type")

    fill_group_b(gh, project_id, item["id"], fields, ticket, area, findings)
    return item.get("id")


def normalize_login(value):
    """A GitHub login reduced to what two spellings of the same person share.

    CODEOWNERS writes owners `@`-prefixed; `--author` is passed bare in one
    document (`create-pr/SKILL.md`) and as "the @me login" in another
    (`create-pr-executor.md`); GitHub itself is case-insensitive. Comparing the
    raw strings therefore failed to drop the author from their own reviewer
    set, and since the owners are comma-joined into ONE `gh pr edit
    --add-reviewer` call, GitHub rejected the whole call and NOBODY was
    requested. A team handle (`@org/team`) normalises the same way; it just
    never equals a user login."""
    text = str(value or "").strip()
    while text.startswith("@"):
        text = text[1:]
    return text.lower()


def resolve_author(gh, author, findings):
    """The PR author's login, or "" when it cannot be established.

    `--author` is optional at the CLI and was never defaulted, so the common
    invocation compared every owner against None and dropped nobody. `@me` is
    what `gh` accepts for a write but not something to compare against, so it
    is resolved to the real login the same way `gh` would."""
    normalized = normalize_login(author)
    if normalized and normalized != "me":
        return normalized
    code, out, err = gh(["gh", "api", "user", "--jq", ".login"])
    login = normalize_login((out or "").strip().splitlines()[-1] if (out or "").strip() else "")
    if code == 0 and login:
        return login
    detail = (err or out or "").strip()
    findings.append(finding(
        "info", "reviewers",
        "the PR author could not be resolved, so the author cannot be dropped from "
        "their own reviewer set; pass --author <login> if GitHub rejects the request",
        command=_render_command(["gh", "api", "user", "--jq", ".login"]),
        error=detail or "no --author was passed and `gh api user` returned no login",
        replayable=True))
    return ""


def reviewers_for(gh, pr_number, repo_root, author, findings, resolver=None):
    """The CODEOWNERS-derived reviewer set, minus the author.

    An empty set is never an empty `--add-reviewer` call: it is one info
    finding naming WHICH of the three reasons applies, because "no CODEOWNERS
    file" and "you are the only owner" call for different things."""
    ok, listed = _guarded(gh, ["gh", "pr", "diff", str(pr_number), "--name-only"],
                          "reviewers", findings, "reading the PR's changed files")
    if not ok:
        return []
    changed = [line.strip() for line in (listed or "").splitlines() if line.strip()]
    resolved = (resolver or _codeowners_resolve)(repo_root, changed)
    candidates = resolved.get("owners") or []
    # Only resolve the author when there is somebody to drop: a repo with no
    # CODEOWNERS requests nobody either way, and a `gh api user` finding there
    # would be noise about a comparison that changes nothing.
    login = resolve_author(gh, author, findings) if candidates else ""
    owners = [o for o in candidates if not login or normalize_login(o) != login]
    if owners:
        return sorted(set(owners))
    reason = resolved.get("reason")
    if reason == "no_codeowners_file":
        message = "No CODEOWNERS file found"
    elif reason == "no_pattern_matched":
        message = "No CODEOWNERS pattern matched the changed files"
    elif resolved.get("owners"):
        message = "Only eligible reviewer is the PR author; skipped (self-review impossible)"
    else:
        message = "No CODEOWNERS owner resolved for the changed files"
    findings.append(finding("info", "reviewers", message))
    return []


def _codeowners_resolve(repo_root, changed):
    import codeowners
    return codeowners.resolve(repo_root, changed)


def pr_metadata_fill(gh, settings, ticket, pr, repo_root, author=None, resolver=None):
    """create-pr step 6a, as one call. Returns {"findings": [...], "applied": [...]}.

    Non-critical throughout: the PR is already created, and no metadata write
    is worth failing it. Every failure is an info finding with the command,
    ready to re-run."""
    findings, applied = [], []
    number = pr.get("number")

    ok, _out = _guarded(gh, ["gh", "pr", "edit", str(number), "--add-assignee", "@me"],
                        "assignee", findings, "assigning the PR")
    if ok:
        applied.append("assignee")

    ttype = ticket.get("type")
    if ttype:
        gh(["gh", "label", "create", ttype, "--description", "Created by the acs pipeline"])
        ok, _out = _guarded(gh, ["gh", "pr", "edit", str(number), "--add-label", ttype],
                            "labels", findings, "applying the %s label" % ttype)
        if ok:
            applied.append("label:%s" % ttype)

    owners = reviewers_for(gh, number, repo_root, author, findings, resolver=resolver)
    if owners:
        ok, _out = _guarded(gh, ["gh", "pr", "edit", str(number),
                                 "--add-reviewer", ",".join(owners)],
                            "reviewers", findings, "requesting review")
        if ok:
            applied.append("reviewers:%s" % ",".join(owners))

    item = project_fill(gh, settings, ticket, pr.get("url"), PR_STATUS_OPTIONS,
                        "project", findings)
    if item:
        applied.append("project-item:%s" % item)
    return {"findings": findings, "applied": applied, "calls": list(gh.calls)}


def tracker_sync_one(gh, settings, ticket, body_path):
    """Create one remote issue and fill its metadata.

    Critical for THIS ticket: a failed `gh issue create` returns external=None
    with an error finding carrying the canonical hint, and the caller keeps
    going. Everything after the create is non-critical, exactly as the skill
    documents."""
    findings = []
    title = ticket.get("rendered_title") or ticket.get("title") or ticket.get("id")
    if not os.path.isfile(body_path):
        findings.append(finding(
            "error", "tracker",
            "%s did not sync: the issue body %s does not exist. The executor "
            "writes it from the rendered description before this command."
            % (ticket.get("id"), body_path),
            command=_render_command(["gh", "issue", "create", "--title", title,
                                     "--body-file", body_path]),
            error="missing body file", replayable=False))
        return None, findings

    code, out, err = gh(["gh", "issue", "create", "--title", title,
                         "--body-file", body_path])
    if code != 0:
        detail = (err or out or "").strip()
        findings.append(finding(
            "error", "tracker",
            "%s did not sync: %s\n%s" % (ticket.get("id"), detail, gh_failure_hint(detail)),
            command=_render_command(["gh", "issue", "create", "--title", title,
                                     "--body-file", body_path]),
            error=detail, replayable=False))
        return None, findings

    url = (out or "").strip().splitlines()[-1] if (out or "").strip() else ""
    number = url.rstrip("/").rsplit("/", 1)[-1] if url else ""
    if not number.isdigit():
        # A ZERO exit whose stdout does not carry an issue URL. Sliced blindly,
        # this produced key "" and reported a SUCCESSFUL sync -- then issued
        # `gh issue edit  --add-label ...` and `gh project item-add --url ` with
        # empty arguments, and record-external persisted "" so sync_candidates
        # excluded the ticket from every future retry. A half-written state with
        # no record is worse than a failed one with a record.
        findings.append(finding(
            "error", "tracker",
            "%s did not sync: `gh issue create` exited 0 but printed no issue "
            "URL (got %r), so the issue number is unknown. Check the tracker "
            "before re-running -- an issue may exist."
            % (ticket.get("id"), (out or "").strip()[:200]),
            command=_render_command(["gh", "issue", "create", "--title", title,
                                     "--body-file", body_path]),
            error="unparseable create output", replayable=False))
        return None, findings
    external = {"provider": "github", "key": number, "url": url}

    labels = ["ACS"] + ([ticket["type"]] if ticket.get("type") else [])
    for label in labels:
        gh(["gh", "label", "create", label, "--description", "Created by the acs pipeline"])
    _guarded(gh, ["gh", "issue", "edit", number, "--add-label", ",".join(labels)],
             "labels", findings, "applying labels")

    if ticket.get("assignee"):
        _guarded(gh, ["gh", "issue", "edit", number, "--add-assignee", ticket["assignee"]],
                 "assignee", findings, "assigning the issue")

    milestone = ticket.get("milestone") or ((settings or {}).get("tracker") or {}).get("milestone")
    if milestone:
        _guarded(gh, ["gh", "issue", "edit", number, "--milestone", milestone],
                 "milestone", findings, "setting the milestone")

    project_fill(gh, settings, ticket, url, TICKET_STATUS_OPTIONS, "project", findings,
                 item_add_json=True)
    return external, findings


def _stamp(findings_list, ticket_id):
    """Tag each finding with the ticket it came from.

    tracker_sync returns ONE flat list, and its non-critical entries carried no
    id -- so a two-ticket batch produced byte-identical entries ("applying
    labels failed", same command) that could not be attributed, while the
    executor charter told the coordinator to record them per synced ticket."""
    for item in findings_list:
        item.setdefault("ticket_id", ticket_id)
    return findings_list


def tracker_sync(gh, settings, tickets, body_paths):
    """create-ticket step 5's batch: critical per ticket, soft per batch.

    Returns {"synced": {id: external}, "failed": [id], "findings": [...]}. A
    ticket that fails leaves its `external` unset and the loop continues, which
    is what lets the failed one be retried on its own."""
    synced, failed, findings = {}, [], []
    for ticket in tickets:
        ident = ticket.get("id")
        try:
            external, ticket_findings = tracker_sync_one(gh, settings, ticket,
                                                         body_paths.get(ident, ""))
        except Exception as exc:  # noqa: BLE001 - AC-5 is about the BATCH surviving
            # "A tracker failure is reported without aborting the batch" held
            # only for a non-zero gh exit. Any OTHER failure -- a tracker
            # answering with a shape the parser does not expect, for instance --
            # propagated out of the loop, and `synced` is only emitted AFTER it:
            # so an issue that HAD been created was never recorded, its external
            # never written, and the next run created it again.
            ticket_findings = [finding(
                "error", "tracker",
                "%s did not sync: %r. The batch continued; check the tracker "
                "before re-running, since an issue may already exist." % (ident, exc),
                command="", error=repr(exc), replayable=False)]
            external = None
        findings.extend(_stamp(ticket_findings, ident))
        if external is None:
            failed.append(ident)
        else:
            synced[ident] = external
    return {"synced": synced, "failed": failed, "findings": findings,
            "calls": list(gh.calls)}


def sync_candidates(tickets, product_titles):
    """create-ticket's "tickets to sync" rule, as a filter.

    Excludes a product-flow delivery ticket and anything already carrying an
    `external` -- a --fan-out run's root is an already-synced epic, and
    re-applying the set literally would re-create its issue as a duplicate."""
    out = []
    for ticket in tickets:
        if ticket.get("external"):
            continue
        if ticket.get("title") in (product_titles or ()):
            continue
        out.append(ticket)
    return out
