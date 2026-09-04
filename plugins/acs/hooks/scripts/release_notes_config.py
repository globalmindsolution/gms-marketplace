"""release_notes_config — the release config, its validation and the JSON-pointer
writer (extracted from release_notes.py by MAR-531).

Everything about WHERE a version lives and how it is written: the schema-shaped
validation of `.acs/release.json`, the pointer navigation that reaches a version
field inside an arbitrary manifest, and the atomic writes that replace one.
Nothing here knows what a release note says.
"""


import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile



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
