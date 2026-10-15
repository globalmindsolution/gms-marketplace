"""acs_lib.prd_template — the templates a PRD document is written from (ADR-0147).

Two built-in templates ship in the plugin's `templates/`: `prd-default` (the
hub, `<prd_dir>/prd.md`) and `prd-feature-default` (one feature's own PRD,
`<prd_dir>/features/<slug>/prd.md`). A repo replaces either with its own
`.acs/templates/<name>.md`. The template's `## ` headings, in order, are the
document's required sections: /acs:create-prd passes them as its
`required_sections` and `feature_required_sections` constraints, so the
authors, the reviewer and the structure floor all read one list. Headings
inside an HTML comment or a fenced block are guidance, not sections.

A feature template must keep `Goals served` and `Requirements`: tickets link
a feature's `R<n>` ids (ADR-0144) and its implemented status is derived from
them (ADR-0146), so a template without them is refused.
"""

import os
import re

from .conventions import PRD_TEMPLATES

#: The sections a feature PRD template may not drop (prd_link / prd_delivery read them).
FEATURE_CORE_SECTIONS = ("Goals served", "Requirements")

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
_H2 = re.compile(r"^## (.+?)\s*$", re.M)


def resolve(kind, repo_root, plugin_root):
    """{kind, name, path, source} — the repo's `.acs/templates/<name>.md` when it
    has one (`source: repo`), else the built-in (`source: builtin`)."""
    name = PRD_TEMPLATES[kind]
    override = os.path.join(repo_root or "", ".acs", "templates", "%s.md" % name)
    if repo_root and os.path.isfile(override):
        return {"kind": kind, "name": name, "path": override, "source": "repo"}
    return {"kind": kind, "name": name, "source": "builtin",
            "path": os.path.join(plugin_root, "templates", "%s.md" % name)}


def sections(text):
    """The `## ` headings of a template, in order, outside comments and fences."""
    stripped = _FENCE.sub("", _COMMENT.sub("", text))
    return [m.group(1).strip() for m in _H2.finditer(stripped)]


def problems(kind, found):
    """Why a template's sections cannot be used ([] when they can)."""
    out = []
    if not found:
        out.append("it declares no `## ` section")
    if len(set(s.lower() for s in found)) != len(found):
        out.append("a section is declared twice")
    if kind == "feature":
        lower = [s.lower() for s in found]
        out += ["it drops `## %s`, which tickets and the implemented status rely on "
                "(ADR-0144, ADR-0146)" % core for core in FEATURE_CORE_SECTIONS
                if core.lower() not in lower]
    return out


def load(kind, repo_root, plugin_root):
    """resolve() plus {sections, joined, problems}; `joined` is the `A; B; C`
    form the structure checks take."""
    found = resolve(kind, repo_root, plugin_root)
    try:
        with open(found["path"], encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return dict(found, sections=[], joined="", problems=["unreadable: %s" % exc])
    names = sections(text)
    return dict(found, sections=names, joined="; ".join(names),
                problems=problems(kind, names))


def builtin_sections(kind):
    """The built-in template's sections (no repo override): the default a
    script falls back to when it is given none."""
    plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    return load(kind, None, plugin_root)["sections"]
