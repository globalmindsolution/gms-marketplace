"""MAR-184 — /acs:init renamed to /acs:initialize: skill directory, registry
mirrors, and repo-wide live-reference sweep.

Covers AC-1 (directory + frontmatter), AC-3 (+part of AC-2 — the skill-name
mirrors: the XSD enum, the two JSON-Schema enums, validate_xml.SKILLS, and
acs_lib.UNHOOKED_SKILLS), AC-5 (the eval routing case), AC-7 (the two
historical carve-outs plus the m2-0 spike doc, ledger C-7, are preserved
verbatim), and AC-8 (a full-repo grep for a live `/acs:init` or bare `/init`
skill-name token returns zero hits outside that same historical allowlist).

T1 is the FIRST of five executor tasks and authors this module as the
integrating oracle for T2-T5: `test_no_live_acs_init_reference_outside_history`
and `test_eval_trigger_case_expects_initialize` are expected to stay RED until
the last Wave-B task lands (T2-T5 still contain live `/acs:init` references
by design at the end of T1) -- that is the intended TDD signal, not a defect.

Run:
  python3 -m unittest tests.acs.test_initialize_skill_reference_sweep -v
"""

import json
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
SCHEMAS_DIR = os.path.join(PLUGIN, "schemas")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")

XSD = os.path.join(SCHEMAS_DIR, "acs-messages.xsd")
SKILL_STATE_SCHEMA = os.path.join(SCHEMAS_DIR, "skill-state.schema.json")
CLARIFICATIONS_SCHEMA = os.path.join(SCHEMAS_DIR, "clarifications.schema.json")

sys.path.insert(0, HOOKS_SCRIPTS)
import validate_xml  # noqa: E402
import acs_lib  # noqa: E402

XS_NS = "{http://www.w3.org/2001/XMLSchema}"

NEW_SKILL_DIR = os.path.join(SKILLS_DIR, "initialize")
NEW_SKILL_MD = os.path.join(NEW_SKILL_DIR, "SKILL.md")
OLD_SKILL_DIR = os.path.join(SKILLS_DIR, "init")

THIS_FILE = os.path.realpath(__file__)

# C-2's two frozen historical records, plus the m2-0 validation spike (ledger
# C-7: a dated runbook/result-log of commands literally typed at the time,
# structurally the same class of artifact as an ADR) -- never rewritten.
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
CHANGELOG = os.path.join(PLUGIN, "CHANGELOG.md")
SPIKE_DOC = os.path.join(REPO_ROOT, "docs", "product", "spikes", "m2-0-validation-spike.md")
ADR_0047 = os.path.join(ADR_DIR, "0047-init-auto-wires-e2e-required-check-report-once.md")

HISTORICAL_DIRS = (os.path.realpath(ADR_DIR),)
HISTORICAL_FILES = (os.path.realpath(CHANGELOG), os.path.realpath(SPIKE_DOC))

# A real .git directory is skipped by name; a linked worktree's top-level
# ".git" is a FILE (a "gitdir: <path>" pointer) whose target path can itself
# contain "/init..." as an unrelated directory-name substring, so it is
# skipped explicitly too, not just as a directory.
SKIP_DIR_NAMES = {".git", "__pycache__"}
SKIP_FILE_NAMES = {".git"}

# Built from parts so this module's own source text can never self-match the
# sweep pattern it defines. The leading "/" is what discriminates the skill
# token from noise like `git init` or `__init__` (both slash-free).
_ACS_INIT_NEEDLE = "/acs:" + "init"
_BARE_INIT_NEEDLE = "/" + "init"
LIVE_REFERENCE_RE = re.compile(
    r"(?:%s|%s)(?![a-z])" % (re.escape(_ACS_INIT_NEEDLE), re.escape(_BARE_INIT_NEEDLE))
)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def is_historical(path):
    """True for a path under the C-2/C-7 carve-outs (never edited by the rename)."""
    real = os.path.realpath(path)
    if real in HISTORICAL_FILES:
        return True
    return any(real == d or real.startswith(d + os.sep) for d in HISTORICAL_DIRS)


def iter_repo_files():
    """Every non-skipped file under the repo root, depth-first."""
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            if name in SKIP_FILE_NAMES:
                continue
            yield os.path.join(dirpath, name)


def xsd_skill_enum_values():
    """The skillName simpleType's <xs:enumeration> values, parsed live from the XSD."""
    root = ET.parse(XSD).getroot()
    simple_type = root.find("%ssimpleType[@name='skillName']" % XS_NS)
    return [e.get("value") for e in simple_type.iter("%senumeration" % XS_NS)]


