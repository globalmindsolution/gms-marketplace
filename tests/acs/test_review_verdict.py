"""The review verdict: `/acs:review-code`'s document, not the coordinator's claim.

`verifier_passed` — the single field the /acs:create-pr gate turns on — was
asserted by the COORDINATOR (MAR-523/527). The gate therefore checked whether a
model had written `true`, not whether a review had passed.

The rule that turns the document into a verdict rather than a self-report is
enforced in one place and asserted here from both sides:

    passed == (the verdict carries no blocking finding still standing)

The v0.5.0 redesign (§2.3) replaced the sixteen-dimension table with a list of
FINDINGS, because a finding is what crosses the review loop. Three fields carry
that loop and the dimension-era verdict had none of them — `id`, `evidence` and
`resolved_when` — so they are required here rather than encouraged in prose.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
REVIEW_SKILL = os.path.join(PLUGIN, "skills", "review-code", "SKILL.md")
LENS_AGENT = os.path.join(PLUGIN, "agents", "review-code-lens.md")
ADJUDICATOR_AGENT = os.path.join(PLUGIN, "agents", "review-code-adjudicator.md")
SCHEMA = os.path.join(PLUGIN, "schemas", "verdict.schema.json")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def finding(**over):
    """A well-formed confirmed blocking finding."""
    doc = {
        "id": "F-1-1",
        "status": "confirmed",
        "severity": "blocking",
        "kind": "defect",
        "lens": "B",
        "file": "src/auth/session.py",
        "line": 142,
        "claim": "refresh() drops the request-scoped tenant id",
        "evidence": ["src/auth/session.py:138-151"],
        "resolved_when": "a test asserts the tenant id survives refresh() and passes",
        "traces_to": ["TC-7"],
        "adjudication": {"verdict": "confirmed", "reason": "refutation failed"},
    }
    doc.update(over)
    return doc


def advisory(**over):
    return finding(**dict({"id": "F-1-2", "status": "advisory",
                           "severity": "advisory", "kind": "craft",
                           "resolved_when": ""}, **over))


def verdict(**over):
    """A well-formed passing verdict; each test spoils exactly one thing."""
    doc = {
        "skill": "review-code",
        "run_id": "SHOP-1",
        "iteration": 1,
        "reviewed_sha": "9c1e4a2",
        "lens": None,
        "passed": True,
        "findings": [],
    }
    doc.update(over)
    return doc


class DerivedPassTest(unittest.TestCase):
    """The invariant, from both directions."""

    def test_a_well_formed_pass_validates(self):
        self.assertEqual(lib.validate_verdict(verdict()), [])

    def test_a_pass_claimed_over_a_blocking_finding_is_rejected(self):
        errors = lib.validate_verdict(verdict(findings=[finding()]))
        self.assertTrue(any("passed is true but the verdict carries" in e for e in errors), errors)

    def test_a_failure_claimed_with_nothing_blocking_is_rejected(self):
        """The other direction matters too: a verdict that reports failure
        without recording what failed is unreviewable."""
        errors = lib.validate_verdict(verdict(passed=False))
        self.assertTrue(any("no finding is `blocking`" in e for e in errors), errors)

    def test_advisory_findings_never_decide_the_verdict(self):
        """A `needs-context` adjudication lands here rather than being dropped,
        and it must not gate."""
        doc = verdict(findings=[advisory()])
        self.assertEqual(lib.validate_verdict(doc), [])
        self.assertTrue(lib.derived_passed(doc))

    def test_a_resolved_finding_no_longer_blocks(self):
        """A finding closed on a later iteration is CARRIED so the trail shows
        closure. Reading it as blocking would make a verdict that records its
        own fixes permanently red."""
        doc = verdict(iteration=2, findings=[finding(status="resolved")])
        self.assertEqual(lib.validate_verdict(doc), [])
        self.assertTrue(lib.derived_passed(doc))

    def test_derived_passed_ignores_what_the_document_claims(self):
        self.assertFalse(lib.derived_passed({"passed": True, "findings": [finding()]}))
        self.assertTrue(lib.derived_passed({"passed": False, "findings": []}))


class LoopFieldsTest(unittest.TestCase):
    """The three fields that carry the loop. Each is required because /acs:code
    cannot act without it — not because a schema likes complete documents."""

    def test_a_finding_without_an_id_is_rejected(self):
        errors = lib.validate_verdict(verdict(passed=False, findings=[finding(id="")]))
        self.assertTrue(any("non-empty string id" in e for e in errors), errors)

    def test_two_findings_may_not_share_an_id(self):
        errors = lib.validate_verdict(verdict(
            passed=False, findings=[finding(), finding()]))
        self.assertTrue(any("used twice" in e for e in errors), errors)

    def test_a_finding_without_evidence_is_rejected(self):
        """Evidence is what stops /acs:code re-deriving the review's work."""
        for bad in ([], None, [""], "src/a.py:1"):
            with self.subTest(evidence=bad):
                errors = lib.validate_verdict(verdict(passed=False,
                                                      findings=[finding(evidence=bad)]))
                self.assertTrue(any("needs evidence" in e for e in errors), errors)

    def test_a_confirmed_finding_without_a_resolved_when_is_rejected(self):
        """Otherwise the verdict tells /acs:code to fix something without
        saying when it is fixed."""
        errors = lib.validate_verdict(verdict(passed=False,
                                              findings=[finding(resolved_when="  ")]))
        self.assertTrue(any("no resolved_when" in e for e in errors), errors)

    def test_an_advisory_finding_needs_no_resolved_when(self):
        """Nothing has to be made true for an advisory: it is carried, not
        worked to."""
        self.assertEqual(lib.validate_verdict(verdict(findings=[advisory()])), [])

    def test_open_findings_are_the_confirmed_ones(self):
        doc = verdict(passed=False, findings=[finding(), advisory(),
                                              finding(id="F-1-3", status="resolved")])
        self.assertEqual([f["id"] for f in lib.open_findings(doc)], ["F-1-1"])

    def test_unanswered_names_the_ids_the_code_result_did_not_answer(self):
        doc = verdict(passed=False, findings=[finding(), finding(id="F-1-9")])
        result = {"resolutions": [{"id": "F-1-1", "status": "fixed"}]}
        self.assertEqual(lib.unanswered(doc, result), ["F-1-9"])
        self.assertEqual(lib.unanswered(doc, {"resolutions": []}), ["F-1-1", "F-1-9"])

    def test_a_dispute_counts_as_an_answer(self):
        """`disputed` is not a way out — the next adjudicator rules again — but
        it IS an answer, so the pre-hook must not demand a fix instead."""
        doc = verdict(passed=False, findings=[finding()])
        self.assertEqual(
            lib.unanswered(doc, {"resolutions": [{"id": "F-1-1", "status": "disputed",
                                                  "reason": "the lookback matched a "
                                                            "different function"}]}), [])

    def test_next_finding_id_skips_the_ids_already_used(self):
        self.assertEqual(lib.next_finding_id(1), "F-1-1")
        self.assertEqual(lib.next_finding_id(1, ["F-1-1", "F-1-2"]), "F-1-3")
        self.assertEqual(lib.next_finding_id(2, ["F-1-1"]), "F-2-1")


