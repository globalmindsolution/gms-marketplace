#!/usr/bin/env python3
"""Deterministic floor for /acs:manage-roadmap (ADR-0145): the roadmap against
its own shape, the PRD hub's Features index and, given the authoring notes,
the notes' milestone outline and answer anchors.

Rules:
  milestone-unversioned  : a `###` heading under `## Milestones` carries no
                           `— v<major>.<minor>.<patch>` version.
  version-unmapped       : a milestone's version has no Release versions row,
                           or the row names another milestone.
  version-orphan         : a Release versions row whose version no milestone has.
  version-duplicate      : two milestones, or two rows, share a version.
  feature-unknown        : a milestone links a feature with no PRD of its own
                           (`features/<slug>/prd.md` beside the hub).
  must-unscheduled       : a Must-have feature of the hub's index is in no milestone.
  wont-scheduled         : a Won't-have feature is in a milestone.
  status-invalid         : a milestone's Status is missing or not planned,
                           in progress or delivered.
  status-mismatch        : a row's Status differs from its milestone's.
  roadmap-milestone-*    : with --plan, prd_conformance_check's milestone-outline
                           family over the notes' `## Roadmap milestones`.
  answer-*               : with --plan and --clarifications, its answer-fidelity
                           family, anchors in `roadmap.md`.

Usage:
  python3 roadmap_check.py --roadmap <roadmap.md> --prd <the hub prd.md>
      [--plan <authoring notes> --mode {create|amend|replan}
       [--clarifications <clarifications.json>] [--added-heading "<heading>" ...]]

Exit codes: 0 clean, 1 findings on stderr as `source:line: [rule] message`,
2 a usage error or an unreadable input.
"""

import json
import os
import re
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import roadmap  # noqa: E402
import prd_conformance_check  # noqa: E402

Finding = namedtuple("Finding", ["source", "line", "rule", "message"])

_LINK = re.compile(r"\]\(\s*(?:\./)?features/([a-z0-9]+(?:-[a-z0-9]+)*)/prd\.md\s*\)")
_USAGE = ("usage: roadmap_check.py --roadmap <roadmap.md> --prd <prd.md> [--plan <notes> "
          "--mode {create|amend|replan} [--clarifications <file>] [--added-heading <h> ...]]")


def hub_groups(prd_text):
    """{slug: group} of the hub's Features index (`must`, `should`, `could`, `won`)."""
    groups, group, inside = {}, None, False
    for line in prd_text.split("\n"):
        h2 = re.match(r"^##\s+(.+?)\s*$", line)
        if h2:
            inside = h2.group(1).lower().startswith("features")
            continue
        if not inside:
            continue
        h3 = re.match(r"^#{3,6}\s+(\w+)", line)
        if h3:
            group = h3.group(1).lower()
            continue
        for slug in _LINK.findall(line):
            groups.setdefault(slug, group)
    return groups


def check_roadmap(roadmap_path, prd_path):
    with open(roadmap_path, encoding="utf-8") as fh:
        text = fh.read()
    with open(prd_path, encoding="utf-8") as fh:
        prd_text = fh.read()
    parsed = roadmap.parse(text)
    features_dir = os.path.join(os.path.dirname(prd_path) or ".", "features")
    groups = hub_groups(prd_text)
    src, findings = roadmap_path, []

    def add(line, rule, message):
        findings.append(Finding(src, line + 1, rule, message))

    for head in parsed["headings"]:
        if not head["versioned"]:
            add(head["line"], "milestone-unversioned",
                "milestone %r has no `— v<major>.<minor>.<patch>` version" % head["text"])
    rows = {}
    for row in parsed["versions"]:
        if row["version"] in rows:
            add(row["line"], "version-duplicate", "v%s has two rows" % row["version"])
        rows[row["version"]] = row
    seen, scheduled = {}, set()
    for m in parsed["milestones"]:
        if m["version"] in seen:
            add(m["line"], "version-duplicate", "v%s is the version of two milestones"
                % m["version"])
        seen[m["version"]] = m
        row = rows.get(m["version"])
        if row is None or row["milestone"].strip().lower() != m["name"].lower():
            add(m["line"], "version-unmapped", "milestone %r (v%s) has no Release versions row "
                "naming it" % (m["name"], m["version"]))
        if m["status"] not in roadmap.STATUSES:
            add(m["line"], "status-invalid", "milestone %r Status is %r, not one of %s"
                % (m["name"], m["status"], ", ".join(roadmap.STATUSES)))
        elif row is not None and row["status"] != m["status"]:
            add(row["line"], "status-mismatch", "v%s row says %r, its milestone %r"
                % (m["version"], row["status"], m["status"]))
        for slug in m["features"]:
            scheduled.add(slug)
            if not os.path.isfile(os.path.join(features_dir, slug, "prd.md")):
                add(m["line"], "feature-unknown", "feature %r has no PRD of its own" % slug)
            if groups.get(slug) == "won":
                add(m["line"], "wont-scheduled", "feature %r is a Won't-have" % slug)
    for row in parsed["versions"]:
        if row["version"] not in seen:
            add(row["line"], "version-orphan", "v%s names no milestone" % row["version"])
    for slug, group in sorted(groups.items()):
        if group == "must" and slug not in scheduled:
            findings.append(Finding(prd_path, 0, "must-unscheduled",
                                    "Must-have feature %r is in no milestone" % slug))
    return findings, text


def main(argv):
    args, values, added = argv[1:], {}, []
    known = ("--roadmap", "--prd", "--plan", "--mode", "--clarifications", "--added-heading")
    if len(args) % 2:
        print(_USAGE, file=sys.stderr)
        return 2
    for flag, value in zip(args[::2], args[1::2]):
        if flag not in known:
            print(_USAGE, file=sys.stderr)
            return 2
        if flag == "--added-heading":
            added.append(value)
        else:
            values[flag] = value
    if "--roadmap" not in values or "--prd" not in values or (
            "--plan" in values and values.get("--mode") not in ("create", "amend", "replan")):
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        findings, text = check_roadmap(values["--roadmap"], values["--prd"])
        if "--plan" in values:
            with open(values["--plan"], encoding="utf-8") as fh:
                plan = fh.read()
            mode = "amend" if values["--mode"] in ("amend", "replan") else "greenfield"
            # Only the milestone headings are the outline; the title and the
            # section headings are the document's shape, checked above.
            outline = "\n".join("### " + h["text"] for h in roadmap.parse(text)["headings"])
            f, _m = prd_conformance_check.check_roadmap_milestones(
                plan, outline, mode, added, values["--plan"])
            findings += f
            if "--clarifications" in values:
                with open(values["--clarifications"], encoding="utf-8") as fh:
                    clar = json.load(fh)["clarifications"]
                f, _m = prd_conformance_check.check_answer_fidelity(
                    plan, clar, "", text, values["--plan"])
                findings += [x for x in f]
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as exc:
        print("error reading input: %s" % exc, file=sys.stderr)
        return 2
    for f in findings:
        print("%s:%d: [%s] %s" % (f.source, f.line, f.rule, f.message), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
