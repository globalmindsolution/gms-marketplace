#!/usr/bin/env python3
"""Dependency-free corroboration checker for a create-prd plan's three
required plan sections (`Code evidence`, `Answer fidelity`, `Roadmap
milestones`) -- the deterministic floor of create-prd-verifier.md's
dimension 7, "Plan conformance" (MAR-304).

Rule families:
  code-evidence    : brownfield/amend only (N/A in greenfield). Reuses
                     `citation_check.py`'s `extract_citations`/
                     `resolve_and_check` UNCHANGED (imported, never
                     re-implemented) against the plan's `## Code evidence`
                     section, then re-tags the rule names under this
                     script's own namespace.
  answer-fidelity  : active every mode. Every `answered`/`assumed`
                     `clarifications.json` ledger entry must have exactly
                     one `## Answer fidelity` line naming a verbatim,
                     whitespace-normalized anchor in prd.md or roadmap.md,
                     or an `N/A: <why>` escape.
  roadmap-outline  : active every mode. Every plan-declared milestone
                     heading must occur, verbatim (whitespace-normalized,
                     leading `#` marker optional), as a heading in
                     roadmap.md; the reverse direction (every roadmap.md
                     heading must be plan-declared) runs against the full
                     roadmap in greenfield/brownfield and against only the
                     `--added-heading` values in amend mode.

Rules:
  code-citation-unresolved       : inherited via import from
                                   citation_check's citation-unresolved.
  code-citation-excerpt-not-found: inherited via import from
                                   citation_check's citation-excerpt-not-found.
  code-evidence-empty           : the `## Code evidence` section (or its
                                   absence) yields zero parseable citation
                                   lines; brownfield/amend only -- this
                                   script's own policy, never
                                   citation_check.main()'s
                                   citation-inventory-empty.
  answer-not-dispositioned      : an answered/assumed ledger id has no
                                   `## Answer fidelity` line.
  answer-anchor-not-found       : the named file does not contain the
                                   whitespace-normalized anchor.
  answer-anchor-file-unknown    : the named target is neither prd.md nor
                                   roadmap.md.
  roadmap-milestone-not-found   : a plan-declared milestone heading is
                                   absent from roadmap.md.
  roadmap-milestone-unplanned   : a roadmap.md heading (full set in
                                   greenfield/brownfield, `--added-heading`
                                   set in amend) has no matching
                                   `## Roadmap milestones` declaration.

Usage:
  python3 plugins/acs/hooks/scripts/prd_conformance_check.py \\
      --plan <iter-n-plan.md> --mode {greenfield|brownfield|amend} \\
      --repo-root <repo-root> \\
      --clarifications <partition>/clarifications.json \\
      --prd <prd_path>/prd.md --roadmap <prd_path>/roadmap.md \\
      [--added-heading "<verbatim milestone heading>" ...]
Importable:
  from prd_conformance_check import (
      check_code_evidence, check_answer_fidelity, check_roadmap_milestones)

Exit codes mirror `citation_check.py`'s CLI contract: 0 clean (every active
family's manifest printed, no findings), 1 one or more findings on stderr,
2 a usage error or an unreadable/malformed plan, clarifications, prd or
roadmap input.
"""

import json
import os
import re
import sys

import citation_check
from citation_check import extract_citations, resolve_and_check, Finding

_ANSWER_LINE = re.compile(r'^-\s+(C-\d+)\s+—\s+(\S+)\s+—\s+"(.*)"\s*$')
_ANSWER_NA_LINE = re.compile(r'^-\s+(C-\d+)\s+N/A:\s*(.+)$')
_MILESTONE_LINE = re.compile(r'^-\s+Milestone:\s+"(.*)"\s*$')
_HEADING_MARKER = re.compile(r'^#{1,6}\s+')

_RULE_RENAME = {
    "citation-unresolved": "code-citation-unresolved",
    "citation-excerpt-not-found": "code-citation-excerpt-not-found",
}

_MODES = ("greenfield", "brownfield", "amend")

_USAGE = ("usage: prd_conformance_check.py --plan <plan.md> "
          "--mode {greenfield|brownfield|amend} --repo-root <path> "
          "--clarifications <clarifications.json> --prd <prd.md> "
          "--roadmap <roadmap.md> [--added-heading <heading> ...]")


