"""Parallelism in the kernel (ADR-0110).

Three mechanisms, each deterministic, that let a coordinator fan work out
without the ledger, the snapshots or the write guard losing track:

  * `acs notes merge` -- the join for a sliced fan-out (survey slices into
    `authoring.md`, judge slices into `<role>.md`), by `## ` heading
  * `slice=` on a subagent's result -- parallel instances of one agent get
    one snapshot each instead of overwriting each other
  * parallel groups in `ship.yaml` -- a stage whose members may all be in
    progress at once (I1), reported together by `due`
  * the file-map guard with several writers live -- a write is judged against
    its own writer when the payload names it, else the union of live writers

Run:  python3 -m unittest tests.acs.test_parallelism -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))

import acs_lib as lib  # noqa: E402
from acs_lib import run as R  # noqa: E402
from acs_lib import workflow as W  # noqa: E402
from acs_lib._common import GateError  # noqa: E402
from test_file_map_guard import FileMapGuardCase  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


def _write(directory, name, text):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


class NotesMergeTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="acs-notes-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_sections_merge_once_in_first_seen_order_with_slice_markers(self):
        a = _write(self.dir, "authoring-api.md",
                   "# Notes\n\nintro\n\n## Code evidence\n- a\n\n## Open questions\n- q1\n")
        b = _write(self.dir, "authoring-web.md",
                   "# Other title\n\n## Risks\n- r\n\n## Code evidence\n- b\n")
        out = os.path.join(self.dir, "authoring.md")
        report = lib.merge_notes([a, b], out)
        self.assertEqual(report["sections"], ["Code evidence", "Open questions", "Risks"])
        with open(out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith("# Notes\n\nintro"), "the first slice's preamble")
        self.assertNotIn("Other title", text)
        self.assertEqual(text.count("## Code evidence"), 1)
        self.assertLess(text.index("<!-- slice: api -->\n- a"),
                        text.index("<!-- slice: web -->\n- b"))

    def test_slice_ids_may_contain_hyphens(self):
        from acs_lib import notes
        self.assertEqual(notes.slice_ids(["x/impact-reviewer-surface.md",
                                          "x/impact-reviewer-form.md"]), ["surface", "form"])
        self.assertEqual(notes.slice_ids(["authoring-web-app.md", "authoring-api.md"]),
                         ["web-app", "api"])
        self.assertEqual(notes.slice_ids(["reviewer-files.md"]), ["files"])

    def test_a_slice_id_does_not_depend_on_its_neighbours(self):
        """The id is what follows the role name, so slices sharing a leading
        word keep it, and a lone file keeps its whole id."""
        from acs_lib import notes
        self.assertEqual(notes.slice_ids(["authoring-web-app.md", "authoring-web-api.md"]),
                         ["web-app", "web-api"])
        self.assertEqual(notes.slice_ids(["authoring-web-app.md"]), ["web-app"])
        self.assertEqual(notes.slice_ids(["iter-1/implementer-integration.json"]),
                         ["integration"])
        self.assertEqual(notes.slice_ids(["api-contract-orders.md",
                                          "api-contract-users.md"]), ["orders", "users"])

    def test_a_later_slice_keeps_its_opening_prose_but_not_its_title(self):
        text, _order = lib.merge_texts([("a", "# Notes\nintro A\n## X\nx1"),
                                        ("b", "# Notes\nintro B\n## X\nx2")])
        self.assertIn("intro A", text)
        self.assertIn("<!-- slice: b -->\nintro B", text)
        self.assertEqual(text.count("# Notes"), 1)
        self.assertLess(text.index("intro B"), text.index("## X"))

    def test_a_fence_closes_only_on_its_own_character(self):
        _pre, sections = lib.split_sections(
            "```\n## not\n~~~\n## still not\n```\n## Y\ny\n")
        self.assertEqual([h for h, _b in sections], ["Y"])
        _pre, sections = lib.split_sections("````\n```\n## inside\n````\n## Z\n")
        self.assertEqual([h for h, _b in sections], ["Z"])

    def test_a_heading_inside_a_code_fence_is_body_text(self):
        a = _write(self.dir, "reviewer-x.md", "## Findings\n```\n## not a heading\n```\n")
        with open(a, encoding="utf-8") as handle:
            _pre, sections = lib.split_sections(handle.read())
        self.assertEqual([h for h, _b in sections], ["Findings"])

    def test_a_published_deliverable_carries_no_slice_markers(self):
        a = _write(self.dir, "api-contract-orders.md", "## Endpoints\n- GET /orders\n")
        b = _write(self.dir, "api-contract-users.md", "## Endpoints\n- GET /users\n")
        out = os.path.join(self.dir, "api-contract.md")
        lib.merge_notes([a, b], out, markers=False)
        with open(out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("<!-- slice:", text)
        self.assertIn("- GET /orders\n\n- GET /users", text)

    def test_a_missing_slice_fails_the_merge(self):
        """Never "pass with a missing slice"."""
        a = _write(self.dir, "reviewer-a.md", "## Findings\n- none\n")
        with self.assertRaises(GateError):
            lib.merge_notes([a, os.path.join(self.dir, "reviewer-b.md")],
                            os.path.join(self.dir, "reviewer.md"))

    def test_the_cli_prints_one_json_object(self):
        import subprocess
        a = _write(self.dir, "authoring-a.md", "## X\n- 1\n")
        b = _write(self.dir, "authoring-b.md", "## X\n- 2\n")
        out = os.path.join(self.dir, "authoring.md")
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "acs.py"), "notes",
                               "merge", "--out", out, a, b],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["sections"], ["X"])


class SliceSnapshotTest(unittest.TestCase):

    def test_a_sliced_result_lands_in_its_own_snapshot(self):
        self.assertTrue(lib.phase_artifact_path("/R", "create-prd", 1, "surveyor",
                                                slice_id="api")
                        .endswith(os.path.join("iter-1", "surveyor-api-message.xml")))
        self.assertTrue(lib.phase_artifact_path("/R", "create-prd", 1, "surveyor")
                        .endswith(os.path.join("iter-1", "surveyor-message.xml")))

    def test_two_slices_do_not_overwrite_each_other(self):
        tdir = tempfile.mkdtemp(prefix="acs-slice-")
        self.addCleanup(shutil.rmtree, tdir, True)
        paths = set()
        for sid in ("a", "b"):
            message = ('<result skill="create-prd" phase="reviewer" slice="%s" '
                       'iteration="1" status="completed"/>' % sid)
            self.assertEqual(lib.validate_message(message), [])
            paths.add(lib.write_phase_snapshot(tdir, "create-prd", "reviewer", message))
        self.assertEqual(len(paths), 2)

    def test_a_slice_id_must_be_safe_as_a_file_name(self):
        errors = lib.validate_message('<result skill="code" phase="implementer" '
                                      'slice="../x" iteration="1"/>')
        self.assertTrue(any("slice=" in e for e in errors), errors)


class ParallelGroupLedgerTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-group-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        path = _write(self.tmp, "ship.yaml",
                      "version: 3\nsteps:\n  - code\n  - [docs-sync, create-e2e-tests]\n"
                      "  - create-pr\n")
        self.wf = W.validate_workflow_file(path)
        repo = os.path.join(self.tmp, "wk", "acme")
        os.makedirs(repo)
        self.rid, self.rdir, _doc = R.create_run(
            repo, {"kind": "prompt", "text": "x"}, self.wf, path)

    def complete(self, step):
        R.start_step(self.rdir, step, self.wf)
        os.makedirs(R.step_dir(self.rdir, step), exist_ok=True)
        with open(os.path.join(R.step_dir(self.rdir, step), "result.json"), "w") as fh:
            fh.write("{}")
        R.finish_step(self.rdir, step, self.wf, status="completed")

    def test_due_is_every_unfinished_member_of_the_first_open_stage(self):
        self.assertEqual(R.due_steps(R.load_run(self.rdir), self.wf), ["code"])
        self.complete("code")
        doc = R.load_run(self.rdir)
        self.assertEqual(R.due_steps(doc, self.wf), ["docs-sync", "create-e2e-tests"])
        self.assertEqual(R.cursor(doc, self.wf), "docs-sync")

    def test_members_of_one_group_may_run_at_once(self):
        self.complete("code")
        R.start_step(self.rdir, "docs-sync", self.wf)
        R.start_step(self.rdir, "create-e2e-tests", self.wf)
        doc = R.load_run(self.rdir)
        self.assertEqual(sorted(R.in_progress_steps(doc)), ["create-e2e-tests", "docs-sync"])
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertEqual(errors, [])

    def test_the_group_completes_only_when_every_member_has(self):
        self.complete("code")
        self.complete("docs-sync")
        self.assertEqual(R.due_steps(R.load_run(self.rdir), self.wf), ["create-e2e-tests"])
        self.complete("create-e2e-tests")
        self.assertEqual(R.due_steps(R.load_run(self.rdir), self.wf), ["create-pr"])

    def test_steps_of_different_stages_may_not_overlap(self):
        R.start_step(self.rdir, "code", self.wf)
        with self.assertRaises(GateError):
            R.start_step(self.rdir, "docs-sync", self.wf)

    def test_i1_catches_an_overlap_across_stages(self):
        doc = R.load_run(self.rdir)
        doc["steps"] = {"code": {"status": "in_progress"},
                        "create-pr": {"status": "in_progress"}}
        R.save_run(self.rdir, doc)
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertTrue(any(e.startswith("I1") for e in errors), errors)


class MultiWriterGuardTest(FileMapGuardCase):
    """Two skills' writers live at once: a parallel group's members, each
    with its own declared map."""

    def setUp(self):
        super().setUp()
        self.declare("src/a.py", skill="code")
        self.declare("tests/e2e/test_a.py", skill="create-e2e-tests")
        self.spawn_writer("impl-1", "acs:code-implementer")
        self.spawn_writer("tw-1", "acs:create-e2e-tests-test-writer")

    def attempt(self, path, agent_id=None):
        payload = {"cwd": self.repo, "tool_name": "Write", "tool_input": {"file_path": path}}
        if agent_id:
            payload["agent_id"] = agent_id
        return self.hook("file-map", payload)

    def test_an_attributed_write_is_judged_against_its_own_map(self):
        self.assertEqual(self.attempt("src/a.py", "impl-1").returncode, 0)
        self.assertEqual(self.attempt("tests/e2e/test_a.py", "tw-1").returncode, 0)
        self.assertEqual(self.attempt("tests/e2e/test_a.py", "impl-1").returncode, 2,
                         "the implementer may not write the test-writer's file")

    def test_a_judge_that_names_itself_is_not_scoped_by_a_sibling_writer(self):
        """A parallel group puts docs-sync's drift-reviewer beside
        create-e2e-tests' test-writer; the reviewer's report is not the
        test-writer's to scope."""
        self.spawn_writer("dr-1", "acs:docs-sync-drift-reviewer")
        self.assertEqual(self.attempt("anywhere/report.md", "dr-1").returncode, 0)
        self.assertEqual(self.attempt("anywhere/report.md").returncode, 2,
                         "an unattributed call is still judged against the writers")

    def test_an_unattributed_denial_names_and_records_every_mapped_writer(self):
        from acs_lib import filemap
        payload = {"cwd": self.repo, "tool_name": "Write",
                   "tool_input": {"file_path": "src/elsewhere.py"}}
        with mock.patch.object(filemap, "_record_guard_denial") as record, \
                mock.patch.object(filemap, "_warn") as warn:
            self.assertEqual(filemap.file_map_guard(payload), 2)
        self.assertEqual(sorted(call.args[3] for call in record.call_args_list),
                         ["code", "create-e2e-tests"])
        message = warn.call_args.args[0]
        self.assertIn("Declared for /acs:code iteration 1:\n  src/a.py", message)
        self.assertIn("Declared for /acs:create-e2e-tests iteration 1:\n"
                      "  tests/e2e/test_a.py", message)

    def test_an_unattributed_write_is_judged_against_the_union(self):
        self.assertEqual(self.attempt("src/a.py").returncode, 0,
                         "not denied because the other writer started last")
        self.assertEqual(self.attempt("tests/e2e/test_a.py").returncode, 0)
        self.assertEqual(self.attempt("src/elsewhere.py").returncode, 2,
                         "outside every live writer's map")


