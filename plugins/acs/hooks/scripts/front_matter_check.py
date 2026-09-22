#!/usr/bin/env python3
"""Dependency-free checker for the YAML front matter of a generated doc.

`structure_lint.py` is the deterministic backstop for a doc's SECTIONS; this
is the one for its FRONT MATTER — the machine-read half of a ticket document.
`analysis.md`'s `api_surface` decides whether `/acs:create-api-contract` runs
at all (`workflows/ship.yaml`'s `api_surface_changed` predicate and the
`create-api-contract` gate both read it), so a front matter that is missing,
unparseable, or carries the wrong type is a pipeline failure discovered one
skill too late. Run this before publishing, and the failure surfaces where it
can still be fixed.

The parse is `acs_lib.yamlsubset`, the SAME parser the gate and the predicate
use, so "it parses here" means "it parses there": a block this checker accepts
cannot be rejected downstream.

Rules:
  - front-matter-missing      : the doc has no leading `---` block.
  - front-matter-unparseable  : the block is outside the YAML subset (the
                                reason and line come from the parser).
  - missing-key               : a required key is absent (or null).
  - wrong-type                : the key is present with the wrong type.
  - bad-value                 : the key is present but outside its declared
                                value set.
  - ticket-mismatch           : `--ticket` was given and `ticket:` names a
                                different id.

Declared types: `str` (non-empty), `bool`, `int` (a real integer — `true` is
not one), `list`, `any` (present and non-null), or a `|`-separated value set
(`normal|high`) for a string that must be one of those literals.

Usage:
  python3 front_matter_check.py --require "ticket: str; api_surface: bool" \\
      [--ticket SHOP-123] DOC.md
Importable:
  from front_matter_check import check_file, check_front_matter, parse_spec
"""

import os
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import yamlsubset  # noqa: E402
from acs_lib.yamlsubset import YamlSubsetError  # noqa: E402

Finding = namedtuple("Finding", ["source", "line", "rule", "message"])

USAGE = ('usage: front_matter_check.py --require "key: type; key: a|b" '
         '[--ticket ID] DOC.md')

#: The declared type names, each mapped to (predicate, human name).
_TYPES = {
    "str": (lambda v: isinstance(v, str) and v.strip() != "", "a non-empty string"),
    "bool": (lambda v: isinstance(v, bool), "a boolean (true/false)"),
    "int": (lambda v: isinstance(v, int) and not isinstance(v, bool), "an integer"),
    "list": (lambda v: isinstance(v, list), "a list"),
    "any": (lambda v: True, "any value"),
}


def parse_spec(raw):
    """Parse a --require argument into [(key, declared type)] pairs.

    Entries are separated by ';' and each reads `key: type`. Raises ValueError
    on a malformed entry, so a typo in the spec fails loudly instead of
    silently checking nothing."""
    spec = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError("malformed --require entry %r (expected 'key: type')" % entry)
        key, declared = entry.split(":", 1)
        key, declared = key.strip(), declared.strip()
        if not key or not declared:
            raise ValueError("malformed --require entry %r (expected 'key: type')" % entry)
        spec.append((key, declared))
    if not spec:
        raise ValueError("--require declared no keys")
    return spec


def _check_value(source, key, declared, value):
    """One key's finding, or None when it conforms."""
    if declared in _TYPES:
        ok, described = _TYPES[declared]
        if not ok(value):
            return Finding(source, 1, "wrong-type",
                           "front matter key %r must be %s, got %r" % (key, described, value))
        return None
    allowed = [v.strip() for v in declared.split("|") if v.strip()]
    if not isinstance(value, str) or value not in allowed:
        return Finding(source, 1, "bad-value",
                       "front matter key %r must be one of %s, got %r"
                       % (key, ", ".join(allowed), value))
    return None


def check_front_matter(text, spec, ticket=None, source="<text>"):
    """Check `text`'s front matter against `spec` ([(key, type)] pairs).

    Returns a list of Finding; empty means the front matter is exactly what
    the declaring skill promised its consumers."""
    try:
        front, _body = yamlsubset.split_front_matter(text)
    except YamlSubsetError as exc:
        return [Finding(source, exc.line or 1, "front-matter-unparseable",
                        "front matter is outside the YAML subset: %s" % exc.reason)]
    if front is None:
        return [Finding(source, 1, "front-matter-missing",
                        "no leading `---` front-matter block")]

    findings = []
    for key, declared in spec:
        if key not in front or front[key] is None:
            findings.append(Finding(source, 1, "missing-key",
                                    "front matter key %r is required" % key))
            continue
        finding = _check_value(source, key, declared, front[key])
        if finding is not None:
            findings.append(finding)

    if ticket is not None and isinstance(front.get("ticket"), str) \
            and front["ticket"] != ticket:
        findings.append(Finding(source, 1, "ticket-mismatch",
                                "front matter names ticket %r, expected %r"
                                % (front["ticket"], ticket)))
    return findings


def check_file(path, spec, ticket=None):
    """Read `path` and check its front matter against `spec`."""
    with open(path, encoding="utf-8") as fh:
        return check_front_matter(fh.read(), spec, ticket=ticket, source=str(path))


def main(argv):
    """CLI entry point: parse --require/--ticket/DOC.md, print findings, return
    the exit code (0 clean, 1 findings, 2 usage or read error)."""
    args = argv[1:]
    require_arg = None
    ticket = None
    positional = []
    index = 0
    while index < len(args):
        current = args[index]
        if current in ("--require", "--ticket"):
            if index + 1 >= len(args):
                print(USAGE, file=sys.stderr)
                return 2
            if current == "--require":
                require_arg = args[index + 1]
            else:
                ticket = args[index + 1]
            index += 2
            continue
        positional.append(current)
        index += 1

    if require_arg is None or len(positional) != 1 or not positional[0].endswith(".md"):
        print(USAGE, file=sys.stderr)
        return 2

    try:
        spec = parse_spec(require_arg)
    except ValueError as exc:
        print("front_matter_check: %s" % exc, file=sys.stderr)
        return 2

    path = positional[0]
    try:
        findings = check_file(path, spec, ticket=ticket)
    except (OSError, UnicodeDecodeError) as exc:
        print("error reading %s: %s" % (path, exc), file=sys.stderr)
        return 2

    for finding in findings:
        print("%s:%d: [%s] %s" % (finding.source, finding.line, finding.rule,
                                  finding.message), file=sys.stderr)
    if findings:
        print("\n%d front-matter finding(s)." % len(findings), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
