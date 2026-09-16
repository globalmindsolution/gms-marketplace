"""markdown_headings.py — the one markdown heading scanner (MAR-522).

Three copies of this six-line loop existed: `citation_check._headings`,
`structure_lint._headings`, and `acs_lib.lanes._plan_headings`, whose docstring
even recorded the duplication and justified it ("kept import-free so this
predicate stays pure"). That justification is what shapes this module: it
imports `re` and nothing else, so the dependency-light CLIs and the pure
plan-approval predicate can all share it without any of them taking on the
kernel as a dependency.

A heading is a line of one to six `#` followed by a space and the text — the
regex all three copies used, unchanged, so what counts as a heading is
identical to before.
"""

import re

#: A markdown ATX heading: 1-6 '#', a space, then the text.
HEADING_RE = re.compile(r"^(#{1,6}) (.*)$")


def headings(text):
    """(line_no, level, text) for every heading line, in document order.

    `line_no` is 1-based. `text` is stripped. Accepts a string or an already
    split sequence of lines — the call sites this replaces had both shapes, and
    splitting a string that was already split is the kind of detail that grows
    a fourth copy.
    """
    lines = text.split("\n") if isinstance(text, str) else text
    found = []
    for idx, raw in enumerate(lines, start=1):
        match = HEADING_RE.match(raw)
        if match:
            found.append((idx, len(match.group(1)), match.group(2).strip()))
    return found
