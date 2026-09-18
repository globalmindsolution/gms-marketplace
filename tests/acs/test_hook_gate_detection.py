"""Behavior tests for acs_lib.hostgates -- the runtime answer to "did the
PreToolUse(Skill) gate actually fire for THIS invocation?".

Originating ticket: MAR-583. On a host that does not raise Claude Code's
lifecycle events nothing in acs gates anything, yet the skills still read as
instructions and a pipeline appears to run. The detection rides on the one
artifact only the real pre-hook can produce -- the session marker
`record_session_marker` writes as the FIRST thing `run_pre_payload` does -- so
"no evidence" is not an inference about the host: it is the absence of the very
event acs's enforcement depends on.

Three properties this module pins, each with the failure it exists to stop:

  * Non-forgeability. `acs.py gate` (the only other `run_pre_payload` caller)
    passes `record_marker=False`, so asking "would this gate pass?" cannot
    manufacture evidence, and a host with no hooks never writes a marker at all.
  * Precision for THIS invocation. The marker records the NORMALIZED entry-point
    skill (`acs:code-standard` -> `code`), and evidence is spent once it is
    consumed, so one gated run's marker cannot be inherited by an ungated one
    inside the 15-minute staleness window.
  * A notice with a complete vocabulary. The enforcement table is derived from
    `hooks/hooks.json` by the test, so a new binding that nobody names in the
    notice fails the suite rather than going unmentioned.

Stdlib-only. Run:
  python3 -m unittest tests.acs.test_hook_gate_detection -v
"""

import contextlib
import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "src", "acs", "hooks", "scripts")
HOOKS_JSON = os.path.join(REPO_ROOT, "src", "acs", "hooks", "hooks.json")
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


class MarkerCase(AcsWorkspaceCase):
    """Fixture helpers over the on-disk session marker the detection reads."""

    def context(self):
        return lib.build_context(self.repo)

    def marker_path(self, ctx):
        return lib.session_marker_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])

    def write_marker(self, ctx, **overrides):
        """A marker in exactly the shape record_session_marker writes, with
        per-case fields overridden; a None override removes the key."""
        marker = {
            "session_id": "sess-1",
            "transcript_path": "/tmp/sess-1.jsonl",
            "cwd": self.repo,
            "checkout_id": ctx["checkout_id"],
            "hook_event_name": "PreToolUse",
            "skill": "acs:code",
            "gate_skill": "code",
            "updated_at": lib.now_iso(),
        }
        for key, value in overrides.items():
            if value is None:
                marker.pop(key, None)
            else:
                marker[key] = value
        lib.write_json(self.marker_path(ctx), marker)
        return marker


