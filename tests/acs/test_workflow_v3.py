"""A workflow is a list (§2.1), and its order is validated from the skills'
own declarations rather than from edges in the file.

Replaces the version-2 half of tests/acs/test_workflow_resolution.py.

The load-bearing claims:

  * every v2 key is REJECTED, not ignored — a workflow that tries to decide
    for a skill whether it has work fails validation rather than working
    silently, and the error says where the key went
  * order is checked WITHOUT any edge in the file: a step's required reads
    must be written by an earlier step, which is derived from acs.yaml
  * the check is loop-aware, so `code` reading `verdict` is not a warning
  * `back_to` must precede `from`, because a loop that does not go back is
    not a loop

Run:  python3 -m unittest tests.acs.test_workflow_v3 -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "plugins", "acs", "hooks", "scripts"))

from acs_lib import workflow as W  # noqa: E402
from acs_lib._common import WorkflowError  # noqa: E402

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "plugins", "acs")
SHIP = os.path.join(PLUGIN, "workflows", "ship.yaml")

VALID = """version: 3
steps:
  - analyze-requirements
  - create-impl-plan
  - code
  - review-code
loops:
  - from: review-code
    back_to: code
    max_iterations: 3
    on_exhausted: fail
"""


def write(text):
    handle, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(handle, "w") as fh:
        fh.write(text)
    return path


class ShippedWorkflowTest(unittest.TestCase):

    def setUp(self):
        self.doc = W.validate_workflow_file(SHIP)

    def test_it_validates(self):
        self.assertEqual(self.doc["version"], 3)

    def test_it_is_ten_steps_in_order(self):
        self.assertEqual(W.steps_of(self.doc), [
            "analyze-requirements", "create-impl-plan", "create-api-contract",
            "create-test-docs", "code", "review-code", "create-e2e-tests",
            "run-e2e-tests", "docs-sync", "create-pr"])

    def test_every_step_is_a_bare_name(self):
        for step in self.doc["steps"]:
            self.assertIsInstance(step, str)

    def test_the_only_construct_is_the_one_loop(self):
        self.assertEqual(set(self.doc) - {"version", "steps"}, {"loops"})
        self.assertEqual(len(W.loops_of(self.doc)), 1)
        self.assertEqual(W.loop_for(self.doc, "review-code"),
                         {"from": "review-code", "back_to": "code",
                          "max_iterations": 3, "on_exhausted": "fail"})

    def test_the_shipped_order_raises_no_warnings(self):
        """In particular: `code` reads `verdict`, which review-code writes one
        step later, and the LOOP is what carries it back."""
        self.assertEqual(W.order_warnings(self.doc), [])

    def test_the_name_is_the_file_name(self):
        self.assertEqual(W.workflow_name(SHIP), "ship")

    def test_it_lives_under_the_plugin_workflows_dir(self):
        self.assertEqual(SHIP, os.path.join(PLUGIN, "workflows", "ship.yaml"))

    def test_it_validates_with_jsonschema_too(self):
        """The stdlib subset validator and the JSON Schema must AGREE: two
        validators that disagree means one of them is decoration."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        with open(os.path.join(PLUGIN, "schemas", "workflow.schema.json"),
                  encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(self.doc, schema)

    def test_the_header_comment_states_the_rules_it_is_enforced_by(self):
        """Successor to test_ship_yaml_default's header pin. The rules the
        header must state are v3's, not v2's: what the schema rejects, why
        (the standalone-skill rule), and that `loops:` is the one construct."""
        with open(SHIP, encoding="utf-8") as fh:
            head = fh.read().split("version:")[0]
        for phrase in ("A LIST", "the schema rejects every one of",
                       "`loops:` is the only construct",
                       "evidenced no-op", "acs workflow validate"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)


class RemovedKeyTest(unittest.TestCase):
    """Rejected, not merely unused."""

    def _refuse(self, text, needle):
        with self.assertRaises(WorkflowError) as caught:
            W.validate_workflow_file(write(text))
        self.assertIn(needle, str(caught.exception))

    def test_version_two_is_refused_with_a_reason(self):
        self._refuse("version: 2\nsteps:\n  - code\n", "version 3")

    def test_stop_after_is_refused(self):
        self._refuse(VALID + "stop_after: create-pr\n", "stop_after")

    def test_max_parallel_is_refused(self):
        self._refuse(VALID + "max_parallel: 2\n", "max_parallel")

    def test_delivery_is_refused(self):
        self._refuse(VALID + "delivery:\n  classify_after: create-impl-plan\n", "delivery")

    def test_name_is_refused(self):
        self._refuse(VALID + "name: ship\n", "name")

    def test_a_step_object_is_refused(self):
        self._refuse("version: 3\nsteps:\n  - id: code\n    skill: code\n", "not an object")

    def test_a_step_with_needs_is_refused(self):
        self._refuse("version: 3\nsteps:\n  - code\n  - id: review-code\n"
                     "    needs: [code]\n", "needs")

    def test_a_step_with_when_is_refused(self):
        self._refuse("version: 3\nsteps:\n  - id: create-api-contract\n"
                     "    when: api_surface_changed\n", "when")


