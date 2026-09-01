"""MAR-184 — /acs:init renamed to /acs:initialize: skill directory, registry
mirrors, and repo-wide live-reference sweep.

Covers AC-1 (directory + frontmatter), AC-3 (+part of AC-2 — the skill-name
mirrors: the XSD enum, the two JSON-Schema enums, validate_xml.SKILLS, and
acs_lib.UNHOOKED_SKILLS), AC-5 (the eval routing case), AC-7 (the two
historical carve-outs plus the m2-0 spike doc, ledger C-7, are preserved
verbatim), and AC-8 (a full-repo grep for a live `/acs:init` or bare `/init`
skill-name token returns zero hits outside that same historical allowlist).

Renamed under MAR-1 (the skill formerly invoked as acs:initialize is now
acs:setup): the task-local classes SkillDirectoryRenamedTest,
FrontmatterNameTest, and SkillNameMirrorsTest now pin the initialize->setup
rename instead of the init->initialize one. HistoryPreservedTest and
EvalTriggerCaseTest below keep guarding MAR-184's original /acs:init
guarantee unchanged.

NoLiveReferenceOutsideHistoryTest now carries TWO methods: the original
MAR-184 /acs:init sweep (unchanged) plus a new MAR-1 /acs:initialize sweep
added in this task, over the same allowlist plus a line-scoped carve-out for
the 2026-08-13 docs/requirements/README.md ledger row (the MAR-184 rename
record). PositiveReplacementTest, TestFilesRenamedTest, and
SkillBodyUnchangedExceptRenameTest are new whole-tree MAR-1 assertions added
in this task. The CHANGELOG-specific assertions (ChangelogEntryTest,
ChangelogAddOnlyTest) are a later task's job, added once the CHANGELOG entry
itself exists.

Run:
  python3 -m unittest tests.acs.test_setup_skill_reference_sweep -v
"""

import glob
import json
import os
import re
import subprocess
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

SETUP_SKILL_DIR = os.path.join(SKILLS_DIR, "setup")
SETUP_SKILL_MD = os.path.join(SETUP_SKILL_DIR, "SKILL.md")
INITIALIZE_SKILL_DIR = os.path.join(SKILLS_DIR, "initialize")

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
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", ".claude"}
SKIP_FILE_NAMES = {".git"}

# Built from parts so this module's own source text can never self-match the
# sweep pattern it defines. The leading "/" is what discriminates the skill
# token from noise like `git init` or `__init__` (both slash-free).
_ACS_INIT_NEEDLE = "/acs:" + "init"
_BARE_INIT_NEEDLE = "/" + "init"
LIVE_REFERENCE_RE = re.compile(
    r"(?:%s|%s)(?![a-z])" % (re.escape(_ACS_INIT_NEEDLE), re.escape(_BARE_INIT_NEEDLE))
)

# MAR-1's own needle: the retired /acs:initialize (and bare /initialize)
# skill-name token, built from parts for the same self-match-immunity reason
# as the needle above -- this module's own MAR-1 prose never writes a live
# "/acs:initialize" or "/initialize" substring.
_ACS_INITIALIZE_NEEDLE = "/acs:" + "initialize"
_BARE_INITIALIZE_NEEDLE = "/" + "initialize"
LIVE_INITIALIZE_RE = re.compile(
    r"(?:%s|%s)(?![a-z])" % (re.escape(_ACS_INITIALIZE_NEEDLE), re.escape(_BARE_INITIALIZE_NEEDLE))
)

# Line-scoped carve-out (deliberately narrower than a whole-file allowlist):
# only the single dated ledger row recording the MAR-184 init->initialize
# rename event is historical prose; every other line of this living-ledger
# index doc must track the current skill name.
REQUIREMENTS_README = os.path.realpath(
    os.path.join(REPO_ROOT, "docs", "requirements", "README.md"))
MAR_184_LEDGER_ROW_RE = re.compile(r"^\| 2026-08-13 \|")


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
    """AC-1: the skill directory itself moved -- setup present, initialize gone."""

    def test_skill_directory_renamed(self):
        self.assertTrue(os.path.isfile(SETUP_SKILL_MD), "%s must exist" % SETUP_SKILL_MD)
        self.assertFalse(
            os.path.isdir(INITIALIZE_SKILL_DIR),
            "%s must no longer exist" % INITIALIZE_SKILL_DIR)


class FrontmatterNameTest(unittest.TestCase):
    """AC-1: the renamed skill's frontmatter name: field matches its directory."""

    def test_frontmatter_name_is_setup(self):
        body = read(SETUP_SKILL_MD)
        m = re.search(r"(?m)^name:\s*(\S+)\s*$", body)
        self.assertIsNotNone(m, "no frontmatter name: field found in %s" % SETUP_SKILL_MD)
        self.assertEqual(m.group(1), "setup")


