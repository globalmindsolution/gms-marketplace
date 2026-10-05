"""A skill's contract text with its `references/` read where SKILL.md points.

Progressive disclosure moves the procedure a run reads only in some arms, or
only at one phase, out of a SKILL.md into `skills/<name>/references/<file>.md`
behind a one-line "read it when ..." pointer. A pin that asserts what a skill
SAYS must keep passing when the sentence moves, and one that genuinely
vanishes must still fail -- so such pins read this text, never which file
says it.

Each of the skill's own reference files is inlined right after the first line
of SKILL.md that points at it, so a moved section still sits where its pointer
does: an assertion about order ("the integration pass runs before the
reviewer") or a slice between two headings measures what it always did. A
reference SKILL.md never points at is appended at the end. Pins about the
SKILL.md file itself -- its front matter, its headings, its length -- keep
reading SKILL.md alone.
"""

import os
import re

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")

#: `references/<file>.md`, optionally behind `skills/<skill>/`; a pointer into
#: another skill's directory is not this skill's own reference.
_POINTER = re.compile(r"(?:skills/([a-z0-9-]+)/)?references/([A-Za-z0-9_.-]+\.md)")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def skill_contract(name):
    """SKILL.md of `name` with its own references inlined at their pointers."""
    base = os.path.join(SKILLS, name)
    refs_dir = os.path.join(base, "references")
    own = (sorted(f for f in os.listdir(refs_dir) if f.endswith(".md"))
           if os.path.isdir(refs_dir) else [])
    inlined = set()
    out = []
    for line in _read(os.path.join(base, "SKILL.md")).splitlines(keepends=True):
        out.append(line)
        for skill, filename in _POINTER.findall(line):
            if (skill and skill != name) or filename not in own or filename in inlined:
                continue
            inlined.add(filename)
            text = _read(os.path.join(refs_dir, filename))
            out.append("\n" + text + ("" if text.endswith("\n") else "\n") + "\n")
    for filename in own:
        if filename not in inlined:
            out.append("\n" + _read(os.path.join(refs_dir, filename)))
    return "".join(out)
