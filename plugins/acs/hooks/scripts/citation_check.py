#!/usr/bin/env python3
"""Dependency-free corroboration checker for a plan's `Upstream inventory` citations.

The 4 bootstrap-doc planners (create-quality, create-standards,
create-operations, create-principles) record upstream-fact citations in an
`Upstream inventory` section of `iter-<n>-plan.md`: one line per citation,
each naming a claim, a backtick-quoted relative path under a declared root,
and a straight-double-quoted verbatim excerpt. This script is the
deterministic ($0, stdlib-only) mechanical floor the verifier invokes to
independently re-open every cited file and confirm the excerpt is really
there, rather than trusting the planner's citation on its word.

The resolved-citations manifest printed to stdout is one JSON object per
citation — {"claim", "path", "line", "excerpt"}. Its "line" key is the
citation's line number in the PLAN file only; it is purely informational and
is never a locus in the cited file. The advisory :line / :line-start-line-end
suffix a planner may append to the cited path is stripped during extraction
(_strip_line_ref) and is not retained anywhere, so a consumer that needs the
substantiating passage inside the cited file must locate it by searching for
the entry's own verbatim "excerpt" text.

Rules:
  - citation-unresolved       : the cited path is absolute, escapes every
                                declared root via a ".." segment or a
                                symlink, or does not resolve to a readable
                                file under any declared root.
  - citation-excerpt-not-found: the path resolves, but the whitespace-
                                normalized excerpt is not a substring of the
                                whitespace-normalized file content.
  - citation-inventory-empty  : the `Upstream inventory` section (or its
                                absence) yields zero parseable citation
                                lines.

Usage:
  python3 plugins/acs/hooks/scripts/citation_check.py \\
      --plan <plan.md> --root prd=<path> --root architecture=<path> \\
      [--root principles=<path>]
Importable:
  from citation_check import extract_citations, resolve_and_check, Finding

Exit codes mirror `structure_lint.py`'s CLI contract: 0 clean (at least one
citation, all resolved, all excerpt-matched), 1 one or more findings on
stderr, 2 a usage error or an unreadable plan file.
"""

import json
import os
import re
import sys
from collections import namedtuple

Finding = namedtuple("Finding", ["source", "line", "rule", "message"])
Citation = namedtuple("Citation", ["line", "claim", "path", "excerpt"])

# Bounded line-prefix heading match — no nested quantifiers, ReDoS-safe.
_HEADING = re.compile(r"^(#{1,6}) (.*)$")

# "- <claim> — `<path>[:line[-line]]` — "<excerpt>"" — one line, non-greedy
# claim so an em-dash inside the claim text does not confuse the boundary.
_CITATION = re.compile(r'^-\s+(.+?)\s+—\s+`([^`]+)`\s+—\s+"(.*)"\s*$')

_PATH_LINE_REF = re.compile(r'^(.+?):\d+(?:-\d+)?$')

_UPSTREAM_HEADING = "Upstream inventory"


def _headings(lines):
    """Return (line_no, level, text) for each heading line, in doc order."""
    found = []
    for idx, raw in enumerate(lines, start=1):
        m = _HEADING.match(raw)
        if m:
            found.append((idx, len(m.group(1)), m.group(2).strip()))
    return found


def _strip_line_ref(raw_path):
    """Drop an advisory trailing :line or :line-start-line-end suffix."""
    m = _PATH_LINE_REF.match(raw_path)
    return m.group(1) if m else raw_path


def _normalize_ws(text):
    """Collapse whitespace runs to a single space and strip both ends."""
    return re.sub(r"\s+", " ", text).strip()


def _section_body_lines(lines, heading_name):
    """Return [(line_no, content), ...] for the named heading's body (any
    level 1-6), bounded by the next equal-or-higher-level heading. None if
    the heading is absent."""
    headings = _headings(lines)
    for i, (line_no, level, text) in enumerate(headings):
        if text == heading_name:
            boundary = len(lines) + 1
            for j in range(i + 1, len(headings)):
                nline, nlevel, _ = headings[j]
                if nlevel <= level:
                    boundary = nline
                    break
            body = lines[line_no:boundary - 1]
            return [(line_no + 1 + k, content) for k, content in enumerate(body)]
    return None


def extract_citations(text, heading=_UPSTREAM_HEADING):
    """Parse citation-grammar lines from the plan's Upstream inventory body.

    Returns a list of Citation, scoped to the section only (D5). An absent
    heading and a present-but-empty section both yield [] — the caller
    reports citation-inventory-empty either way."""
    lines = text.split("\n")
    body = _section_body_lines(lines, heading)
    if body is None:
        return []
    citations = []
    for line_no, content in body:
        m = _CITATION.match(content.strip())
        if not m:
            continue
        claim, raw_path, excerpt = m.groups()
        citations.append(Citation(line_no, claim.strip(), _strip_line_ref(raw_path), excerpt))
    return citations


