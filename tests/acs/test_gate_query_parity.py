"""`acs gate` answers exactly what the pre-hook would, and still writes nothing.

Originating ticket: MAR-586. `acs gate --skill <s>` is documented as running a
skill's pre-gate without running the skill, and the recorded GATE cases invoke
it while asserting the HOOK's stderr -- because the two were historically the
same answer. They had stopped being: with `mutate=False` and no run yet,
`resolve_run_for` returned `(None, None, wf)` and `gate_step` returned before
the lock check, the invariants, the input check and every safety brake, so the
query reported `{"ok": true}` on an epic the hook refuses outright.

This module pins both halves of the restoration at once, because either alone
is a bug:

  * the query's exit code and stderr equal the hook's, for the same subject,
    compared in two INDEPENDENT sandboxes -- the hook mutates, so asking both
    in one workspace would compare the query against a state the hook had
    already changed, which is the ordering artefact that hid the defect;
  * the query still creates no run, takes no lock, opens no step and settles
    no no-op: the whole workspace tree is hashed before and after and must be
    byte-identical.

Stdlib-only. Run:  python3 -m unittest tests.acs.test_gate_query_parity -v
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

from acs_lib import run as run_machine  # noqa: E402

lib = acs_case.lib

#: A plan whose `## Contract` owes no e2e -- the input to the no-op decision
#: the query must be able to READ without RECORDING.
PLAN_OWING_NO_E2E = """# Plan

Restore the pre-hook gate.

## Contract
delivery_path: standard
owes:
  api_contract: false
  test_cases: true
  e2e: false
  reason: "a pre-hook gate has no browser flow"