class SkillNameMirrorsTest(unittest.TestCase):
    """AC-3/AC-4: every skill-name registry mirror says setup, not initialize."""

    def test_every_skill_name_mirror_says_setup(self):
        sources = {
            "acs-messages.xsd skillName": xsd_skill_enum_values(),
            "skill-state.schema.json skill.enum": json_schema_skill_enum_values(
                SKILL_STATE_SCHEMA, SKILL_STATE_POINTER),
            "clarifications.schema.json skill.enum": json_schema_skill_enum_values(
                CLARIFICATIONS_SCHEMA, CLARIFICATIONS_POINTER),
            "validate_xml.SKILLS": list(validate_xml.SKILLS),
            "acs_lib.UNHOOKED_SKILLS": list(acs_lib.UNHOOKED_SKILLS),
            "acs_lib.ATTRIBUTION_SKILL_MAP values": list(acs_lib.ATTRIBUTION_SKILL_MAP.values()),
        }
        for label, values in sources.items():
            with self.subTest(source=label):
                self.assertIn("setup", values, "%s must list 'setup'" % label)
                self.assertNotIn("initialize", values, "%s must not list stale 'initialize'" % label)


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

    def test_no_live_acs_initialize_reference_outside_history(self):
        """AC-2: the MAR-1 sweep -- same allowlist, plus the line-scoped
        MAR-184 ledger-row carve-out (not a whole-file allowlist: every
        other line of docs/requirements/README.md must track "setup")."""
        hits = []
        for path in iter_repo_files():
            real = os.path.realpath(path)
            if real == THIS_FILE or is_historical(path):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    lines = fh.readlines()
            except (UnicodeDecodeError, OSError):
                continue
            is_ledger = real == REQUIREMENTS_README
            for lineno, line in enumerate(lines, start=1):
                if is_ledger and MAR_184_LEDGER_ROW_RE.match(line):
                    continue
                if LIVE_INITIALIZE_RE.search(line):
                    hits.append("%s:%d: %s" % (
                        os.path.relpath(path, REPO_ROOT), lineno, line.strip()))
        self.assertEqual(
            hits, [],
            "live /acs:initialize or /initialize reference(s) found outside "
            "the historical allowlist (docs/adr/**, plugins/acs/CHANGELOG.md, "
            "docs/product/spikes/m2-0-validation-spike.md, and the "
            "2026-08-13 docs/requirements/README.md ledger row):\n" + "\n".join(hits))


# Every T2/T3 file that gained a live /acs:setup or bare `setup` skill-name
# literal -- absence of the old token is not enough on its own (a file that
# named neither the old nor the new skill would pass a negative-only check
# vacuously), so this positively asserts the replacement landed.
T2_T3_SETUP_PATHS = (
    "plugins/acs/skills/handoff/SKILL.md",
    "plugins/acs/skills/install-hooks/SKILL.md",
    "plugins/acs/skills/merge-pr/SKILL.md",
    "plugins/acs/skills/ship/SKILL.md",
    "plugins/acs/skills/standardize-project/SKILL.md",
    "plugins/acs/skills/update/SKILL.md",
    "plugins/acs/agents/standardize-project-planner.md",
    "plugins/acs/agents/standardize-project-executor.md",
    "plugins/acs/agents/standardize-project-verifier.md",
    "plugins/acs/README.md",
    "plugins/acs/docs/INTERNALS.md",
    "plugins/acs/docs/AUTHORING.md",
    "plugins/acs/templates/CLAUDE.acs.md",
    "plugins/acs/templates/ci/acs-conventions.yml",
    "plugins/acs/templates/ci/acs-tests.yml",
    "plugins/acs/templates/ci/acs-e2e.yml",
    "plugins/acs/templates/ci/check-conventions.py",
    "plugins/acs/templates/ci/commit-msg",
    "plugins/acs/templates/ci/install-hooks.sh",
    "plugins/acs/templates/ci/pre-push",
    "plugins/acs/templates/ci/run-tests.py",
    "plugins/acs/templates/ci/run-e2e.py",
    ".acs/ci/check-conventions.py",
    ".acs/ci/commit-msg",
    ".acs/ci/install-hooks.sh",
    ".acs/ci/pre-push",
    ".acs/ci/run-tests.py",
    ".github/workflows/acs-conventions.yml",
    ".github/workflows/acs-tests.yml",
    "README.md",
    "docs/product/prd.md",
    "docs/product/roadmap.md",
    "docs/product/operating-model.md",
    "docs/product/spikes/m2-0-validation-spike.md",
    "docs/quality/testing-strategy.md",
    "docs/architecture/hld/deployment.md",
    "docs/architecture/lld/contracts.md",
    "docs/architecture/lld/runtime-coupling-inventory.md",
    "docs/architecture/lld/flows/standardize-project.md",
    "docs/architecture/lld/flows/tests-coverage-gate.md",
    "docs/requirements/README.md",
    "docs/requirements/functional/configuration.md",
    "docs/requirements/functional/skills.md",
    "docs/requirements/functional/hooks.md",
    "docs/requirements/functional/usage.md",
    "docs/requirements/functional/workflow.md",
    "docs/requirements/non-functional/packaging-distribution.md",
    "docs/requirements/non-functional/portability.md",
    "docs/requirements/non-functional/security.md",
    "tests/acs/fixtures/mar145_clause_inventory.json",
    "evals/acs/README.md",
    "evals/acs/harness.py",
    "evals/acs/scenarios/s01_install_gate_smoke.py",
    "evals/acs/scenarios/s04_skill_triggers.py",
    "evals/acs/scenarios/s06_update_migration.py",
)

