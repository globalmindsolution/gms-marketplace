"""Contract tests for /acs:ship's post-code fix-and-re-test loop.

Combines a schema-load-and-assert pattern (stdlib json, no jsonschema
runtime validator is used anywhere in this repo) with prose-contract checks
over ship/SKILL.md (stdlib re). Run:
  python3 -m unittest tests.acs.test_ship_fix_retest_loop -v
"""

import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
PIPELINE_SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "pipeline-state.schema.json")
SETTINGS_SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_json(path):
    return json.loads(read(path))


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` up to the next same-or-higher-level heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class PipelineStateSchemaTest(unittest.TestCase):
    """AC-3: "test" joins the steps enum; fix_loops is a documented,
    independent counter."""

    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(PIPELINE_SCHEMA_PATH)

    def test_test_step_in_steps_enum(self):
        enum = self.schema["properties"]["steps"]["propertyNames"]["enum"]
        self.assertIn("test", enum)

    def test_fix_loops_property_documented(self):
        step_schema = self.schema["properties"]["steps"]["additionalProperties"]
        fix_loops = step_schema["properties"].get("fix_loops")
        self.assertIsNotNone(fix_loops, "per-step object must document fix_loops")
        self.assertEqual(fix_loops["type"], "integer")
        self.assertEqual(fix_loops["minimum"], 0)


class SettingsSchemaTest(unittest.TestCase):
    """AC-3/AC-5: post_code_test.fix_loops_cap and post_code_test.enabled."""

    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SETTINGS_SCHEMA_PATH)
        cls.post_code_test = cls.schema["properties"].get("post_code_test")

    def test_post_code_test_property_exists(self):
        self.assertIsNotNone(self.post_code_test, "settings.schema.json must gain post_code_test")

    def test_fix_loops_cap_documented(self):
        cap = self.post_code_test["properties"]["fix_loops_cap"]
        self.assertEqual(cap["type"], "integer")
        self.assertEqual(cap["default"], 2)

    def test_enabled_allows_boolean_or_null_default_null(self):
        enabled = self.post_code_test["properties"]["enabled"]
        one_of_types = {branch["type"] for branch in enabled["oneOf"]}
        self.assertEqual(one_of_types, {"boolean", "null"})
        self.assertIsNone(enabled["default"])

    def test_description_states_e2e_gate_rule(self):
        desc = self.post_code_test["description"]
        self.assertIsNotNone(re.search(r"(?i)e2e", desc))
        self.assertIsNotNone(re.search(r"(?i)off|on\b", desc))


class ShipSkillGateAndLoopTest(unittest.TestCase):
    """AC-4/AC-5: ship/SKILL.md documents the gate rule verbatim and reuses
    the existing needs_input relay pattern rather than a new mechanism."""

    def _body(self):
        return read(SHIP_SKILL)

    def _normalized_body(self):
        return re.sub(r"\s+", " ", self._body())

    def test_pipeline_order_table_gains_test_row(self):
        table = section(self._body(), "## Pipeline order")
        self.assertIsNotNone(re.search(r"(?m)^\|.*\btest\b.*\|", table))

    def test_gate_rule_stated_verbatim(self):
        body = self._normalized_body()
        self.assertIsNotNone(
            re.search(r"(?i)OFF only when neither .*settings\.e2e.* nor .*suites\.e2e", body),
            "ship/SKILL.md must state the e2e-presence gate rule verbatim")

    def test_relay_reuses_needs_input_pattern_not_a_new_mechanism(self):
        body = self._body()
        occurrences = [m.start() for m in re.finditer(r"Re-invoke after needs_input", body)]
        # The existing bullet itself plus at least one new cross-reference.
        self.assertGreaterEqual(
            len(occurrences), 2,
            "the new test-step bullet must reference the existing "
            "'Re-invoke after needs_input' bullet, not invent a new one")

    def test_no_new_relay_vocabulary_heading_introduced(self):
        body = self._body()
        # Negative-space: "## " headings naming a distinct relay/handoff
        # mechanism stay at the pre-change count (Running a step, Handling
        # the handoff -- no third relay-describing H2 is added).
        relay_headings = re.findall(r"(?m)^## .*(?:[Rr]elay|[Hh]andoff).*$", body)
        self.assertEqual(len(relay_headings), 1,
                         "exactly one relay/handoff-describing heading "
                         "('## Handling the handoff') must exist -- no new one added")

    # The counter is written through a supported writer, never a hand-edited
    # step dict. Two writers qualify -- update_pipeline's `extra=` parameter
    # (MAR-510) and the pipeline-step.py CLI that wraps it (MAR-511) -- so
    # these assert the property, not which of the two the prose currently uses.
    SETS_COUNTER = r'(extra=\{"fix_loops"|--set fix_loops=)'
    CLEARS_COUNTER = r'(extra=\{"fix_loops": None\}|--unset fix_loops)'

    def test_fix_loops_is_written_through_a_supported_writer(self):
        """AC-2: the prose used to claim no acs_lib change was needed because
        update_pipeline "already writes an arbitrary-shape step dict" -- it did
        not, which is why MAR-510 exists."""
        gate = section(self._body(), "## Post-code test gate")
        self.assertIsNotNone(
            re.search(self.SETS_COUNTER, gate),
            "the test-gate steps must write fix_loops through a named writer")
        self.assertNotIn(
            "no `acs_lib.py`\ncode change", self._body(),
            "the claim that update_pipeline already writes an arbitrary-shape "
            "step dict is false and must not survive")

    def test_a_passing_step_clears_the_counter(self):
        """AC-3: a pass records completed AND removes fix_loops."""
        gate = section(self._body(), "## Post-code test gate")
        window = re.search(r"(?s)Verdict is `pass`.{0,500}", gate)
        self.assertIsNotNone(window)
        self.assertIsNotNone(re.search(self.CLEARS_COUNTER, window.group(0)))

    def test_re_entry_after_a_capped_run_resets_the_counter(self):
        """AC-4: without a reset, a resumed run re-reads the capped value, falls
        into the cap case on its first failure, and can never make progress --
        the dead end the ticket was filed for."""
        gate = section(self._body(), "## Post-code test gate")
        self.assertIsNotNone(
            re.search(r"(?i)re-entry reset", gate),
            "the gate must define what happens when the step is re-entered after a cap")
        window = re.search(r"(?si)re-entry reset.{0,600}", gate).group(0)
        self.assertIsNotNone(re.search(self.CLEARS_COUNTER, window))
        self.assertIsNotNone(re.search(r"(?i)failed", window))

    def test_fix_loops_cap_independent_note(self):
        body = self._normalized_body()
        self.assertIsNotNone(
            re.search(r"(?i)fix_loops.{0,120}independent", body) or
            re.search(r"(?i)independent.{0,120}fix_loops", body),
            "ship/SKILL.md must state fix_loops is independent of /code's own iteration cap")

    def test_cap_exhausted_stop_case_present(self):
        handoff = section(self._body(), "## Handling the handoff")
        self.assertIsNotNone(re.search(r"(?i)cap", handoff))

    def test_orchestration_not_step_work_note_present(self):
        body = self._body()
        gate = section(body, "## Post-code test gate")
        self.assertIsNotNone(
            re.search(r"(?i)orchestrat", gate),
            "the post-code test gate section must carry the "
            "'orchestration, not step-work' clarity note")


class Adr0068Test(unittest.TestCase):
    """AC-7: docs/adr/0068-*.md exists, Accepted, cross-references 0044 and
    this ticket's mechanism."""

    def _adr_body(self):
        import glob
        matches = glob.glob(os.path.join(ADR_DIR, "0068-*.md"))
        self.assertTrue(matches, "docs/adr/0068-*.md must exist")
        return read(matches[0])

    def test_status_accepted(self):
        self.assertIn("**Status**: Accepted", self._adr_body())

    def test_references_adr_0044(self):
        self.assertIn("0044", self._adr_body())

    def test_references_mechanism(self):
        body = self._adr_body()
        self.assertTrue(
            "fix_loops" in body or "--for-ticket" in body,
            "ADR 0068 must reference fix_loops or --for-ticket")


if __name__ == "__main__":
    unittest.main()
