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

  * the preamble (everything before the first `## `) is the first input's,
    followed by any later input's preamble that says more than a `# ` title
    (a slice's opening prose is content; its repeated title is not);
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
from .skills import ROLE_KINDS

_H1 = re.compile(r"^# +\S")
_H2 = re.compile(r"^## +(.+?)\s*$")
_FENCE = re.compile(r"^(`{3,}|~{3,})")

#: The stems a sliced file starts with: `authoring-<id>.md` for survey notes,
#: `<role>-<id>.*` for a role's report. Longest first, so `impact-reviewer-`
#: is stripped before `reviewer-` could be.
_FILE_ROLES = tuple(sorted(set(ROLE_KINDS) | {"authoring"}, key=len, reverse=True))


def slice_ids(paths):
    """The slice id of each file: its stem minus the `<role>-` (or
    `authoring-`) it starts with (`impact-reviewer-surface.md` -> `surface`,
    `authoring-web-app.md` -> `web-app`). Both role names and slice ids may
    contain hyphens, so the split is never positional: the role is matched
    against the known role names, and a file's id is the same however many
    other files it is merged with. A stem that starts with no known role falls
    back to what the inputs do not share (cut back to a hyphen), and a lone
    such stem to what follows its first hyphen."""
    stems = [os.path.splitext(os.path.basename(p))[0] for p in paths]
    out = [_strip_role(stem) for stem in stems]
    unknown = [i for i, sid in enumerate(out) if sid is None]
    if not unknown:
        return out
    rest = [stems[i] for i in unknown]
    if len(rest) == 1:
        stem = rest[0]
        guessed = [stem.split("-", 1)[1] if "-" in stem else stem]
    else:
        prefix = os.path.commonprefix(rest)
        prefix = prefix[:prefix.rfind("-") + 1] if "-" in prefix else ""
        guessed = [stem[len(prefix):] or stem for stem in rest]
    for index, sid in zip(unknown, guessed):
        out[index] = sid
    return out


def _strip_role(stem):
    for role in _FILE_ROLES:
        if stem.startswith(role + "-") and len(stem) > len(role) + 1:
            return stem[len(role) + 1:]
    return None


def slice_id(path):
    return slice_ids([path])[0]


def split_sections(text):
    """(preamble, [(heading, body), ...]). Headings inside fenced code blocks
    are body text: a slice quoting a markdown example must not open a section.
    A fence closes only on the character that opened it, at least as many
    times (CommonMark), so a `~~~` line inside a ``` block is body text too."""
    preamble, sections = [], []
    current = None
    fence = None
    for line in text.splitlines():
        opened = _FENCE.match(line.strip())
        if opened:
            marker = opened.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) \
                    and not line.strip()[len(marker):].strip():
                fence = None
        match = None if fence is not None else _H2.match(line)
        if match:
            current = (match.group(1).strip(), [])
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current[1].append(line)
    return "\n".join(preamble).strip("\n"), [
        (heading, "\n".join(body).strip("\n")) for heading, body in sections]


def _without_title(preamble):
    """A later slice's preamble minus its `# ` title lines: the merged file
    already has the first input's title, and a second one is not content."""
    return "\n".join(line for line in preamble.splitlines()
                     if not _H1.match(line)).strip("\n")


def merge_texts(named_texts, markers=True):
    """Merge [(slice_id, text), ...] into one markdown document; returns
    (text, section_headings). `markers=False` leaves out the
    `<!-- slice: -->` lines -- for a join that becomes a DELIVERABLE published
    into the repo, where the slicing is workspace bookkeeping, not content."""
    if not named_texts:
        raise GateError("nothing to merge: name at least one input")
    order, bodies = [], {}
    preambles = []
    for index, (sid, text) in enumerate(named_texts):
        pre, sections = split_sections(text)
        if index:
            pre = _without_title(pre)
            if pre.strip():
                preambles.append("<!-- slice: %s -->\n%s" % (sid, pre) if markers else pre)
        elif pre:
            preambles.append(pre)
        for heading, body in sections:
            if heading not in bodies:
                order.append(heading)
                bodies[heading] = []
            if body.strip():
                bodies[heading].append("<!-- slice: %s -->\n%s" % (sid, body)
                                       if markers else body)
    out = list(preambles)
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
