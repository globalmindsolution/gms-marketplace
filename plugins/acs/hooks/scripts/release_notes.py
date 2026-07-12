#!/usr/bin/env python3
"""release_notes.py — deterministic, settings-driven changelog draft + version-bump helper (MAR-129).

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

Usage:
  release_notes.py status --version <X.Y.Z> --repo-root <path> --release-config <json-file-or-string>
  release_notes.py draft  --version <X.Y.Z> --repo-root <path> --workspace <path> --release-config <json-file-or-string>
  release_notes.py bump   --version <X.Y.Z> --repo-root <path> --workspace <path> --release-config <json-file-or-string> [--dry-run]

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

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
UNRELEASED_RE = re.compile(r"^## \[Unreleased\][^\n]*\n", re.M)
NEXT_SECTION_RE = re.compile(r"^## \[", re.M)
FIX_WORD_RE = re.compile(r"\b(fix|fixes|fixed|bug|bugfix|repair|regression)\b", re.I)
CATEGORIES = ("Added", "Fixed", "Changed")


class ReleaseNotesError(Exception):
    """Malformed invocation, an unreadable/missing file, or an invalid --release-config (AC-2 exit-2)."""


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
    # ensure_ascii=False preserves non-ASCII manifest content (e.g. em-dashes) verbatim,
    # so a bump never escapes an unrelated description line into the release diff.
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# --release-config — load (two-attempt) + hand-rolled structural validation
# ---------------------------------------------------------------------------

def _resolve_release_config_value(value):
    """Two-attempt resolution: literal JSON text first, else an existing file's JSON contents."""
    try:
        return json.loads(value)
    except ValueError:
        pass
    if os.path.isfile(value):
        try:
            with open(value, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError) as exc:
            raise ReleaseNotesError("--release-config file %r is not valid JSON: %s" % (value, exc))
    raise ReleaseNotesError(
        "--release-config %r is neither valid JSON nor an existing file" % value)


def _validate_repo_relative(rel_path, repo_root, field_label):
    """A configured file path must be repo-relative and MUST NOT escape --repo-root."""
    if not isinstance(rel_path, str) or not rel_path:
        raise ReleaseNotesError("release config: %s must be a non-empty string" % field_label)
    if os.path.isabs(rel_path):
        raise ReleaseNotesError(
            "release config: %s %r must be repo-relative, not absolute" % (field_label, rel_path))
    repo_norm = os.path.normpath(repo_root)
    full = os.path.normpath(os.path.join(repo_norm, rel_path))
    if full != repo_norm and not full.startswith(repo_norm + os.sep):
        raise ReleaseNotesError(
            "release config: %s %r escapes --repo-root" % (field_label, rel_path))


def validate_release_config(config, repo_root):
    """Hand-rolled structural/type check over the release block (Security NFR (v)) — no read/write yet."""
    if not isinstance(config, dict):
        raise ReleaseNotesError("--release-config must resolve to a JSON object")

    locations = config.get("version_locations")
    if not isinstance(locations, list) or not locations:
        raise ReleaseNotesError("release config: 'version_locations' must be a non-empty list")
    for entry in locations:
        if not isinstance(entry, dict):
            raise ReleaseNotesError("release config: version_locations entry must be an object")
        _validate_repo_relative(entry.get("file"), repo_root, "version_locations[].file")
        pointer = entry.get("pointer")
        if not isinstance(pointer, str) or not pointer:
            raise ReleaseNotesError("release config: version_locations[].pointer must be a non-empty string")
        kind = entry.get("kind", "json-pointer")
        if kind != "json-pointer":
            raise ReleaseNotesError("release config: unsupported version_locations[].kind %r" % kind)

    extra_refs = config.get("extra_refs", [])
    if not isinstance(extra_refs, list):
        raise ReleaseNotesError("release config: 'extra_refs' must be a list")
    for entry in extra_refs:
        if not isinstance(entry, dict):
            raise ReleaseNotesError("release config: extra_refs entry must be an object")
        _validate_repo_relative(entry.get("file"), repo_root, "extra_refs[].file")
        selector = entry.get("selector")
        if not isinstance(selector, dict):
            raise ReleaseNotesError("release config: extra_refs[].selector must be an object")
        pointer = selector.get("pointer")
        if not isinstance(pointer, str) or not pointer:
            raise ReleaseNotesError("release config: extra_refs[].selector.pointer must be a non-empty string")
        match = selector.get("match")
        if not isinstance(match, dict) or not match:
            raise ReleaseNotesError("release config: extra_refs[].selector.match must be a non-empty object")
        set_path = selector.get("set")
        if not isinstance(set_path, str) or not set_path:
            raise ReleaseNotesError("release config: extra_refs[].selector.set must be a non-empty string")
        value_format = entry.get("value_format")
        if not isinstance(value_format, str) or "{version}" not in value_format:
            raise ReleaseNotesError("release config: extra_refs[].value_format must contain '{version}'")

    _validate_repo_relative(config.get("changelog_path"), repo_root, "changelog_path")

    tag_format = config.get("tag_format")
    if not isinstance(tag_format, str) or "{version}" not in tag_format:
        raise ReleaseNotesError("release config: 'tag_format' must be a string containing '{version}'")

    base_branch = config.get("base_branch")
    if not isinstance(base_branch, str) or not base_branch:
        raise ReleaseNotesError("release config: 'base_branch' must be a non-empty string")

    release_branch_format = config.get("release_branch_format")
    if not isinstance(release_branch_format, str) or "{version}" not in release_branch_format:
        raise ReleaseNotesError(
            "release config: 'release_branch_format' must be a string containing '{version}'")

    publish_driver = config.get("publish_driver")
    if publish_driver is not None and not isinstance(publish_driver, dict):
        raise ReleaseNotesError("release config: 'publish_driver' must be an object")


