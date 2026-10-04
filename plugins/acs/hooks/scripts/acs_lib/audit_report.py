"""acs_lib.audit_report — an audit skill's report, checked against its template (ADR-0123).

An Audit-phase skill writes one report, `steps/<skill>/iter-1/report.md`, from a
template (`templates/<skill>-report.md`, or the repo's `.acs/templates/` copy of
the same name). The template IS the contract, so a repo that overrides it changes
the contract with it:

  - every `## ` section the template has appears in the report, in the template's
    order (a report may add sections of its own);
  - a section the template marks `<!-- acs:count <key> -->` is counted: each entry
    is one `### ` heading under it, and that number is `states.audit.<key>`.

The counts are derived, never asserted: `run_post` writes these over whatever the
result document claimed, and records the disagreement. Headings inside HTML
comments and fenced code blocks are not headings.
"""

import os
import re

from .conventions import AUDIT_TEMPLATES
from .settings import resolve_template

_HEADING = re.compile(r"^(#{2,3}) (.+?)\s*$")
_COUNT = re.compile(r"<!--\s*acs:count\s+([a-z][a-z0-9_-]*)\s*-->")
_FENCE = re.compile(r"^\s*(```|~~~)")


def report_path(rdir, skill):
    return os.path.join(rdir, "steps", skill, "iter-1", "report.md")


def _scan(text):
    """[(level, title, count_key_or_None)] for the `##`/`###` headings outside
    comments and fences; a count marker belongs to the `##` above it."""
    out, in_comment, in_fence = [], False, False
    for line in text.splitlines():
        if not in_comment and _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        marker = _COUNT.search(line)
        if marker and out and out[-1][0] == 2 and out[-1][2] is None:
            out[-1] = (2, out[-1][1], marker.group(1))
        if in_comment:
            in_comment = "-->" not in line
            continue
        if "<!--" in line and "-->" not in line.split("<!--", 1)[1]:
            in_comment = True
            continue
        match = _HEADING.match(line)
        if match:
            out.append((len(match.group(1)), match.group(2), None))
    return out


def contract(template_text):
    """[(section, count_key or None)] in the template's order."""
    return [(title, key) for level, title, key in _scan(template_text) if level == 2]


def entries(report_text):
    """{section: number of `###` entries under it}, for every `##` section."""
    counts, current = {}, None
    for level, title, _key in _scan(report_text):
        if level == 2:
            current = title
            counts.setdefault(current, 0)
        elif current is not None:
            counts[current] += 1
    return counts


def check(report_text, template_text):
    """(problems, counts): the contract's breaches, and {count_key: n}."""
    sections = contract(template_text)
    found = entries(report_text)
    order = [title for level, title, _ in _scan(report_text) if level == 2]
    problems = ["section `## %s` is missing" % title
                for title, _ in sections if title not in found]
    present = [title for title, _ in sections if title in found]
    positions = [order.index(title) for title in present]
    if positions != sorted(positions):
        problems.append("sections are out of the template's order: expected %s"
                        % ", ".join(present))
    counts = {key: found.get(title, 0) for title, key in sections if key}
    return problems, counts


def template_path(skill, repo_root, plugin_root):
    """The repo's `.acs/templates/<name>.md` when it has one, else the built-in."""
    name = AUDIT_TEMPLATES[skill]
    override = os.path.join(repo_root or "", ".acs", "templates", "%s.md" % name)
    if repo_root and os.path.isfile(override):
        return override
    return resolve_template(name, repo_root, plugin_root)


def derive(rdir, skill, repo_root, plugin_root):
    """(problems, counts, report) for an audit skill's report; ([], {}, None) for
    any other skill. A missing report or template is a problem, not a crash."""
    if skill not in AUDIT_TEMPLATES:
        return [], {}, None
    path = report_path(rdir, skill)
    template = template_path(skill, repo_root, plugin_root)
    if not template:
        return ["template %r not found" % AUDIT_TEMPLATES[skill]], {}, path
    if not os.path.isfile(path):
        return ["no report at %s" % path], {}, path
    with open(path, encoding="utf-8") as fh:
        report_text = fh.read()
    with open(template, encoding="utf-8") as fh:
        template_text = fh.read()
    problems, counts = check(report_text, template_text)
    return problems, counts, path
