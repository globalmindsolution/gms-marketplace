#!/usr/bin/env python3
"""codeowners.py — CODEOWNERS parser + last-match-wins owner resolution.

Gives /acs:create-pr a deterministic way to resolve the raw set of
CODEOWNERS-matched owners for a PR's changed files, so the reviewer-request
prose step (Spec 02) can drop the author and request the remainder.

  resolve   Find the repo's CODEOWNERS file (git's own precedence order),
            parse it, match each changed file against the pattern lines using
            last-match-wins semantics, and print the raw matched-owner union
            as JSON to stdout.

Stdlib-only, Python >= 3.9. Pure parse+match: no `acs_lib` import, no
workspace read/write, no lock, no `gh` call, no network. Shape mirrors
pr-conventions.py: argparse with subparsers, JSON to stdout, sys.exit
non-zero on malformed invocation only.

Usage:
  codeowners.py resolve --repo-root /path/to/repo \\
      --changed-files /path/to/changed-files.txt \\
      [--codeowners-path /path/to/override/CODEOWNERS]

  codeowners.py resolve --repo-root /path/to/repo --changed-files -
      (reads the newline-delimited changed-file list from stdin)
"""

import argparse
import fnmatch
import json
import os
import re
import sys

MAX_LINES = 5000
PRECEDENCE = (".github/CODEOWNERS", "docs/CODEOWNERS", "CODEOWNERS")


def find_codeowners_file(repo_root):
    """Return the first CODEOWNERS path that exists, in git's own precedence order."""
    for rel in PRECEDENCE:
        candidate = os.path.join(repo_root, *rel.split("/"))
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_codeowners(text):
    """Parse CODEOWNERS text into an ordered list of (pattern, [owners]) rules, skipping comments/blanks."""
    rules = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        pattern, owners = parts[0], parts[1:]
        rules.append((pattern, owners))
    return rules


def _pattern_to_regex(pattern):
    """Translate a gitignore-style glob pattern to a compiled regex via stdlib fnmatch.translate."""
    return re.compile(fnmatch.translate(pattern))


def match_owners(rules, changed_files):
    """Resolve the raw owner union across changed files, last-matching rule wins per file."""
    compiled = [(_pattern_to_regex(pattern), owners) for pattern, owners in rules]
    union = []
    for changed_file in changed_files:
        winner = None
        for regex, owners in compiled:
            if regex.match(changed_file):
                winner = owners
        if winner:
            for owner in winner:
                if owner not in union:
                    union.append(owner)
    return union


def resolve(repo_root, changed_files, codeowners_path=None):
    """Find + parse the repo's CODEOWNERS file and resolve owners for changed_files; never raises."""
    path = codeowners_path or find_codeowners_file(repo_root)
    if path is None:
        return {"source": None, "owners": [], "reason": "no_codeowners_file"}

    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    if len(lines) >= MAX_LINES:
        return {"source": None, "owners": [], "reason": "file_too_large"}

    rules = parse_codeowners("".join(lines))
    owners = match_owners(rules, changed_files)
    source = os.path.relpath(path, repo_root) if not codeowners_path else path
    if not owners:
        return {"source": source, "owners": [], "reason": "no_pattern_matched"}
    return {"source": source, "owners": owners, "reason": None}


def _read_changed_files(arg):
    """Read a newline-delimited changed-file list from a path arg, or stdin when arg is '-'."""
    text = sys.stdin.read() if arg == "-" else open(arg, "r", encoding="utf-8").read()
    return [line.strip() for line in text.splitlines() if line.strip()]


def _add_resolve_parser(sub):
    p = sub.add_parser("resolve")
    p.add_argument("--repo-root", required=True)
    p.add_argument("--changed-files", required=True)
    p.add_argument("--codeowners-path", default=None)
    return p


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_resolve_parser(sub)
    args = parser.parse_args(argv)

    if args.cmd == "resolve":
        changed_files = _read_changed_files(args.changed_files)
        result = resolve(args.repo_root, changed_files, args.codeowners_path)
        print(json.dumps(result))
        sys.exit(0)

    sys.exit(2)  # pragma: no cover - unreachable, argparse `required=True` gates cmd


if __name__ == "__main__":
    main()