class ShapeTest(unittest.TestCase):

    def test_required_fields(self):
        for field in ("skill", "run_id", "iteration", "reviewed_sha", "passed"):
            with self.subTest(field=field):
                doc = verdict()
                del doc[field]
                self.assertTrue(any(field in e for e in lib.validate_verdict(doc)))

    def test_reviewed_sha_is_required_because_code_diffs_from_it(self):
        errors = lib.validate_verdict(verdict(reviewed_sha="  "))
        self.assertTrue(any("reviewed_sha is required" in e for e in errors), errors)

    def test_findings_must_be_a_list(self):
        self.assertTrue(any("findings is required" in e
                            for e in lib.validate_verdict(verdict(findings="none"))))

    def test_a_finding_status_must_be_one_of_the_three(self):
        """`refuted` is deliberately not among them: a refuted finding stays in
        the adjudication record and never reaches the verdict."""
        errors = lib.validate_verdict(verdict(findings=[advisory(status="refuted")]))
        self.assertTrue(any("refuted finding does not belong" in e for e in errors), errors)

    def test_a_finding_kind_must_be_known(self):
        errors = lib.validate_verdict(verdict(findings=[advisory(kind="vibes")]))
        self.assertTrue(any("kind 'vibes' is not one of" in e for e in errors), errors)

    def test_the_gate_reports_through_a_finding_like_any_other(self):
        """A build, lint, suite or coverage failure is `kind: gate` with the
        failing command as evidence — it needs no separate channel."""
        doc = verdict(passed=False, findings=[finding(
            id="F-1-9", kind="gate", lens=None, file=None, line=None,
            claim="coverage 76% < 80%",
            evidence=["python3 -m coverage report", "TOTAL 76%"],
            resolved_when="coverage >= 80% on the full suite")])
        self.assertEqual(lib.validate_verdict(doc), [])
        self.assertFalse(lib.derived_passed(doc))

    def test_a_finding_needs_a_severity_and_a_claim(self):
        for over in ({"severity": "loud"}, {"claim": "  "}, {"claim": None}):
            with self.subTest(over=over):
                self.assertTrue(lib.validate_verdict(verdict(passed=False,
                                                             findings=[finding(**over)])))

    def test_a_lens_must_be_one_of_the_five_and_match_what_was_asked_for(self):
        self.assertTrue(lib.validate_verdict(verdict(lens="F")))
        self.assertEqual(lib.validate_verdict(verdict(lens="E"), lens="E"), [])
        self.assertTrue(any("does not match" in e
                            for e in lib.validate_verdict(verdict(lens="B"), lens="C")))

    def test_an_adjudication_verdict_must_be_known(self):
        errors = lib.validate_verdict(verdict(
            findings=[advisory(adjudication={"verdict": "probably"})]))
        self.assertTrue(any("adjudication verdict" in e for e in errors), errors)

    def test_a_non_object_is_reported_rather_than_crashing(self):
        for doc in (None, [], "verdict", 7):
            with self.subTest(doc=doc):
                self.assertTrue(lib.validate_verdict(doc))