SETUP_LITERAL_RE = re.compile(r"/acs:setup|(?<![A-Za-z0-9_-])setup(?![A-Za-z0-9_-])")


class PositiveReplacementTest(unittest.TestCase):
    """AC-5: every T2+T3 file positively names /acs:setup or the bare
    `setup` skill-name literal -- positive match, never absence of the old
    token alone (test_create_spec_reference_sweep.py's pinned lesson)."""

    def test_every_t2_t3_file_names_setup(self):
        for rel in T2_T3_SETUP_PATHS:
            path = os.path.join(REPO_ROOT, rel)
            with self.subTest(path=rel):
                self.assertTrue(os.path.isfile(path), "%s must exist" % path)
                self.assertIsNotNone(
                    SETUP_LITERAL_RE.search(read(path)),
                    "%s must contain a positive /acs:setup or bare 'setup' "
                    "skill-name literal" % rel)


class TestFilesRenamedTest(unittest.TestCase):
    """AC-6: the 9 dedicated test_initialize_*.py modules are gone; all 9
    renamed test_setup_*.py modules (the 8 prose-contract modules plus this
    sweep module itself) exist."""

    SETUP_TEST_MODULES = (
        "test_setup_e2e_gate.py",
        "test_setup_in_repo_state_root.py",
        "test_setup_offers.py",
        "test_setup_operations_path.py",
        "test_setup_principles_path.py",
        "test_setup_quality_path.py",
        "test_setup_standards_path.py",
        "test_setup_suites.py",
        "test_setup_skill_reference_sweep.py",
    )

    def test_no_test_initialize_modules_remain(self):
        stray = glob.glob(os.path.join(REPO_ROOT, "tests", "acs", "test_initialize_*.py"))
        self.assertEqual(stray, [], "stray test_initialize_*.py module(s): %s" % stray)

    def test_all_nine_setup_modules_present(self):
        for name in self.SETUP_TEST_MODULES:
            path = os.path.join(REPO_ROOT, "tests", "acs", name)
            self.assertTrue(os.path.isfile(path), "%s must exist" % path)


def _base_ref():
    """`origin/main` is preferred over a local `main` for the same staleness
    reason documented in test_e2e_integrity_metric_docs.py: a long-lived
    worktree's local `main` can drift behind, producing a false failure."""
    for ref in ("origin/main", "main"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return ref
    return None


class SkillBodyUnchangedExceptRenameTest(unittest.TestCase):
    """AC-8: applying the rename's own two token substitutions (frontmatter
    `name:` line, and every `/acs:initialize` occurrence) to the pre-change
    skill body must reproduce the current setup/SKILL.md byte-for-byte --
    any other edit fails this equality. Self-skips with no base ref,
    mirroring test_e2e_integrity_metric_docs.py's idiom."""

    def setUp(self):
        self.base = _base_ref()
        if self.base is None:
            self.skipTest("no base ref (origin/main or main) to diff against")

    def test_skill_body_unchanged_except_rename_tokens(self):
        result = subprocess.run(
            ["git", "show", "%s:plugins/acs/skills/initialize/SKILL.md" % self.base],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest(
                "%s has no plugins/acs/skills/initialize/SKILL.md" % self.base)
        expected = result.stdout.replace("/acs:initialize", "/acs:setup")
        expected = re.sub(r"(?m)^name: initialize$", "name: setup", expected)
        self.assertEqual(expected, read(SETUP_SKILL_MD))


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
