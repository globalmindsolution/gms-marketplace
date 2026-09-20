"""Behavior tests for skill-start.py's runtime report on hook-gate integrity.

Originating ticket: MAR-583. `acs_lib.hostgates` answers "did the
PreToolUse(Skill) gate fire for THIS invocation?"; this module pins what
skill-start.py -- the first action of every acs skill -- does with that answer:

  * it exposes the verdict as `gate_enforcement` in BOTH context documents it
    prints, the normal payload and the `/acs:merge-pr --pr` exempt-pr one, so
    neither mode can be silently unreported;
  * when there is no evidence the gates fired it writes the notice naming the
    four enforcements this run cannot confirm to stderr as well, and records the
    verdict on the run entry, where an audit can still read it after the run;
  * under `hook_gates.when_absent: refuse` it blocks the run with exit 2 BEFORE
    any partition, lock, pointer or ledger write, so a refused run leaves
    nothing to unwind and no run entry exists to carry a verdict;
  * under the default `warn` a host with no hooks at all still completes -- the
    degraded state is made visible, never closed by blocking work.

The gated half is pinned just as hard: a run the real `dispatch.py pre`
gated is silent, refuses nothing, and prints a payload that differs from the
pre-MAR-583 one by exactly the added field.

Stdlib-only. Run:
  python3 -m unittest tests.acs.test_ungated_run_reporting -v
"""

import json
import os
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

lib = acs_case.lib

MODULE_FILENAME = "skill-start.py"
SKILL_START_PATH = os.path.join(acs_case.SCRIPTS, MODULE_FILENAME)
REPO_ID = "acme-shop"

#: The four enforcements acs_lib.HOOK_ENFORCEMENTS names, in its own words.
ENFORCEMENTS = ["precondition gate", "file-map guard",
                "phase-artifact validation", "session bookkeeping"]

#: The payload skill-start.py printed BEFORE this ticket (skill-start.py:361-383
#: at the merge base). AC-6's "otherwise unchanged" is this set, verbatim.
PRE_CHANGE_PAYLOAD_KEYS = {
    "skill", "flow", "ticket_id", "ticket", "partition", "repo_id", "workspace",
    "checkout_id", "checkout_root", "plugin_root", "settings", "settings_sources",
    "models", "prior_run_status", "reconcile", "handoff_summary", "design",
    "pipeline", "epic_marked_in_progress", "post_hook",
}

#: The same, for the exempt-pr document (skill-start.py:95-114 at the merge base).
PRE_CHANGE_EXEMPT_PR_KEYS = {
    "skill", "mode", "repo_id", "workspace", "checkout_id", "checkout_root",
    "plugin_root", "settings", "settings_sources", "exempt_reason", "pr",
    "post_hook",
}

EXEMPT_PR_DOC = {
    "number": 87, "state": "OPEN", "headRefName": "chore/cleanup",
    "baseRefName": "main", "labels": [{"name": "acs-exempt"}],
    "isDraft": False, "url": "https://github.com/acme/shop/pull/87",
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class SkillStartCase(acs_case.AcsWorkspaceCase):
    """A workspace plus the two ways a run becomes gated or ungated: firing the
    real pre-hook, or simply never firing it (the host with no hooks)."""

    def settings(self, when_absent=None, **extra):
        """Rewrite .acs/settings.json, optionally naming hook_gates.when_absent."""
        data = {"ticket_prefix": "SHOP", "test_coverage_percent": 90}
        if when_absent is not None:
            data["hook_gates"] = {"when_absent": when_absent}
        data.update(extra)
        self.write_settings(data)

    def mint(self, ticket_id, status="open"):
        """A live partition with a valid ticket.json -- no subprocess."""
        tdir = lib.ticket_dir(self.ws, REPO_ID, ticket_id)
        os.makedirs(tdir, exist_ok=True)
        ticket = lib.new_ticket_doc(ticket_id, ticket_id, "task", status=status)
        lib.save_ticket(tdir, ticket)
        lib.update_index(self.ws, REPO_ID, ticket, archived=False)
        return tdir

    def gate(self, skill="code"):
        """Drive the REAL dispatch.py pre, which is the only writer of the
        evidence a gated verdict rests on. The gate's own verdict is irrelevant
        here: the evidence write runs before it, pass or block."""
        self.pre(skill)
        ckid = lib.checkout_id(self.repo)
        evidence = lib.read_json(lib.gate_evidence_path(self.ws, REPO_ID, ckid))
        self.assertIsInstance(evidence, dict, "the pre-hook wrote no gate evidence")
        self.assertEqual(evidence["gate_skill"], skill)

    def start(self, ticket_id, skill="code", extra_argv=()):
        """Run skill-start.py in-process; returns (code, payload_or_None, stderr)."""
        mod = acs_case.load_module(MODULE_FILENAME)
        argv = ["--skill", skill, "--ticket", ticket_id] + list(extra_argv)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, argv)
        return code, (json.loads(out) if out.strip() else None), err

    def entry(self, ticket_id, skill="code"):
        tdir = lib.ticket_dir(self.ws, REPO_ID, ticket_id)
        return lib.load_state(tdir, skill, ticket_id)["runs"][-1]