class MapLessWriterGuardTest(FileMapGuardCase):
    """A writer whose skill declares no map (docs-sync's doc-updater) beside
    one that does (create-e2e-tests' test-writer)."""

    def setUp(self):
        super().setUp()
        self.declare("tests/e2e/", skill="create-e2e-tests")
        self.spawn_writer("tw-1", "acs:create-e2e-tests-test-writer")
        self.spawn_writer("du-1", "acs:docs-sync-doc-updater")

    def attempt(self, path, agent_id=None):
        payload = {"cwd": self.repo, "tool_name": "Write", "tool_input": {"file_path": path}}
        if agent_id:
            payload["agent_id"] = agent_id
        return self.hook("file-map", payload)

    def test_it_does_not_switch_the_mapped_writer_s_guard_off(self):
        self.assertEqual(self.attempt("tests/e2e/test_x.py").returncode, 0)
        self.assertEqual(self.attempt("src/app.py").returncode, 2,
                         "an unattributed write outside the e2e map is denied")

    def test_its_own_attributed_writes_still_pass(self):
        self.assertEqual(self.attempt("docs/guide.md", "du-1").returncode, 0)
        self.assertEqual(self.attempt("src/app.py", "tw-1").returncode, 2)

    def test_its_own_step_directory_stays_writable_unattributed(self):
        target = os.path.join(R.step_dir(self.rdir_path, "docs-sync"), "iter-1",
                              "authoring-general.md")
        self.assertEqual(self.attempt(target).returncode, 0)