class FreshnessTest(unittest.TestCase):
    """A verdict is evidence only for the run that produced it."""

    def test_the_identity_fields_are_checked_against_the_callers(self):
        for field, wrong in (("skill", "docs-sync"), ("run_id", "SHOP-9"),
                             ("iteration", 3)):
            with self.subTest(field=field):
                errors = lib.validate_verdict(verdict(), **{field: wrong})
                self.assertTrue(any("evidence only" in e for e in errors), errors)

    def test_a_matching_document_passes_the_same_check(self):
        self.assertEqual(lib.validate_verdict(verdict(), skill="review-code",
                                              run_id="SHOP-1", iteration=1), [])


class SchemaAgreesWithValidatorTest(unittest.TestCase):
    """The hooks run the hand-written validate_verdict; the shipped schema is
    what everything else reads. Nothing stops the two drifting unless something
    round-trips the same fixtures through both, so this does."""

    @classmethod
    def setUpClass(cls):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:  # pragma: no cover - jsonschema is a test-only dep
            raise unittest.SkipTest("jsonschema not installed")
        with open(SCHEMA, encoding="utf-8") as fh:
            cls.schema = json.load(fh)
        cls.validator = Draft202012Validator(cls.schema)

    def _schema_errors(self, doc):
        return [e.message for e in self.validator.iter_errors(doc)]

    def test_a_well_formed_verdict_satisfies_both(self):
        doc = verdict()
        self.assertEqual(lib.validate_verdict(doc), [])
        self.assertEqual(self._schema_errors(doc), [])

    def test_a_verdict_carrying_findings_satisfies_both(self):
        doc = verdict(passed=False, findings=[finding(), advisory()])
        self.assertEqual(lib.validate_verdict(doc), [])
        self.assertEqual(self._schema_errors(doc), [])

    def test_the_enums_agree(self):
        props = self.schema["properties"]
        item = props["findings"]["items"]["properties"]
        self.assertEqual(item["status"]["enum"], list(lib.FINDING_STATUSES))
        self.assertEqual(item["severity"]["enum"], list(lib.SEVERITIES))
        self.assertEqual(item["kind"]["enum"], list(lib.FINDING_KINDS))
        self.assertEqual(item["lens"]["enum"], list(lib.LENSES))
        self.assertEqual(item["adjudication"]["properties"]["verdict"]["enum"],
                         list(lib.ADJUDICATIONS))
        self.assertEqual([v for v in props["lens"]["enum"] if v], list(lib.LENSES))

    def test_the_schema_says_which_rule_it_cannot_express(self):
        """A schema that silently omitted the invariant would read as the whole
        contract; this one names the function that carries it."""
        self.assertIn("validate_verdict", self.schema["description"])

    def test_every_shape_rule_the_schema_states_is_also_rejected_by_the_validator(self):
        """One deliberately-bad document per shape keyword. The schema and the
        validator may each catch MORE than the other -- validate_verdict owns
        the rules JSON Schema cannot express -- but neither may ACCEPT what the
        other rejects on shape."""
        cases = {
            "missing skill": dict(verdict(), skill=None),
            "iteration below minimum": dict(verdict(), iteration=0),
            "empty reviewed_sha": dict(verdict(), reviewed_sha=""),
            "passed not a boolean": dict(verdict(), passed="yes"),
            "finding without an id": verdict(passed=False, findings=[finding(id="")]),
            "unknown finding status": verdict(findings=[advisory(status="refuted")]),
            "unknown finding kind": verdict(findings=[advisory(kind="vibes")]),
            "bad finding severity": verdict(passed=False, findings=[finding(severity="loud")]),
            "finding with no evidence": verdict(passed=False, findings=[finding(evidence=[])]),
            "lens not one of A-E": dict(verdict(), lens="F"),
        }
        for name, doc in cases.items():
            with self.subTest(name):
                self.assertTrue(self._schema_errors(doc),
                                "%s: the schema accepted it" % name)
                self.assertTrue(lib.validate_verdict(doc),
                                "%s: validate_verdict accepted it" % name)


class VerdictCliTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.rdir_path = self.ensure_run(self.ticket)
        self.assertEqual(self.start("review-code", self.ticket).returncode, 0)

    def _write(self, doc, iteration=1, lens=None):
        return lib.write_verdict(self.rdir_path, "review-code", iteration,
                                 dict(doc, run_id=self.ticket), lens)

    def _show(self, *args):
        return self.run_script("acs.py", "verdict", "show", "--skill", "review-code", *args)

    def test_show_reports_the_derived_verdict(self):
        self._write(verdict())
        body = json.loads(self._show().stdout)
        self.assertTrue(body["ok"])
        self.assertTrue(body["passed"])
        self.assertEqual(body["blocking"], 0)

    def test_show_refuses_a_document_that_claims_more_than_it_supports(self):
        """It used to EMIT this document with ok:false beside passed:true.
        `passed` is derived from the findings and an absent findings list
        derives True, so a document the command itself called invalid was
        reported as a pass -- to a coordinator whose instructions say to copy
        `passed` and never mention `ok`."""
        self._write(verdict(findings=[finding()]))
        out = self._show()
        self.assertEqual(out.returncode, 2)
        self.assertIn("not usable", out.stderr)
        self.assertEqual(out.stdout.strip(), "")

    def test_show_refuses_a_verdict_that_is_barely_a_document(self):
        """derived_passed({}) is True, so the emptiest possible file used to
        read as a pass all the way to the create-pr gate."""
        lib.write_verdict(self.rdir_path, "review-code", 1,
                          {"skill": "review-code", "run_id": self.ticket})
        out = self._show()
        self.assertEqual(out.returncode, 2)
        self.assertIn("not usable", out.stderr)

    def test_show_refuses_when_there_is_no_verdict(self):
        out = self._show()
        self.assertEqual(out.returncode, 2)
        self.assertIn("no verdict at", out.stderr)

    def test_show_refuses_a_verdict_from_another_iteration(self):
        """A verdict is evidence only for the run that produced it: iteration
        1's clean verdict sitting on iteration 3's path is not iteration 3's
        verdict, and reading it as a pass makes the audit surface lie."""
        self._write(verdict(), iteration=3)
        out = self._show("--iteration", "3")
        self.assertEqual(out.returncode, 2)
        self.assertIn("verdict iteration is 1 but this is 3", out.stderr)
        self.assertEqual(out.stdout.strip(), "")

    def test_show_refuses_a_verdict_from_another_skill(self):
        """The same freshness rule on the other axis: a docs-sync verdict read
        at the review path is not the review's verdict."""
        self._write(verdict(skill="docs-sync"))
        out = self._show()
        self.assertEqual(out.returncode, 2)
        self.assertIn("docs-sync", out.stderr)
        self.assertIn("evidence only", out.stderr)

    def test_show_reports_a_verdict_whose_iteration_matches(self):
        """Freshness refuses a mismatch, not a match: a document about the run
        that was asked for still reports its derived verdict."""
        self._write(verdict(iteration=3), iteration=3)
        out = self._show("--iteration", "3")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["passed"])
        self.assertEqual(body["blocking"], 0)