class GateEvidenceTest(MarkerCase):
    """AC-1: gate_evidence answers gated/ungated for THIS invocation, with a
    machine-readable reason. One arm per way the evidence can fail."""

    def assert_ungated(self, reason, **overrides):
        ctx = self.context()
        if overrides:
            self.write_marker(ctx, **overrides)
        marker, verdict = lib.gate_evidence(ctx, "code")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], reason)
        # The marker is handed back ONLY to be consumed, so an unusable one is
        # never returned: nothing downstream can stamp evidence it rejected.
        self.assertIsNone(marker)
        return verdict

    def test_an_accepted_marker_for_this_skill_reads_gated(self):
        ctx = self.context()
        written = self.write_marker(ctx)
        marker, verdict = lib.gate_evidence(ctx, "code")
        self.assertTrue(verdict["gated"])
        self.assertEqual(verdict["reason"], "gate_marker_accepted")
        self.assertEqual(marker["gate_skill"], written["gate_skill"])
        self.assertEqual(verdict["unconfirmed"], [])
        self.assertIsNone(verdict["notice"])

    def test_no_marker_at_all_reads_ungated(self):
        self.assertFalse(os.path.exists(self.marker_path(self.context())))
        self.assert_ungated("no_gate_marker")

    def test_a_marker_older_than_the_staleness_window_reads_ungated(self):
        self.assert_ungated("marker_stale",
                            updated_at=iso_ago(lib.SESSION_MARKER_MAX_AGE_SECONDS + 60))

    def test_a_marker_from_another_checkout_reads_ungated(self):
        self.assert_ungated("marker_foreign_checkout", checkout_id="shop-deadbeef")

    def test_a_marker_with_an_unparseable_timestamp_reads_ungated(self):
        self.assert_ungated("marker_unparseable", updated_at="last tuesday")

    def test_a_marker_written_before_gate_evidence_existed_reads_ungated(self):
        # Pre-MAR-583 markers carry no gate_skill: the honest answer is ungated,
        # self-correcting on the next real hook fire.
        self.assert_ungated("marker_predates_gate_evidence", gate_skill=None)

    def test_a_marker_for_a_different_skill_reads_ungated(self):
        self.assert_ungated("marker_for_other_skill", gate_skill="create-pr")

    def test_an_already_consumed_marker_reads_ungated(self):
        ctx = self.context()
        stamp = lib.now_iso()
        self.assert_ungated("marker_already_consumed",
                            updated_at=stamp, gate_consumed_for=stamp)
        self.assertTrue(os.path.exists(self.marker_path(ctx)))

    def test_the_verdict_carries_the_response_and_a_timestamp(self):
        ctx = self.context()
        _marker, verdict = lib.gate_evidence(ctx, "code")
        self.assertEqual(verdict["response"], "warn")
        self.assertIsNotNone(lib.parse_iso(verdict["checked_at"]))


class AcceptedSessionMarkerTest(MarkerCase):
    """accepted_session_marker is skill-start's staleness/cross-session guard,
    widened to say WHY it rejected -- the reason gate_evidence reports."""

    def test_accepts_a_fresh_marker_for_this_checkout_with_no_reason(self):
        ctx = self.context()
        self.write_marker(ctx)
        marker, reason = lib.accepted_session_marker(ctx)
        self.assertIsNone(reason)
        self.assertEqual(marker["checkout_id"], ctx["checkout_id"])

    def test_a_non_dict_marker_file_reads_as_absent(self):
        ctx = self.context()
        lib.write_json(self.marker_path(ctx), ["not", "a", "marker"])
        marker, reason = lib.accepted_session_marker(ctx)
        self.assertIsNone(marker)
        self.assertEqual(reason, "no_gate_marker")

    def test_the_window_is_the_one_skill_start_has_always_applied(self):
        self.assertEqual(lib.SESSION_MARKER_MAX_AGE_SECONDS, 15 * 60)


class GateResponseTest(unittest.TestCase):
    """AC-4: hook_gates.when_absent selects the response; warn is the default."""

    def test_absent_settings_block_is_warn(self):
        self.assertEqual(lib.gate_response({}), "warn")
        self.assertEqual(lib.gate_response(None), "warn")

    def test_refuse_is_read_from_the_settings_block(self):
        self.assertEqual(lib.gate_response({"hook_gates": {"when_absent": "refuse"}}), "refuse")

    def test_an_unrecognized_value_falls_back_to_warn_never_refuse(self):
        # validate_settings rejects such a value outright; this is the second
        # line -- a malformed block must never escalate a run into a refusal.
        self.assertEqual(lib.gate_response({"hook_gates": {"when_absent": "block"}}), "warn")
        self.assertEqual(lib.gate_response({"hook_gates": "yes"}), "warn")

    def test_the_default_is_named_once(self):
        self.assertEqual(lib.DEFAULT_GATE_RESPONSE, "warn")
        self.assertEqual(lib.GATE_RESPONSES, ("warn", "refuse"))


