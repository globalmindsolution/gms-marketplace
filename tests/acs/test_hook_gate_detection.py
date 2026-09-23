"""Behavior tests for acs_lib.hostgates -- the runtime answer to "did the
PreToolUse(Skill) gate actually fire for THIS invocation?".

Originating ticket: MAR-583. On a host that does not raise Claude Code's
lifecycle events nothing in acs gates anything, yet the skills still read as
instructions and a pipeline appears to run.

The evidence rides on a DEDICATED artifact, `sessions/<checkout>-gate.json`,
written only by the real pre-hook. Revision 1 of the plan carried it on the
session marker instead and three defects followed, because that file also
carries cost attribution and the two want opposite things: gate evidence must
be rewritten by every fire and spent once, while attribution must never be
clobbered and must age out honestly. The artifact under test here holds no
`session_id`, `transcript_path` or `cwd`, so it cannot corrupt attribution --
it has none to corrupt.

Four properties this module pins, each with the failure it exists to stop:

  * Non-forgeability. `acs.py gate` (the only other `run_pre_payload` caller)
    passes `record_marker=False`, so asking "would this gate pass?" cannot
    manufacture evidence, and a host with no hooks never writes the artifact.
  * Precision for THIS invocation. The artifact records the NORMALIZED entry
    point (`acs:code-standard` -> `code`) and is spent on consumption, so one
    gated run's evidence cannot be inherited by an ungated one inside the
    staleness window.
  * Fail-open, still. MAR-514 requires that an evidence-write failure never
    block a gated skill -- including a failure of the warning ABOUT that
    failure, which must not escape into run_pre's fail-closed handler.
  * A notice with a complete vocabulary, derived from `hooks/hooks.json` by the
    test, so a new binding nobody names in the notice fails the suite.

Stdlib-only. Run:
  python3 -m unittest tests.acs.test_hook_gate_detection -v
"""

import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
HOOKS_JSON = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "hooks.json")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def iso_ago(seconds):
    """An ISO instant `seconds` in the past, in acs's own second-resolution form."""
    moment = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def hooks_json_bindings():
    """Every (event, matcher) binding hooks.json declares, as `Event` or
    `Event:matcher` -- the vocabulary the notice must account for."""
    with open(HOOKS_JSON, encoding="utf-8") as fh:
        doc = json.load(fh)
    bindings = set()
    for event, groups in doc["hooks"].items():
        for group in groups:
            matcher = group.get("matcher")
            bindings.add("%s:%s" % (event, matcher) if matcher else event)
    return bindings


class EvidenceCase(AcsWorkspaceCase):
    """Fixture helpers over the on-disk gate-evidence artifact."""

    def context(self):
        return lib.build_context(self.repo)

    def gate_path(self, ctx):
        return lib.gate_evidence_path(
            ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])

    def write_evidence(self, ctx, **overrides):
        """The artifact in exactly the shape record_gate_evidence writes, with
        per-case fields overridden; a None override removes the key."""
        evidence = {
            "gate_skill": "code",
            "checkout_id": ctx["checkout_id"],
            "fired_at": lib.now_iso(),
            "consumed_for": None,
        }
        for key, value in overrides.items():
            if value is None:
                evidence.pop(key, None)
            else:
                evidence[key] = value
        lib.write_json(self.gate_path(ctx), evidence)
        return evidence


