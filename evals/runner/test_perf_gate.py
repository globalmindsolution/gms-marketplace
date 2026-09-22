#!/usr/bin/env python3
"""Self-test for the tier-3 gate. Stdlib only, no model, no network.

METHODOLOGY.md names "the harness and the dataset share an author" as a threat
to validity: a blind spot in one is mirrored in the other. The collector cannot
be exercised without spending money, so the comparator is where that risk is
paid down — these cases assert the *decision rules* hold, independently of any
real measurement.

The records below are synthetic and deliberately so. They test the arithmetic
and the rules, and they say nothing whatever about acs. A measurement of acs
comes only from `make measure`.

    python3 runner/test_perf_gate.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import perf_gate as pg  # noqa: E402

PROVISIONAL = {
    "basis": "provisional",
    "reliability": {
        "routing_positive_accuracy_floor": {"value": 1.0, "severity": "major"},
        "routing_negative_accuracy_floor": {"value": 1.0, "severity": "critical"},
        "routing_control_floor": {"value": 1.0, "severity": "critical"},
        "pipeline_completion_floor": {"value": 1.0, "severity": "major"},
    },
    "cost": {"median_regression_ratio": {"value": 1.25, "severity": "major"},
             "absolute_floor_usd": {"value": 0.05}},
    "time": {"median_regression_ratio": {"value": 1.5, "severity": "major"},
             "absolute_floor_seconds": {"value": 5.0}},
    "quality": {
        "verify_iterations_median_ceiling_delta": {"value": 1, "severity": "major"},
        "coverage_floor_delta": {"value": -2.0, "severity": "major"},
        "blocking_findings_rate_ceiling": {"value": 0.0, "severity": "major"},
    },
}
CALIBRATED = dict(PROVISIONAL, basis="calibrated")


def routing(pid="ROUTE-code", skill="acs:code", routed=None, must=True,
            seconds=4.0, cost=0.01, control=False):
    routed = routed if routed is not None else [skill] * 3
    probe = {"id": pid, "kind": "routing", "skill": skill,
             "expect": {"must_route": must, "skill": skill,
                        "control": control},
             "runs": [{"ok": True, "routed_to": r, "seconds": seconds,
                       "cost_usd": cost} for r in routed]}
    probe["aggregate"] = pg.summarize(probe)
    return probe


def pipeline(pid="PIPE-code", skill="acs:code", n=3, ok=True, seconds=600.0,
             cost=2.0, iters=1, coverage=85.0, blocking=0):
    probe = {"id": pid, "kind": "pipeline", "skill": skill,
             "runs": [{"ok": ok, "seconds": seconds, "cost_usd": cost,
                       "status": "completed" if ok else "error",
                       "quality": {"verify_iterations": iters,
                                   "coverage_percent": coverage,
                                   "blocking_findings": blocking}}
                      for _ in range(n)]}
    probe["aggregate"] = pg.summarize(probe)
    return probe


def unmeasured_pipeline(pid="PIPE-docs-sync", skill="acs:docs-sync",
                       measured=(), holes=1):
    """A pipeline probe some of whose runs never reached the skill.

    `measured` is one (ok, status) pair per run that actually ran; `holes` is
    the number whose setup fell short.
    """
    runs = [{"ok": False, "unmeasured": "setup prompt failed: timeout",
             "seconds": 0.0, "cost_usd": None, "error": "setup prompt failed"}
            for _ in range(holes)]
    runs += [{"ok": ok, "seconds": 40.0, "cost_usd": 0.3, "status": status,
              "quality": {"verify_iterations": 0, "coverage_percent": None,
                          "blocking_findings": 0}}
             for ok, status in measured]
    probe = {"id": pid, "kind": "pipeline", "skill": skill, "runs": runs}
    probe["aggregate"] = pg.summarize(probe)
    return probe


def measurement(probes, version="0.5.0", sset="1.0.0", incomplete=False,
                digest=None):
    build = {"version": version}
    if digest:
        build["digest"] = digest
    return {"schema": "acs-evals/measurement/1",
            "build": build, "scenario_set_version": sset,
            "environment": {"claude_cli_version": "2.1.263"},
            "incomplete": incomplete, "probes": probes}


class _Build:
    def __init__(self, version="0.5.0", digest="c0ffee", root="/plugins/acs"):
        self.version, self.digest, self.root = version, digest, root


class TestSummarise(unittest.TestCase):

    def test_median_ignores_missing_and_takes_the_middle(self):
        self.assertEqual(pg.median([3, 1, 2]), 2.0)
        self.assertEqual(pg.median([4, 1, 2, 3]), 2.5)
        self.assertIsNone(pg.median([None, "x"]))

    def test_median_not_mean_so_one_timeout_does_not_move_the_gate(self):
        # The whole reason the gate reads medians: four fast runs and one
        # 30-minute hang must not read as a 6-minute skill.
        self.assertEqual(pg.median([10, 10, 10, 10, 1800]), 10.0)

    def test_spread_carries_the_range_calibration_needs(self):
        s = pg.spread([1.0, 5.0, 3.0])
        self.assertEqual((s["median"], s["min"], s["max"], s["n"]),
                         (3.0, 1.0, 5.0, 3))

    def test_a_negative_probe_scores_a_hit_when_the_skill_stays_silent(self):
        # Inverted deliberately so one floor covers both probe kinds.
        probe = routing(pid="ROUTE-update", skill="acs:update", must=False,
                        routed=[None, None, None])
        self.assertEqual(probe["aggregate"]["reliability"]["rate"], 1.0)

    def test_a_negative_probe_that_auto_invokes_scores_no_hit(self):
        probe = routing(pid="ROUTE-update", skill="acs:update", must=False,
                        routed=[None, "acs:update", None])
        self.assertAlmostEqual(probe["aggregate"]["reliability"]["rate"], 2 / 3)


class TestUnmeasuredRuns(unittest.TestCase):
    """A run that never reached the skill is a hole, not a failure.

    The 2026-09-13 measurement is why this class exists. PIPE-docs-sync's
    setup prompt is a whole /acs:code cycle; sized by docs-sync's own budget
    it timed out, and a second run's setup finished clean but left no
    changeset, so docs-sync correctly refused. Both were scored as docs-sync
    failing. The skill was never once exercised on the app profile, and the
    gate reported it as 0% reliable rather than unmeasured.
    """

    def test_a_hole_leaves_the_reliability_denominator(self):
        probe = unmeasured_pipeline(measured=[(True, "completed"),
                                              (True, "completed")], holes=1)
        rel = probe["aggregate"]["reliability"]
        self.assertEqual((rel["hits"], rel["total"], rel["rate"]), (2, 2, 1.0))
        self.assertEqual(probe["aggregate"]["unmeasured"], 1)

    def test_a_skill_that_ran_and_failed_stays_in_the_denominator(self):
        # The distinction the whole class turns on: this one IS the plugin's.
        probe = unmeasured_pipeline(measured=[(True, "completed"),
                                              (True, "failed")], holes=0)
        rel = probe["aggregate"]["reliability"]
        self.assertEqual((rel["hits"], rel["total"]), (1, 2))
        self.assertEqual(probe["aggregate"]["unmeasured"], 0)

    def test_a_hole_does_not_drag_the_medians_the_gate_compares(self):
        # An unmeasured run records zero seconds and no cost.
        probe = unmeasured_pipeline(measured=[(True, "completed"),
                                              (True, "completed")], holes=1)
        agg = probe["aggregate"]
        self.assertEqual(agg["seconds"]["median"], 40.0)
        self.assertEqual(agg["seconds"]["n"], 2)
        self.assertEqual(agg["cost_usd"]["median"], 0.3)

    def test_a_hole_is_reported_on_its_own_axis(self):
        probe = unmeasured_pipeline(measured=[(True, "completed"),
                                              (True, "completed")], holes=1)
        found = pg.compare(measurement([probe]), None, PROVISIONAL)
        cov = [f for f in found if f["axis"] == "coverage"]
        self.assertEqual(len(cov), 1)
        self.assertEqual(cov[0]["severity"], "major")
        self.assertIn("1 of 3 runs measured nothing", cov[0]["summary"])
        # ... and not as a reliability failure of the skill.
        self.assertEqual([f for f in found if f["axis"] == "reliability"], [])

    def test_a_scenario_that_measured_nothing_says_so_rather_than_zero(self):
        probe = unmeasured_pipeline(pid="PIPE-docs-sync-app", measured=[],
                                    holes=3)
        found = pg.compare(measurement([probe]), None, PROVISIONAL)
        summaries = " | ".join(f["summary"] for f in found)
        self.assertIn("3 of 3 runs measured nothing", summaries)
        self.assertIn("unevaluated", summaries)
        self.assertNotIn("completed 0 of 3", summaries)

    def test_a_hole_blocks_even_while_thresholds_are_provisional(self):
        # It is an absolute finding: nothing was measured, whatever the
        # ratios would have said.
        probe = unmeasured_pipeline(measured=[(True, "completed")], holes=2)
        found = pg.compare(measurement([probe]), None, PROVISIONAL)
        state, headline, detail = pg.verdict(measurement([probe]), None,
                                             PROVISIONAL, found)
        self.assertEqual(state, "fail")
        self.assertEqual(headline, "Skill performance: BLOCKED")
        self.assertIn("2 of 3 runs measured nothing", detail)


class TestPipelineHits(unittest.TestCase):
    """A pipeline hit is the measured skill's OWN ledger saying `completed`.

    The 2026-09-14 PIPE-code diagnostic is why: two sessions exited 0 after
    routing "TKT-1 is ready to implement" to /acs:ship, which ran
    /acs:analyze-ticket and stopped. /acs:code never ran, so its ledger did
    not exist, and `status != "failed"` scored both as completions of a
    skill that was never exercised.
    """

    def _probe(self, ok, status):
        probe = {"id": "PIPE-code", "kind": "pipeline", "skill": "acs:code",
                 "runs": [{"ok": ok, "seconds": 10.0, "cost_usd": 1.0,
                           "status": status,
                           "quality": {"verify_iterations": None,
                                       "coverage_percent": None,
                                       "blocking_findings": None}}]}
        return pg.summarize(probe)["reliability"]

    def test_a_clean_session_with_no_ledger_is_not_a_hit(self):
        self.assertEqual(self._probe(True, None)["hits"], 0)

    def test_a_failed_ledger_is_not_a_hit(self):
        self.assertEqual(self._probe(True, "failed")["hits"], 0)

    def test_a_handed_off_ledger_is_not_a_hit(self):
        self.assertEqual(self._probe(True, "handed_off")["hits"], 0)

    def test_a_completed_ledger_on_a_clean_session_is_a_hit(self):
        rel = self._probe(True, "completed")
        self.assertEqual((rel["hits"], rel["total"]), (1, 1))

    def test_a_completed_ledger_on_a_broken_session_is_not_a_hit(self):
        # The ledger can say completed while the session itself died after
        # (a post-hook crash, a kill during the report); the session's exit
        # is still part of what the consumer experienced.
        self.assertEqual(self._probe(False, "completed")["hits"], 0)


class TestAbsoluteGates(unittest.TestCase):
    """Floors that hold with no baseline — definitions, not measurements."""

    def test_an_off_domain_control_scores_a_hit_only_when_nothing_routes(self):
        quiet = routing("CONTROL-off-domain", skill=None, must=False,
                        routed=[None, None, None], control=True)
        self.assertEqual(quiet["aggregate"]["reliability"]["hits"], 3)
        noisy = routing("CONTROL-off-domain", skill=None, must=False,
                        routed=[None, "acs:code", None], control=True)
        self.assertEqual(noisy["aggregate"]["reliability"]["hits"], 2)

    def test_a_registration_canary_that_misses_is_critical(self):
        m = {"probes": [routing("CONTROL-registration-canary", "acs:setup",
                                routed=["acs:setup", None, "acs:setup"],
                                control=True)]}
        f = pg.compare(m, None, PROVISIONAL)
        self.assertEqual([x["severity"] for x in f], ["critical"])
        self.assertIn("instrument", f[0]["summary"])
        state, headline, _ = pg.verdict(m, None, PROVISIONAL, f)
        self.assertEqual(state, "fail")
        self.assertIn("critical", headline)

    def test_an_unregistered_command_that_registers_is_critical(self):
        m = {"probes": [routing("CONTROL-unregistered-command",
                                "acs:no-such-skill", must=False,
                                routed=["acs:no-such-skill", None, None],
                                control=True)]}
        f = pg.compare(m, None, PROVISIONAL)
        self.assertEqual([x["severity"] for x in f], ["critical"])

    def test_a_passing_control_is_silent(self):
        m = {"probes": [
            routing("CONTROL-registration-canary", "acs:setup", control=True),
            routing("CONTROL-unregistered-command", "acs:no-such-skill",
                    must=False, routed=[None] * 3, control=True),
            routing("CONTROL-off-domain", None, must=False, routed=[None] * 3,
                    control=True)]}
        self.assertEqual(pg.compare(m, None, PROVISIONAL), [])

    def test_a_routing_scoped_baseline_is_named_in_the_verdict(self):
        m = {"probes": [routing(), pipeline()], "scope": "full"}
        base = {"probes": [routing(seconds=4.0)], "scope": "routing",
                "scenario_set_version": None}
        f = pg.compare(m, base, PROVISIONAL)
        self.assertEqual(f, [])
        state, _headline, detail = pg.verdict(m, base, PROVISIONAL, f)
        self.assertEqual(state, "pass")
        self.assertIn("routing-scoped", detail)

    def test_a_routing_baseline_survives_a_pipeline_change(self):
        m = {"probes": [routing()], "set_hashes": {"routing": "r1", "pipeline": "p2"}}
        base = {"probes": [routing()], "scope": "routing",
                "set_hashes": {"routing": "r1", "pipeline": "p1"}}
        self.assertIsNone(pg.incomparable(m, base))

    def test_a_routing_baseline_is_refused_when_the_probes_changed(self):
        m = {"probes": [routing()], "set_hashes": {"routing": "r2", "pipeline": "p1"}}
        base = {"probes": [routing()], "scope": "routing",
                "set_hashes": {"routing": "r1", "pipeline": "p1"}}
        self.assertIn("routing half", pg.incomparable(m, base))

    def test_a_full_baseline_needs_both_halves_unchanged(self):
        m = {"probes": [routing()], "set_hashes": {"routing": "r1", "pipeline": "p2"}}
        base = {"probes": [routing()], "scope": "full",
                "set_hashes": {"routing": "r1", "pipeline": "p1"}}
        self.assertIn("pipeline half", pg.incomparable(m, base))

    def test_documents_without_hashes_fall_back_to_the_version_label(self):
        m = {"probes": [routing()], "scenario_set_version": "1.1.0"}
        base = {"probes": [routing()], "scenario_set_version": "1.0.0"}
        self.assertIn("not comparable", pg.incomparable(m, base))
        self.assertIsNone(pg.incomparable(m, dict(base, scenario_set_version="1.1.0")))

    def test_a_clean_first_measurement_is_uncompared_never_passed(self):
        m = measurement([routing(), pipeline()])
        f = pg.compare(m, None, PROVISIONAL)
        state, headline, _ = pg.verdict(m, None, PROVISIONAL, f)
        self.assertEqual(f, [])
        self.assertEqual(state, "warn")
        self.assertIn("UNCOMPARED", headline)

    def test_no_measurement_is_unmeasured_and_fails(self):
        state, headline, detail = pg.verdict(None, None, PROVISIONAL, [])
        self.assertEqual(state, "fail")
        self.assertIn("UNMEASURED", headline)
        self.assertIn("unknown — not unchanged", detail)

    def test_a_split_routing_result_is_a_finding_not_a_pass(self):
        # Four of five is the case the decision rule exists for.
        m = measurement([routing(routed=["acs:code"] * 4 + ["acs:ship"])])
        f = pg.compare(m, None, PROVISIONAL)
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["axis"], f[0]["severity"]),
                         ("reliability", "major"))
        state, _, _ = pg.verdict(m, None, PROVISIONAL, f)
        self.assertEqual(state, "fail")

    def test_one_auto_invocation_of_a_user_only_skill_is_critical(self):
        m = measurement([routing(pid="ROUTE-update-negative",
                                 skill="acs:update", must=False,
                                 routed=[None, None, "acs:update"])])
        f = pg.compare(m, None, PROVISIONAL)
        self.assertEqual(f[0]["severity"], "critical")
        state, headline, _ = pg.verdict(m, None, PROVISIONAL, f)
        self.assertEqual(state, "fail")
        self.assertIn("critical", headline)

    def test_absolute_gates_block_even_while_thresholds_are_provisional(self):
        # Provisional calibration excuses ratios, never floors.
        m = measurement([pipeline(ok=False)])
        f = pg.compare(m, None, PROVISIONAL)
        state, _, _ = pg.verdict(m, None, PROVISIONAL, f)
        self.assertEqual(state, "fail")

    def test_a_run_that_ends_carrying_a_blocking_finding_fails(self):
        m = measurement([pipeline(blocking=1)])
        f = pg.compare(m, None, PROVISIONAL)
        self.assertTrue(any(x["axis"] == "quality" for x in f))
        self.assertEqual(pg.verdict(m, None, PROVISIONAL, f)[0], "fail")

    def test_a_probe_that_never_ran_is_reported_not_skipped(self):
        probe = {"id": "PIPE-code", "kind": "pipeline", "skill": "acs:code",
                 "runs": []}
        probe["aggregate"] = pg.summarize(probe)
        f = pg.compare(measurement([probe]), None, PROVISIONAL)
        self.assertIn("did not execute", f[0]["summary"])


class TestRelativeGates(unittest.TestCase):
    """Ratios against a baseline — opinions until calibrated."""

    def test_a_doubling_of_cost_is_found(self):
        base = measurement([pipeline(cost=2.0)], version="0.4.9")
        m = measurement([pipeline(cost=4.0)])
        f = pg.compare(m, base, PROVISIONAL)
        self.assertEqual([x["axis"] for x in f], ["cost_usd"])
        self.assertIn("2.00x", f[0]["summary"])
        self.assertTrue(f[0]["relative"])

    def test_a_provisional_ratio_reports_but_does_not_block(self):
        base = measurement([pipeline(cost=2.0)], version="0.4.9")
        m = measurement([pipeline(cost=4.0)])
        f = pg.compare(m, base, PROVISIONAL)
        state, headline, _ = pg.verdict(m, base, PROVISIONAL, f)
        self.assertEqual(state, "warn")
        self.assertIn("uncalibrated drift", headline)

    def test_the_same_ratio_blocks_once_thresholds_are_calibrated(self):
        base = measurement([pipeline(cost=2.0)], version="0.4.9")
        m = measurement([pipeline(cost=4.0)])
        f = pg.compare(m, base, CALIBRATED)
        state, _, _ = pg.verdict(m, base, CALIBRATED, f)
        self.assertEqual(state, "fail")

    def test_a_tiny_baseline_is_exempt_so_noise_does_not_fire(self):
        # $0.004 -> $0.008 is a doubling and means nothing.
        base = measurement([routing(cost=0.004)], version="0.4.9")
        m = measurement([routing(cost=0.008)])
        self.assertEqual(pg.compare(m, base, CALIBRATED), [])

    def test_time_is_banded_looser_than_cost(self):
        # 1.4x trips cost's 1.25x ceiling but not time's 1.5x.
        base = measurement([pipeline(seconds=600.0, cost=2.0)], version="0.4.9")
        m = measurement([pipeline(seconds=840.0, cost=2.0)])
        self.assertEqual(pg.compare(m, base, CALIBRATED), [])

    def test_rising_verify_iterations_are_a_quality_finding(self):
        base = measurement([pipeline(iters=1)], version="0.4.9")
        m = measurement([pipeline(iters=3)])
        f = pg.compare(m, base, CALIBRATED)
        self.assertTrue(any("verify iterations" in x["summary"] for x in f))

    def test_falling_coverage_is_a_quality_finding(self):
        base = measurement([pipeline(coverage=85.0)], version="0.4.9")
        m = measurement([pipeline(coverage=80.0)])
        f = pg.compare(m, base, CALIBRATED)
        self.assertTrue(any("coverage fell" in x["summary"] for x in f))

    def test_an_improvement_is_never_a_finding(self):
        base = measurement([pipeline(cost=4.0, seconds=900.0, iters=3,
                                     coverage=80.0)], version="0.4.9")
        m = measurement([pipeline(cost=1.0, seconds=300.0, iters=1,
                                  coverage=90.0)])
        self.assertEqual(pg.compare(m, base, CALIBRATED), [])


class TestComparability(unittest.TestCase):

    def test_a_changed_scenario_set_refuses_the_baseline(self):
        # A changed experiment makes the numbers incomparable; saying so beats
        # comparing them anyway.
        base = measurement([pipeline()], version="0.4.9", sset="1.0.0")
        m = measurement([pipeline()], sset="2.0.0")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "base.json")
            import json
            with open(path, "w") as fh:
                json.dump(base, fh)
            got, refusal = pg.pick_baseline(m, path)
        self.assertIsNone(got)
        self.assertIn("not comparable", refusal)

    def test_an_incomplete_measurement_is_named_in_the_verdict(self):
        m = measurement([routing()], incomplete=True)
        _, _, detail = pg.verdict(m, None, PROVISIONAL,
                                  pg.compare(m, None, PROVISIONAL))
        self.assertIn("incomplete", detail)


class TestBuildIdentity(unittest.TestCase):
    """The gate judges a measurement of THIS build, or refuses to judge.

    A release quoting numbers taken before its own changes is the failure a
    gate that runs before every cut exists to prevent, so the comparison is
    on the tree's content digest -- not the version string, which an
    unreleased tree shares with the release it supersedes.
    """

    def test_the_same_content_is_judged(self):
        m = measurement([routing()], digest="c0ffee")
        self.assertIsNone(pg.stale_measurement(m, _Build(digest="c0ffee")))

    def test_the_version_label_does_not_matter_when_the_content_does(self):
        # A cut bumps plugin.json AFTER the gate passed on this content; the
        # measurement it passed on is still a measurement of it.
        m = measurement([routing()], version="0.4.9", digest="c0ffee")
        self.assertIsNone(pg.stale_measurement(
            m, _Build(version="0.5.0", digest="c0ffee")))

    def test_changed_content_is_refused_and_both_builds_are_named(self):
        m = measurement([routing()], digest="c0ffee")
        why = pg.stale_measurement(m, _Build(digest="d15ea5e"))
        self.assertIn("c0ffee", why)
        self.assertIn("d15ea5e", why)
        self.assertIn("/plugins/acs", why, "name the tree it resolved, so a "
                      "mismatch caused by resolving the wrong tree is obvious")

    def test_a_measurement_with_no_digest_is_refused(self):
        m = measurement([routing()])
        self.assertIn("no content digest", pg.stale_measurement(m, _Build()))

    def test_no_build_in_hand_is_refused_not_assumed(self):
        m = measurement([routing()], digest="c0ffee")
        self.assertIn("ACS_PLUGIN_ROOT", pg.stale_measurement(m, None))

    def test_a_stale_verdict_fails_as_unmeasured(self):
        state, headline, detail = pg.stale_verdict("the plugin changed")
        self.assertEqual(state, "fail")
        self.assertIn("UNMEASURED", headline)
        self.assertIn("the plugin changed", detail)
        self.assertIn("not unchanged", detail)

    def test_a_root_that_is_not_a_build_resolves_to_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            build, why = pg.build_under_test(d)
        self.assertIsNone(build)
        self.assertIn("acs.py", why)

    def test_the_result_file_records_a_stale_verdict(self):
        """A perf.json left over from the last judged measurement would say
        PASSED about a build the gate just refused to judge."""
        import json
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "perf.json")
            state, headline, detail = pg.stale_verdict("why")
            pg.write_result(path, measurement([routing()]), None, None,
                            PROVISIONAL, state, headline, detail, [],
                            stale="why")
            with open(path) as fh:
                got = json.load(fh)
        self.assertEqual(got["state"], "fail")
        self.assertEqual(got["stale"], "why")
        self.assertEqual(got["findings"], [])


class RoutingHoleTest(unittest.TestCase):
    """A routing run the instrument never delivered to the model leaves the
    reliability denominator and is reported on the coverage axis, exactly as
    a pipeline run whose setup fell short."""

    def test_an_unmeasured_routing_run_is_a_hole_not_a_miss(self):
        probe = {"id": "ROUTE-create-docs", "kind": "routing", "skill": "acs:create-docs",
                 "expect": {"must_route": True, "skill": "acs:create-docs"},
                 "runs": [{"ok": True, "routed_to": "acs:create-docs", "seconds": 2.0},
                          {"ok": False, "routed_to": None, "seconds": 180.0,
                           "unmeasured": "no model turn, twice"},
                          {"ok": True, "routed_to": "acs:create-docs", "seconds": 2.5}]}
        agg = pg.summarize(probe)
        self.assertEqual((agg["reliability"]["hits"], agg["reliability"]["total"]), (2, 2))
        self.assertEqual(agg["unmeasured"], 1)
        self.assertEqual(agg["seconds"]["max"], 2.5)

    def test_a_reply_that_did_not_route_is_still_a_miss(self):
        probe = {"id": "ROUTE-create-prd", "kind": "routing", "skill": "acs:create-prd",
                 "expect": {"must_route": True, "skill": "acs:create-prd"},
                 "runs": [{"ok": True, "routed_to": None, "seconds": 2.4}]}
        agg = pg.summarize(probe)
        self.assertEqual((agg["reliability"]["hits"], agg["reliability"]["total"]), (0, 1))
        self.assertEqual(agg["unmeasured"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