class NoticeTest(MarkerCase):
    """AC-2: the notice names which enforcement is not in force, and its
    vocabulary covers every binding hooks.json declares."""

    def ungated_verdict(self, settings=None):
        ctx = self.context()
        if settings is not None:
            ctx["settings"] = settings
        _marker, verdict = lib.gate_evidence(ctx, "code")
        return verdict

    def test_names_all_four_enforcements(self):
        verdict = self.ungated_verdict()
        notice = lib.gate_notice(verdict)
        for name in ("precondition gate", "file-map guard",
                     "phase-artifact validation", "session bookkeeping"):
            self.assertIn(name, notice)
            self.assertIn(name, verdict["unconfirmed"])

    def test_the_notice_claims_only_that_the_evidence_is_absent(self):
        """The marker write is deliberately fail-open (gates.run_pre_payload,
        MAR-514), so its absence cannot tell a gate that never fired from one
        whose write failed. The notice must claim the weaker, true thing --
        under warn a false "the gate did not fire" is a signal that cries wolf."""
        notice = lib.gate_notice(self.ungated_verdict())
        self.assertNotIn("did not fire", notice)
        self.assertIn("no evidence", notice)
        self.assertIn("fail-open", notice)

    def test_the_refuse_notice_says_what_it_refuses_on(self):
        """Refusal rides on ABSENCE of evidence, which includes the gate that
        fired and could not record it: the operator is told so, here."""
        verdict = self.ungated_verdict({"hook_gates": {"when_absent": "refuse"}})
        notice = lib.gate_notice(verdict)
        self.assertIn("absence of that evidence", notice)

    def test_the_notice_names_the_reason_and_the_settings_key(self):
        verdict = self.ungated_verdict()
        notice = lib.gate_notice(verdict)
        self.assertIn("no_gate_marker", notice)
        self.assertIn("hook_gates.when_absent", notice)

    def test_the_warn_notice_says_the_run_continues(self):
        notice = lib.gate_notice(self.ungated_verdict())
        self.assertIn("continues", notice)
        self.assertIn("refuse", notice)

    def test_the_refuse_notice_says_the_run_is_blocked(self):
        verdict = self.ungated_verdict({"hook_gates": {"when_absent": "refuse"}})
        self.assertEqual(verdict["response"], "refuse")
        notice = lib.gate_notice(verdict)
        self.assertIn("blocked", notice)
        self.assertIn("warn", notice)

    def test_a_gated_verdict_has_no_notice(self):
        ctx = self.context()
        self.write_marker(ctx)
        _marker, verdict = lib.gate_evidence(ctx, "code")
        self.assertIsNone(lib.gate_notice(verdict))

    def test_enforcement_table_covers_every_hooks_json_binding(self):
        declared = set()
        for bindings, _name in lib.HOOK_ENFORCEMENTS:
            declared.update(bindings)
        self.assertEqual(declared, hooks_json_bindings())

    def test_the_table_has_one_entry_per_named_enforcement(self):
        names = [name for _bindings, name in lib.HOOK_ENFORCEMENTS]
        self.assertEqual(names, ["precondition gate", "file-map guard",
                                 "phase-artifact validation", "session bookkeeping"])


