#!/usr/bin/env python3
"""Dependency-free floor for the per-feature PRDs of a create-prd doc set
(ADR-0142) -- the deterministic half of the reviewer's dimensions 1, 2 and 10
for the `<prd_dir>/features/<slug>/prd.md` documents.

The product PRD (`prd.md`, the hub) lists every feature under `## Features
(prioritized)` as a bullet in a MoSCoW group (`### Must have` ...), linking the
feature's own PRD:

    - [Wishlist](features/wishlist/prd.md) — save products for later (supports G1, G3)

A Won't-have bullet may omit the link. This script checks the hub against the
feature documents on disk, and each feature document against the hub:

Rules:
  feature-link-missing     : a Must/Should/Could bullet links no feature PRD.
  feature-doc-missing      : a linked `features/<slug>/prd.md` does not exist.
  feature-doc-unindexed    : a `features/<slug>/prd.md` on disk is linked from
                             no bullet of the hub's Features section.
  feature-goal-unknown     : a goal id (`G<n>`) a bullet or a feature's `##
                             Goals served` names is not in the hub's `## Goals
                             & success metrics` (checked only when that section
                             names goal ids at all).
  feature-goals-mismatch   : the goal ids of a feature's hub bullet and of its
                             own `## Goals served` section differ.
  feature-requirement-ids  : a feature's `## Requirements` section has no
                             `- **R<n>** ...` line, or repeats an id.
  missing-section / empty-section / section-order
                           : `structure_lint`'s rules over the feature's
                             required sections (`--feature-sections`).

Usage:
  python3 plugins/acs/hooks/scripts/prd_feature_check.py --prd <the hub prd.md> \\
      [--feature-sections "A; B; C"]

Exit codes mirror `prd_conformance_check.py`: 0 clean (one JSON manifest line
per feature document on stdout), 1 findings on stderr as `source:line: [rule]
message`, 2 a usage error or an unreadable hub.
"""

import json
import os
import re
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import markdown_headings  # noqa: E402
import structure_lint  # noqa: E402

Finding = namedtuple("Finding", ["source", "line", "rule", "message"])

DEFAULT_FEATURE_SECTIONS = ("Summary; Goals served; Requirements; "
                            "Acceptance criteria; Dependencies; Out of scope")

_LINK = re.compile(r"\]\(\s*(?:\./)?features/([a-z0-9]+(?:-[a-z0-9]+)*)/prd\.md\s*\)")
_GOAL = re.compile(r"\bG\d+\b")
_BULLET = re.compile(r"^[-*]\s+\S")
_REQUIREMENT = re.compile(r"^\s*[-*]\s+\*\*(R\d+)\*\*")
_USAGE = 'usage: prd_feature_check.py --prd <prd.md> [--feature-sections "A; B; C"]'


def _section(lines, title_prefix):
    """(start_line, [(line_no, text)]) of the H2 section whose heading starts
    with `title_prefix`, else (0, [])."""
    heads = markdown_headings.headings(lines)
    for i, (line_no, level, text) in enumerate(heads):
        if level == 2 and text.lower().startswith(title_prefix.lower()):
            end = len(lines) + 1
            for nline, nlevel, _ in heads[i + 1:]:
                if nlevel <= 2:
                    end = nline
                    break
            return line_no, [(n, lines[n - 1]) for n in range(line_no + 1, end)]
    return 0, []


def _index(feature_lines):
    """[(line_no, group, slug or None, goals)] for each top-level bullet of
    the hub's Features section; `group` is the nearest `###` MoSCoW word."""
    out, group = [], None
    for line_no, raw in feature_lines:
        head = re.match(r"^#{3,6}\s+(\w+)", raw)
        if head:
            group = head.group(1).lower()
            continue
        if _BULLET.match(raw):
            link = _LINK.search(raw)
            out.append((line_no, group, link.group(1) if link else None,
                        set(_GOAL.findall(raw))))
    return out


def check_features(prd_path, feature_sections=DEFAULT_FEATURE_SECTIONS):
    """(findings, manifest) for the hub at `prd_path` and its feature PRDs."""
    with open(prd_path, encoding="utf-8") as fh:
        hub_lines = fh.read().split("\n")
    root = os.path.join(os.path.dirname(prd_path) or ".", "features")
    findings, manifest = [], []

    _at, feature_lines = _section(hub_lines, "Features")
    _at, goal_lines = _section(hub_lines, "Goals")
    known_goals = set(_GOAL.findall("\n".join(t for _n, t in goal_lines)))
    index = _index(feature_lines)
    linked = {}
    for line_no, group, slug, goals in index:
        if slug is None:
            if group != "won":
                findings.append(Finding(prd_path, line_no, "feature-link-missing",
                                        "a %s-have feature links no features/<slug>/prd.md"
                                        % (group or "prioritized")))
            continue
        linked[slug] = (line_no, goals)

    on_disk = sorted(d for d in (os.listdir(root) if os.path.isdir(root) else [])
                     if os.path.isfile(os.path.join(root, d, "prd.md")))
    for slug, (line_no, _goals) in sorted(linked.items()):
        if slug not in on_disk:
            findings.append(Finding(prd_path, line_no, "feature-doc-missing",
                                    "features/%s/prd.md is linked but does not exist" % slug))
    for slug in on_disk:
        if slug not in linked:
            findings.append(Finding(os.path.join(root, slug, "prd.md"), 0, "feature-doc-unindexed",
                                    "no bullet of the Features section links this document"))

    sections = structure_lint._parse_sections(feature_sections)
    for slug in on_disk:
        path = os.path.join(root, slug, "prd.md")
        manifest.append({"family": "feature-docs", "feature": slug, "path": path})
        findings += [Finding(*f) for f in structure_lint.lint_file(path, sections, ordered=True)]
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        goals_at, goals_body = _section(lines, "Goals served")
        own = set(_GOAL.findall("\n".join(t for _n, t in goals_body)))
        hub = linked.get(slug, (0, set()))[1]
        if slug in linked and own != hub:
            findings.append(Finding(path, goals_at, "feature-goals-mismatch",
                                    "Goals served names %s but the hub's bullet names %s"
                                    % (sorted(own) or "none", sorted(hub) or "none")))
        for goal in sorted((own | hub) - known_goals if known_goals else ()):
            findings.append(Finding(path, goals_at, "feature-goal-unknown",
                                    "%s is not a goal in the hub's Goals & success metrics" % goal))
        req_start, req_body = _section(lines, "Requirements")
        ids = [m.group(1) for _n, t in req_body for m in [_REQUIREMENT.match(t)] if m]
        if not ids or len(ids) != len(set(ids)):
            findings.append(Finding(path, req_start, "feature-requirement-ids",
                                    "Requirements needs one `- **R<n>** ...` line per requirement, "
                                    "each id once"))
    return findings, manifest


def main(argv):
    args = argv[1:]
    values = {}
    for flag, value in zip(args[::2], args[1::2]):
        if flag not in ("--prd", "--feature-sections"):
            print(_USAGE, file=sys.stderr)
            return 2
        values[flag] = value
    if len(args) % 2 or "--prd" not in values:
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        findings, manifest = check_features(
            values["--prd"], values.get("--feature-sections", DEFAULT_FEATURE_SECTIONS))
    except (OSError, UnicodeDecodeError) as exc:
        print("error reading %s: %s" % (values["--prd"], exc), file=sys.stderr)
        return 2
    for entry in manifest:
        print(json.dumps(entry))
    for f in findings:
        print("%s:%d: [%s] %s" % (f.source, f.line, f.rule, f.message), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
