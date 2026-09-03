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


class TestNoPartitionFallback(acs_case.AcsWorkspaceCase):
    """55: a resolvable pointer ticket whose partition directory does not
    exist renders the fallback line plus the "(no partition)" suffix."""

    def test_pointer_ticket_without_a_partition_renders_the_no_partition_line(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-404"})
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        self.assertEqual(
            mod.render(payload), "Opus · shop · acs: SHOP-404 (no partition)")


class TestProductFlowSteps(acs_case.AcsWorkspaceCase):
    """62-66: the product-flow arm emits a glyph only for skills actually
    recorded in steps, in PRODUCT_SKILLS + merge-pr order."""

    def test_product_flow_renders_only_the_recorded_product_steps(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-7")
        os.makedirs(tdir, exist_ok=True)
        acs_case.lib.save_ticket(
            tdir, acs_case.lib.new_ticket_doc("SHOP-7", "SHOP-7", "task"))
        acs_case.lib.update_pipeline(tdir, "SHOP-7", "create-prd", "completed")
        acs_case.lib.update_pipeline(tdir, "SHOP-7", "merge-pr", "in_progress")
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-7"})
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        self.assertEqual(
            mod.render(payload), "Opus · SHOP-7 task · ✓prd ▶merge-pr")


class TestDesignStepVisibility(acs_case.AcsWorkspaceCase):
    """68, 72-73: needs_design=True shows the design step; a child ticket
    (parent set, needs_design falsey) omits it."""

    def test_a_child_ticket_omits_the_design_step_while_a_design_ticket_shows_it(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}

        designed_tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-8")
        os.makedirs(designed_tdir, exist_ok=True)
        designed = acs_case.lib.new_ticket_doc("SHOP-8", "SHOP-8", "story")
        designed["needs_design"] = True
        acs_case.lib.save_ticket(designed_tdir, designed)
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-8"})
        self.assertEqual(
            mod.render(payload),
            "Opus · SHOP-8 story · ○ticket ○design ○spec ○code ○pr ○merge")

        child_tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-9")
        os.makedirs(child_tdir, exist_ok=True)
        child = acs_case.lib.new_ticket_doc("SHOP-9", "SHOP-9", "story", parent="SHOP-1")
        acs_case.lib.save_ticket(child_tdir, child)
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-9"})
        self.assertEqual(
            mod.render(payload),
            "Opus · SHOP-9 story · ○ticket ○spec ○code ○pr ○merge")


class TestCostAndLockSuffixes(acs_case.AcsWorkspaceCase):
    """86-90: the cost suffix appears only when cost is non-zero, and the
    lock suffix appears only when the lock is held by a different checkout."""

    def test_cost_and_foreign_lock_suffixes_appear_only_when_they_apply(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}

        cost_tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-10")
        os.makedirs(cost_tdir, exist_ok=True)
        acs_case.lib.save_ticket(
            cost_tdir, acs_case.lib.new_ticket_doc("SHOP-10", "SHOP-10", "story"))
        pipeline = acs_case.lib.load_pipeline(cost_tdir, "SHOP-10")
        pipeline["totals"]["cost_usd"] = 4.21
        acs_case.lib.write_json(os.path.join(cost_tdir, "pipeline-state.json"), pipeline)
        acs_case.lib.write_json(
            acs_case.lib.lock_path(cost_tdir), {"checkout_id": "other-session-ckid"})
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-10"})
        self.assertEqual(
            mod.render(payload),
            "Opus · SHOP-10 story · ○ticket ○spec ○code ○pr ○merge · ~$4.21 · 🔒other session")

        nocost_tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-11")
        os.makedirs(nocost_tdir, exist_ok=True)
        acs_case.lib.save_ticket(
            nocost_tdir, acs_case.lib.new_ticket_doc("SHOP-11", "SHOP-11", "story"))
        acs_case.lib.acquire_lock(nocost_tdir, self.repo)
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-11"})
        self.assertEqual(
            mod.render(payload),
            "Opus · SHOP-11 story · ○ticket ○spec ○code ○pr ○merge")


class TestMainNeverCrashes(unittest.TestCase):
    """100-107: when render() raises and fallback() also raises, main()
    prints the irreducible literal "Claude" rather than letting either
    exception escape."""

    def test_main_prints_the_irreducible_line_when_even_the_fallback_raises(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        tmp = tempfile.mkdtemp(prefix="acs-statusline-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with acs_case.pushd(tmp):
            code, out, err = acs_case.run_main(mod, [], stdin="[]")
        self.assertEqual(code, 0)
        self.assertEqual(out, "Claude\n")


class TestCostSamplerWiring(acs_case.AcsWorkspaceCase):
    """cost_sampler.record_cost_sample is invoked from main(), independent of
    render()'s early-return paths (no active ticket, resolvable ticket with
    no partition) -- and a raising sampler never breaks the printed line
    (G7 never-crash)."""

    def test_record_cost_sample_called_with_no_active_ticket(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        with mock.patch("cost_sampler.record_cost_sample") as record:
            with acs_case.pushd(self.repo):
                code, out, err = acs_case.run_main(mod, [], stdin=json.dumps(payload))
        self.assertEqual(code, 0)
        record.assert_called_once_with(payload)
        self.assertIn("no active ticket", out)

    def test_record_cost_sample_called_when_pointer_resolves_but_no_partition(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-404"})
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        with mock.patch("cost_sampler.record_cost_sample") as record:
            with acs_case.pushd(self.repo):
                code, out, err = acs_case.run_main(mod, [], stdin=json.dumps(payload))
        self.assertEqual(code, 0)
        record.assert_called_once_with(payload)
        self.assertIn("no partition", out)

    def test_a_raising_sampler_never_breaks_the_status_line(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-20")
        os.makedirs(tdir, exist_ok=True)
        acs_case.lib.save_ticket(tdir, acs_case.lib.new_ticket_doc("SHOP-20", "SHOP-20", "story"))
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-20"})
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}
        with mock.patch("cost_sampler.record_cost_sample", side_effect=RuntimeError("boom")):
            with acs_case.pushd(self.repo):
                code, out, err = acs_case.run_main(mod, [], stdin=json.dumps(payload))
        self.assertEqual(code, 0)
        self.assertIn("SHOP-20", out)


class TestDisplayCostPrefersSample(acs_case.AcsWorkspaceCase):
    """108-111 (the '~$' bit, design conformance item 31): prefers a real,
    recently recorded cost_sampler sample over pipeline.totals.cost_usd,
    falling back to the pipeline figure only when no sample exists yet."""

    def test_prefers_latest_sample_falls_back_to_pipeline_totals_when_none(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-30")
        os.makedirs(tdir, exist_ok=True)
        acs_case.lib.save_ticket(
            tdir, acs_case.lib.new_ticket_doc("SHOP-30", "SHOP-30", "story"))
        pipeline = acs_case.lib.load_pipeline(tdir, "SHOP-30")
        pipeline["totals"]["cost_usd"] = 4.21
        acs_case.lib.write_json(os.path.join(tdir, "pipeline-state.json"), pipeline)
        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-30"})
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = {"model": {"display_name": "Opus"}, "cwd": self.repo}

        self.assertIn("~$4.21", mod.render(payload))

        cost_sampler.record_cost_sample({"cwd": self.repo, "cost": {"total_cost_usd": 9.99}})
        self.assertIn("~$9.99", mod.render(payload))
        self.assertNotIn("~$4.21", mod.render(payload))


if __name__ == "__main__":
    unittest.main()
