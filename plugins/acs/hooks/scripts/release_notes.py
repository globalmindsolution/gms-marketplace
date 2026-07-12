#!/usr/bin/env python3
"""release_notes.py — deterministic changelog draft + version-bump helper (MAR-129).

Stdlib-only, Python >= 3.9. Provides three argparse subcommands, each emitting one JSON object
to stdout:

  status   Probe manifest/changelog/branch/PR/tag state for a target version (idempotency).
  draft    Authoritatively assemble the dated CHANGELOG section from the merged-ticket archive
           since the last tag, cross-checked against [Unreleased], with a coverage report.
  bump     Bump both manifests' version (+ acs source.ref) and write the dated CHANGELOG
           section (regenerated via the same draft path), atomically per file.

Pure read-derive-write over repo files (--repo-root) and the workspace archive (--workspace);
no `acs_lib` import, no lock/partition machinery. `git`/`gh` are invoked via subprocess.run with
argument lists only. Never runs `git tag` or `gh release create` — those stay in release.yml.

Usage:
  release_notes.py status --version <X.Y.Z> --repo-root <path>
  release_notes.py draft  --version <X.Y.Z> --repo-root <path> --workspace <path>
  release_notes.py bump   --version <X.Y.Z> --repo-root <path> --workspace <path> [--dry-run]

Exit 0 on every successful data outcome (including "nothing to release"). Exit 2 on a malformed
invocation or an unreadable/missing CHANGELOG.md/manifest, with `{"command", "error"}` on stderr.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
UNRELEASED_RE = re.compile(r"^## \[Unreleased\][^\n]*\n", re.M)
NEXT_SECTION_RE = re.compile(r"^## \[", re.M)
FIX_WORD_RE = re.compile(r"\b(fix|fixes|fixed|bug|bugfix|repair|regression)\b", re.I)
CATEGORIES = ("Added", "Fixed", "Changed")


class ReleaseNotesError(Exception):
    """Malformed invocation or an unreadable/missing CHANGELOG.md/manifest (AC-2 exit-2 contract)."""


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _marketplace_path(repo_root):
    return os.path.join(repo_root, ".claude-plugin", "marketplace.json")


def _plugin_path(repo_root):
    return os.path.join(repo_root, "plugins", "acs", ".claude-plugin", "plugin.json")


def _changelog_path(repo_root):
    return os.path.join(repo_root, "plugins", "acs", "CHANGELOG.md")


# ---------------------------------------------------------------------------
# I/O — read-or-raise, atomic write
# ---------------------------------------------------------------------------

def _read_json_or_raise(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ReleaseNotesError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise ReleaseNotesError("invalid JSON in %s: %s" % (path, exc))


def _read_text_or_raise(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise ReleaseNotesError("cannot read %s: %s" % (path, exc))


def _read_json_or_none(path):
    """Best-effort read used for archive enumeration, where a missing file just means "skip"."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _preflight(repo_root):
    """Read both manifests + CHANGELOG.md; raises ReleaseNotesError if any is unreadable/missing."""
    market = _read_json_or_raise(_marketplace_path(repo_root))
    plugin = _read_json_or_raise(_plugin_path(repo_root))
    changelog_text = _read_text_or_raise(_changelog_path(repo_root))
    return market, plugin, changelog_text


