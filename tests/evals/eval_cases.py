"""Read the plugin's `claude plugin eval` suite as data, for the free checks.

The case files under plugins/acs/evals/ ARE the suite -- nothing renders them
-- so every check that asserts something about the probe set reads them here,
and so does scripts/eval_gate.py. Neither the CLI nor these checks run in CI
(ADR-0022, ADR-0108): the checks beside this file (tests/evals/check_*.py) run
from the `acs-eval-checks` pre-commit hook and as the release gate's first
step, and they are the only thing that catches a malformed case before someone
pays to discover it.

Deliberately STRICT. Frontmatter is parsed by a small stdlib reader that
understands exactly the YAML shapes the suite uses -- `key: value`,
`key: [a, b]`, `key: { a: b }`, `key: >-` folded blocks, single-quoted strings
-- and raises on any line it does not understand. A permissive reader would
turn a typo into a silently missing key, which is how a grader ends up checking
nothing.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
EVALS = os.path.join(PLUGIN, "evals")

#: Keys the reference documents for prompt.md frontmatter. "An unknown key is
#: an error" -- at run time, which is to say after money is spent.
PROMPT_KEYS = frozenset({
    "schema_version", "name", "description", "tags", "plugins", "runs",
    "expected_outcome", "model", "max_turns", "timeout_seconds",
    "allowed_tools", "append_system_prompt", "env",
})

#: Every grader takes these, plus the options for its type.
GRADER_COMMON_KEYS = frozenset({"type", "weight", "arm"})
GRADER_TYPE_KEYS = {
    "regex": frozenset({"pattern", "flags", "match", "target"}),
    "tool_used": frozenset({"tool", "input_match", "min", "max"}),
    "tool_order": frozenset({"before", "after"}),
    "file_exists": frozenset({"path", "exists"}),
    "llm": frozenset({"criteria", "focus"}),
    "baseline": frozenset({"baseline_file", "criteria"}),
}
ARMS = frozenset({"with-only", "both"})

#: The one kind tag every routing case carries, alongside `routing`.
ROUTING_KINDS = ("description", "explicit", "negative", "control")

_SKILL_IN_INPUT_MATCH = re.compile(r'\(\?:\[\\w-\]\+:\)\?([a-z0-9][a-z0-9-]*)"$')


class CaseFormatError(ValueError):
    """A case file the strict reader does not understand."""


def _scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _flow(text, open_, close):
    inner = text.strip()[1:-1].strip()
    if not inner:
        return [] if open_ == "[" else {}
    parts = [p.strip() for p in inner.split(",")]
    if open_ == "[":
        return [_scalar(p) for p in parts]
    out = {}
    for part in parts:
        if ":" not in part:
            raise CaseFormatError("flow mapping entry without a colon: %r" % part)
        k, v = part.split(":", 1)
        out[k.strip()] = _scalar(v)
    return out


def parse_yaml_subset(text, where="<frontmatter>"):
    """Parse the flat YAML subset the suite uses. Raises on anything else."""
    data = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            raise CaseFormatError("%s: unexpected indented line %d: %r" % (where, i + 1, line))
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*):(?:\s(.*))?$", line)
        if not m:
            raise CaseFormatError("%s: cannot read line %d: %r" % (where, i + 1, line))
        key, rest = m.group(1), (m.group(2) or "").strip()
        if key in data:
            raise CaseFormatError("%s: duplicate key %r" % (where, key))
        if rest in (">-", ">", "|", "|-", ""):
            block = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            if rest == "":
                data[key] = _nested(block, where, key)
            elif rest.startswith(">"):
                data[key] = " ".join(b for b in block if b)
            else:
                data[key] = "\n".join(block).strip("\n")
            continue
        if rest.startswith("["):
            data[key] = _flow(rest, "[", "]")
        elif rest.startswith("{"):
            data[key] = _flow(rest, "{", "}")
        else:
            data[key] = _scalar(rest)
        i += 1
    return data


def _nested(block, where, key):
    """A one-level block mapping, as case.yaml's `context:` and `execution:`."""
    out = {}
    for line in block:
        if not line:
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not m:
            raise CaseFormatError("%s: cannot read %s entry %r" % (where, key, line))
        v = m.group(2).strip()
        if v.startswith("["):
            out[m.group(1)] = _flow(v, "[", "]")
        elif v.startswith("{"):
            out[m.group(1)] = _flow(v, "{", "}")
        else:
            out[m.group(1)] = _scalar(v)
    return out


