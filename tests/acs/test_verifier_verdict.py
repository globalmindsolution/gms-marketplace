"""MAR-527: the verdict is the verifier's document, not the coordinator's claim.

`verifier_passed` — the single field the /acs:create-pr gate turns on — was
asserted by the COORDINATOR. The verifier is the only role that knows the
verdict, and it already writes a full report; the coordinator was transcribing
a conclusion it did not reach, so the gate checked whether a model had written
`true`, not whether a verifier had passed.

The rule that turns the document into a verdict rather than a self-report is
enforced in one place and asserted here from both sides:

    passed == (the verdict carries no blocking finding)
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
SCHEMA = os.path.join(PLUGIN, "schemas", "verdict.schema.json")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def verdict(**over):
    """A well-formed passing verdict; each test spoils exactly one thing."""
    doc = {
        "skill": "code",
        "ticket_id": "SHOP-1",
        "iteration": 1,
        "lens": None,
        "passed": True,
        "dimensions": [{"id": 1, "name": "Acceptance-criteria conformance",
                        "result": "pass", "evidence": "AC-1 traced to tests/test_a.py:12"},
                       {"id": 14, "result": "n/a", "evidence": "light depth"}],
        "findings": [],
    }
    doc.update(over)
    return doc


def blocking(dimension="coverage", detail="86.2% vs target 90"):
    return {"severity": "blocking", "dimension": dimension, "detail": detail}


class DerivedPassTest(unittest.TestCase):
    """The invariant, from both directions."""

    def test_a_well_formed_pass_validates(self):
        self.assertEqual(lib.validate_verdict(verdict()), [])

    def test_a_pass_claimed_over_a_blocking_finding_is_rejected(self):
        errors = lib.validate_verdict(verdict(findings=[blocking()],
                                              dimensions=[{"id": 3, "result": "fail"}]))
        self.assertTrue(any("passed is true but the verdict carries" in e for e in errors), errors)

    def test_a_failure_claimed_with_nothing_blocking_is_rejected(self):
        """The other direction matters too: a verdict that reports failure
        without recording what failed is unreviewable."""
        errors = lib.validate_verdict(verdict(passed=False))
        self.assertTrue(any("no finding is `blocking`" in e for e in errors), errors)

    def test_info_findings_never_decide_the_verdict(self):
        """The demoted documentation sub-checks depend on this: reported,
        carried, and never gating."""
        doc = verdict(findings=[{"severity": "info", "dimension": "documentation",
                                 "detail": "roadmap wording drifted"}])
        self.assertEqual(lib.validate_verdict(doc), [])
        self.assertTrue(lib.derived_passed(doc))

    def test_a_failed_dimension_needs_a_blocking_finding_to_match(self):
        """Otherwise the per-dimension table and the findings list disagree
        about what happened, and only one of them gates."""
        errors = lib.validate_verdict(verdict(
            passed=True, dimensions=[{"id": 3, "result": "fail"}]))
        self.assertTrue(any("with no blocking finding to match" in e for e in errors), errors)

    def test_derived_passed_ignores_what_the_document_claims(self):
        self.assertFalse(lib.derived_passed({"passed": True, "findings": [blocking()]}))
        self.assertTrue(lib.derived_passed({"passed": False, "findings": []}))


class ShapeTest(unittest.TestCase):

    def test_required_fields(self):
        for field in ("skill", "ticket_id", "iteration", "passed"):
            with self.subTest(field=field):
                doc = verdict()
                del doc[field]
                self.assertTrue(any(field in e for e in lib.validate_verdict(doc)))

    def test_dimensions_must_be_a_non_empty_list_of_known_ids(self):
        self.assertTrue(any("dimensions is required" in e
                            for e in lib.validate_verdict(verdict(dimensions=[])))) 
        self.assertTrue(any("not one of 1-16" in e for e in lib.validate_verdict(
            verdict(dimensions=[{"id": 17, "result": "pass"}]))))

    def test_a_dimension_reported_twice_is_rejected(self):
        errors = lib.validate_verdict(verdict(dimensions=[{"id": 1, "result": "pass"},
                                                          {"id": 1, "result": "fail"}]))
        self.assertTrue(any("reported twice" in e for e in errors), errors)

    def test_n_a_is_a_real_result_not_a_missing_one(self):
        self.assertEqual(lib.validate_verdict(
            verdict(dimensions=[{"id": 14, "result": "n/a"}])), [])
        self.assertTrue(any("result" in e for e in lib.validate_verdict(
            verdict(dimensions=[{"id": 14, "result": "skipped"}]))))

    def test_a_finding_needs_a_severity_and_a_detail(self):
        for finding in ({"severity": "loud", "detail": "x"},
                        {"severity": "blocking", "detail": "  "},
                        {"severity": "blocking"}):
            with self.subTest(finding=finding):
                self.assertTrue(lib.validate_verdict(verdict(passed=False, findings=[finding])))

    def test_a_lens_must_be_one_of_the_four_and_match_what_was_asked_for(self):
        self.assertTrue(lib.validate_verdict(verdict(lens="E")))
        self.assertEqual(lib.validate_verdict(verdict(lens="B"), lens="B"), [])
        self.assertTrue(any("does not match" in e
                            for e in lib.validate_verdict(verdict(lens="B"), lens="C")))

    def test_a_non_object_is_reported_rather_than_crashing(self):
        for doc in (None, [], "verdict", 7):
            with self.subTest(doc=doc):
                self.assertTrue(lib.validate_verdict(doc))


class MergeTest(unittest.TestCase):
    """Merging is arithmetic over the lens files, so the coordinator invokes it
    rather than authoring a verdict it did not reach."""

    def _lens(self, lens, dims, findings=()):
        return verdict(lens=lens, dimensions=dims, findings=list(findings),
                       passed=not any(f["severity"] == "blocking" for f in findings))

    def test_passed_is_the_conjunction_and_findings_the_union(self):
        merged = lib.merge_lens_verdicts([
            self._lens("A", [{"id": 1, "result": "pass"}]),
            self._lens("B", [{"id": 6, "result": "fail"}], [blocking("quality", "dead code")]),
            self._lens("C", [{"id": 8, "result": "pass"}]),
            self._lens("D", [{"id": 14, "result": "pass"}]),
        ])
        self.assertFalse(merged["passed"])
        self.assertEqual([f["dimension"] for f in merged["findings"]], ["quality"])
        self.assertEqual([d["id"] for d in merged["dimensions"]], [1, 6, 8, 14])
        self.assertEqual(merged["merged_from"], ["A", "B", "C", "D"])
        self.assertIsNone(merged["lens"])

    def test_all_lenses_passing_merges_to_a_pass(self):
        merged = lib.merge_lens_verdicts(
            [self._lens(l, [{"id": i, "result": "pass"}]) for i, l in enumerate(lib.LENSES, 1)])
        self.assertTrue(merged["passed"])
        self.assertEqual(lib.validate_verdict(merged), [])

    def test_the_worst_result_wins_when_two_lenses_report_one_dimension(self):
        merged = lib.merge_lens_verdicts([
            self._lens("A", [{"id": 1, "result": "n/a"}]),
            self._lens("B", [{"id": 1, "result": "pass"}]),
        ])
        self.assertEqual(merged["dimensions"][0]["result"], "pass")

    def test_non_dict_entries_are_skipped(self):
        merged = lib.merge_lens_verdicts([None, "x", self._lens("A", [{"id": 1, "result": "pass"}])])
        self.assertTrue(merged["passed"])


class DimensionDriftTest(unittest.TestCase):
    """The dimension table is a copy of the charter's numbering. Recompute it
    live so the copy cannot rot -- the same discipline the message-schema skill
    enum uses."""

    def test_the_table_matches_the_verifier_charter(self):
        with open(VERIFIER, encoding="utf-8") as fh:
            body = fh.read()
        charter = {int(m.group(1)): m.group(2)
                   for m in re.finditer(r"(?m)^(\d+)\. \*\*(.+?)\*\*", body)}
        self.assertEqual(charter, lib.VERDICT_DIMENSIONS)


class SchemaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(SCHEMA, encoding="utf-8") as fh:
            cls.schema = json.load(fh)

    def test_the_shipped_schema_agrees_with_the_validator_on_the_enums(self):
        props = self.schema["properties"]
        dim = props["dimensions"]["items"]["properties"]
        self.assertEqual(dim["result"]["enum"], list(lib.DIMENSION_RESULTS))
        self.assertEqual(dim["id"]["maximum"], len(lib.VERDICT_DIMENSIONS))
        finding = props["findings"]["items"]["properties"]
        self.assertEqual(finding["severity"]["enum"], list(lib.SEVERITIES))
        self.assertEqual([v for v in props["lens"]["enum"] if v], list(lib.LENSES))

    def test_the_schema_says_which_rule_it_cannot_express(self):
        """A schema that silently omits the invariant would read as the whole
        contract; this one names the function that carries it."""
        self.assertIn("validate_verdict", self.schema["description"])


class SubagentStopVerdictTest(AcsWorkspaceCase):
    """The hook that makes the verdict mandatory."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.tdir_path = self.tdir(self.ticket)
        out = self.start("code", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)

    def _message(self, status="completed", iteration="1", phase="verify"):
        return ('<result skill="code" phase="%s" ticket-id="%s" iteration="%s" status="%s">'
                '<stop-reason>done</stop-reason></result>' % (phase, self.ticket, iteration, status))

    def _stop(self, agent_type="acs:code-verifier", message=None, agent_id="a-1"):
        import subprocess
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), "subagent-stop"],
            input=json.dumps({"cwd": self.repo, "agent_id": agent_id,
                              "agent_type": agent_type,
                              "last_assistant_message": message or self._message()}),
            capture_output=True, text=True, cwd=self.repo)

    def _write(self, doc, iteration=1, lens=None):
        return lib.write_verdict(self.tdir_path, "code", iteration,
                                 dict(doc, ticket_id=self.ticket), lens)

    def test_a_verifier_that_writes_no_verdict_is_sent_back(self):
        out = self._stop()
        self.assertEqual(out.returncode, 2)
        self.assertIn("no verdict at", out.stderr)
        self.assertIn("iter-1-verdict.json", out.stderr)

    def test_a_valid_verdict_lets_the_verifier_stop(self):
        self._write(verdict())
        out = self._stop()
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_verdict_that_claims_a_pass_over_a_blocking_finding_is_refused(self):
        self._write(verdict(findings=[blocking()], dimensions=[{"id": 3, "result": "fail"}]))
        out = self._stop()
        self.assertEqual(out.returncode, 2)
        self.assertIn("passed is true but the verdict carries", out.stderr)

    def test_the_verdict_is_looked_up_at_the_iteration_the_message_declares(self):
        self._write(verdict(iteration=3), iteration=3)
        self.assertEqual(self._stop(message=self._message(iteration="3")).returncode, 0)
        self.assertEqual(self._stop(message=self._message(iteration="2")).returncode, 2)

    def test_only_a_verifier_is_asked_for_one(self):
        for role in ("planner", "executor"):
            with self.subTest(role=role):
                out = self._stop(agent_type="acs:code-%s" % role,
                                 message=self._message(phase="execute" if role == "executor" else "plan"))
                self.assertEqual(out.returncode, 0, out.stderr)

    def test_an_unfinished_verification_is_not_asked_for_a_verdict(self):
        """`needs_input` and `failed` mean the verifier could not judge; there
        is nothing for it to have concluded."""
        for status in ("needs_input", "failed"):
            with self.subTest(status=status):
                out = self._stop(message=self._message(status=status), agent_id="a-%s" % status)
                self.assertEqual(out.returncode, 0, out.stderr)

    def test_it_stops_asking_after_the_block_limit(self):
        codes = [self._stop().returncode for _ in range(4)]
        self.assertEqual(codes[0], 2)
        self.assertEqual(codes[1:], [0, 0, 0])

    def test_the_give_up_message_names_what_was_wrong(self):
        for _ in range(lib.BLOCK_LIMIT):
            self._stop()
        out = self._stop()
        self.assertEqual(out.returncode, 0)
        self.assertIn("verdict is still unusable", out.stderr)


class VerdictCliTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.tdir_path = self.tdir(self.ticket)
        self.assertEqual(self.start("code", self.ticket).returncode, 0)

    def _write(self, doc, iteration=1, lens=None):
        return lib.write_verdict(self.tdir_path, "code", iteration,
                                 dict(doc, ticket_id=self.ticket), lens)

    def test_show_reports_the_derived_verdict(self):
        self._write(verdict())
        body = json.loads(self.run_script("acs.py", "verdict", "show").stdout)
        self.assertTrue(body["ok"])
        self.assertTrue(body["passed"])
        self.assertEqual(body["blocking"], 0)

    def test_show_surfaces_a_document_that_claims_more_than_it_supports(self):
        self._write(verdict(findings=[blocking()], dimensions=[{"id": 3, "result": "fail"}]))
        out = self.run_script("acs.py", "verdict", "show")
        body = json.loads(out.stdout)
        self.assertFalse(body["ok"])
        self.assertTrue(body["claimed_passed"])
        self.assertFalse(body["passed"], "the DERIVED verdict is what the caller reads")
        self.assertEqual(body["blocking"], 1)

    def test_show_refuses_when_there_is_no_verdict(self):
        out = self.run_script("acs.py", "verdict", "show")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no verdict at", out.stderr)

    def test_merge_writes_the_iteration_verdict_from_the_four_lenses(self):
        for lens, dim in zip(lib.LENSES, (1, 6, 8, 14)):
            self._write(verdict(lens=lens, dimensions=[{"id": dim, "result": "pass"}]), lens=lens)
        body = json.loads(self.run_script("acs.py", "verdict", "merge").stdout)
        self.assertTrue(body["passed"])
        self.assertEqual(body["merged_from"], list(lib.LENSES))
        self.assertTrue(os.path.exists(lib.verdict_path(self.tdir_path, "code", 1)))

    def test_merge_refuses_when_a_lens_verdict_is_missing(self):
        self._write(verdict(lens="A", dimensions=[{"id": 1, "result": "pass"}]), lens="A")
        out = self.run_script("acs.py", "verdict", "merge")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no verdict for lens B, C, D", out.stderr)

    def test_a_merged_failure_carries_the_blocking_finding_through(self):
        for lens, dim in zip(lib.LENSES, (1, 6, 8, 14)):
            findings = [blocking("quality", "dead code")] if lens == "B" else []
            self._write(verdict(lens=lens, dimensions=[{"id": dim, "result": "pass"}],
                                findings=findings, passed=not findings), lens=lens)
        body = json.loads(self.run_script("acs.py", "verdict", "merge").stdout)
        self.assertFalse(body["passed"])
        self.assertEqual(body["blocking"], 1)


class ProseTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(VERIFIER, encoding="utf-8") as fh:
            cls.verifier = fh.read()
        with open(CODE_SKILL, encoding="utf-8") as fh:
            cls.skill = fh.read()

    def test_the_verifier_is_told_to_write_the_verdict(self):
        self.assertIn("iter-<n>-verdict.json", self.verifier)
        self.assertIn("`passed` is DERIVED, not decided", self.verifier)

    def test_the_verifier_no_longer_defers_the_conclusion_to_the_coordinator(self):
        self.assertNotIn("the coordinator sets `verifier_passed: true`", self.verifier)

    def test_the_coordinator_reads_the_verdict_rather_than_concluding_it(self):
        self.assertIn("acs.py\" verdict show", self.skill)
        self.assertIn("acs.py\" verdict merge", self.skill)
        self.assertNotIn("`verifier_passed`: `true` ONLY on a zero-findings verifier pass",
                         self.skill)


if __name__ == "__main__":
    unittest.main()
