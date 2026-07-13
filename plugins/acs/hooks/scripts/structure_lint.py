#!/usr/bin/env python3
"""Dependency-free linter for section/structure conformance in generated Markdown docs.

The acs doc-producing skills (create-prd, create-architecture, create-design,
create-principles, create-standards, create-quality, create-operations) each
declare a required-section list in their SKILL.md. This linter is the
deterministic ($0, stdlib-only) backstop that checks a generated doc against
that declared list: every required section present, non-empty, and (when
asked) in the declared order.

Rules:
  - missing-section : a declared section name has no matching heading anywhere
                       in the doc.
  - empty-section    : the heading is present but no non-blank content line
                       appears before the next heading (of any level) or EOF.
  - section-order    : only emitted when ordered=True/--ordered — two declared
                       sections appear in the doc in the reverse of their
                       declared relative order. A declared name that is
                       ambiguous (repeated in the declared list, or matching
                       more than one heading in the doc) is excluded from the
                       order check and relaxed to presence + non-empty only,
                       so an ambiguous list can never false-block a
                       conforming doc.

Usage:
  python3 plugins/acs/hooks/scripts/structure_lint.py --sections "A; B; C" \\
      [--ordered] DOC.md
Importable:
  from structure_lint import lint_structure, lint_file, Finding

CLI-vs-API `ordered` default note: the CLI's `--ordered` is opt-in (default
off) — a verifier-invoked run should never false-block on order alone unless
it asks for it. The importable `lint_structure`/`lint_file` default
`ordered=True` — a caller reaching for the API directly typically already
wants strict order checking. This asymmetry is intentional and not
reconciled into one default.
"""

import re
import sys
from collections import namedtuple

Finding = namedtuple("Finding", ["source", "line", "rule", "message"])

# Bounded line-prefix heading match — no nested quantifiers, ReDoS-safe.
_HEADING = re.compile(r"^(#{1,6}) (.*)$")


def _parse_sections(raw):
    """Split a --sections CLI argument on ';' and strip each name."""
    return [s.strip() for s in raw.split(";")]


def _headings(lines):
    """Return (line_no, level, text) for each heading line, in doc order."""
    found = []
    for idx, raw in enumerate(lines, start=1):
        m = _HEADING.match(raw)
        if m:
            found.append((idx, len(m.group(1)), m.group(2).strip()))
    return found


def lint_structure(text, sections, ordered=True, source="<text>"):
    """Check each declared section is present, non-empty, and (if ordered) in order."""
    lines = text.split("\n")
    headings = _headings(lines)
    by_name = {}
    for i, (_line_no, _level, htext) in enumerate(headings):
        by_name.setdefault(htext, []).append(i)

    unique_sections = list(dict.fromkeys(sections))
    ambiguous = {n for n in unique_sections if sections.count(n) > 1}

    findings = []
    present = {}  # name -> (heading_index, line_no)

    for name in unique_sections:
        occs = by_name.get(name, [])
        if len(occs) > 1:
            ambiguous.add(name)
        if not occs:
            findings.append(Finding(source, 0, "missing-section",
                                     "required section %r not found" % name))
            continue
        i = occs[0]
        line_no, level, _ = headings[i]
        boundary = len(lines) + 1
        for j in range(i + 1, len(headings)):
            nline, nlevel, _ = headings[j]
            if nlevel <= level:
                boundary = nline
                break
        body = lines[line_no:boundary - 1]
        if not any(l.strip() for l in body):
            findings.append(Finding(source, line_no, "empty-section",
                                     "section %r has no content" % name))
        present[name] = (i, line_no)

    if ordered:
        seq = [n for n in unique_sections if n in present and n not in ambiguous]
        for k in range(len(seq) - 1):
            a, b = seq[k], seq[k + 1]
            if present[a][0] > present[b][0]:
                findings.append(Finding(
                    source, present[b][1], "section-order",
                    "section %r appears before %r in the doc, out of declared order"
                    % (b, a)))

    return findings


def lint_file(path, sections, ordered=True):
    """Read *path* and lint it against the declared *sections*."""
    with open(path, encoding="utf-8") as fh:
        return lint_structure(fh.read(), sections, ordered=ordered, source=str(path))


def main(argv):
    """CLI entry point: parse --sections/--ordered/DOC.md, print findings, return the exit code."""
    args = argv[1:]
    usage = 'usage: structure_lint.py --sections "A; B; C" [--ordered] DOC.md'
    sections_arg = None
    ordered = False
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--sections":
            if i + 1 >= len(args):
                print(usage, file=sys.stderr)
                return 2
            sections_arg = args[i + 1]
            i += 2
            continue
        if a == "--ordered":
            ordered = True
            i += 1
            continue
        positional.append(a)
        i += 1

    if sections_arg is None or len(positional) != 1 or not positional[0].endswith(".md"):
        print(usage, file=sys.stderr)
        return 2

    path = positional[0]
    sections = _parse_sections(sections_arg)
    try:
        findings = lint_file(path, sections, ordered=ordered)
    except (OSError, UnicodeDecodeError) as exc:
        print("error reading %s: %s" % (path, exc), file=sys.stderr)
        return 2

    for f in findings:
        print("%s:%d: [%s] %s" % (f.source, f.line, f.rule, f.message), file=sys.stderr)
    if findings:
        print("\n%d structure finding(s)." % len(findings), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
