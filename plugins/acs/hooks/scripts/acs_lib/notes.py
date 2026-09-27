"""acs_lib.notes — join the markdown a parallel fan-out wrote, deterministically.

When a coordinator runs several instances of one agent at once — survey
slices over disjoint areas of a repo, judge slices over disjoint check
dimensions — each instance writes its own file (`iter-<n>/authoring-<id>.md`,
`iter-<n>/<role>-<id>.md`). Everything downstream reads ONE file: the writer
reads `authoring.md`, `prd_conformance_check.py` parses its sections, the next
writer reads the judge's report. So the slices are joined, and the join is
this function rather than the model merging prose by hand: merging by hand is
where a section is dropped, reordered or silently rewritten.

The rule is by `## ` heading:

  * the preamble (everything before the first `## `) is the first input's;
  * every H2 heading appears ONCE, in the order it was first seen;
  * each input's body under that heading is appended in input order, prefixed
    by a `<!-- slice: <id> -->` marker so a reader can tell whose it is.

A heading is compared by its text with surrounding whitespace removed, so two
slices writing `## Code evidence` land in one section. `###` and deeper
headings are body text and stay where their slice put them.
"""

import os
import re

from ._common import GateError

_H2 = re.compile(r"^## +(.+?)\s*$")
_FENCE = re.compile(r"^(```|~~~)")


def slice_ids(paths):
    """The slice id of each file: its stem minus the prefix every input
    shares, cut back to a hyphen (`impact-reviewer-surface.md` and
    `impact-reviewer-form.md` -> `surface`, `form`; `authoring-web-app.md`
    and `authoring-api.md` -> `web-app`, `api`). Both role names and slice ids
    may contain hyphens, so the split is never positional. A lone input keeps
    what follows its last hyphen."""
    stems = [os.path.splitext(os.path.basename(p))[0] for p in paths]
    if len(stems) == 1:
        stem = stems[0]
        return [stem.rsplit("-", 1)[-1] if "-" in stem else stem]
    prefix = os.path.commonprefix(stems)
    prefix = prefix[:prefix.rfind("-") + 1] if "-" in prefix else ""
    return [stem[len(prefix):] or stem for stem in stems]


def slice_id(path):
    return slice_ids([path])[0]


def split_sections(text):
    """(preamble, [(heading, body), ...]). Headings inside fenced code blocks
    are body text: a slice quoting a markdown example must not open a section."""
    preamble, sections = [], []
    current = None
    fenced = False
    for line in text.splitlines():
        if _FENCE.match(line.strip()):
            fenced = not fenced
        match = None if fenced else _H2.match(line)
        if match:
            current = (match.group(1).strip(), [])
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current[1].append(line)
    return "\n".join(preamble).strip("\n"), [
        (heading, "\n".join(body).strip("\n")) for heading, body in sections]


def merge_texts(named_texts, markers=True):
    """Merge [(slice_id, text), ...] into one markdown document; returns
    (text, section_headings). `markers=False` leaves out the
    `<!-- slice: -->` lines -- for a join that becomes a DELIVERABLE published
    into the repo, where the slicing is workspace bookkeeping, not content."""
    if not named_texts:
        raise GateError("nothing to merge: name at least one input")
    order, bodies = [], {}
    preamble = ""
    for index, (sid, text) in enumerate(named_texts):
        pre, sections = split_sections(text)
        if index == 0:
            preamble = pre
        for heading, body in sections:
            if heading not in bodies:
                order.append(heading)
                bodies[heading] = []
            if body.strip():
                bodies[heading].append("<!-- slice: %s -->\n%s" % (sid, body)
                                       if markers else body)
    out = [preamble] if preamble else []
    for heading in order:
        block = "## %s" % heading
        if bodies[heading]:
            block += "\n\n" + "\n\n".join(bodies[heading])
        out.append(block)
    return "\n\n".join(out).rstrip("\n") + "\n", order


def merge_files(paths, out, markers=True):
    """Read `paths`, merge them, write `out`. Returns {out, sections, inputs}.
    Every input must exist: a missing slice is a failed slice, and a merge that
    quietly left it out would read as a pass (never "pass with a missing slice")."""
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        raise GateError("cannot merge: missing slice file(s): %s" % ", ".join(missing))
    named = []
    for sid, path in zip(slice_ids(paths), paths):
        with open(path, encoding="utf-8") as handle:
            named.append((sid, handle.read()))
    text, order = merge_texts(named, markers=markers)
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, out)
    return {"out": out, "sections": order, "inputs": [p for p in paths]}