class GateEvidenceTest(EvidenceCase):
    """AC-1: gate_evidence answers gated/ungated for THIS invocation with a
    machine-readable reason. One arm per way the evidence can fail."""

    def test_fresh_evidence_for_this_skill_is_gated(self):
        ctx = self.context()
        self.write_evidence(ctx, gate_skill="code")
        evidence, verdict = lib.gate_evidence(ctx, "code")
        self.assertTrue(verdict["gated"])
        self.assertEqual(verdict["reason"], "gate_evidence_accepted")
        self.assertEqual(verdict["unconfirmed"], [])
        self.assertIsNone(verdict["notice"])
        self.assertIsNotNone(evidence)

    def test_no_artifact_is_ungated(self):
        ctx = self.context()
        evidence, verdict = lib.gate_evidence(ctx, "code")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "no_gate_evidence")
        self.assertIsNone(evidence)

    def test_evidence_from_another_checkout_is_ungated(self):
        ctx = self.context()
        self.write_evidence(ctx, checkout_id="somewhere-else")
        _evidence, verdict = lib.gate_evidence(ctx, "code")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "evidence_foreign_checkout")

    def test_stale_evidence_is_ungated(self):
        ctx = self.context()
        self.write_evidence(
            ctx, fired_at=iso_ago(lib.GATE_EVIDENCE_MAX_AGE_SECONDS + 60))
        _evidence, verdict = lib.gate_evidence(ctx, "code")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "evidence_stale")

    def test_unparseable_timestamp_is_ungated(self):
        ctx = self.context()
        self.write_evidence(ctx, fired_at="not-a-time")
        _evidence, verdict = lib.gate_evidence(ctx, "code")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "evidence_unparseable")

    def test_evidence_for_a_different_entry_point_is_ungated(self):
        ctx = self.context()
        self.write_evidence(ctx, gate_skill="create-ticket")
        _evidence, verdict = lib.gate_evidence(ctx, "code")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "evidence_for_other_skill")

    def test_the_ungated_verdict_never_returns_the_evidence(self):
        """Nothing can stamp evidence the verdict rejected."""
        ctx = self.context()
        self.write_evidence(ctx, gate_skill="create-ticket")
        evidence, _verdict = lib.gate_evidence(ctx, "code")
        self.assertIsNone(evidence)


class EvidenceHoldsNoAttributionTest(EvidenceCase):
    """Verifier checklist item 2: the artifact carries no correlation field --
    it records that the gate fired, nothing else."""

    def test_the_written_artifact_has_no_correlation_fields(self):
        ctx = self.context()
        lib.record_gate_evidence(ctx, "code")
        on_disk = lib.read_json(self.gate_path(ctx))
        for field in ("session_id", "transcript_path", "cwd"):
            self.assertNotIn(field, on_disk)

    def test_the_session_marker_it_was_split_from_is_gone(self):
        """ADR-0104 removed the session-correlation marker with the usage
        recording it served; the evidence file is the one that stays."""
        for name in ("session_marker_path", "record_session_marker",
                     "accepted_session_marker", "SESSION_MARKER_MAX_AGE_SECONDS"):
            self.assertFalse(hasattr(lib, name), name)


class EvidenceConsumptionTest(EvidenceCase):
    """One hook fire gates exactly one run.

    The stamp is asserted against a KNOWN seeded instant, never against a
    timestamp read back out of the artifact: docs/standards/standards.md:55-60
    forbids equality on a timestamp value, and routing such a read through a
    local variable (which revision 1 did) both evades the repo's AST guard and
    leaves the property pinned only by same-second collapse."""

    def test_consumption_stamps_the_instant_it_spent(self):
        ctx = self.context()
        fired = iso_ago(30)
        self.write_evidence(ctx, fired_at=fired)
        evidence, _verdict = lib.gate_evidence(ctx, "code")
        lib.consume_gate_evidence(ctx, evidence)
        on_disk = lib.read_json(self.gate_path(ctx))
        self.assertEqual(on_disk["consumed_for"], fired)

    def test_consumed_evidence_does_not_gate_a_second_run(self):
        ctx = self.context()
        self.write_evidence(ctx, fired_at=iso_ago(30))
        evidence, first = lib.gate_evidence(ctx, "code")
        self.assertTrue(first["gated"])
        lib.consume_gate_evidence(ctx, evidence)
        _again, second = lib.gate_evidence(ctx, "code")
        self.assertFalse(second["gated"])
        self.assertEqual(second["reason"], "evidence_already_consumed")

    def test_a_fresh_fire_clears_the_consumption_stamp(self):
        ctx = self.context()
        self.write_evidence(ctx, fired_at=iso_ago(30))
        evidence, _verdict = lib.gate_evidence(ctx, "code")
        lib.consume_gate_evidence(ctx, evidence)
        lib.record_gate_evidence(ctx, "code")
        _again, verdict = lib.gate_evidence(ctx, "code")
        self.assertTrue(verdict["gated"])


class GateResponseTest(unittest.TestCase):
    """AC-4: settings.hook_gates.when_absent resolution."""

    def test_default_is_warn(self):
        self.assertEqual(lib.gate_response({}), "warn")

    def test_both_values_resolve(self):
        self.assertEqual(lib.gate_response({"hook_gates": {"when_absent": "warn"}}), "warn")
        self.assertEqual(lib.gate_response({"hook_gates": {"when_absent": "refuse"}}), "refuse")

    def test_an_unrecognized_value_falls_back_to_warn(self):
        self.assertEqual(
            lib.gate_response({"hook_gates": {"when_absent": "explode"}}), "warn")