class MarkerWriterTest(MarkerCase):
    """The evidence side: only the real PreToolUse(Skill) hook writes it, and
    it records the normalized entry point the leg then invokes."""

    def test_pre_hook_records_the_normalized_entry_point_skill(self):
        # A delivery-path leg is gated AS its entry point (ADR-0095), and the
        # leg then runs `skill-start.py --skill code` -- so the evidence has to
        # be recorded under `code`, not under the leg's own spelling.
        self.pre("code-standard", args_text="SHOP-1")
        ctx = self.context()
        marker = lib.read_json(self.marker_path(ctx))
        self.assertEqual(marker["gate_skill"], "code")
        self.assertEqual(marker["skill"], "acs:code-standard")

    def test_the_recorded_evidence_is_what_gate_evidence_accepts(self):
        self.pre("create-ticket")
        ctx = self.context()
        _marker, verdict = lib.gate_evidence(ctx, "create-ticket")
        self.assertTrue(verdict["gated"])

    def test_acs_py_gate_writes_no_evidence(self):
        # `acs.py gate` answers "would this gate pass?" with no PreToolUse
        # envelope, and passes record_marker=False precisely so it cannot forge
        # a gated verdict for the run that follows.
        ctx = self.context()
        result = self.run_script("acs.py", "gate", "--skill", "create-ticket")
        self.assertIn(result.returncode, (0, 2), result.stderr)
        self.assertFalse(os.path.exists(self.marker_path(ctx)))
        _marker, verdict = lib.gate_evidence(ctx, "create-ticket")
        self.assertFalse(verdict["gated"])
        # Positive control for the absence above: the SAME path is created when
        # the real hook fires, so the assertion is not vacuous.
        self.pre("create-ticket")
        self.assertTrue(os.path.exists(self.marker_path(ctx)))

    def test_a_host_with_no_hooks_never_produces_evidence(self):
        # The Devin/Codex condition: nothing ever calls self.pre(...).
        ctx = self.context()
        marker, verdict = lib.gate_evidence(ctx, "code")
        self.assertIsNone(marker)
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "no_gate_marker")

    def test_marker_write_still_records_the_envelope_fields(self):
        """The added field must not cost the marker its session-correlation
        payload -- append_in_progress_run threads those onto the run entry."""
        ctx = self.context()
        marker = lib.record_session_marker(
            ctx, {"session_id": "sess-9", "transcript_path": "/tmp/sess-9.jsonl",
                  "cwd": self.repo, "hook_event_name": "PreToolUse",
                  "tool_input": {"skill": "acs:code-small"}}, "code")
        self.assertEqual(marker["session_id"], "sess-9")
        self.assertEqual(marker["skill"], "acs:code-small")
        self.assertEqual(marker["gate_skill"], "code")

    def test_an_omitted_skill_records_a_null_gate_skill(self):
        ctx = self.context()
        marker = lib.record_session_marker(ctx, {"cwd": self.repo})
        self.assertIsNone(marker["gate_skill"])


class EvidenceConsumptionTest(MarkerCase):
    """Evidence is spent once used: one hook fire gates exactly one run, so a
    second invocation inside the 15-minute window cannot inherit it."""

    def test_consumed_evidence_is_not_reusable(self):
        self.pre("create-ticket")
        ctx = self.context()
        marker, verdict = lib.gate_evidence(ctx, "create-ticket")
        self.assertTrue(verdict["gated"])
        lib.consume_gate_evidence(ctx, marker)

        _again, second = lib.gate_evidence(ctx, "create-ticket")
        self.assertFalse(second["gated"])
        self.assertEqual(second["reason"], "marker_already_consumed")

    def test_consuming_stamps_the_marker_it_spent(self):
        self.pre("create-ticket")
        ctx = self.context()
        marker, _verdict = lib.gate_evidence(ctx, "create-ticket")
        spent = marker["updated_at"]
        lib.consume_gate_evidence(ctx, marker)
        on_disk = lib.read_json(self.marker_path(ctx))
        self.assertEqual(on_disk["gate_consumed_for"], spent)
        # The rest of the marker survives: session threading still reads it.
        self.assertEqual(on_disk["gate_skill"], "create-ticket")

    def test_a_fresh_hook_fire_clears_the_consumption_stamp(self):
        self.pre("create-ticket")
        ctx = self.context()
        marker, _verdict = lib.gate_evidence(ctx, "create-ticket")
        lib.consume_gate_evidence(ctx, marker)

        self.pre("create-ticket")
        _marker, verdict = lib.gate_evidence(ctx, "create-ticket")
        self.assertTrue(verdict["gated"])
        self.assertNotIn("gate_consumed_for", lib.read_json(self.marker_path(ctx)))