def json_schema_skill_enum_values(path, pointer):
    """Walk *pointer* (a list of keys) into the JSON document at *path* to its enum list."""
    node = json.loads(read(path))
    for key in pointer:
        node = node[key]
    return node


SKILL_STATE_POINTER = ["properties", "skill", "enum"]
CLARIFICATIONS_POINTER = [
    "properties", "clarifications", "items", "properties", "skill", "enum",
]


class SkillDirectoryRenamedTest(unittest.TestCase):
    """AC-1: the skill directory itself moved -- new present, old gone."""

    def test_skill_directory_renamed(self):
        self.assertTrue(os.path.isfile(NEW_SKILL_MD), "%s must exist" % NEW_SKILL_MD)
        self.assertFalse(os.path.isdir(OLD_SKILL_DIR), "%s must no longer exist" % OLD_SKILL_DIR)


class FrontmatterNameTest(unittest.TestCase):
    """AC-1: the renamed skill's frontmatter name: field matches its directory."""

    def test_frontmatter_name_is_initialize(self):
        body = read(NEW_SKILL_MD)
        m = re.search(r"(?m)^name:\s*(\S+)\s*$", body)
        self.assertIsNotNone(m, "no frontmatter name: field found in %s" % NEW_SKILL_MD)
        self.assertEqual(m.group(1), "initialize")


class SkillNameMirrorsTest(unittest.TestCase):
    """AC-3 (+AC-2): every skill-name registry mirror says initialize, not init."""

    def test_every_skill_name_mirror_says_initialize(self):
        sources = {
            "acs-messages.xsd skillName": xsd_skill_enum_values(),
            "skill-state.schema.json skill.enum": json_schema_skill_enum_values(
                SKILL_STATE_SCHEMA, SKILL_STATE_POINTER),
            "clarifications.schema.json skill.enum": json_schema_skill_enum_values(
                CLARIFICATIONS_SCHEMA, CLARIFICATIONS_POINTER),
            "validate_xml.SKILLS": list(validate_xml.SKILLS),
            "acs_lib.UNHOOKED_SKILLS": list(acs_lib.UNHOOKED_SKILLS),
        }
        for label, values in sources.items():
            with self.subTest(source=label):
                self.assertIn("initialize", values, "%s must list 'initialize'" % label)
                self.assertNotIn("init", values, "%s must not list stale 'init'" % label)


class HistoryPreservedTest(unittest.TestCase):
    """AC-7: the two C-2 carve-outs and the C-7 spike doc are untouched."""

    def test_history_preserved_verbatim(self):
        self.assertTrue(
            os.path.isfile(ADR_0047),
            "%s must still exist under its exact historical filename" % ADR_0047)
        self.assertIn("/acs:init", read(ADR_0047))
        self.assertIn("/acs:init", read(CHANGELOG))
        self.assertIn("/acs:init", read(SPIKE_DOC))


class NoLiveReferenceOutsideHistoryTest(unittest.TestCase):
    """AC-8: a full-repo sweep for the live skill token returns zero hits
    outside the historical allowlist."""

    def test_no_live_acs_init_reference_outside_history(self):
        hits = []
        for path in iter_repo_files():
            if os.path.realpath(path) == THIS_FILE or is_historical(path):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    lines = fh.readlines()
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(lines, start=1):
                if LIVE_REFERENCE_RE.search(line):
                    hits.append("%s:%d: %s" % (
                        os.path.relpath(path, REPO_ROOT), lineno, line.strip()))
        self.assertEqual(
            hits, [],
            "live /acs:init or /init reference(s) found outside the historical "
            "allowlist (docs/adr/**, plugins/acs/CHANGELOG.md, "
            "docs/product/spikes/m2-0-validation-spike.md):\n" + "\n".join(hits))


class EvalTriggerCaseTest(unittest.TestCase):
    """AC-5: s04_skill_triggers.py's CASES list names no "init" expected skill."""

    def test_eval_trigger_case_expects_initialize(self):
        s04_path = os.path.join(REPO_ROOT, "evals", "acs", "scenarios", "s04_skill_triggers.py")
        body = read(s04_path)
        m = re.search(r"CASES\s*=\s*\[(.*?)\n\]\n", body, re.S)
        self.assertIsNotNone(m, "CASES list not found in %s" % s04_path)
        expected_skills = re.findall(r'"([a-z0-9-]+)"\),', m.group(1))
        self.assertNotIn(
            "init", expected_skills,
            "CASES must not expect the stale skill literal \"init\" -- expected "
            "\"initialize\" (got expected-skill values: %s)" % expected_skills)