class NoticeTest(EvidenceCase):
    """AC-2: the notice names every enforcement, and claims only absence of
    evidence -- never that the gate did not fire."""

    def verdict(self):
        return lib.gate_evidence(self.context(), "code")[1]

    def test_every_hooks_json_binding_is_named(self):
        named = set()
        for bindings, _name in lib.HOOK_ENFORCEMENTS:
            named.update(bindings)
        self.assertEqual(named, hooks_json_bindings())

    def test_the_notice_names_each_enforcement(self):
        notice = self.verdict()["notice"]
        for _bindings, name in lib.HOOK_ENFORCEMENTS:
            self.assertIn(name, notice)

    def test_the_notice_claims_absence_of_evidence_not_absence_of_the_gate(self):
        notice = self.verdict()["notice"]
        self.assertIn("no evidence", notice.lower())
        self.assertIn("fail-open", notice.lower())

    def test_a_gated_verdict_has_no_notice(self):
        ctx = self.context()
        self.write_evidence(ctx)
        self.assertIsNone(lib.gate_evidence(ctx, "code")[1]["notice"])


class FailOpenTest(EvidenceCase):
    """Verifier checklist item 3, and MAR-514's guarantee: an evidence-write
    failure must never block a gated skill -- nor may the warning about it."""

    def break_sessions_dir(self):
        """Force the write to raise by pre-creating sessions/ as a plain file."""
        sessions = lib.sessions_dir(self.ws, lib.repo_partition_id(self.repo))
        os.makedirs(os.path.dirname(sessions), exist_ok=True)
        with open(sessions, "w") as fh:
            fh.write("not a directory")

    def test_a_failed_evidence_write_does_not_block_the_gate(self):
        self.break_sessions_dir()
        result = self.run_script(
            "pre-create-ticket.py",
            stdin=json.dumps({"cwd": self.repo, "tool_name": "Skill",
                              "tool_input": {"skill": "acs:create-ticket"}}))
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.path.exists("/dev/full"), "needs /dev/full")
    def test_a_failed_warning_about_it_does_not_block_the_gate_either(self):
        """The regression: the warning sat inside the outer try, so an
        unwritable stderr reached run_pre's fail-closed handler and returned 2.

        The accepted set is measured, not assumed:

          0   -- clean exit (the nested form, on an interpreter where the
                 unrelated warning below does not strand the buffer)
          120 -- CPython failing to flush stdio at shutdown. With stderr
                 unwritable, ANY buffered stderr write strands the buffer, and
                 this fixture provokes one that has nothing to do with the
                 gate: read_json warns that the sessions path it was handed is
                 not a directory. Non-blocking, and not acs's to fix here.
          1   -- the exception escaped as a traceback (measured: the un-nested
                 form returns 1 on 3.11)
          2   -- run_pre's fail-closed arm caught it and BLOCKED the skill,
                 which a bookkeeping failure must never do

        So 0 and 120 pass; 1 and 2 fail. Asserting == 0 measured the
        interpreter rather than acs, and asserting != 2 missed the regression
        entirely, since it escapes as 1."""
        self.break_sessions_dir()
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=os.path.join(REPO_ROOT, "plugins", "acs"))
        with open("/dev/full", "w") as devfull:
            result = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "pre-create-ticket.py")],
                input=json.dumps({"cwd": self.repo, "tool_name": "Skill",
                                  "tool_input": {"skill": "acs:create-ticket"}}),
                stdout=subprocess.PIPE, stderr=devfull, text=True,
                cwd=self.repo, env=env)
        self.assertIn(result.returncode, (0, 120),
                      "the gate crashed (1) or blocked (2) a run it enforced")


class NonForgeabilityTest(EvidenceCase):
    """`acs.py gate` must not be able to manufacture evidence."""

    def test_the_gate_probe_records_nothing(self):
        ctx = self.context()
        lib.run_pre_payload(
            "create-ticket",
            {"cwd": self.repo, "tool_name": "Skill",
             "tool_input": {"skill": "acs:create-ticket"}},
            record_marker=False)
        self.assertFalse(os.path.exists(self.gate_path(ctx)))


if __name__ == "__main__":
    unittest.main()