class ContextFieldTest(SkillStartCase):
    """AC-1/AC-2: the verdict reaches the coordinator in the context document,
    in both payload shapes, and an ungated one carries the notice."""

    def test_gated_run_reports_gated_true(self):
        self.mint("SHOP-1")
        self.gate()
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        verdict = payload["gate_enforcement"]
        self.assertTrue(verdict["gated"])
        self.assertEqual(verdict["reason"], "gate_evidence_accepted")
        self.assertEqual(verdict["unconfirmed"], [])
        self.assertIsNone(verdict["notice"])

    def test_ungated_run_reports_gated_false(self):
        self.mint("SHOP-1")
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        verdict = payload["gate_enforcement"]
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "no_gate_evidence")
        self.assertEqual(verdict["response"], "warn")
        self.assertTrue(verdict["checked_at"])

    def test_notice_lists_the_four_enforcements(self):
        self.mint("SHOP-1")
        _code, payload, _err = self.start("SHOP-1")
        verdict = payload["gate_enforcement"]
        self.assertEqual(verdict["unconfirmed"], ENFORCEMENTS)
        for name in ENFORCEMENTS:
            self.assertIn(name, verdict["notice"])

    def test_notice_also_reaches_stderr(self):
        self.mint("SHOP-1")
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertIn("DEGRADED ENFORCEMENT", err)
        for name in ENFORCEMENTS:
            self.assertIn(name, err)
        self.assertIn(payload["gate_enforcement"]["notice"], err)

    def test_exempt_pr_payload_carries_the_verdict(self):
        bindir = tempfile.mkdtemp(prefix="acs-fakebin-", dir=self.tmp)
        env = acs_case.fake_gh(bindir, "echo '%s'" % json.dumps(EXEMPT_PR_DOC))
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["mode"], "exempt-pr")
        verdict = payload["gate_enforcement"]
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "no_gate_evidence")
        self.assertIn("DEGRADED ENFORCEMENT", out.stderr)

    def test_exempt_pr_payload_is_otherwise_unchanged(self):
        bindir = tempfile.mkdtemp(prefix="acs-fakebin-", dir=self.tmp)
        env = acs_case.fake_gh(bindir, "echo '%s'" % json.dumps(EXEMPT_PR_DOC))
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertIn("gate_enforcement", payload)
        self.assertEqual(set(payload) - {"gate_enforcement"},
                         PRE_CHANGE_EXEMPT_PR_KEYS)


