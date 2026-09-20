"""Behavior tests for statusline.py's never-crash fallback branches: the
missing-partition line, the product-flow step filter, the design-step
visibility rule (parent-owned vs. standalone), the cost/foreign-lock
suffixes, and the doubly-nested main() handler when even fallback() raises.

Originating ticket: MAR-178. Before this module none of these branches were
exercised in-process -- the existing suite drives statusline.py only through
a subprocess and only asserts exit code, never render()'s return value.
Fixtures mint tickets and pipeline state in-process via acs_case.lib (never
through new-ticket.py's subprocess) -- this seam needs no subprocess at all.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402
import cost_sampler  # noqa: E402

MODULE_FILENAME = "statusline.py"
REPO_ID = "acme-shop"


def seed_run(case, run_id, steps=None, cost=None):
    """A run on disk plus the pointer naming it, the way a real invocation
    leaves them. The run's id IS its ticket id when the subject is a ticket
    (§4.2), so one argument names both."""
    repo = acs_case.lib.repo_dir(case.ws, REPO_ID)
    rdir = acs_case.lib.run_dir(repo, run_id)
    wf, wf_path = acs_case.lib.workflow_for(
        acs_case.lib.build_context(case.repo), with_path=True)
    acs_case.lib.create_run(repo, {"kind": "ticket", "ticket_id": run_id},
                            wf, wf_path, run_id=run_id)
    if steps or cost is not None:
        doc = acs_case.lib.load_run(rdir)
        for step, status in (steps or {}).items():
            doc["steps"][step] = {"status": status}
        if cost is not None:
            doc.setdefault("totals", {})["cost_usd"] = cost
        acs_case.lib.write_json(os.path.join(rdir, "run.json"), doc)
    acs_case.lib.save_pointer(repo, acs_case.lib.checkout_id(case.repo), run_id=run_id)
    return rdir


class TestNoRunOnDiskFallback(acs_case.AcsWorkspaceCase):
    """A pointer naming a run that is not on disk renders the fallback line
    plus a suffix saying so -- never a crash, and never a blank line that
    leaves the reader guessing which of the two it was."""

    def test_pointer_without_a_run_renders_the_no_run_line(self):
        acs_case.lib.save_pointer(
            acs_case.lib.repo_dir(self.ws, REPO_ID),
            acs_case.lib.checkout_id(self.repo), run_id="SHOP-404")
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        self.assertEqual(
            mod.render(payload), "Opus · shop · acs: SHOP-404 (no run on disk)")

    def test_no_pointer_at_all_says_there_is_no_active_run(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        self.assertEqual(mod.render(payload), "Opus · shop · acs: no active run")


class TestTheWorkflowIsTheStepList(acs_case.AcsWorkspaceCase):
    """The row is `ship.yaml`'s list with a glyph each. Membership and order
    are the workflow's, so a new workflow changes the status line by itself
    -- there is no second list here to keep level with it."""

    def test_every_workflow_step_gets_a_glyph_in_workflow_order(self):
        seed_run(self, "SHOP-7", steps={"analyze-requirements": "completed",
                                        "create-impl-plan": "in_progress"})
        mod = acs_case.load_module(MODULE_FILENAME)
        rendered = mod.render({"model": {"display_name": "Opus"}, "cwd": self.repo})
        self.assertEqual(
            rendered,
            "Opus · SHOP-7 · ✓requirements ▶plan ○contract ○cases ○code ○review "
            "○e2e ○e2e-run ○docs ○pr")

    def test_the_labels_come_from_the_workflow_not_a_hardcoded_table(self):
        wf = acs_case.lib.validate_workflow_file(acs_case.lib.default_workflow_path())
        mod = acs_case.load_module(MODULE_FILENAME)
        seed_run(self, "SHOP-12")
        rendered = mod.render({"model": {"display_name": "Opus"}, "cwd": self.repo})
        for step in acs_case.lib.steps_of(wf):
            with self.subTest(step=step):
                self.assertIn(mod.short(step), rendered)


class TestReviewIterationSuffix(acs_case.AcsWorkspaceCase):
    """The one number worth a reader's attention mid-run: which review round
    this is, and what the cap is."""

    def test_the_suffix_appears_only_past_the_first_iteration(self):
        rdir = seed_run(self, "SHOP-13")
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        self.assertNotIn("review 1/", mod.render(payload))

        doc = acs_case.lib.load_run(rdir)
        doc["loops"] = {"review-code": {"iteration": 2, "max": 3}}
        acs_case.lib.write_json(os.path.join(rdir, "run.json"), doc)
        self.assertIn("review 2/3", mod.render(payload))


class TestCostAndLockSuffixes(acs_case.AcsWorkspaceCase):
    """The cost suffix appears only when cost is non-zero, and the lock suffix
    only when the lock is held by a different checkout."""

    def test_cost_and_foreign_lock_suffixes_appear_only_when_they_apply(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}

        rdir = seed_run(self, "SHOP-10", cost=4.21)
        acs_case.lib.write_json(
            acs_case.lib.lock_path(rdir), {"checkout_id": "other-session-ckid"})
        rendered = mod.render(payload)
        self.assertIn("~$4.21", rendered)
        self.assertIn("🔒other session", rendered)

        quiet = seed_run(self, "SHOP-11")
        acs_case.lib.acquire_lock(quiet, self.repo)
        rendered = mod.render(payload)
        self.assertNotIn("~$", rendered)
        self.assertNotIn("🔒", rendered,
                         "our own lock is not news; only a foreign one is")


class TestMainNeverCrashes(unittest.TestCase):
    """100-107: when render() raises and fallback() also raises, main()
    prints the irreducible literal "Claude" rather than letting either
    exception escape."""

    def test_main_prints_the_irreducible_line_when_even_the_fallback_raises(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        tmp = tempfile.mkdtemp(prefix="acs-statusline-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with acs_case.pushd(tmp), \
                mock.patch.object(mod, "fallback", side_effect=RuntimeError("boom")):
            code, out, err = acs_case.run_main(mod, [], stdin="[]")
        self.assertEqual(code, 0)
        self.assertEqual(out, "Claude\n")

    def test_a_non_dict_payload_renders_the_fallback_line_not_the_irreducible_one(self):
        """MAR-520: the payload accessors moved to claude_code_adapter are
        total, so a payload that is valid JSON but not an object (here a
        list) degrades to the normal fallback line -- model plus the cwd's
        basename -- instead of reaching main()'s last-ditch handler. The
        handler above still stands for anything that does raise."""
        mod = acs_case.load_module(MODULE_FILENAME)
        tmp = tempfile.mkdtemp(prefix="acs-statusline-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with acs_case.pushd(tmp):
            code, out, err = acs_case.run_main(mod, [], stdin="[]")
        self.assertEqual(code, 0)
        self.assertEqual(out, "Claude · %s\n" % os.path.basename(tmp))


class TestCostSamplerWiring(acs_case.AcsWorkspaceCase):
    """cost_sampler.record_cost_sample is invoked from main(), independent of
    render()'s early-return paths (no active run, a pointer naming a run that
    is not on disk) -- and a raising sampler never breaks the printed line
    (G7 never-crash)."""

    def test_record_cost_sample_called_with_no_active_run(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        with mock.patch("cost_sampler.record_cost_sample") as record:
            with acs_case.pushd(self.repo):
                code, out, err = acs_case.run_main(mod, [], stdin=json.dumps(payload))
        self.assertEqual(code, 0)
        record.assert_called_once_with(payload)
        self.assertIn("no active run", out)

    def test_record_cost_sample_called_when_the_pointer_names_no_run_on_disk(self):
        acs_case.lib.save_pointer(
            acs_case.lib.repo_dir(self.ws, REPO_ID),
            acs_case.lib.checkout_id(self.repo), run_id="SHOP-404")
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        with mock.patch("cost_sampler.record_cost_sample") as record:
            with acs_case.pushd(self.repo):
                code, out, err = acs_case.run_main(mod, [], stdin=json.dumps(payload))
        self.assertEqual(code, 0)
        record.assert_called_once_with(payload)
        self.assertIn("no run on disk", out)

    def test_a_raising_sampler_never_breaks_the_status_line(self):
        seed_run(self, "SHOP-20")
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        with mock.patch("cost_sampler.record_cost_sample", side_effect=RuntimeError("boom")):
            with acs_case.pushd(self.repo):
                code, out, err = acs_case.run_main(mod, [], stdin=json.dumps(payload))
        self.assertEqual(code, 0)
        self.assertIn("SHOP-20", out)


class TestDisplayCostPrefersSample(acs_case.AcsWorkspaceCase):
    """The '~$' figure prefers a real, recently recorded cost_sampler sample
    over the run's own totals, falling back to the recorded figure only when
    no sample exists yet: totals lag the just-finalized invocation."""

    def test_prefers_latest_sample_falls_back_to_run_totals_when_none(self):
        seed_run(self, "SHOP-30", cost=4.21)
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}

        self.assertIn("~$4.21", mod.render(payload))

        cost_sampler.record_cost_sample({"cwd": self.repo, "cost": {"total_cost_usd": 9.99}})
        self.assertIn("~$9.99", mod.render(payload))
        self.assertNotIn("~$4.21", mod.render(payload))


if __name__ == "__main__":
    unittest.main()