def _strip_heading_marker(s):
    """Drop a leading `#{1,6} ` run, if present -- the marker is optional."""
    return _HEADING_MARKER.sub("", s, count=1)


def _headings_match(a, b):
    """Whitespace-normalized, marker-optional heading-text equality."""
    return (citation_check._normalize_ws(_strip_heading_marker(a))
            == citation_check._normalize_ws(_strip_heading_marker(b)))


def check_code_evidence(text, repo_root, plan_path):
    """Resolve the plan's `## Code evidence` citations via the imported
    citation_check helpers, re-tagged under this script's own rule names."""
    citations = extract_citations(text, heading="Code evidence")
    if not citations:
        return (
            [Finding(plan_path, 0, "code-evidence-empty",
                     "Code evidence section has no parseable citations")],
            [],
        )
    findings, manifest = resolve_and_check(citations, {"repo": repo_root}, plan_path)
    findings = [
        Finding(f.source, f.line, _RULE_RENAME.get(f.rule, f.rule), f.message)
        for f in findings
    ]
    for entry in manifest:
        entry["family"] = "code-evidence"
    return findings, manifest


def _parse_answer_lines(text):
    """Return {ledger id: {"line", "na", "target"/"anchor" or "reason"}}."""
    lines = text.split("\n")
    body = citation_check._section_body_lines(lines, "Answer fidelity")
    entries = {}
    if body is None:
        return entries
    for line_no, content in body:
        stripped = content.strip()
        m = _ANSWER_LINE.match(stripped)
        if m:
            cid, target, anchor = m.groups()
            entries[cid] = {"line": line_no, "na": False, "target": target, "anchor": anchor}
            continue
        m = _ANSWER_NA_LINE.match(stripped)
        if m:
            cid, reason = m.groups()
            entries[cid] = {"line": line_no, "na": True, "reason": reason.rstrip()}
    return entries


def check_answer_fidelity(text, clarifications, prd_text, roadmap_text, plan_path):
    """Corroborate every answered/assumed ledger entry against its `## Answer
    fidelity` disposition -- population is the ledger, never the plan."""
    declared = _parse_answer_lines(text)
    file_texts = {"prd.md": prd_text, "roadmap.md": roadmap_text}
    findings = []
    manifest = []

    for entry in clarifications:
        if entry.get("status") not in ("answered", "assumed"):
            continue
        cid = entry.get("id")
        disp = declared.get(cid)
        if disp is None:
            findings.append(Finding(
                plan_path, 0, "answer-not-dispositioned",
                "ledger entry %s has no ## Answer fidelity line" % cid))
            continue

        if disp["na"]:
            manifest.append({
                "id": cid, "family": "answer-fidelity",
                "na": True, "reason": disp["reason"], "line": disp["line"],
            })
            continue

        target = disp["target"]
        if target not in file_texts:
            findings.append(Finding(
                plan_path, disp["line"], "answer-anchor-file-unknown",
                "answer fidelity target %r for %s is neither prd.md nor roadmap.md"
                % (target, cid)))
            continue

        haystack = citation_check._normalize_ws(file_texts[target])
        if citation_check._normalize_ws(disp["anchor"]) not in haystack:
            findings.append(Finding(
                plan_path, disp["line"], "answer-anchor-not-found",
                "anchor for %s not found in %s" % (cid, target)))
            continue

        manifest.append({
            "id": cid, "family": "answer-fidelity",
            "na": False, "target": target, "anchor": disp["anchor"], "line": disp["line"],
        })

    return findings, manifest