class StepAdmissionTest(unittest.TestCase):

    def _refuse(self, text, needle):
        with self.assertRaises(WorkflowError) as caught:
            W.validate_workflow_file(write(text))
        self.assertIn(needle, str(caught.exception))

    def test_an_unknown_skill_is_refused(self):
        self._refuse("version: 3\nsteps:\n  - not-a-skill\n", "is not a skill that ships")

    def test_a_leg_may_not_be_a_step(self):
        self._refuse("version: 3\nsteps:\n  - code-standard\n", "is a leg of 'code'")

    def test_a_skill_with_no_io_may_not_be_a_step(self):
        self._refuse("version: 3\nsteps:\n  - setup\n", "declares no reads and no writes")


class OrderValidationTest(unittest.TestCase):
    """The check that replaced `needs:` — derived from the skills, not from
    an edge list an author maintains."""

    def test_a_required_read_before_its_producer_is_refused(self):
        with self.assertRaises(WorkflowError) as caught:
            W.validate_workflow_file(write(
                "version: 3\nsteps:\n  - analyze-requirements\n"
                "  - create-api-contract\n  - create-impl-plan\n"))
        message = str(caught.exception)
        self.assertIn("create-api-contract", message)
        self.assertIn("'plan'", message)
        self.assertIn("create-impl-plan", message)

    def test_a_required_read_nobody_writes_is_refused(self):
        with self.assertRaises(WorkflowError) as caught:
            W.validate_workflow_file(write("version: 3\nsteps:\n  - create-impl-plan\n"))
        self.assertIn("no step in this workflow writes", str(caught.exception))

    def test_a_swap_that_does_not_matter_passes(self):
        """docs-sync and the e2e pair: neither reads the other's output."""
        doc = W.validate_workflow_file(write(
            "version: 3\nsteps:\n  - analyze-requirements\n  - create-impl-plan\n"
            "  - code\n  - docs-sync\n  - create-e2e-tests\n  - run-e2e-tests\n"))
        self.assertIn("docs-sync", W.steps_of(doc))

    def test_the_subject_is_a_run_level_input(self):
        """analyze-requirements requires `subject`, which no step writes."""
        W.validate_workflow_file(write("version: 3\nsteps:\n  - analyze-requirements\n"))

    def test_an_optional_read_out_of_order_is_a_warning_not_an_error(self):
        doc = W.validate_workflow_file(write(
            "version: 3\nsteps:\n  - analyze-requirements\n  - create-impl-plan\n"
            "  - create-test-docs\n  - create-api-contract\n"))
        warnings = W.order_warnings(doc)
        self.assertTrue(any("api-contract" in w for w in warnings), warnings)


class LoopValidationTest(unittest.TestCase):

    def test_back_to_must_precede_from(self):
        with self.assertRaises(WorkflowError) as caught:
            W.validate_workflow_file(write(
                "version: 3\nsteps:\n  - analyze-requirements\n  - create-impl-plan\n"
                "  - code\n  - review-code\n"
                "loops:\n  - from: code\n    back_to: review-code\n"
                "    max_iterations: 3\n    on_exhausted: fail\n"))
        self.assertIn("not EARLIER", str(caught.exception))

    def test_a_loop_endpoint_must_be_a_step(self):
        with self.assertRaises(WorkflowError) as caught:
            W.validate_workflow_file(write(
                "version: 3\nsteps:\n  - analyze-requirements\n  - create-impl-plan\n"
                "loops:\n  - from: review-code\n    back_to: code\n"
                "    max_iterations: 3\n    on_exhausted: fail\n"))
        self.assertIn("is not a step", str(caught.exception))

    def test_on_exhausted_admits_only_fail(self):
        """A run that exhausted its review loop never passes with findings."""
        with self.assertRaises(WorkflowError):
            W.validate_workflow_file(write(VALID.replace("on_exhausted: fail",
                                                         "on_exhausted: pass")))


if __name__ == "__main__":
    unittest.main()
