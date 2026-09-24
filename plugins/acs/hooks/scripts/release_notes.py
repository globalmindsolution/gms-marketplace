#!/usr/bin/env python3
"""release_notes.py — deterministic, settings-driven changelog draft + version-bump helper, with a
git-history fallback for merged-ticket enumeration.

Stdlib-only, Python >= 3.9. Provides three argparse subcommands, each emitting one JSON object
to stdout:

  status   Probe manifest/changelog/branch/PR/tag state for a target version (idempotency).
  draft    Authoritatively assemble the dated CHANGELOG section from the merged-ticket archive
           since the last tag, cross-checked against [Unreleased], with a coverage report.
  bump     Bump every configured version location (+ extra_refs) and write the dated CHANGELOG
           section (regenerated via the same draft path), atomically per file.

Pure read-derive-write over repo files (--repo-root), the workspace archive (--workspace), and a
`--release-config <json-file-or-string>` block naming which files/pointers to bump (no `acs_lib`
import, no lock/partition machinery). `git`/`gh` are invoked via subprocess.run with argument
lists only. Never runs `git tag` or `gh release create` — those stay in release.yml.

`draft`/`bump`'s merged-ticket enumeration reads the workspace archive first, then falls back to
`base_branch` commit subjects since the boundary tag for tickets no archive entry recorded (e.g.
merged directly on GitHub, bypassing `/acs:merge-pr`'s cleanup step); each ticket's `source` field
in `draft`'s JSON output is `"archive"` or `"git-log"`. `--ticket-prefix` optionally anchors the
fallback's commit-subject match to a specific ticket-id prefix.

Usage:
  release_notes.py status --version <X.Y.Z> --repo-root <path> --release-config <json-file-or-string>
  release_notes.py draft  --version <X.Y.Z> --repo-root <path> --workspace <path> --release-config <json-file-or-string> [--ticket-prefix <PREFIX>]
  release_notes.py bump   --version <X.Y.Z> --repo-root <path> --workspace <path> --release-config <json-file-or-string> [--dry-run] [--ticket-prefix <PREFIX>]

Exit 0 on every successful data outcome (including "nothing to release"). Exit 2 on a malformed
invocation, an unreadable/missing CHANGELOG.md/manifest, or a malformed/absent/mis-pointed
--release-config block, with `{"command", "error"}` on stderr.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

# The module split (MAR-531) is invisible to every caller: this file stays the
# entry point /acs:release invokes and the module the tests import, and
# re-exports the whole pre-split surface -- private helpers included, because
# the tests reach them by name. Import from the module that OWNS a name when
# you add code; import from here only to keep an existing caller working.
# The scripts dir must be on sys.path BEFORE the sibling imports below,
# or loading this file by absolute path raises ModuleNotFoundError.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from release_notes_config import (ReleaseNotesError, _distinct_manifest_files,
    DEFAULT_VERSION_POINTER, _find_selector_match, _is_list_index,
    _pointer_navigate_to_container, _pointer_segments,
    _read_json_or_none, _read_json_or_raise,
    _read_text_or_raise, _render_format,
    _resolve_release_config_value, _validate_repo_relative,
    atomic_write_json, atomic_write_text, expand_version_locations,
    load_and_validate_release_config, pointer_get,
    pointer_set, relative_pointer_set,
    validate_release_config)  # noqa: F401
from release_notes_git import (VERSION_RE, _is_valid_version, _parse_iso, _run_git,
    gh_pr_list, release_branch, since_tag, tag_creation_time,
    tag_exists)  # noqa: F401
from release_notes_tickets import (CATEGORIES, FIX_WORD_RE, _GENERIC_TICKET_PREFIX_RE,
    _PR_SUFFIX_RE, _pr_suffix, _resolve_ticket_title,
    _ticket_subject_re, categorize,
    enumerate_git_log_tickets, enumerate_merged_tickets,
    resolve_pr_ref)  # noqa: F401
UNRELEASED_RE = re.compile(r"^## \[Unreleased\][^\n]*\n", re.M)
NEXT_SECTION_RE = re.compile(r"^## \[", re.M)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def _has_dated_section(text, version):
    pattern = re.compile(
        r"^## \[" + re.escape(version) + r"\][^\n]*-\s*\d{4}-\d{2}-\d{2}", re.M,
    )
    return bool(pattern.search(text))


def _preflight_version_locations(config, repo_root):
    """Read changelog_path + every distinct version_locations file; raise if any is unreadable."""
    changelog_text = _read_text_or_raise(os.path.join(repo_root, config["changelog_path"]))
    manifests = {}
    for entry in config["version_locations"]:
        f = entry["file"]
        if f not in manifests:
            manifests[f] = _read_json_or_raise(os.path.join(repo_root, f))
    return manifests, changelog_text


def compute_status(version, repo_root, config):
    """The four AC-6 idempotency signals for `version`, resolved from `config` (settings-driven)."""
    config = expand_version_locations(config)
    manifests, changelog_text = _preflight_version_locations(config, repo_root)

    manifests_at_target = True
    for entry in config["version_locations"]:
        value = pointer_get(manifests[entry["file"]], entry["pointer"], entry["file"])
        if value != version:
            manifests_at_target = False

    rendered_tag = _render_format(config["tag_format"], version)
    rendered_branch = _render_format(config["release_branch_format"], version)
    return {
        "manifests_at_target": manifests_at_target,
        "changelog_section_dated": _has_dated_section(changelog_text, version),
        "release_branch": release_branch(repo_root, rendered_branch),
        "open_pr": gh_pr_list(repo_root, rendered_branch),
        "tag_exists": tag_exists(repo_root, rendered_tag),
    }


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


def build_draft(version, repo_root, workspace, config, today=None, ticket_prefix=None):
    """Authoritatively assemble the dated CHANGELOG section + coverage report (AC-3)."""
    config = expand_version_locations(config)
    _manifests, changelog_text = _preflight_version_locations(config, repo_root)
    unreleased_text = _extract_unreleased_body(changelog_text)

    base_branch = config["base_branch"]
    tag = since_tag(repo_root, base_branch)
    tag_time = tag_creation_time(repo_root, tag) if tag else None

    merged = enumerate_merged_tickets(
        workspace, tag_time, repo_root=repo_root, base_branch=base_branch,
        since_tag=tag, ticket_prefix=ticket_prefix,
    )
    merged.sort(key=lambda t: t["id"])
    for ticket in merged:
        pr_number, pr_url = resolve_pr_ref(workspace, repo_root, ticket["id"], base_branch)
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
         "pr_number": t["pr_number"], "pr_url": t["pr_url"], "category": t["category"],
         "source": t["source"]}
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
# bump — two-phase resolve-then-write across the whole configured file set
# ---------------------------------------------------------------------------

def _insert_dated_section(text, draft_section):
    match = UNRELEASED_RE.search(text)
    if not match:
        raise ReleaseNotesError("no '## [Unreleased]' heading found in CHANGELOG.md")
    next_match = NEXT_SECTION_RE.search(text, match.end())
    next_start = next_match.start() if next_match else len(text)
    return text[:match.end()] + "\n" + draft_section + "\n" + text[next_start:]


UNRELEASED_MODES = ("promote", "replace")


def _resolve_release_section(changelog_text, draft, unreleased):
    """The section `bump` will write: the generated one, or the promoted body."""
    if unreleased is not None and unreleased not in UNRELEASED_MODES:
        raise ReleaseNotesError(
            "invalid --unreleased %r: expected one of %s"
            % (unreleased, " | ".join(UNRELEASED_MODES)))

    body = _extract_unreleased_body(changelog_text).strip()
    if not body:
        return draft["draft_section"]

    if unreleased is None:
        raise ReleaseNotesError(
            "'## [Unreleased]' has a body (%d lines) and --unreleased was not given. "
            "Writing the generated section would discard it. Pass --unreleased promote "
            "to publish that body as the release notes (every merged ticket must "
            "already be covered by it), or --unreleased replace to drop it in favour "
            "of the generated ticket list." % len(body.splitlines()))

    if unreleased == "replace":
        return draft["draft_section"]

    missing = draft.get("unreleased_missing") or []
    if missing:
        raise ReleaseNotesError(
            "--unreleased promote refused: the '## [Unreleased]' body does not "
            "mention %d merged ticket(s) since the last tag: %s. Add them to the "
            "body (or use --unreleased replace) so the release notes name every "
            "ticket this version ships." % (len(missing), ", ".join(missing)))

    header = draft["draft_section"].splitlines()[0]
    return header + "\n\n" + body.rstrip("\n") + "\n"


def bump(version, repo_root, workspace, config, dry_run=False, today=None, ticket_prefix=None,
         unreleased=None):
    """Bump every version_locations/extra_refs entry + the dated CHANGELOG section, atomically (AC-2/4).

    Two-phase (resolve-then-write): every file is read and every pointer/selector confirmed
    resolvable in-memory BEFORE any write, so a mid-set failure never touches disk (AC-2 literal,
    extended across the whole configured file set).

    `unreleased` decides what happens to a NON-EMPTY `## [Unreleased]` body,
    and is required whenever there is one:

      "replace"  the generated section wins; the body is dropped (what this
                 command always did, and right for a repo whose [Unreleased]
                 is a scratch list the archive already says better).
      "promote"  the body IS the release notes: it moves under the dated
                 heading verbatim, and every merged ticket must already be
                 covered by it (`unreleased_missing` empty) or the call is
                 refused naming the ids.

    Passing neither, with a non-empty body, is refused rather than guessed.
    Dropping hand-written release notes -- breaking-change entries, migration
    steps -- in favour of a list of ticket titles is not a silent default
    either way round: a repo that writes them loses them, a repo that does not
    gets a section it did not mean. An empty body needs no choice; the
    generated section is the only candidate.
    """
    config = expand_version_locations(config)
    status = compute_status(version, repo_root, config)
    if status["manifests_at_target"] and status["changelog_section_dated"]:
        return {"ok": True, "files_changed": [], "already_at_target": True}

    # --- Phase 1: resolve ---
    distinct_files = _distinct_manifest_files(config)
    objects = {f: _read_json_or_raise(os.path.join(repo_root, f)) for f in distinct_files}

    for entry in config["version_locations"]:
        obj = objects[entry["file"]]
        pointer_get(obj, entry["pointer"], entry["file"])  # confirm resolvable before overwrite
        pointer_set(obj, entry["pointer"], version, entry["file"])

    for entry in config.get("extra_refs", []):
        obj = objects[entry["file"]]
        selector = entry["selector"]
        array = pointer_get(obj, selector["pointer"], entry["file"])
        if not isinstance(array, list):
            raise ReleaseNotesError(
                "extra_refs selector pointer %r does not resolve to an array in %s"
                % (selector["pointer"], entry["file"]))
        target = _find_selector_match(array, selector["match"])
        if target is None:
            raise ReleaseNotesError(
                "extra_refs selector match %r found no element in %s" % (selector["match"], entry["file"]))
        rendered_value = _render_format(entry["value_format"], version)
        relative_pointer_set(target, selector["set"], rendered_value, entry["file"])

    changelog_full_path = os.path.join(repo_root, config["changelog_path"])
    changelog_text = _read_text_or_raise(changelog_full_path)
    draft = build_draft(version, repo_root, workspace, config, today=today, ticket_prefix=ticket_prefix)
    section = _resolve_release_section(changelog_text, draft, unreleased)
    new_changelog_text = _insert_dated_section(changelog_text, section)

    files_changed = sorted(set(distinct_files) | {config["changelog_path"]})
    if dry_run:
        return {"ok": True, "files_changed": files_changed, "already_at_target": False}

    # --- Phase 2: write (every file resolved cleanly above — all-or-nothing from here) ---
    try:
        for f in distinct_files:
            atomic_write_json(os.path.join(repo_root, f), objects[f])
        atomic_write_text(changelog_full_path, new_changelog_text)
    except Exception as exc:
        raise ReleaseNotesError("bump write failed: %s" % exc)

    return {"ok": True, "files_changed": files_changed, "already_at_target": False}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_RELEASE_CONFIG_HELP = (
    "the resolved .acs/settings.json 'release' block, as a literal JSON string or a path to a "
    "JSON file (naming version_locations, extra_refs, changelog_path, tag_format, base_branch, "
    "release_branch_format)"
)


def _add_status_parser(sub):
    p = sub.add_parser("status")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--release-config", required=True, help=_RELEASE_CONFIG_HELP)
    return p


_TICKET_PREFIX_HELP = (
    "optional ticket-id prefix (e.g. 'MAR') anchoring the git-history fallback's commit-subject "
    "match; omitted, the fallback accepts any generic [A-Z][A-Z0-9]{1,9}-N-shaped id"
)


def _add_draft_parser(sub):
    p = sub.add_parser("draft")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--release-config", required=True, help=_RELEASE_CONFIG_HELP)
    p.add_argument("--ticket-prefix", default=None, help=_TICKET_PREFIX_HELP)
    return p


def _add_bump_parser(sub):
    p = sub.add_parser("bump")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--release-config", required=True, help=_RELEASE_CONFIG_HELP)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ticket-prefix", default=None, help=_TICKET_PREFIX_HELP)
    p.add_argument("--unreleased", choices=list(UNRELEASED_MODES), default=None,
                   help="what to do with a non-empty '## [Unreleased]' body: "
                        "'promote' publishes it as the release notes, 'replace' "
                        "drops it for the generated ticket list. Required when "
                        "there is one.")
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
        config = load_and_validate_release_config(args.release_config, args.repo_root)
        if args.cmd == "status":
            result = compute_status(args.version, args.repo_root, config)
        elif args.cmd == "draft":
            result = build_draft(args.version, args.repo_root, args.workspace, config,
                                  ticket_prefix=args.ticket_prefix)
        elif args.cmd == "bump":
            result = bump(args.version, args.repo_root, args.workspace, config, dry_run=args.dry_run,
                           ticket_prefix=args.ticket_prefix, unreleased=args.unreleased)
        else:
            sys.exit(2)  # pragma: no cover - unreachable, argparse `required=True` gates cmd
        print(json.dumps(result))
        sys.exit(0)
    except ReleaseNotesError as exc:
        print(json.dumps({"command": command, "error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