def load_and_validate_release_config(value, repo_root):
    """Resolve + validate --release-config, before any manifest/CHANGELOG file is opened."""
    config = _resolve_release_config_value(value)
    validate_release_config(config, repo_root)
    return config


def _render_format(template, version):
    """Narrow single-token substitution — never a general str.format() call (config-injection safety)."""
    return template.replace("{version}", version)


def _distinct_manifest_files(config):
    """Sorted-by-first-appearance distinct file paths named across version_locations + extra_refs."""
    files = []
    seen = set()
    for entry in config.get("version_locations", []):
        f = entry["file"]
        if f not in seen:
            seen.add(f)
            files.append(f)
    for entry in config.get("extra_refs", []):
        f = entry["file"]
        if f not in seen:
            seen.add(f)
            files.append(f)
    return files


# ---------------------------------------------------------------------------
# JSON-pointer resolver (RFC 6901) + name-match selector setter
# ---------------------------------------------------------------------------

def _pointer_segments(pointer, file_label):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ReleaseNotesError("invalid JSON pointer %r in %s" % (pointer, file_label))
    return [seg.replace("~1", "/").replace("~0", "~") for seg in pointer.split("/")[1:]]


def _is_list_index(segment):
    return segment.isdigit()


def _pointer_navigate_to_container(obj, segments, file_label):
    """Walk all but the last segment; return (container, key) for the final segment.

    Raises ReleaseNotesError on any missing key, out-of-range index, or wrong container type —
    at any depth, not just the last segment (an unresolvable pointer, per the resolver contract).
    """
    container = obj
    for seg in segments[:-1]:
        if isinstance(container, dict):
            if seg not in container:
                raise ReleaseNotesError("JSON pointer segment %r not found in %s" % (seg, file_label))
            container = container[seg]
        elif isinstance(container, list):
            if not _is_list_index(seg) or int(seg) >= len(container):
                raise ReleaseNotesError("JSON pointer segment %r out of range in %s" % (seg, file_label))
            container = container[int(seg)]
        else:
            raise ReleaseNotesError("JSON pointer segment %r cannot descend into %s" % (seg, file_label))

    last = segments[-1]
    if isinstance(container, dict):
        if last not in container:
            raise ReleaseNotesError("JSON pointer segment %r not found in %s" % (last, file_label))
        return container, last
    if isinstance(container, list):
        if not _is_list_index(last) or int(last) >= len(container):
            raise ReleaseNotesError("JSON pointer segment %r out of range in %s" % (last, file_label))
        return container, int(last)
    raise ReleaseNotesError("JSON pointer segment %r cannot resolve in %s" % (last, file_label))


def pointer_get(obj, pointer, file_label):
    container, key = _pointer_navigate_to_container(obj, _pointer_segments(pointer, file_label), file_label)
    return container[key]


def pointer_set(obj, pointer, value, file_label):
    container, key = _pointer_navigate_to_container(obj, _pointer_segments(pointer, file_label), file_label)
    container[key] = value


def relative_pointer_set(obj, rel_path, value, file_label):
    """Set a plain '/'-joined relative key path (no leading slash, no RFC 6901 escaping) under
    an already-selector-matched element; every segment but the last MUST already be an existing dict."""
    segments = rel_path.split("/")
    container = obj
    for seg in segments[:-1]:
        if not isinstance(container, dict) or not isinstance(container.get(seg), dict):
            raise ReleaseNotesError(
                "extra_refs 'set' path %r: segment %r missing or not an object in %s"
                % (rel_path, seg, file_label))
        container = container[seg]
    if not isinstance(container, dict):
        raise ReleaseNotesError(
            "extra_refs 'set' path %r: final container not an object in %s" % (rel_path, file_label))
    container[segments[-1]] = value


