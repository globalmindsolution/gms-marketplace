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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))

import acs_lib as lib  # noqa: E402
from acs_lib import run as R  # noqa: E402
from acs_lib import workflow as W  # noqa: E402
from acs_lib._common import GateError  # noqa: E402
from test_file_map_guard import FileMapGuardCase  # noqa: E402


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

    def test_an_unattributed_write_is_judged_against_the_union(self):
        self.assertEqual(self.attempt("src/a.py").returncode, 0,
                         "not denied because the other writer started last")
        self.assertEqual(self.attempt("tests/e2e/test_a.py").returncode, 0)
        self.assertEqual(self.attempt("src/elsewhere.py").returncode, 2,
                         "outside every live writer's map")


if __name__ == "__main__":
    unittest.main()