def _has_dotdot(path):
    return ".." in path.split("/")


def _is_unsafe_path(path):
    """Screen planner-authored path text before any filesystem call: absolute,
    `..`-escaping, or containing an embedded NUL byte."""
    return os.path.isabs(path) or _has_dotdot(path) or "\x00" in path


def _resolve_under_roots(path, roots):
    """Join *path* against each declared root and confirm realpath()
    containment. Returns the resolved real path, or None."""
    for _name, root in roots.items():
        root_real = os.path.realpath(root)
        candidate_real = os.path.realpath(os.path.join(root, path))
        if candidate_real == root_real or candidate_real.startswith(root_real + os.sep):
            if os.path.isfile(candidate_real):
                return candidate_real
    return None


def resolve_and_check(citations, roots, plan_path):
    """Resolve, containment-check, read-once-cache and excerpt-match every
    citation. Returns (findings, manifest) — manifest entries are plain
    dicts ready for JSON-line output."""
    findings = []
    manifest = []
    file_cache = {}

    for citation in citations:
        if _is_unsafe_path(citation.path):
            findings.append(Finding(
                plan_path, citation.line, "citation-unresolved",
                "citation path %r is absolute, escapes its root, or contains a NUL byte" % citation.path))
            continue

        try:
            resolved = _resolve_under_roots(citation.path, roots)
        except ValueError as exc:
            findings.append(Finding(
                plan_path, citation.line, "citation-unresolved",
                "citation path %r could not be resolved: %s" % (citation.path, exc)))
            continue
        if resolved is None:
            findings.append(Finding(
                plan_path, citation.line, "citation-unresolved",
                "citation path %r does not resolve under any declared root" % citation.path))
            continue

        if resolved not in file_cache:
            try:
                with open(resolved, encoding="utf-8") as fh:
                    file_cache[resolved] = _normalize_ws(fh.read())
            except (OSError, UnicodeDecodeError) as exc:
                findings.append(Finding(
                    plan_path, citation.line, "citation-unresolved",
                    "cannot read cited file %r: %s" % (citation.path, exc)))
                continue

        if _normalize_ws(citation.excerpt) not in file_cache[resolved]:
            findings.append(Finding(
                plan_path, citation.line, "citation-excerpt-not-found",
                "excerpt for claim %r not found in %s" % (citation.claim, citation.path)))
            continue

        manifest.append({
            "claim": citation.claim,
            "path": citation.path,
            "line": citation.line,
            "excerpt": citation.excerpt,
        })

    return findings, manifest


def _parse_root_arg(raw):
    """Split one --root NAME=PATH argument. Returns (name, path) or None."""
    if "=" not in raw:
        return None
    name, _, path = raw.partition("=")
    if not name or not path:
        return None
    return name, path


def main(argv):
    """CLI entry point: parse --plan/--root, print findings+manifest, return the exit code."""
    args = argv[1:]
    usage = ("usage: citation_check.py --plan <plan.md> "
              "--root <name>=<path> [--root <name>=<path> ...]")
    plan_path = None
    roots = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--plan":
            if i + 1 >= len(args):
                print(usage, file=sys.stderr)
                return 2
            plan_path = args[i + 1]
            i += 2
            continue
        if a == "--root":
            if i + 1 >= len(args):
                print(usage, file=sys.stderr)
                return 2
            parsed = _parse_root_arg(args[i + 1])
            if parsed is None:
                print(usage, file=sys.stderr)
                return 2
            name, path = parsed
            roots[name] = path
            i += 2
            continue
        print(usage, file=sys.stderr)
        return 2

    if plan_path is None or not roots:
        print(usage, file=sys.stderr)
        return 2

    try:
        with open(plan_path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print("error reading %s: %s" % (plan_path, exc), file=sys.stderr)
        return 2

    citations = extract_citations(text)
    if not citations:
        findings = [Finding(plan_path, 0, "citation-inventory-empty",
                             "Upstream inventory section has no parseable citations")]
        manifest = []
    else:
        findings, manifest = resolve_and_check(citations, roots, plan_path)

    for entry in manifest:
        print(json.dumps(entry))

    for f in findings:
        print("%s:%d: [%s] %s" % (f.source, f.line, f.rule, f.message), file=sys.stderr)

    if findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