class DeriveSliceReportsTest(unittest.TestCase):

    def test_the_integration_implementer_s_red_suite_is_read(self):
        from acs_lib import derive
        tdir = tempfile.mkdtemp(prefix="acs-derive-")
        self.addCleanup(shutil.rmtree, tdir, True)
        idir = os.path.join(R.step_dir(tdir, "code"), "iter-1")
        os.makedirs(idir)
        for name, failed in (("implementer-1.json", 0), ("implementer-2.json", 0),
                             ("implementer-integration.json", 2)):
            with open(os.path.join(idir, name), "w") as fh:
                json.dump({"tests": {"passed": 10, "failed": failed}}, fh)
        names = sorted(os.path.basename(p) for _n, p, _d in derive.execute_reports(tdir, "code"))
        self.assertIn("implementer-integration.json", names)
        value, _why = derive._tests_from_execute_reports(tdir, "code")
        self.assertEqual(value["failed"], 2)


class ParallelGroupRunTest(AcsWorkspaceCase):
    """The run ledger follows the whole group: the lock, SessionEnd and a
    handoff all see every member, not the first."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.walk_to(self.ticket, "review-code")
        for step in ("create-e2e-tests", "docs-sync"):
            out = self.run_script("acs.py", "step", "start", "--step", step,
                                  "--run", self.ticket)
            self.assertEqual(out.returncode, 0, out.stderr)
        self.rdir_path = self.rdir(self.ticket)
        self.assertEqual(sorted(R.in_progress_steps(R.load_run(self.rdir_path))),
                         ["create-e2e-tests", "docs-sync"])

    def finish(self, step):
        vocabulary = lib.outcome_vocabulary(step)
        result = {"status": "completed"}
        if vocabulary:
            result["outcome"] = vocabulary[0]
        return self.post(step, self.ticket, result)

    def test_the_last_member_to_finish_releases_the_lock(self):
        from acs_lib import posthook
        doc = R.load_run(self.rdir_path)
        with mock.patch.object(posthook, "release_lock") as release:
            self.assertFalse(posthook._release_unless_sibling_running(
                self.rdir_path, self.repo, doc))
            release.assert_not_called()
            doc["steps"]["docs-sync"]["status"] = "completed"
            doc["steps"]["create-e2e-tests"]["status"] = "completed"
            self.assertTrue(posthook._release_unless_sibling_running(
                self.rdir_path, self.repo, doc))
            release.assert_called_once()

    def test_session_end_interrupts_every_member(self):
        out = self.run_script("dispatch.py", "session-end",
                              stdin=json.dumps({"cwd": self.repo}))
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = R.load_run(self.rdir_path)
        for step in ("create-e2e-tests", "docs-sync"):
            self.assertEqual(R.step_entry(doc, step)["status"], "interrupted", step)
            self.assertEqual(R.step_entry(doc, step)["stop_reason"], "session_end")
        self.assertFalse(os.path.exists(lib.lock_path(self.rdir_path)))

    def test_the_stop_reminder_names_a_member_that_has_no_result_yet(self):
        first = lib.in_flight_steps(self.rdir_path)[0]
        other = ({"create-e2e-tests", "docs-sync"} - {first}).pop()
        path = lib.result_path(self.rdir_path, first)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump({"status": "completed"}, fh)
        out = self.run_script("dispatch.py", "stop", stdin=json.dumps({"cwd": self.repo}))
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("/acs:%s " % other, out.stderr)

    def test_a_handoff_interrupts_every_member_and_resumes_through_ship(self):
        out = self.run_script("handoff.py", "--summary", "stopping here")
        self.assertEqual(out.returncode, 0, out.stderr)
        report = json.loads(out.stdout)
        self.assertEqual(sorted(report["steps"]), ["create-e2e-tests", "docs-sync"])
        self.assertEqual(report["continue_with"], "/acs:ship %s" % self.ticket)
        doc = R.load_run(self.rdir_path)
        self.assertEqual(R.in_progress_steps(doc), [])
        self.assertFalse(os.path.exists(lib.lock_path(self.rdir_path)))


class DiffJudgeGoesLastTest(unittest.TestCase):
    """docs-sync runs beside create-e2e-tests, so its drift review has to
    judge the diff both leave behind."""

    def read(self, skill):
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "skills", skill, "SKILL.md"),
                  encoding="utf-8") as handle:
            return " ".join(handle.read().split())

    def test_ship_holds_a_diff_reading_judge_until_every_sibling_writer_has_written(self):
        """ADR-0127: writers write, they do not commit; the judge waits on
        the last write, and no member contends for the index."""
        text = self.read("ship")
        self.assertIn("A judge that reads the changeset goes last.", text)
        self.assertIn("spawns only after every sibling writer has written (not committed", text)
        self.assertNotIn("index.lock", text)
        self.assertIn("run that judge once more before the member finishes", text)

    def test_docs_sync_says_its_drift_review_judges_the_final_diff(self):
        text = self.read("docs-sync")
        self.assertIn("In a parallel group, the drift-reviewer judges the FINAL diff.", text)
        self.assertIn("one more drift review before Finish", text)


if __name__ == "__main__":
    unittest.main()