class LedgerTest(SkillStartCase):
    """AC-3: the verdict is durable on runs[-1], at the guard-denial grain, so
    an audit reads it off the ledger entry itself -- the record the run leaves
    behind, not a value recomputed later from evidence that has since been
    spent, rewritten, or aged out of the staleness window."""

    def test_run_entry_records_the_ungated_verdict(self):
        self.mint("SHOP-1")
        code, _payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        verdict = self.entry("SHOP-1")["gate_enforcement"]
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "no_gate_evidence")
        self.assertEqual(verdict["response"], "warn")
        self.assertEqual(verdict["unconfirmed"], ENFORCEMENTS)
        self.assertIn("DEGRADED ENFORCEMENT", verdict["notice"])

    def test_run_entry_records_a_gated_verdict(self):
        self.mint("SHOP-1")
        self.gate()
        code, _payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        verdict = self.entry("SHOP-1")["gate_enforcement"]
        self.assertTrue(verdict["gated"])
        self.assertEqual(verdict["reason"], "gate_evidence_accepted")

    def test_the_entry_records_what_the_context_document_reported(self):
        """One verdict, two readers: the coordinator reads it now on stdout, an
        audit reads the same object later on the entry."""
        self.mint("SHOP-1")
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.entry("SHOP-1")["gate_enforcement"],
                         payload["gate_enforcement"])

    # A refused run carries no verdict because it writes no entry at all. That
    # property is pinned by RefuseResponseTest.test_no_partition_lock_pointer_
    # or_state_is_written, which drives a real refusal. Asserting it here off a
    # freshly minted partition held by fixture construction alone: it passed
    # with the entire refuse path deleted.

    def test_a_run_entry_predating_the_record_stays_readable(self):
        """Forward-only: an entry written before this shipped simply has no
        field, and reading the ledger must not depend on one being there."""
        tdir = self.mint("SHOP-1")
        lib.append_invocation(tdir, "code", "SHOP-1")
        self.assertNotIn("gate_enforcement",
                         lib.load_state(tdir, "code", "SHOP-1")["runs"][-1])


class DefaultResponseTest(SkillStartCase):
    """AC-5: warn is the default, so a host that fires no hooks still runs."""

    def test_ungated_run_exits_zero_and_writes_its_run_entry(self):
        self.mint("SHOP-1")
        code, _payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        entry = self.entry("SHOP-1")
        self.assertEqual(entry["status"], "in_progress")
        self.assertFalse(entry["gate_enforcement"]["gated"])

    def test_ungated_run_is_not_blocked_without_settings(self):
        self.write_settings({"ticket_prefix": "SHOP"})
        self.mint("SHOP-1")
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(payload["settings"]["hook_gates"]["when_absent"], "warn")
        self.assertEqual(payload["gate_enforcement"]["response"], "warn")


class GatedRunIsSilentTest(SkillStartCase):
    """AC-6, first half: a gated run behaves exactly as it did before."""

    def test_no_stderr_notice_when_gated(self):
        self.mint("SHOP-1")
        self.gate()
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertTrue(payload["gate_enforcement"]["gated"])
        self.assertNotIn("DEGRADED ENFORCEMENT", err)
        self.assertEqual(err, "")

    def test_gated_run_is_not_refused_even_under_refuse(self):
        self.settings(when_absent="refuse")
        self.mint("SHOP-1")
        self.gate()
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertTrue(payload["gate_enforcement"]["gated"])
        self.assertEqual(payload["gate_enforcement"]["response"], "refuse")

    def test_gated_payload_is_otherwise_unchanged(self):
        self.mint("SHOP-1")
        self.gate()
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertIn("gate_enforcement", payload)
        self.assertEqual(set(payload) - {"gate_enforcement"},
                         PRE_CHANGE_PAYLOAD_KEYS)


