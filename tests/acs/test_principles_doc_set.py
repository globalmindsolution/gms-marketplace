"""MAR-133 -- stand up the engineering-principles doc set.

Activates `principles_path` in `.acs/settings.json` (previously unset) and
authors `docs/principles/principles.md` by hand, mirroring the
`/acs:create-principles` output contract (`## Principles` then
`## Rationale`) since the installed plugin is still 0.3.7 and the skill
itself shipped in v0.4.0. The load-bearing principle encodes PRD C-20
(consumer-repo generality), which generalizes C-16.

Stdlib-only (json, os, re, unittest); guards a bare `import jsonschema`
behind `skipUnless` so the CI "Tests & validation" job (which does not
install jsonschema) stays green -- see
tests/acs/test_settings_models_pinned.py for the same pattern.

Run:  python3 -m unittest tests.acs.test_mar133_principles -v
"""

import json
import os
import re
import unittest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(REPO_ROOT, ".acs", "settings.json")
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
DOC_PATH = os.path.join(REPO_ROOT, "docs", "principles", "principles.md")

FORBIDDEN_ARTIFACTS = (
    ".claude-plugin/marketplace.json",
    "plugins/acs/.claude-plugin/plugin.json",
    "source.ref",
    "plugins/acs/CHANGELOG.md",
    "release.yml",
)

CUE_RE = re.compile(r"violation|reviewer|hardcod", re.IGNORECASE)
TRACE_RE = re.compile(r"\b[CGR]-\d+\b|Portability|NFR")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` up to the next same-or-higher-level heading (or EOF)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def principle_names(principles_section):
    """Bolded principle names in order, e.g. '1. **Name** -- ...'."""
    return re.findall(r"\*\*(.+?)\*\*", principles_section)


class SettingsPrinciplesPathTest(unittest.TestCase):
    """AC-1: principles_path set + settings stay schema-valid."""

    def test_settings_is_valid_json(self):
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            json.load(fh)  # raises JSONDecodeError on malformed JSON

    def test_settings_principles_path_is_docs_principles(self):
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            settings = json.load(fh)
        self.assertEqual(settings.get("principles_path"), "docs/principles")

    def test_principles_path_schema_conformant_stdlib(self):
        """No jsonschema import: mirror test_mar81's stdlib structural
        check -- the schema's `principles_path` property is the oneOf
        [string(minLength 1) | null] shape, and the committed value
        satisfies the string branch."""
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            settings = json.load(fh)

        prop = schema["properties"]["principles_path"]
        string_branch = next(
            branch for branch in prop["oneOf"] if branch.get("type") == "string"
        )
        self.assertEqual(string_branch.get("minLength"), 1)
        null_branch = next(
            branch for branch in prop["oneOf"] if branch.get("type") == "null"
        )
        self.assertIsNotNone(null_branch)

        value = settings["principles_path"]
        self.assertIsInstance(value, str)
        self.assertGreaterEqual(len(value), string_branch["minLength"])

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
    def test_settings_full_schema_valid(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            settings = json.load(fh)
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(settings))
        self.assertEqual(errors, [], "settings.json schema errors: %r" % (errors,))


class PrinciplesDocStructureTest(unittest.TestCase):
    """AC-2: doc exists, headings in order, no leftover template comments."""

    def test_principles_doc_exists(self):
        self.assertTrue(os.path.exists(DOC_PATH), "%s not found" % DOC_PATH)

    def test_required_headings_in_order(self):
        body = read(DOC_PATH)
        self.assertLess(body.index("## Principles"), body.index("## Rationale"))

    def test_no_template_html_comments(self):
        body = read(DOC_PATH)
        self.assertNotIn("<!--", body)


class ConsumerGeneralityPrincipleTest(unittest.TestCase):
    """AC-3: consumer-repo generality is first, names the forbidden
    artifacts, traces C-20, gives a violation cue."""

    def test_consumer_generality_is_first_principle(self):
        body = read(DOC_PATH)
        names = principle_names(section(body, "## Principles"))
        self.assertTrue(names, "no bolded principle names found under ## Principles")
        self.assertEqual(names[0], "Consumer-repo generality")

    def test_consumer_generality_names_forbidden_artifacts(self):
        body = read(DOC_PATH)
        for artifact in FORBIDDEN_ARTIFACTS:
            self.assertIn(artifact, body, "missing forbidden artifact %r" % artifact)
        self.assertIn("`main` branch", body, "doc must name the main branch")

    def test_consumer_generality_traces_c20_and_gives_cue(self):
        body = read(DOC_PATH)
        self.assertIn("C-20", body)
        self.assertTrue(
            any(token in body for token in ("C-16", "G30", "G33")),
            "doc must cite at least one of C-16/G30/G33 alongside C-20",
        )
        self.assertRegex(body, CUE_RE)


class EveryPrincipleHasRationaleTest(unittest.TestCase):
    """AC-4: every principle has a matching Rationale entry + PRD trace."""

    def test_every_principle_has_rationale_and_trace(self):
        body = read(DOC_PATH)
        names = principle_names(section(body, "## Principles"))
        rationale = section(body, "## Rationale")
        self.assertTrue(names, "no bolded principle names found under ## Principles")
        for name in names:
            self.assertIn(name, rationale, "%r has no ## Rationale entry" % name)
        self.assertRegex(rationale, TRACE_RE, "## Rationale has no PRD-trace token")
        self.assertRegex(rationale, CUE_RE, "## Rationale gives no violation cue")


class LiveViolationRecordedTest(unittest.TestCase):
    """AC-5: records the live /acs:release violation + enforcement note."""

    def test_records_live_release_violation(self):
        body = read(DOC_PATH)
        self.assertIn("/acs:release", body)
        self.assertIn("#251", body)
        self.assertIn("MAR-128", body)
        self.assertRegex(body, r"v0\.4[^\n]{0,80}enforc|enforc[^\n]{0,80}v0\.4")


if __name__ == "__main__":
    unittest.main()