### Executor tasks & file map
- task 1: src/acs/hooks/scripts/acs_lib/gates.py
"""


class GateQueryCase(acs_case.AcsWorkspaceCase):
    """Fixture: the standard workspace, plus a twin of it for the hook to dirty."""

    def twin(self):
        """A second, independent sandbox holding byte-identical state.

        The hook WRITES -- a run, a lock, a pointer, a session marker. Driving
        it and the query in one workspace would let whichever ran first decide
        what the second one sees, which is exactly how this defect stayed
        invisible: run the hook first and a run exists, so the query then
        answers correctly. The twin is copied before either runs.
        """
        base = tempfile.mkdtemp(prefix="acs-twin-")
        self.addCleanup(shutil.rmtree, base, True)
        repo, ws = os.path.join(base, "shop"), os.path.join(base, "workspace")
        shutil.copytree(self.repo, repo)
        shutil.copytree(self.ws, ws)
        with open(os.path.join(repo, ".acs", "settings.local.json"), "w") as fh:
            json.dump({"workspace_path": ws}, fh)
        return repo

    def query(self, skill, ticket=None, cwd=None):
        """`acs gate --skill <s> [--ticket <id>]`, the way a human asks."""
        argv = ["gate", "--skill", skill]
        if ticket:
            argv += ["--ticket", ticket]
        return self.run_script("acs.py", *argv, cwd=cwd or self.repo)

    def snapshot(self, root):
        """Every path under `root`, with each file's bytes digested.

        One assertion instead of six named-file checks, so a seventh side
        effect cannot slip past: no run, no lock, no runs-index, no pointer,
        no step state, no session marker, and nothing not yet invented.
        """
        out = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(dirnames):
                out[os.path.relpath(os.path.join(dirpath, name), root) + "/"] = "<dir>"
            for name in sorted(filenames):
                path = os.path.join(dirpath, name)
                with open(path, "rb") as fh:
                    out[os.path.relpath(path, root)] = hashlib.sha256(fh.read()).hexdigest()
        return out


class GateQueryParityTest(GateQueryCase):
    """The query is a faithful dry-run of the hook: same exit code, same stderr."""

    def assert_parity(self, skill, args_text):
        hook = self.pre(skill, args_text, cwd=self.twin())
        query = self.query(skill, args_text or None)
        self.assertEqual(
            query.returncode, hook.returncode,
            "acs gate --skill %s exited %s where pre-%s.py exited %s\nquery stderr: %r\n"
            "hook stderr: %r" % (skill, query.returncode, skill, hook.returncode,
                                 query.stderr, hook.stderr))
        self.assertEqual(query.stderr, hook.stderr)
        return query

    def test_gate_matches_the_hook_on_an_epic_for_code(self):
        """R-1, the regression proof: the query used to exit 0 on an epic."""
        epic = self.new_ticket("Checkout revamp", "epic")
        out = self.assert_parity("code", epic)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs pre-code: blocked", out.stderr)
        self.assertIn(
            "ticket %s is an epic — epics are never implemented directly; run "
            "/acs:create-design %s first if the epic has no design yet, then break it "
            "down into child tickets with /acs:create-ticket %s (epic fan-out), then "
            "run /acs:code on a child." % (epic, epic, epic), out.stderr)
        self.assertIn("no plan for this run", out.stderr)
        self.assertEqual(json.loads(out.stdout), {"ok": False, "skill": "code",
                                                  "exit_code": 2})

    def test_gate_matches_the_hook_for_merge_pr_and_create_design(self):
        """The two non-step gates answer the same way through either door."""
        ticket = self.new_ticket("Add user login", "task")
        for skill in ("merge-pr", "create-design"):
            with self.subTest(skill=skill):
                out = self.assert_parity(skill, ticket)
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertIn("acs pre-%s: blocked" % skill, out.stderr)

    def test_gate_prints_the_out_of_order_advisory_the_hook_prints(self):
        """Equality with the hook, never a hard-coded sentence.

        The advisory's wording is not this ticket's to change, so the assertion
        is that the two sides agree -- which stays true whichever line
        `render_advisory` produces, and cannot be used to smuggle a wording
        change through.
        """
        ticket = self.new_ticket("Add user login", "task")
        out = self.assert_parity("docs-sync", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(lib.ADVISORY_MARK, out.stderr)
        self.assertIn(ticket, out.stderr)


class GateQueryIsSideEffectFreeTest(GateQueryCase):
    """Sight is restored through a projection, so the query still writes nothing."""

    def test_gate_creates_no_run_no_lock_no_step(self):
        ticket = self.new_ticket("Add user login", "task")
        runs = os.path.join(lib.repo_dir(self.ws, "acme-shop"), "runs")
        for skill in ("code", "create-pr", "merge-pr", "create-design"):
            with self.subTest(skill=skill):
                before = self.snapshot(self.ws)
                self.query(skill, ticket)
                self.assertEqual(self.snapshot(self.ws), before,
                                 "acs gate --skill %s wrote to the workspace" % skill)
                self.assertFalse(os.path.exists(runs),
                                 "acs gate --skill %s opened a run at %s" % (skill, runs))

    def test_gate_settles_no_no_op_for_create_e2e_tests(self):
        """The specific bug `mutate=False` fixed: asking about a step that owes
        nothing used to COMPLETE it, so the step could never afterwards run."""
        ticket = self.new_ticket("Add user login", "task")
        rdir = self.ensure_run(ticket)
        plan = run_machine.artifact_path(rdir, "plan", None, self.workflow())
        os.makedirs(os.path.dirname(plan), exist_ok=True)
        with open(plan, "w", encoding="utf-8") as fh:
            fh.write(PLAN_OWING_NO_E2E)

        before = self.snapshot(self.ws)
        out = self.query("create-e2e-tests", ticket)

        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("nothing to do on this run", out.stderr)
        self.assertEqual(self.snapshot(self.ws), before,
                         "the query recorded the no-op it was only asked about")
        self.assertFalse(os.path.isfile(lib.state_path(rdir, "create-e2e-tests")),
                         "create-e2e-tests was completed by a question about it")
        doc = lib.require_run(rdir)
        self.assertNotIn("create-e2e-tests", doc.get("steps") or {})


class ProjectedRunTest(unittest.TestCase):
    """The projection is the document `create_run` would have written."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-projected-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.wf_path = lib.default_workflow_path()
        self.wf = lib.validate_workflow_file(self.wf_path)
        self.subject = {"kind": "ticket", "ticket_id": "SHOP-1"}

    def test_a_projection_writes_nothing_and_is_not_a_run(self):
        run_id, rdir, doc = lib.projected_run(self.repo, self.subject, self.wf,
                                              self.wf_path)
        self.assertEqual(run_id, "SHOP-1")
        self.assertEqual(doc["run_id"], "SHOP-1")
        self.assertEqual(doc["cursor"], lib.steps_of(self.wf)[0])
        self.assertFalse(os.path.exists(rdir), "the projection created %s" % rdir)
        self.assertIsNone(lib.load_run(rdir))

    def test_the_projection_and_a_real_run_cannot_drift(self):
        """`create_run` builds its document THROUGH the projection, so the two
        agree by construction rather than by a reviewer noticing."""
        _run_id, _rdir, projected = lib.projected_run(self.repo, self.subject,
                                                      self.wf, self.wf_path)
        _run_id, rdir, created = lib.create_run(self.repo, self.subject, self.wf,
                                                self.wf_path)
        self.assertTrue(os.path.isdir(rdir))
        volatile = ("started_at",)
        self.assertEqual({k: v for k, v in created.items() if k not in volatile},
                         {k: v for k, v in projected.items() if k not in volatile})


if __name__ == "__main__":
    unittest.main()