def atomic_write_text(path, text):
    """Write `text` to `path` via a same-directory temp file + os.rename (AC-2 literal)."""
    directory = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.rename(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def atomic_write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Version / datetime helpers
# ---------------------------------------------------------------------------

def _is_valid_version(version):
    return bool(VERSION_RE.match(version or ""))


def _parse_iso(value):
    """Parse an ISO-8601 datetime (accepts a trailing 'Z'); returns None on any failure."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# git / gh helpers — argument lists only, never a shell string
# ---------------------------------------------------------------------------

def _run_git(repo_root, args):
    return subprocess.run(["git"] + args, cwd=repo_root, capture_output=True, text=True)


def since_tag(repo_root):
    """git describe --tags --abbrev=0 main -> tag string, or None (no reachable tag / bootstrap)."""
    result = _run_git(repo_root, ["describe", "--tags", "--abbrev=0", "main"])
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def tag_creation_time(repo_root, tag):
    result = _run_git(
        repo_root, ["for-each-ref", "--format=%(creatordate:iso-strict)", "refs/tags/%s" % tag],
    )
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def tag_exists(repo_root, version):
    result = _run_git(repo_root, ["rev-parse", "-q", "--verify", "refs/tags/v%s" % version])
    return result.returncode == 0


def release_branch(repo_root, version):
    branch = "release/v%s" % version
    result = _run_git(repo_root, ["ls-remote", "--heads", "origin", "refs/heads/%s" % branch])
    if result.returncode == 0 and result.stdout.strip():
        return branch
    return None


def gh_pr_list(repo_root, version):
    """The single `gh` seam: resolve the open release/v<version> PR, or None. Tests monkeypatch this."""
    branch = "release/v%s" % version
    result = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number,url"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except ValueError:
        return None
    if isinstance(data, list) and data:
        entry = data[0]
        if isinstance(entry, dict) and "number" in entry:
            return {"number": entry["number"], "url": entry.get("url")}
    return None


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def _has_dated_section(text, version):
    pattern = re.compile(
        r"^## \[" + re.escape(version) + r"\][^\n]*-\s*\d{4}-\d{2}-\d{2}", re.M,
    )
    return bool(pattern.search(text))


def compute_status(version, repo_root):
    """The four AC-6 idempotency signals for `version` against `repo_root`."""
    market, plugin, changelog_text = _preflight(repo_root)
    manifests_at_target = market.get("version") == version and plugin.get("version") == version
    return {
        "manifests_at_target": manifests_at_target,
        "changelog_section_dated": _has_dated_section(changelog_text, version),
        "release_branch": release_branch(repo_root, version),
        "open_pr": gh_pr_list(repo_root, version),
        "tag_exists": tag_exists(repo_root, version),
    }


# ---------------------------------------------------------------------------
# draft — archive enumeration, categorization, rendering
# ---------------------------------------------------------------------------

def enumerate_merged_tickets(workspace, tag_time):
    """Merged-since-boundary tickets from <workspace>/archive/*/ (R6: merge time = last runs[].ended_at)."""
    archive_dir = os.path.join(workspace, "archive")
    if not os.path.isdir(archive_dir):
        return []

    tag_dt = _parse_iso(tag_time) if tag_time else None
    result = []
    for name in sorted(os.listdir(archive_dir)):
        tdir = os.path.join(archive_dir, name)
        if not os.path.isdir(tdir):
            continue

        merge_state = _read_json_or_none(os.path.join(tdir, "merge-pr-state.json"))
        if not isinstance(merge_state, dict):
            continue
        states = merge_state.get("states")
        if not isinstance(states, dict) or states.get("merged") is not True:
            continue
        runs = merge_state.get("runs")
        if not isinstance(runs, list) or not runs or not isinstance(runs[-1], dict):
            continue
        merge_dt = _parse_iso(runs[-1].get("ended_at"))
        if merge_dt is None:
            continue
        if tag_dt is not None and merge_dt <= tag_dt:
            continue

        ticket_json = _read_json_or_none(os.path.join(tdir, "ticket.json"))
        if not isinstance(ticket_json, dict):
            continue
        result.append({
            "id": ticket_json.get("id", name),
            "title": ticket_json.get("title", ""),
            "parent": ticket_json.get("parent"),
            "description": ticket_json.get("description", ""),
            "docs_only": bool(ticket_json.get("docs_only", False)),
        })
    return result


def resolve_pr_ref(workspace, repo_root, ticket_id):
    """Primary: archive/<id>/create-pr-state.json. Fallback: git log subject `(#N)` suffix."""
    create_pr_state = _read_json_or_none(
        os.path.join(workspace, "archive", ticket_id, "create-pr-state.json"),
    )
    if isinstance(create_pr_state, dict):
        states = create_pr_state.get("states")
        pr = states.get("pr") if isinstance(states, dict) else None
        if isinstance(pr, dict) and pr.get("number") is not None:
            return pr.get("number"), pr.get("url")

    result = _run_git(repo_root, ["log", "--oneline", "--grep=%s" % ticket_id, "main"])
    if result.returncode == 0:
        boundary = re.compile(r"\b" + re.escape(ticket_id) + r"\b")
        for line in result.stdout.splitlines():
            if not boundary.search(line):
                continue
            match = re.search(r"\(#(\d+)\)\s*$", line)
            if match:
                return int(match.group(1)), None
    return None, None


def categorize(ticket):
    text = "%s %s" % (ticket.get("title") or "", ticket.get("description") or "")
    if FIX_WORD_RE.search(text):
        return "Fixed"
    if ticket.get("docs_only"):
        return "Changed"
    return "Added"


def _resolve_ticket_title(workspace, ticket_id):
    for candidate in (
        os.path.join(workspace, "archive", ticket_id, "ticket.json"),
        os.path.join(workspace, ticket_id, "ticket.json"),
    ):
        data = _read_json_or_none(candidate)
        if isinstance(data, dict) and data.get("title"):
            return data["title"]
    return ticket_id


def _pr_suffix(ticket):
    if ticket.get("pr_number"):
        return " (#%s)" % ticket["pr_number"]
    return ""


def render_draft_section(version, date_str, tickets, resolve_parent_title):
    """Render `## [<version>] - <date>` + grouped ### category bullets; bare header when tickets==[]."""
    header = "## [%s] - %s" % (version, date_str)
    if not tickets:
        return header + "\n"

    lines = [header, ""]
    for category in CATEGORIES:
        cat_tickets = [t for t in tickets if t["category"] == category]
        if not cat_tickets:
            continue
        lines.append("### %s" % category)
        lines.append("")
        parent_order = []
        by_parent = {}
        for ticket in cat_tickets:
            parent = ticket.get("parent")
            if parent not in by_parent:
                by_parent[parent] = []
                parent_order.append(parent)
            by_parent[parent].append(ticket)
        for parent in parent_order:
            group = by_parent[parent]
            if parent is None:
                for t in group:
                    lines.append("- %s: %s%s" % (t["id"], t["title"], _pr_suffix(t)))
            else:
                parent_title = resolve_parent_title(parent)
                lines.append("- **%s** (%s)" % (parent_title, parent))
                for t in group:
                    lines.append("  - %s: %s%s" % (t["id"], t["title"], _pr_suffix(t)))
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _extract_unreleased_body(text):
    match = UNRELEASED_RE.search(text)
    if not match:
        return ""
    next_match = NEXT_SECTION_RE.search(text, match.end())
    end = next_match.start() if next_match else len(text)
    return text[match.end():end]


def build_draft(version, repo_root, workspace, today=None):
    """Authoritatively assemble the dated CHANGELOG section + coverage report (AC-3)."""
    _market, _plugin, changelog_text = _preflight(repo_root)
    unreleased_text = _extract_unreleased_body(changelog_text)

    tag = since_tag(repo_root)
    tag_time = tag_creation_time(repo_root, tag) if tag else None

    merged = enumerate_merged_tickets(workspace, tag_time)
    merged.sort(key=lambda t: t["id"])
    for ticket in merged:
        pr_number, pr_url = resolve_pr_ref(workspace, repo_root, ticket["id"])
        ticket["pr_number"] = pr_number
        ticket["pr_url"] = pr_url
        ticket["category"] = categorize(ticket)

    covered, missing = [], []
    for ticket in merged:
        pattern = re.compile(r"\b" + re.escape(ticket["id"]) + r"\b")
        (covered if pattern.search(unreleased_text) else missing).append(ticket["id"])

    date_str = today or datetime.date.today().isoformat()
    draft_section = render_draft_section(
        version, date_str, merged, lambda pid: _resolve_ticket_title(workspace, pid),
    )

    tickets_out = [
        {"id": t["id"], "title": t["title"], "parent": t["parent"],
         "pr_number": t["pr_number"], "pr_url": t["pr_url"], "category": t["category"]}
        for t in merged
    ]
    return {
        "version": version,
        "since_tag": tag,
        "tickets": tickets_out,
        "unreleased_covered": covered,
        "unreleased_missing": missing,
        "coverage": {"merged": len(merged), "covered": len(covered), "missing": len(missing)},
        "draft_section": draft_section,
    }


# ---------------------------------------------------------------------------
# bump
# ---------------------------------------------------------------------------

def _insert_dated_section(text, draft_section):
    match = UNRELEASED_RE.search(text)
    if not match:
        raise ReleaseNotesError("no '## [Unreleased]' heading found in CHANGELOG.md")
    next_match = NEXT_SECTION_RE.search(text, match.end())
    next_start = next_match.start() if next_match else len(text)
    return text[:match.end()] + "\n" + draft_section + "\n" + text[next_start:]


def bump(version, repo_root, workspace, dry_run=False, today=None):
    """Bump both manifests + source.ref and write the dated CHANGELOG section, atomically (AC-2/4)."""
    market, plugin, changelog_text = _preflight(repo_root)

    status = compute_status(version, repo_root)
    if status["manifests_at_target"] and status["changelog_section_dated"]:
        return {"ok": True, "files_changed": [], "already_at_target": True}

    draft = build_draft(version, repo_root, workspace, today=today)

    new_market = json.loads(json.dumps(market))
    new_market["version"] = version
    for entry in new_market.get("plugins") or []:
        if isinstance(entry, dict) and entry.get("name") == "acs":
            source = entry.get("source")
            if isinstance(source, dict):
                source["ref"] = "v%s" % version

    new_plugin = json.loads(json.dumps(plugin))
    new_plugin["version"] = version

    new_changelog_text = _insert_dated_section(changelog_text, draft["draft_section"])

    files_changed = [
        ".claude-plugin/marketplace.json",
        "plugins/acs/.claude-plugin/plugin.json",
        "plugins/acs/CHANGELOG.md",
    ]
    if dry_run:
        return {"ok": True, "files_changed": files_changed, "already_at_target": False}

    try:
        atomic_write_json(_marketplace_path(repo_root), new_market)
        atomic_write_json(_plugin_path(repo_root), new_plugin)
        atomic_write_text(_changelog_path(repo_root), new_changelog_text)
    except Exception as exc:
        raise ReleaseNotesError("bump write failed: %s" % exc)

    return {"ok": True, "files_changed": files_changed, "already_at_target": False}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_status_parser(sub):
    p = sub.add_parser("status")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    return p


def _add_draft_parser(sub):
    p = sub.add_parser("draft")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--workspace", required=True)
    return p


def _add_bump_parser(sub):
    p = sub.add_parser("bump")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None):
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="release_notes.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_status_parser(sub)
    _add_draft_parser(sub)
    _add_bump_parser(sub)
    args = parser.parse_args(raw_argv)
    command = "release_notes.py " + " ".join(raw_argv)

    try:
        if not _is_valid_version(args.version):
            raise ReleaseNotesError("invalid --version %r: expected X.Y.Z" % args.version)
        if args.cmd == "status":
            result = compute_status(args.version, args.repo_root)
        elif args.cmd == "draft":
            result = build_draft(args.version, args.repo_root, args.workspace)
        elif args.cmd == "bump":
            result = bump(args.version, args.repo_root, args.workspace, dry_run=args.dry_run)
        else:
            sys.exit(2)  # pragma: no cover - unreachable, argparse `required=True` gates cmd
        print(json.dumps(result))
        sys.exit(0)
    except ReleaseNotesError as exc:
        print(json.dumps({"command": command, "error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