class FinishRequiresAVerdictTest(AcsWorkspaceCase):
    """"Derived, never asserted" has a Stop half: a review that completed
    without a verdict concluded nothing, and the loop has nothing to carry."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.rdir_path = self.ensure_run(self.ticket)
        self.assertEqual(self.start("review-code", self.ticket).returncode, 0)

    def _finish(self, outcome="passed"):
        return self.run_script("acs.py", "step", "finish", "--step", "review-code",
                               "--run", self.ticket, "--status", "completed",
                               "--outcome", outcome)

    def test_a_review_cannot_complete_without_one(self):
        out = self._finish()
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("without a verdict", out.stderr)

    def test_a_review_cannot_complete_on_an_unusable_one(self):
        lib.write_verdict(self.rdir_path, "review-code", 1,
                          {"skill": "review-code", "run_id": self.ticket})
        out = self._finish()
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("not usable", out.stderr)

    def test_a_review_with_a_well_formed_verdict_completes(self):
        lib.write_verdict(self.rdir_path, "review-code", 1,
                          dict(verdict(), run_id=self.ticket))
        out = self._finish()
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_blocking_verdict_completes_and_re_enters_the_loop(self):
        """A review that found something is a review that worked. The verdict
        is required; a PASSING verdict is not."""
        lib.write_verdict(self.rdir_path, "review-code", 1,
                          dict(verdict(passed=False, findings=[finding()]),
                               run_id=self.ticket))
        out = self._finish(outcome="blocking_findings")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["loops"]["review-code"]["iteration"], 2)

    def test_an_interrupted_review_is_not_asked_for_one(self):
        """The reviewer could not judge; there is nothing for it to have
        concluded."""
        out = self.run_script("acs.py", "step", "finish", "--step", "review-code",
                              "--run", self.ticket, "--status", "interrupted",
                              "--stop-reason", "session_end")
        self.assertEqual(out.returncode, 0, out.stderr)


class ProseTest(unittest.TestCase):
    """The skill and its agents must say what the kernel enforces."""

    @classmethod
    def setUpClass(cls):
        with open(REVIEW_SKILL, encoding="utf-8") as fh:
            cls.skill = fh.read()

    def test_the_coordinator_is_told_to_write_the_verdict(self):
        self.assertIn("verdict.json", self.skill)

    def test_the_coordinator_does_not_assert_the_conclusion(self):
        self.assertIn("`passed` is **not yours to assert**", self.skill)

    def test_the_loop_fields_are_named_in_the_skill(self):
        for field in ("id", "evidence", "resolved_when"):
            with self.subTest(field=field):
                self.assertIn(field, self.skill)

    def test_the_agent_files_exist_for_the_roles_the_skill_spawns(self):
        for path in (LENS_AGENT, ADJUDICATOR_AGENT):
            with self.subTest(path=os.path.basename(path)):
                self.assertTrue(os.path.isfile(path), path)


if __name__ == "__main__":
    unittest.main()
