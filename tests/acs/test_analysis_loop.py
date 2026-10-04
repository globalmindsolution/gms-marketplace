"""The /acs:analyze-requirements controller (ADR-0114): `acs.py analysis <verb>`.

Every transition is driven through the real CLI against a fixture workspace,
with the `<result>` snapshots written where the SubagentStop hook writes them.
Nothing here passes the controller a verdict: each test writes the evidence and
asserts what the controller DERIVED from it.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib

from acs_lib import analysis_loop as L  # noqa: E402

TICKET_TITLE = "Bulk import"

DRAFT = """---
ticket: {tid}
ready_for_planning: true
api_surface: false
needs_design_recommendation: false
---

# Analysis — {tid}: Bulk import

## Problem restated
Imports are slow.
## Impact map
| Path | Component | Change | Evidence |
| --- | --- | --- | --- |
| `src/a.py` | import | faster | `a.py:1` |
## Questions
_None recorded._
## Assumptions
None.
## Risks
None.
## Refined acceptance criteria
All testable.
## Verdict
ready_for_planning: true
"""


class AnalysisLoopCase(AcsWorkspaceCase):
    def setUp(self):
        super().setUp()
        for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
            subprocess.run(["git", "-C", self.repo, "config", key, value], check=True)
        with open(os.path.join(self.repo, "README.md"), "w") as fh:
            fh.write("shop\n")
        subprocess.run(["git", "-C", self.repo, "add", "README.md"], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-qm", "init"], check=True)
        # The analysis is the first commit of the ticket's branch, never the
        # default branch's (publish refuses there: TestPublish).
        subprocess.run(["git", "-C", self.repo, "checkout", "-qb", "feature/ticket"],
                       check=True)
        self.tid = self.new_ticket(TICKET_TITLE, "task")
        out = self.start("analyze-requirements", self.tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.r = self.rdir(self.tid)

    # -- driving the CLI ----------------------------------------------------

    def cli(self, verb, *args, code=0):
        out = self.run_script("acs.py", "analysis", verb, "--run", self.tid, *args)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def next(self):
        return self.cli("next")

    def loop(self):
        return L.load_loop(self.r)

    # -- writing evidence ---------------------------------------------------

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def snapshot(self, phase, iteration, slice_id=None, status="completed", body="",
                 attrs=None, path=None):
        a = {"skill": "analyze-requirements", "phase": phase, "iteration": str(iteration),
             "ticket-id": self.tid, "status": status}
        if slice_id:
            a["slice"] = slice_id
        a.update(attrs or {})
        rendered = " ".join('%s="%s"' % (k, v) for k, v in a.items() if v is not None)
        self.write(path or L.snapshot_path(self.r, iteration, phase, slice_id),
                   "<task/>\n<result %s>%s</result>\n" % (rendered, body))

    def finding(self, text, dimension="completeness", file="analysis.md",
                severity="blocking"):
        return ('<finding severity="%s" dimension="%s" file="%s">%s</finding>'
                % (severity, dimension, file, text))

    def do_survey(self, skip=None):
        for lane in self.loop()["lanes"]:
            if lane["slice"] == skip:
                continue
            self.snapshot(lane["phase"], 1, lane["slice"])
            self.write(L.notes_path(self.r, lane["slice"]),
                       "# Notes\n\n## Impact surface\n%s rows\n" % lane["slice"])
            self.write(L.lane_report_path(self.r, lane), "{}")

    def do_synthesis(self):
        self.snapshot("analyst", 1, "synthesis")
        self.write(L.notes_path(self.r, "synthesis"), "## Synthesis\nNo contradictions.\n")
        self.write(L.iter_path(self.r, 1, "analyst-synthesis.json"), "{}")

    def do_draft(self, n, text=None):
        self.snapshot("analyst", n)
        self.write(L.draft_path(self.r), text if text is not None else DRAFT.format(tid=self.tid))
        self.write(L.iter_path(self.r, n, "analyst.json"), "{}")
        if n >= 2:
            self.write(L.iter_path(self.r, n, "authoring.md"), "## Findings addressed\n-\n")

    def do_review(self, n, findings=None, statuses=None):
        findings, statuses = findings or {}, statuses or {}
        for sid, _dims in L.JUDGE_SLICES:
            body = "<findings>%s</findings>" % "".join(findings.get(sid, ()))
            self.snapshot("impact-reviewer", n, sid, status=statuses.get(sid, "completed"),
                          body=body)
            self.write(L.review_report_path(self.r, n, sid), "## Findings\n%s\n" % sid)

    def to_draft(self, areas=""):
        self.cli("plan", "--areas", areas)
        self.do_survey()
        self.cli("record-survey")
        self.do_synthesis()
        self.cli("record-synthesis")
        self.cli("record-clarify")
        self.assertEqual(self.next()["action"], "draft")

    def to_publish(self):
        self.to_draft()
        self.do_draft(1)
        self.cli("record-draft")
        self.do_review(1)
        out = self.cli("record-review")
        self.assertTrue(out["passed"])
        self.assertEqual(out["next"]["action"], "publish")


class TestTransitions(AnalysisLoopCase):
    def test_next_before_plan_is_plan(self):
        self.assertEqual(self.next()["action"], "plan")

    def test_plan_declares_requirements_lane_and_one_impact_lane_by_default(self):
        out = self.cli("plan")
        self.assertEqual([(l["phase"], l["slice"]) for l in out["lanes"]],
                         [("analyst", "requirements"), ("impact-analyst", "repo")])
        survey = self.next()
        self.assertEqual(survey["action"], "survey")
        self.assertEqual(survey["iteration"], 1)
        self.assertEqual(survey["lanes"][0]["pass"], "requirements")
        self.assertTrue(survey["lanes"][1]["snapshot"].endswith(
            "iter-1/impact-analyst-repo-message.xml"))
        self.assertTrue(survey["lanes"][1]["notes"].endswith("iter-1/authoring-repo.md"))

    def test_plan_one_impact_lane_per_area_reserved_names_prefixed(self):
        out = self.cli("plan", "--areas", "api, web,api,synthesis")
        self.assertEqual([l["slice"] for l in out["lanes"]],
                         ["requirements", "api", "web", "area-synthesis"])

    def test_plan_rejects_bad_area_and_double_plan(self):
        self.cli("plan", "--areas", "a b", code=2)
        self.cli("plan")
        self.cli("plan", code=2)

    def test_full_happy_path(self):
        self.to_draft("api,web")
        joined = self.read(L.notes_path(self.r))
        self.assertIn("<!-- slice: synthesis -->", joined)
        self.assertIn("<!-- slice: web -->", joined)
        draft = self.next()
        self.assertEqual((draft["pass"], draft["findings"]), ("draft", []))
        self.do_draft(1)
        self.assertEqual(self.cli("record-draft")["next"]["action"], "review")
        review = self.next()
        self.assertEqual([s["slice"] for s in review["slices"]], ["surface", "form", "evidence"])
        self.assertEqual([d["name"] for d in review["slices"][1]["dimensions"]],
                         ["front-matter", "structure", "scope"])
        self.do_review(1, findings={"form": [self.finding("nit", severity="advisory")]})
        out = self.cli("record-review")
        self.assertTrue(out["passed"])
        self.assertIn("## De-duplicated findings",
                      self.read(L.review_report_path(self.r, 1)))
        self.assertEqual(self.next()["action"], "publish")
        self.cli("publish")
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")
        done = self.next()
        self.assertEqual(done["action"], "completed")
        self.assertTrue(done["publication"]["verified"])
        self.cli("record-draft", code=2)  # terminal: nothing more to record

    def test_out_of_order_record_is_refused(self):
        self.cli("record-survey", code=2)  # no loop yet
        self.cli("plan")
        self.cli("record-draft", code=2)

    def test_failed_review_goes_to_next_draft_with_findings_verbatim(self):
        self.to_draft()
        self.do_draft(1)
        self.cli("record-draft")
        self.do_review(1, findings={"surface": [self.finding("Missing  src/b.py")],
                                    "evidence": [self.finding("Uncited row", "grounding")]})
        out = self.cli("record-review")
        self.assertFalse(out["passed"])
        nxt = self.next()
        self.assertEqual((nxt["action"], nxt["iteration"]), ("draft", 2))
        self.assertEqual([f["text"] for f in nxt["findings"]], ["Missing  src/b.py", "Uncited row"])
        self.assertTrue(nxt["notes"][1].endswith("iter-2/authoring.md"))

    def test_failed_slice_fails_the_iteration(self):
        self.to_draft()
        self.do_draft(1)
        self.cli("record-draft")
        self.do_review(1, statuses={"form": "failed"})
        out = self.cli("record-review")
        self.assertFalse(out["passed"])
        self.assertEqual(out["blocking"][0]["dimension"], "review-failed")


class TestStallAndCap(AnalysisLoopCase):
    def review_round(self, n, findings):
        self.do_draft(n)
        self.cli("record-draft")
        self.do_review(n, findings=findings)
        return self.cli("record-review")

    def test_identical_blocking_set_stalls(self):
        self.to_draft()
        self.review_round(1, {"surface": [self.finding("A")], "form": [self.finding("B", "scope")]})
        out = self.review_round(2, {"surface": [self.finding("A")],
                                    "form": [self.finding("B", "scope")]})
        self.assertEqual(out["next"]["action"], "failed")
        self.assertEqual(out["next"]["stop_reason"], "stalled")

    def test_reordered_and_rewhitespaced_identical_set_stalls(self):
        self.to_draft()
        self.review_round(1, {"surface": [self.finding("A  one"), self.finding("B", "scope")]})
        out = self.review_round(2, {"evidence": [self.finding("B", "scope")],
                                    "form": [self.finding(" A\none ")]})
        self.assertEqual(out["next"]["stop_reason"], "stalled")

    def test_different_set_drafts_again_then_cap(self):
        self.to_draft()
        self.review_round(1, {"surface": [self.finding("A")]})
        out = self.review_round(2, {"surface": [self.finding("A"), self.finding("C")]})
        self.assertEqual((out["next"]["action"], out["next"]["iteration"]), ("draft", 3))
        out = self.review_round(3, {"surface": [self.finding("D")]})
        self.assertEqual((out["next"]["action"], out["next"]["stop_reason"]), ("failed", "cap"))
        self.assertEqual(self.loop()["iteration"], 3)

    def test_duplicates_within_an_iteration_are_deduped(self):
        self.to_draft()
        out = self.review_round(1, {"surface": [self.finding("Same")],
                                    "evidence": [self.finding("Same")]})
        self.assertEqual(len(out["blocking"]), 1)
        self.assertIn("duplicate of surface",
                      self.read(L.review_report_path(self.r, 1)))


class TestBlocked(AnalysisLoopCase):
    def assert_blocked(self, out, needle, kind="machinery"):
        nxt = out["next"]
        self.assertEqual(nxt["action"], "blocked", nxt)
        self.assertEqual(nxt["kind"], kind)
        self.assertIn(needle, nxt["reason"])
        self.assertFalse(out["recorded"])

    def test_missing_snapshot_blocks_then_retry_clears(self):
        self.cli("plan")
        self.do_survey(skip="repo")
        self.assert_blocked(self.cli("record-survey"), "missing <result> snapshot")
        self.assertEqual(self.next()["retry"], "survey")
        self.do_survey()
        self.assertEqual(self.cli("record-survey")["next"]["action"], "synthesize")

    def test_wrong_attributes_block(self):
        self.cli("plan")
        self.do_survey()
        lane = self.loop()["lanes"][1]
        for attrs, needle in (({"slice": "web"}, "slice='web'"),
                              ({"iteration": "2"}, "iteration='2'"),
                              ({"phase": "analyst"}, "phase='analyst'"),
                              ({"skill": "code"}, "skill='code'"),
                              ({"ticket-id": "SHOP-99"}, "ticket-id"),
                              ({"status": "maybe"}, "status='maybe'")):
            self.snapshot(lane["phase"], 1, lane["slice"], attrs=attrs,
                          path=L.snapshot_path(self.r, 1, lane["phase"], lane["slice"]))
            self.assert_blocked(self.cli("record-survey"), needle)

    def test_malformed_snapshot_blocks(self):
        self.cli("plan")
        self.do_survey()
        path = L.snapshot_path(self.r, 1, "analyst", "requirements")
        self.write(path, "prose only")
        self.assert_blocked(self.cli("record-survey"), "no <result> element")
        self.write(path, '<result skill="analyze-requirements" iteration="x"></result>')
        self.assert_blocked(self.cli("record-survey"), "malformed")

    def test_missing_artifact_and_bad_report_block(self):
        self.cli("plan")
        self.do_survey()
        os.unlink(L.notes_path(self.r, "repo"))
        self.assert_blocked(self.cli("record-survey"), "missing artifact")
        self.do_survey()
        self.write(L.lane_report_path(self.r, self.loop()["lanes"][0]), "[]")
        self.assert_blocked(self.cli("record-survey"), "not a JSON object")

    def test_agent_failed_and_needs_input_in_survey(self):
        self.cli("plan")
        self.do_survey()
        self.snapshot("analyst", 1, "requirements", status="failed",
                      body="<errors><error>ticket unreadable</error></errors>")
        self.assert_blocked(self.cli("record-survey"), "ticket unreadable", "agent_failed")
        self.snapshot("analyst", 1, "requirements", status="needs_input")
        self.assert_blocked(self.cli("record-survey"), "needs_input", "needs_input")

    def test_synthesis_blocks(self):
        self.cli("plan")
        self.do_survey()
        self.cli("record-survey")
        self.assert_blocked(self.cli("record-synthesis"), "missing <result> snapshot")
        self.snapshot("analyst", 1, "synthesis", status="failed")
        self.assert_blocked(self.cli("record-synthesis"), "status=failed", "agent_failed")
        self.do_synthesis()
        os.unlink(L.notes_path(self.r, "synthesis"))
        self.assert_blocked(self.cli("record-synthesis"), "missing artifact")

    def test_blocking_open_question_still_publishes_then_blocks_needs_input(self):
        """references/not-ready-for-planning.md: the not-ready analysis is
        drafted, reviewed and published, and the loop ends blocked."""
        self.cli("plan")
        self.do_survey()
        self.cli("record-survey")
        self.do_synthesis()
        self.cli("record-synthesis")
        nxt = self.cli("record-clarify", "--blocking-open")["next"]
        self.assertEqual(nxt["action"], "draft")
        self.assertIn("not-ready-for-planning", nxt["not_ready"])
        self.do_draft(1, text=DRAFT.format(tid=self.tid).replace(
            "ready_for_planning: true\napi", "ready_for_planning: false\napi"))
        self.cli("record-draft")
        self.do_review(1)
        self.cli("record-review")
        self.cli("publish")
        end = self.cli("record-publication")["next"]
        self.assertEqual((end["action"], end["kind"], end["retry"]),
                         ("blocked", "needs_input", None))
        self.assertTrue(end["publication"]["verified"])
        doc = lib.load_state(self.r, "analyze-requirements", self.tid)
        doc["invocations"][-1].update(status="interrupted", stop_reason="needs_input")
        lib.save_state(self.r, "analyze-requirements", doc)
        lib.append_invocation(self.r, "analyze-requirements", self.tid)
        self.assertEqual(self.next()["action"], "plan")

    def test_a_later_clarify_without_the_flag_clears_not_ready(self):
        self.to_draft()
        self.snapshot("analyst", 1, status="needs_input")
        self.cli("record-draft")
        self.cli("record-clarify", "--blocking-open")
        self.snapshot("analyst", 1, status="needs_input")
        self.cli("record-draft")
        self.assertIsNone(self.cli("record-clarify")["next"]["not_ready"])

    def test_draft_needs_input_returns_to_clarify_without_spending_iteration(self):
        self.to_draft()
        self.snapshot("analyst", 1, status="needs_input",
                      body="<questions><question>Which format?</question></questions>")
        out = self.cli("record-draft")
        self.assert_blocked(out, "Which format?", "needs_input")
        self.assertEqual(out["next"]["retry"], "clarify")
        nxt = self.cli("record-clarify")["next"]
        self.assertEqual((nxt["action"], nxt["iteration"]), ("draft", 1))

    def test_draft_and_review_machinery_blocks_spend_nothing(self):
        self.to_draft()
        self.assert_blocked(self.cli("record-draft"), "missing <result> snapshot")
        self.do_draft(1)
        os.unlink(L.iter_path(self.r, 1, "analyst.json"))
        self.assert_blocked(self.cli("record-draft"), "missing artifact")
        self.do_draft(1)
        self.cli("record-draft")
        self.do_review(1)
        os.unlink(L.snapshot_path(self.r, 1, "impact-reviewer", "evidence"))
        self.assert_blocked(self.cli("record-review"), "impact-reviewer-evidence-message.xml")
        os.unlink(L.review_report_path(self.r, 1, "form"))
        self.do_review(1)
        os.unlink(L.review_report_path(self.r, 1, "form"))
        self.assert_blocked(self.cli("record-review"), "impact-reviewer-form.md")
        self.do_review(1, statuses={"surface": "needs_input"})
        self.assert_blocked(self.cli("record-review"), "needs_input", "needs_input")
        self.assertEqual(self.loop()["iteration"], 1)
        self.assertEqual(self.loop()["history"], [])
        self.do_review(1)
        self.assertTrue(self.cli("record-review")["passed"])

    def test_draft_on_second_iteration_needs_its_notes(self):
        self.to_draft()
        self.do_draft(1)
        self.cli("record-draft")
        self.do_review(1, findings={"surface": [self.finding("A")]})
        self.cli("record-review")
        self.do_draft(2)
        os.unlink(L.iter_path(self.r, 2, "authoring.md"))
        self.assert_blocked(self.cli("record-draft"), "iter-2/authoring.md")


class TestPublish(AnalysisLoopCase):
    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo] + list(args), capture_output=True,
                              text=True, check=True).stdout

    def test_publish_refuses_the_default_branch_and_writes_nothing(self):
        self.to_publish()
        self.git("checkout", "-q", "master")
        head = self.git("rev-parse", "HEAD")
        out = self.run_script("acs.py", "analysis", "publish", "--run", self.tid)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("default branch", out.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertFalse(os.path.exists(
            os.path.join(self.repo, "docs", "tickets", self.tid, "analysis.md")))

    def test_publish_refuses_a_detached_head(self):
        self.to_publish()
        self.git("checkout", "-q", "--detach")
        out = self.run_script("acs.py", "analysis", "publish", "--run", self.tid)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("detached", out.stderr)

    def test_publish_copies_exact_bytes_commits_docs_folder_only_never_pushes(self):
        bare = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        self.git("remote", "set-url", "--push", "origin", bare)
        self.to_publish()
        with open(os.path.join(self.repo, "other.txt"), "w") as fh:
            fh.write("unrelated\n")
        self.git("add", "other.txt")
        docs = os.path.join(self.repo, "docs", "tickets", self.tid)
        os.makedirs(docs, exist_ok=True)
        with open(os.path.join(docs, "ticket.md"), "w") as fh:
            fh.write("# ticket\n")
        out = self.cli("publish")
        pub = out["publication"]
        self.assertEqual(pub["path"], os.path.join(docs, "analysis.md"))
        with open(pub["path"], "rb") as a, open(L.draft_path(self.r), "rb") as b:
            self.assertEqual(a.read(), b.read())
        files = self.git("show", "--name-only", "--format=", "HEAD").split()
        self.assertEqual(sorted(files), ["docs/tickets/%s/analysis.md" % self.tid,
                                         "docs/tickets/%s/ticket.md" % self.tid])
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(),
                         "%s Add requirements analysis" % self.tid)
        self.assertIn("other.txt", self.git("diff", "--cached", "--name-only"))
        self.assertEqual(subprocess.run(["git", "-C", bare, "for-each-ref"], capture_output=True,
                                        text=True).stdout, "")
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")

    def test_publish_refused_unless_review_passed(self):
        self.to_draft()
        self.cli("publish", code=2)

    def test_draft_checks_run_beside_the_review_and_fail_its_iteration(self):
        """ADR-0125: the deterministic checks run when the draft is recorded,
        not after a passing review, and their findings fail THAT iteration even
        when every judge slice passed -- so nothing reaches publish unchecked."""
        self.to_draft()
        self.do_draft(1, text=DRAFT.format(tid=self.tid).replace("## Risks\n", ""))
        review = self.cli("record-draft")["next"]
        self.assertEqual(review["action"], "review")
        self.assertEqual([f["dimension"] for f in review["draft_checks"]], ["structure"])
        self.do_review(1)
        out = self.cli("record-review")
        self.assertFalse(out["passed"])
        self.assertEqual(out["blocking"][0]["slice"], "draft-checks")
        self.cli("publish", code=2)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs", "tickets", self.tid,
                                                     "analysis.md")))
        nxt = self.next()
        self.assertEqual((nxt["action"], nxt["iteration"]), ("draft", 2))
        self.assertEqual(nxt["findings"][0]["dimension"], "structure")

    def test_a_clean_draft_records_no_check_findings(self):
        self.to_draft()
        self.do_draft(1)
        self.assertEqual(self.cli("record-draft")["next"]["draft_checks"], [])

    def test_a_loop_recorded_before_the_checks_moved_still_gets_them(self):
        """A draft recorded by an older acs carries no `checks`; the review
        runs them over the same bytes rather than passing unchecked."""
        self.to_draft()
        self.do_draft(1, text=DRAFT.format(tid=self.tid).replace("## Risks\n", ""))
        self.cli("record-draft")
        loop = self.loop()
        del loop["draft"]["checks"]
        L.save_loop(self.r, loop)
        self.do_review(1)
        self.assertFalse(self.cli("record-review")["passed"])

    def test_publish_refuses_a_draft_changed_after_review(self):
        self.to_publish()
        with open(L.draft_path(self.r), "a") as fh:
            fh.write("\nsneaky\n")
        self.cli("publish", code=2)

    def test_record_publication_derives_from_disk(self):
        self.to_publish()
        out = self.cli("record-publication")
        self.assertEqual(out["next"]["action"], "blocked")
        self.assertIn("nothing published", out["next"]["reason"])
        self.cli("publish")
        path = self.loop()["publication"]["path"]
        with open(path, "a") as fh:
            fh.write("edit\n")
        self.assertIn("not the reviewed bytes", self.cli("record-publication")["next"]["reason"])
        os.unlink(path)
        self.assertIn("is missing", self.cli("record-publication")["next"]["reason"])

    def test_record_publication_requires_the_commit(self):
        self.to_publish()
        self.cli("publish")
        self.git("reset", "-q", "--soft", "HEAD~1")
        out = self.cli("record-publication")
        self.assertIn("HEAD does not carry", out["next"]["reason"])

    def test_republish_of_identical_bytes_makes_no_new_commit(self):
        self.to_publish()
        self.cli("publish")
        head = self.git("rev-parse", "HEAD")
        out = self.cli("publish")
        self.assertFalse(out["publication"]["committed"])
        self.assertEqual(self.git("rev-parse", "HEAD"), head)


class TestReadOnlyAndRestart(AnalysisLoopCase):
    def tree(self):
        out = {}
        for root, _dirs, files in os.walk(self.r):
            for name in files:
                path = os.path.join(root, name)
                with open(path, "rb") as fh:
                    out[path] = (fh.read(), os.stat(path).st_mtime_ns)
        return out

    def test_next_writes_nothing(self):
        before = self.tree()
        self.next()
        self.assertEqual(self.tree(), before)
        self.cli("plan")
        self.do_survey()
        before = self.tree()
        for _ in range(2):
            self.assertEqual(self.next()["action"], "survey")
        self.assertEqual(self.tree(), before)

    def test_a_new_invocation_after_a_terminal_loop_plans_afresh(self):
        self.to_publish()
        self.cli("publish")
        self.cli("record-publication")
        self.assertEqual(self.next()["action"], "completed")
        lib.append_invocation(self.r, "analyze-requirements", self.tid)  # still open: no-op
        doc = lib.load_state(self.r, "analyze-requirements", self.tid)
        doc["invocations"][-1]["status"] = "completed"
        lib.save_state(self.r, "analyze-requirements", doc)
        lib.append_invocation(self.r, "analyze-requirements", self.tid)
        self.assertEqual(self.next()["action"], "plan")
        self.assertEqual(self.cli("plan")["next"]["action"], "survey")

    def test_a_loop_whose_invocation_was_interrupted_resumes_to_finish(self):
        self.to_publish()
        self.cli("publish")
        self.cli("record-publication")
        doc = lib.load_state(self.r, "analyze-requirements", self.tid)
        doc["invocations"][-1]["status"] = "interrupted"
        lib.save_state(self.r, "analyze-requirements", doc)
        lib.append_invocation(self.r, "analyze-requirements", self.tid)
        self.assertEqual(self.next()["action"], "completed")
        self.cli("plan", code=2)

    def test_run_without_ticket_subject_is_refused(self):
        out = self.run_script("acs.py", "analysis", "next", "--run", "NOPE-1")
        self.assertEqual(out.returncode, 2)


class TestLibraryUnits(unittest.TestCase):
    def test_area_slices(self):
        self.assertEqual(L.area_slices([]), [{"area": None, "slice": "repo"}])
        self.assertEqual(L.area_slices(["api/", "repo"]),
                         [{"area": "api", "slice": "api"}, {"area": "repo", "slice": "area-repo"}])
        with self.assertRaises(lib.GateError):
            L.area_slices(["x" * 41])

    def test_blocking_set_is_order_and_whitespace_insensitive(self):
        a = {"blocking": [{"dimension": "d", "file": "f", "text": "x  y"},
                          {"dimension": "e", "file": "f", "text": "z"}]}
        b = {"blocking": [{"dimension": "e", "file": "f", "text": "z\n"},
                          {"dimension": "d", "file": "f", "text": " x y"}]}
        self.assertEqual(L.blocking_set(a), L.blocking_set(b))
        c = {"blocking": [{"dimension": "d", "file": "g", "text": "x y"}]}
        self.assertNotEqual(L.blocking_set(a), L.blocking_set(c))

    def test_actions_cover_the_adr(self):
        for action in ("survey", "synthesize", "clarify", "draft", "review", "publish",
                       "completed", "blocked", "failed"):
            self.assertIn(action, L.ACTIONS)

    def test_save_loop_refuses_an_invalid_document(self):
        with self.assertRaises(lib.GateError):
            L.save_loop("/nonexistent", {"phase": "nope"})