def _find_selector_match(array, match):
    """The first array element where every match field is equal — never a brittle index pointer."""
    for element in array:
        if isinstance(element, dict) and all(element.get(k) == v for k, v in match.items()):
            return element
    return None


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


def since_tag(repo_root, base_branch):
    """git describe --tags --abbrev=0 <base_branch> -> tag string, or None (bootstrap case)."""
    result = _run_git(repo_root, ["describe", "--tags", "--abbrev=0", base_branch])
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


def tag_exists(repo_root, rendered_tag):
    result = _run_git(repo_root, ["rev-parse", "-q", "--verify", "refs/tags/%s" % rendered_tag])
    return result.returncode == 0


def release_branch(repo_root, rendered_branch):
    result = _run_git(repo_root, ["ls-remote", "--heads", "origin", "refs/heads/%s" % rendered_branch])
    if result.returncode == 0 and result.stdout.strip():
        return rendered_branch
    return None


def gh_pr_list(repo_root, rendered_branch):
    """The single `gh` seam: resolve the open PR for `rendered_branch`, or None. Tests monkeypatch this."""
    result = subprocess.run(
        ["gh", "pr", "list", "--head", rendered_branch, "--state", "open", "--json", "number,url"],
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


def resolve_pr_ref(workspace, repo_root, ticket_id, base_branch):
    """Primary: archive/<id>/create-pr-state.json. Fallback: git log subject `(#N)` suffix."""
    create_pr_state = _read_json_or_none(
        os.path.join(workspace, "archive", ticket_id, "create-pr-state.json"),
    )
    if isinstance(create_pr_state, dict):
        states = create_pr_state.get("states")
        pr = states.get("pr") if isinstance(states, dict) else None
        if isinstance(pr, dict) and pr.get("number") is not None:
            return pr.get("number"), pr.get("url")

    result = _run_git(repo_root, ["log", "--oneline", "--grep=%s" % ticket_id, base_branch])
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


def build_draft(version, repo_root, workspace, config, today=None):
    """Authoritatively assemble the dated CHANGELOG section + coverage report (AC-3)."""
    _manifests, changelog_text = _preflight_version_locations(config, repo_root)
    unreleased_text = _extract_unreleased_body(changelog_text)

    base_branch = config["base_branch"]
    tag = since_tag(repo_root, base_branch)
    tag_time = tag_creation_time(repo_root, tag) if tag else None

    merged = enumerate_merged_tickets(workspace, tag_time)
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
# bump — two-phase resolve-then-write across the whole configured file set
# ---------------------------------------------------------------------------

def _insert_dated_section(text, draft_section):
    match = UNRELEASED_RE.search(text)
    if not match:
        raise ReleaseNotesError("no '## [Unreleased]' heading found in CHANGELOG.md")
    next_match = NEXT_SECTION_RE.search(text, match.end())
    next_start = next_match.start() if next_match else len(text)
    return text[:match.end()] + "\n" + draft_section + "\n" + text[next_start:]


def bump(version, repo_root, workspace, config, dry_run=False, today=None):
    """Bump every version_locations/extra_refs entry + the dated CHANGELOG section, atomically (AC-2/4).

    Two-phase (resolve-then-write): every file is read and every pointer/selector confirmed
    resolvable in-memory BEFORE any write, so a mid-set failure never touches disk (AC-2 literal,
    extended across the whole configured file set).
    """
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
    draft = build_draft(version, repo_root, workspace, config, today=today)
    new_changelog_text = _insert_dated_section(changelog_text, draft["draft_section"])

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


def _add_draft_parser(sub):
    p = sub.add_parser("draft")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--release-config", required=True, help=_RELEASE_CONFIG_HELP)
    return p


def _add_bump_parser(sub):
    p = sub.add_parser("bump")
    p.add_argument("--version", required=True)
    p.add_argument("--repo-root", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--release-config", required=True, help=_RELEASE_CONFIG_HELP)
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
        config = load_and_validate_release_config(args.release_config, args.repo_root)
        if args.cmd == "status":
            result = compute_status(args.version, args.repo_root, config)
        elif args.cmd == "draft":
            result = build_draft(args.version, args.repo_root, args.workspace, config)
        elif args.cmd == "bump":
            result = bump(args.version, args.repo_root, args.workspace, config, dry_run=args.dry_run)
        else:
            sys.exit(2)  # pragma: no cover - unreachable, argparse `required=True` gates cmd
        print(json.dumps(result))
        sys.exit(0)
    except ReleaseNotesError as exc:
        print(json.dumps({"command": command, "error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