class NoClobberArmTest(MarkerCase):
    """record_session_marker refuses to write an envelope's nulls OVER a marker
    that carries a real session_id, so the next run keeps its cost/usage
    attribution. That arm must still let the fire it is serving REPLACE the gate
    evidence: a genuine hook fire that inherits the previous marker's spent
    stamp or entry point reads as ungated for a run the gate did enforce."""

    def seed_attributed_marker(self, skill="create-ticket"):
        """A marker as a real PreToolUse envelope leaves it: session_id present."""
        return lib.record_session_marker(
            self.context(),
            {"session_id": "REAL", "transcript_path": "/tmp/real.jsonl",
             "cwd": self.repo, "hook_event_name": "PreToolUse",
             "tool_input": {"skill": "acs:" + skill}}, skill)

    def test_a_fire_without_a_session_id_clears_the_consumption_stamp(self):
        ctx = self.context()
        self.seed_attributed_marker()
        marker, first = lib.gate_evidence(ctx, "create-ticket")
        self.assertTrue(first["gated"])
        lib.consume_gate_evidence(ctx, marker)

        # dispatch.py's envelope here carries no session_id -- the arm's case.
        self.pre("create-ticket")

        _marker, second = lib.gate_evidence(ctx, "create-ticket")
        self.assertTrue(second["gated"], second["reason"])

    def test_a_fire_without_a_session_id_records_its_own_entry_point(self):
        ctx = self.context()
        self.seed_attributed_marker()
        self.pre("code-standard", args_text="SHOP-1")
        on_disk = lib.read_json(self.marker_path(ctx))
        self.assertEqual(on_disk["gate_skill"], "code")
        self.assertEqual(on_disk["skill"], "acs:code-standard")

    def test_the_attribution_the_arm_protects_still_survives(self):
        ctx = self.context()
        self.seed_attributed_marker()
        self.pre("create-ticket")
        on_disk = lib.read_json(self.marker_path(ctx))
        self.assertEqual(on_disk["session_id"], "REAL")
        self.assertEqual(on_disk["transcript_path"], "/tmp/real.jsonl")


class FailOpenEvidenceTest(MarkerCase):
    """run_pre_payload records the evidence inside a deliberate fail-open
    try/except: MAR-514 established that a marker-write bug must never make the
    gate exit 2 (tests/acs/test_session_marker.py). That write is now the only
    proof the gate fired, so a swallowed failure must read as "no evidence" --
    never as "the gate did not fire" -- and must not be silent about it."""

    def break_the_marker_write(self):
        """sessions/ as a plain file: write_json's makedirs then fails for real,
        with no monkeypatching -- MAR-514's own fixture for the same failure."""
        sessions = lib.sessions_dir(self.ws, "acme-shop")
        os.makedirs(os.path.dirname(sessions), exist_ok=True)
        with open(sessions, "w", encoding="utf-8") as fh:
            fh.write("not a directory")

    def fire_the_gate(self):
        """The real pre path, in-process, returning what it wrote to stderr."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = lib.run_pre_payload(
                "create-ticket",
                {"cwd": self.repo, "session_id": "sess-1",
                 "hook_event_name": "PreToolUse",
                 "tool_input": {"skill": "acs:create-ticket"}})
        return code, err.getvalue()

    def test_a_failed_write_is_reported_rather_than_vanishing(self):
        self.break_the_marker_write()
        code, err = self.fire_the_gate()
        self.assertEqual(code, 0, "MAR-514: a marker-write failure never blocks the gate")
        self.assertIn("session marker", err)

    def test_the_verdict_after_a_failed_write_claims_only_absence(self):
        self.break_the_marker_write()
        code, _err = self.fire_the_gate()
        self.assertEqual(code, 0)
        with contextlib.redirect_stderr(io.StringIO()):
            marker, verdict = lib.gate_evidence(self.context(), "create-ticket")
        self.assertIsNone(marker)
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "no_gate_marker")
        self.assertNotIn("did not fire", verdict["notice"])


if __name__ == "__main__":
    unittest.main()