def split_frontmatter(path):
    """(frontmatter dict, body) of a markdown file. The opening `---` must be
    the file's first line: the CLI reads a file that starts with anything else
    as having no frontmatter at all."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise CaseFormatError("%s: frontmatter is never closed" % path)
    return parse_yaml_subset(text[4:end], path), text[end + 5:]


class Grader(object):
    def __init__(self, path):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.fm, self.body = split_frontmatter(path)

    @property
    def type(self):
        return self.fm.get("type")

    def skill(self):
        """The bare skill a `tool_used: Skill` grader's input_match names."""
        if self.type != "tool_used" or self.fm.get("tool") != "Skill":
            return None
        pattern = self.fm.get("input_match")
        if not pattern:
            return None
        m = _SKILL_IN_INPUT_MATCH.search(pattern)
        if not m:
            raise CaseFormatError(
                "%s: input_match is not the canonical routing form: %r"
                % (self.path, pattern))
        return m.group(1)


class Case(object):
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.group = os.path.basename(os.path.dirname(path))
        prompt = os.path.join(path, "prompt.md")
        self.fm, self.prompt = split_frontmatter(prompt) if os.path.isfile(prompt) else ({}, "")
        self.prompt = self.prompt.strip()
        yaml = os.path.join(path, "case.yaml")
        self.case_yaml = None
        if os.path.isfile(yaml):
            with open(yaml, encoding="utf-8") as fh:
                self.case_yaml = parse_yaml_subset(fh.read(), yaml)
        gdir = os.path.join(path, "graders")
        self.graders = [Grader(os.path.join(gdir, n))
                        for n in sorted(os.listdir(gdir)) if n.endswith(".md")] \
            if os.path.isdir(gdir) else []

    @property
    def tags(self):
        tags = list(self.fm.get("tags") or [])
        if self.case_yaml:
            tags += list(self.case_yaml.get("tags") or [])
        return tags

    @property
    def kind(self):
        kinds = [t for t in self.tags if t in ROUTING_KINDS]
        return kinds[0] if len(kinds) == 1 else None

    @property
    def explicit(self):
        return self.prompt.startswith("/")

    def routing_grader(self):
        found = [g for g in self.graders if g.skill() is not None]
        return found[0] if len(found) == 1 else None

    @property
    def skill(self):
        g = self.routing_grader()
        return g.skill() if g else None

    @property
    def must_route(self):
        g = self.routing_grader()
        return bool(g and (g.fm.get("min", 1) or 0) >= 1)


def all_cases():
    """Every case directory under the eval dir: one holding prompt.md or
    case.yaml. `results/` is run output, never a case."""
    out = []
    for dirpath, dirnames, filenames in os.walk(EVALS):
        dirnames[:] = sorted(d for d in dirnames if d not in ("results", "graders"))
        if "prompt.md" in filenames or "case.yaml" in filenames:
            out.append(Case(dirpath))
            dirnames[:] = []
    return out


def routing_cases():
    return [c for c in all_cases() if "routing" in c.tags]


def probe_cases():
    """Routing cases that probe a SKILL -- every kind but the off-domain
    control, which asserts that no skill fires at all."""
    return [c for c in routing_cases() if c.kind != "control"]


def shipped_skills():
    skills = os.path.join(PLUGIN, "skills")
    return sorted(n for n in os.listdir(skills)
                  if os.path.isfile(os.path.join(skills, n, "SKILL.md")))


def probe_dicts():
    """The routing probes in the shape the older coverage tests consume:
    {"skill": "acs:<name>", "must_route", "prompt", "kind"}.

    Those tests used to read evals/dataset/routing.json. The dataset is gone --
    the case files are the source of truth -- so this adapts the cases to that
    shape, and every assertion built on it keeps its exact logic while its data
    source changes underneath."""
    return [{"skill": "acs:" + c.skill, "must_route": c.must_route,
             "prompt": c.prompt, "kind": c.kind, "case": c.name}
            for c in probe_cases()]