class RefuseResponseTest(SkillStartCase):
    """AC-6, second half: under refuse the run is blocked before anything
    durable exists (clarification C-6), so there is nothing to unwind."""

    def test_exit_2_with_actionable_stderr(self):
        self.settings(when_absent="refuse")
        self.mint("SHOP-1")
        code, payload, err = self.start("SHOP-1")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)
        self.assertIn("DEGRADED ENFORCEMENT", err)
        self.assertIn("refuse", err)
        self.assertIn("precondition gate", err)
        self.assertNotIn("Traceback", err)

    def test_no_partition_lock_pointer_or_state_is_written(self):
        self.settings(when_absent="refuse")
        tdir = self.mint("SHOP-1")
        code, _payload, _err = self.start("SHOP-1")
        self.assertEqual(code, 2)
        # The partition the fixture minted is untouched: no .lock, no
        # <skill>-state.json run entry, no run.json row.
        self.assertEqual(os.listdir(tdir), ["ticket.json"])
        self.assertFalse(os.path.exists(lib.lock_path(tdir)))
        ckid = lib.checkout_id(self.repo)
        self.assertFalse(os.path.exists(lib.pointer_path(self.ws, REPO_ID, ckid)))

    def test_refused_exempt_pr_mode_prints_no_payload(self):
        self.settings(when_absent="refuse")
        bindir = tempfile.mkdtemp(prefix="acs-fakebin-", dir=self.tmp)
        env = acs_case.fake_gh(bindir, "echo '%s'" % json.dumps(EXEMPT_PR_DOC))
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertIn("DEGRADED ENFORCEMENT", out.stderr)

    def test_acs_py_start_refuses_identically(self):
        self.settings(when_absent="refuse")
        self.mint("SHOP-1")
        direct = self.run_script("skill-start.py", "--skill", "code",
                                 "--ticket", "SHOP-1")
        delegated = self.run_script("acs.py", "start", "--skill", "code",
                                    "--ticket", "SHOP-1")
        self.assertEqual(direct.returncode, 2, direct.stderr)
        self.assertEqual(delegated.returncode, direct.returncode)
        self.assertEqual(delegated.stderr, direct.stderr)
        self.assertEqual(delegated.stdout, direct.stdout)


class NoticePlacementTest(SkillStartCase):
    """The notice announces that the run CONTINUES ungated, so it belongs to a
    run that is going ahead -- never ahead of a refusal that says the opposite."""

    def test_an_unrelated_refusal_is_not_prefixed_by_the_notice(self):
        code, _payload, err = self.start("SHOP-999")
        self.assertEqual(code, 2)
        self.assertNotIn("DEGRADED ENFORCEMENT", err)
        self.assertIn("no partition for SHOP-999", err)

    def test_the_refusal_the_gate_itself_raises_still_carries_it(self):
        self.settings(when_absent="refuse")
        code, _payload, err = self.start("SHOP-999")
        self.assertEqual(code, 2)
        self.assertIn("DEGRADED ENFORCEMENT", err)
        self.assertNotIn("no partition for SHOP-999", err)


class EvidenceConsumptionTest(SkillStartCase):
    """One hook fire gates exactly one run -- pinned at the skill-start level,
    which is where the residual "inherited evidence" failure would show."""

    def test_consumed_evidence_is_not_reusable(self):
        self.mint("SHOP-1")
        self.mint("SHOP-2")
        self.gate()
        code, first, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertTrue(first["gate_enforcement"]["gated"])
        code, second, err = self.start("SHOP-2")
        self.assertEqual(code, 0, err)
        self.assertFalse(second["gate_enforcement"]["gated"])
        self.assertEqual(second["gate_enforcement"]["reason"],
                         "evidence_already_consumed")

    def test_a_fresh_hook_fire_clears_the_consumption_stamp(self):
        self.mint("SHOP-1")
        self.mint("SHOP-2")
        self.gate()
        code, first, err = self.start("SHOP-1")
        self.assertEqual(code, 0, err)
        self.assertTrue(first["gate_enforcement"]["gated"])
        self.gate()
        code, second, err = self.start("SHOP-2")
        self.assertEqual(code, 0, err)
        self.assertTrue(second["gate_enforcement"]["gated"])

    def test_evidence_for_another_skill_does_not_gate_this_one(self):
        self.mint("SHOP-1")
        self.gate("create-pr")
        code, payload, err = self.start("SHOP-1", skill="code")
        self.assertEqual(code, 0, err)
        self.assertFalse(payload["gate_enforcement"]["gated"])
        self.assertEqual(payload["gate_enforcement"]["reason"],
                         "evidence_for_other_skill")


class MarkerMaxAgeTest(unittest.TestCase):
    """The 900s staleness window has ONE home now: acs_lib.hostgates. A second
    spelling in skill-start.py is how the two silently drift apart."""

    def test_skill_start_keeps_no_second_max_age_constant(self):
        source = read(SKILL_START_PATH)
        self.assertNotIn("_SESSION_MARKER_MAX_AGE_SECONDS", source)
        self.assertNotIn("15 * 60", source)
        self.assertEqual(lib.SESSION_MARKER_MAX_AGE_SECONDS, 15 * 60)


if __name__ == "__main__":
    unittest.main()