def check_roadmap_milestones(text, roadmap_text, mode, added_headings, plan_path):
    """Bidirectionally corroborate the plan's `## Roadmap milestones` outline
    against roadmap.md's headings; the reverse direction is mode-scoped."""
    lines = text.split("\n")
    body = citation_check._section_body_lines(lines, "Roadmap milestones")
    declared = []
    if body is not None:
        for line_no, content in body:
            m = _MILESTONE_LINE.match(content.strip())
            if m:
                declared.append((line_no, m.group(1)))

    roadmap_headings = [
        heading_text for (_line_no, _level, heading_text)
        in citation_check._headings(roadmap_text.split("\n"))
    ]

    findings = []
    manifest = []

    for line_no, heading in declared:
        if any(_headings_match(heading, rh) for rh in roadmap_headings):
            manifest.append({"family": "roadmap-outline", "milestone": heading, "line": line_no})
        else:
            findings.append(Finding(
                plan_path, line_no, "roadmap-milestone-not-found",
                "declared milestone %r not found in roadmap.md" % heading))

    population = added_headings if mode == "amend" else roadmap_headings
    for rh in population:
        if not any(_headings_match(rh, heading) for _line_no, heading in declared):
            findings.append(Finding(
                plan_path, 0, "roadmap-milestone-unplanned",
                "roadmap.md heading %r has no matching Roadmap milestones declaration" % rh))

    return findings, manifest


def _read_text(path):
    """Read *path* as utf-8 text. Returns (text, None) or (None, error-str)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, str(exc)


def main(argv):
    """CLI entry point: parse flags, run the three rule families, print the
    manifest + findings, and return the exit code."""
    args = argv[1:]
    known = ("--plan", "--mode", "--repo-root", "--clarifications",
             "--prd", "--roadmap", "--added-heading")
    plan_path = None
    mode = None
    repo_root = None
    clarifications_path = None
    prd_path = None
    roadmap_path = None
    added_headings = []

    i = 0
    while i < len(args):
        a = args[i]
        if a not in known:
            print(_USAGE, file=sys.stderr)
            return 2
        if i + 1 >= len(args):
            print(_USAGE, file=sys.stderr)
            return 2
        value = args[i + 1]
        if a == "--plan":
            plan_path = value
        elif a == "--mode":
            mode = value
        elif a == "--repo-root":
            repo_root = value
        elif a == "--clarifications":
            clarifications_path = value
        elif a == "--prd":
            prd_path = value
        elif a == "--roadmap":
            roadmap_path = value
        elif a == "--added-heading":
            added_headings.append(value)
        i += 2

    if (plan_path is None or mode is None or repo_root is None
            or clarifications_path is None or prd_path is None or roadmap_path is None):
        print(_USAGE, file=sys.stderr)
        return 2
    if mode not in _MODES:
        print(_USAGE + " (unknown --mode %r)" % mode, file=sys.stderr)
        return 2
    if added_headings and mode != "amend":
        print(_USAGE + " (--added-heading is amend-mode only)", file=sys.stderr)
        return 2

    plan_text, err = _read_text(plan_path)
    if err is not None:
        print("error reading %s: %s" % (plan_path, err), file=sys.stderr)
        return 2

    clar_text, err = _read_text(clarifications_path)
    if err is not None:
        print("error reading %s: %s" % (clarifications_path, err), file=sys.stderr)
        return 2
    try:
        clar_data = json.loads(clar_text)
        clarifications = clar_data["clarifications"]
        if not isinstance(clarifications, list):
            raise ValueError("'clarifications' is not a list")
    except (ValueError, KeyError, TypeError) as exc:
        print("error parsing %s: %s" % (clarifications_path, exc), file=sys.stderr)
        return 2

    prd_text, err = _read_text(prd_path)
    if err is not None:
        print("error reading %s: %s" % (prd_path, err), file=sys.stderr)
        return 2

    roadmap_text, err = _read_text(roadmap_path)
    if err is not None:
        print("error reading %s: %s" % (roadmap_path, err), file=sys.stderr)
        return 2

    findings = []
    manifest = []

    if mode != "greenfield":
        f, m = check_code_evidence(plan_text, repo_root, plan_path)
        findings += f
        manifest += m

    f, m = check_answer_fidelity(plan_text, clarifications, prd_text, roadmap_text, plan_path)
    findings += f
    manifest += m

    f, m = check_roadmap_milestones(plan_text, roadmap_text, mode, added_headings, plan_path)
    findings += f
    manifest += m

    for entry in manifest:
        print(json.dumps(entry))

    for finding in findings:
        print("%s:%d: [%s] %s" % (finding.source, finding.line, finding.rule, finding.message),
              file=sys.stderr)

    if findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))  # pragma: no cover
