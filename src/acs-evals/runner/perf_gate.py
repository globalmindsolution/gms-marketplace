#!/usr/bin/env python3
"""Tier 3's gate: compare a measurement against a baseline and say what moved.

Tier 1 asks "did the plumbing change bytes". This asks the four questions a
release actually turns on — did the skills get less reliable, worse, more
expensive, or slower — and it is the half of tier 3 that needs no model, no
network and no money, so it runs anywhere tier 1 runs.

    python3 runner/perf_gate.py --measurement results/measurements.json
    python3 runner/perf_gate.py --measurement M --baseline dataset/baselines/acs-0.4.10.json
    python3 runner/perf_gate.py --measurement M --json results/perf.json

Two rules shape everything below.

**Absence is not a pass.** With no measurement the verdict is UNMEASURED and
the exit status is non-zero. The failure mode this tier exists to fix is a
green report that quietly means less than a reader thinks, so it may never be
green by default.

**A guess may not block a release.** The gates split in two. *Absolute* gates —
routing accuracy, run completion, unresolved blocking findings — are definitions
rather than measurements: a positive probe that routes on 4 of 5 runs is
unreliable whatever any baseline says, so these block on the first measurement,
with no baseline needed. *Relative* gates — cost, time, verify iterations —
compare against a recorded baseline through a ratio, and a ratio nobody has
calibrated against observed noise is an opinion. While
`dataset/thresholds.json` says `basis: provisional`, relative findings are
reported and never block. `calibration_protocol` in that file is how they stop
being provisional.
"""

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATASET = os.path.join(ROOT, "dataset")
BASELINES = os.path.join(DATASET, "baselines")


# --------------------------------------------------------------------------
# Summarising runs
#
# Shared with runner/measure_skills.py deliberately: the collector writes these
# aggregates and the gate reads them, so one implementation of "what is the
# median" keeps the two from disagreeing about the same runs.
# --------------------------------------------------------------------------

def median(values):
    """Median of the numbers present, or None if there are none.

    Median rather than mean throughout: one 30-minute timeout in five runs
    should not move the number a release is judged on.
    """
    nums = sorted(v for v in values if isinstance(v, (int, float)))
    if not nums:
        return None
    mid = len(nums) // 2
    if len(nums) % 2:
        return float(nums[mid])
    return (nums[mid - 1] + nums[mid]) / 2.0


def spread(values):
    """median/min/max/n — the shape the gate compares and calibration reads.

    The range is carried because a threshold set without knowing the noise
    floor is a guess, and a guess that blocks releases trains people to
    override the gate.
    """
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return {"median": median(nums), "min": float(min(nums)),
            "max": float(max(nums)), "n": len(nums)}


def summarize(probe):
    """Build a probe's `aggregate` from its raw runs."""
    runs = probe.get("runs") or []
    kind = probe.get("kind")
    agg = {"runs": len(runs)}

    if kind == "routing":
        expect = probe.get("expect") or {}
        want = expect.get("skill") or probe.get("skill")
        must = expect.get("must_route", True)
        # A negative probe scores a hit when the skill did NOT fire, so both
        # kinds read as "higher is better" and one floor covers both. A probe
        # that names no skill at all (the off-domain control) fires when ANY
        # skill routed: the answer it must produce is "nothing".
        def fired(run):
            if want is None:
                return run.get("routed_to") is not None
            return run.get("routed_to") == want
        hits = sum(1 for r in runs if fired(r) == bool(must))
    else:
        hits = sum(1 for r in runs if r.get("ok"))
    agg["reliability"] = {
        "hits": hits, "total": len(runs),
        "rate": (hits / len(runs)) if runs else None,
    }

    agg["seconds"] = spread([r.get("seconds") for r in runs])
    agg["cost_usd"] = spread([r.get("cost_usd") for r in runs])

    quals = [r.get("quality") or {} for r in runs]
    agg["verify_iterations"] = spread([q.get("verify_iterations") for q in quals])
    agg["coverage_percent"] = spread([q.get("coverage_percent") for q in quals])
    blocking = [q.get("blocking_findings") for q in quals
                if isinstance(q.get("blocking_findings"), int)]
    agg["blocking_findings_rate"] = (
        sum(1 for b in blocking if b > 0) / len(blocking) if blocking else None)
    return agg


# --------------------------------------------------------------------------
# Comparing
# --------------------------------------------------------------------------

def _finding(probe_id, axis, severity, summary, observed=None, baseline=None,
             threshold=None, relative=False):
    return {"probe": probe_id, "axis": axis, "severity": severity,
            "summary": summary, "observed": observed, "baseline": baseline,
            "threshold": threshold, "relative": relative}


def _agg(probe):
    return probe.get("aggregate") or summarize(probe)


def _ratio_check(probe_id, axis, label, obs, base, rule, floor_value,
                 severity, prefix="", suffix=""):
    """One relative gate. Returns a finding, or None when the axis held."""
    if not obs or not base:
        return None
    o, b = obs.get("median"), base.get("median")
    if not isinstance(o, (int, float)) or not isinstance(b, (int, float)):
        return None
    if b <= 0:
        return None
    # Small baselines are exempt: a routing probe moving $0.004 -> $0.006 is a
    # 50% regression and means nothing. The floor keeps the gate off noise.
    if floor_value is not None and b < floor_value:
        return None
    ratio = o / b
    if ratio <= rule:
        return None
    return _finding(
        probe_id, axis, severity,
        "median %s rose to %s%.4g%s from %s%.4g%s (%.2fx, ceiling %.2fx)"
        % (label, prefix, o, suffix, prefix, b, suffix, ratio, rule),
        observed=o, baseline=b, threshold=rule, relative=True)


def compare(measurement, baseline, thresholds):
    """Every finding in the measurement, worst axis first.

    A finding is a statement that a declared threshold was crossed. Whether it
    blocks is decided later, by `verdict`, because that also depends on whether
    the threshold was calibrated.
    """
    findings = []
    rel = thresholds.get("reliability", {})
    cost = thresholds.get("cost", {})
    time_t = thresholds.get("time", {})
    qual = thresholds.get("quality", {})

    base_by_id = {p["id"]: p for p in (baseline or {}).get("probes", [])}

    for probe in measurement.get("probes", []):
        pid = probe["id"]
        kind = probe.get("kind")
        agg = _agg(probe)
        base = base_by_id.get(pid)
        base_agg = _agg(base) if base else None

        # -- Absolute: reliability ------------------------------------------
        r = agg.get("reliability") or {}
        rate, total = r.get("rate"), r.get("total") or 0
        if total == 0:
            findings.append(_finding(
                pid, "reliability", "major",
                "no runs recorded — the probe did not execute"))
        elif kind == "routing":
            expect = probe.get("expect") or {}
            negative = not expect.get("must_route", True)
            control = bool(expect.get("control"))
            if control:
                # A control's answer is known in advance; missing it says the
                # instrument is broken, and nothing measured around it can be
                # read. That is why its floor carries its own severity.
                key = "routing_control_floor"
            else:
                key = ("routing_negative_accuracy_floor" if negative
                       else "routing_positive_accuracy_floor")
            spec = rel.get(key, {})
            floor = spec.get("value", 1.0)
            if rate is not None and rate < floor:
                if control:
                    summary = ("control failed on %d of %d runs (floor %.0f%%) "
                               "— the instrument, not the plugin, is suspect; "
                               "no other probe in this measurement can be read"
                               % (total - r.get("hits", 0), total, floor * 100))
                else:
                    summary = ("%s on %d of %d runs (floor %.0f%%)"
                               % ("auto-invoked despite disable-model-invocation"
                                  if negative else "routed to the expected skill",
                                  r.get("hits", 0) if not negative
                                  else total - r.get("hits", 0),
                                  total, floor * 100))
                findings.append(_finding(
                    pid, "reliability",
                    spec.get("severity", "critical" if control else "major"),
                    summary, observed=rate, threshold=floor))
        else:
            spec = rel.get("pipeline_completion_floor", {})
            floor = spec.get("value", 1.0)
            if rate is not None and rate < floor:
                findings.append(_finding(
                    pid, "reliability", spec.get("severity", "major"),
                    "completed %d of %d runs (floor %.0f%%)"
                    % (r.get("hits", 0), total, floor * 100),
                    observed=rate, threshold=floor))

        # -- Absolute: quality that needs no baseline -----------------------
        spec = qual.get("blocking_findings_rate_ceiling", {})
        ceiling = spec.get("value", 0.0)
        bfr = agg.get("blocking_findings_rate")
        if isinstance(bfr, (int, float)) and bfr > ceiling:
            findings.append(_finding(
                pid, "quality", spec.get("severity", "major"),
                "%.0f%% of runs finished carrying an unresolved blocking "
                "finding (ceiling %.0f%%)" % (bfr * 100, ceiling * 100),
                observed=bfr, threshold=ceiling))

        if base_agg is None:
            continue  # nothing relative to say about a probe with no baseline

        # -- Relative: cost, time, quality ----------------------------------
        f = _ratio_check(
            pid, "cost_usd", "cost", agg.get("cost_usd"),
            base_agg.get("cost_usd"),
            cost.get("median_regression_ratio", {}).get("value", 1.25),
            cost.get("absolute_floor_usd", {}).get("value"),
            cost.get("median_regression_ratio", {}).get("severity", "major"),
            prefix="$")
        if f:
            findings.append(f)

        f = _ratio_check(
            pid, "seconds", "wall clock", agg.get("seconds"),
            base_agg.get("seconds"),
            time_t.get("median_regression_ratio", {}).get("value", 1.5),
            time_t.get("absolute_floor_seconds", {}).get("value"),
            time_t.get("median_regression_ratio", {}).get("severity", "major"),
            suffix="s")
        if f:
            findings.append(f)

        spec = qual.get("verify_iterations_median_ceiling_delta", {})
        delta_max = spec.get("value", 1)
        obs_i = (agg.get("verify_iterations") or {}).get("median")
        base_i = (base_agg.get("verify_iterations") or {}).get("median")
        if isinstance(obs_i, (int, float)) and isinstance(base_i, (int, float)):
            if obs_i - base_i > delta_max:
                findings.append(_finding(
                    pid, "quality", spec.get("severity", "major"),
                    "median verify iterations rose to %.1f from %.1f "
                    "(ceiling +%s)" % (obs_i, base_i, delta_max),
                    observed=obs_i, baseline=base_i, threshold=delta_max,
                    relative=True))

        spec = qual.get("coverage_floor_delta", {})
        delta_min = spec.get("value", -2.0)
        obs_c = (agg.get("coverage_percent") or {}).get("median")
        base_c = (base_agg.get("coverage_percent") or {}).get("median")
        if isinstance(obs_c, (int, float)) and isinstance(base_c, (int, float)):
            if obs_c - base_c < delta_min:
                findings.append(_finding(
                    pid, "quality", spec.get("severity", "major"),
                    "median coverage fell to %.1f%% from %.1f%% (floor %s pp)"
                    % (obs_c, base_c, delta_min),
                    observed=obs_c, baseline=base_c, threshold=delta_min,
                    relative=True))

    order = {"critical": 0, "major": 1, "minor": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["probe"]))
    return findings


# --------------------------------------------------------------------------
# The verdict
# --------------------------------------------------------------------------

def verdict(measurement, baseline, thresholds, findings):
    """(state, headline, detail) — mirrors docs/RUBRIC.md's four states.

    The two states tier 1 does not have are the honest ones: UNMEASURED when
    nothing was run, and UNCOMPARED when this is the first measurement and
    there is nothing to regress against.
    """
    if measurement is None:
        return ("fail", "Skill performance: UNMEASURED",
                "No tier-3 measurement exists for this build. Quality, "
                "reliability, cost and time are unknown — not unchanged. Run "
                "`make measure` before quoting this gate.")

    provisional = thresholds.get("basis") != "calibrated"
    blocking = [f for f in findings
                if not (provisional and f["relative"])]
    crit = [f for f in blocking if f["severity"] == "critical"]
    major = [f for f in blocking if f["severity"] == "major"]
    deferred = [f for f in findings if f not in blocking]

    if measurement.get("incomplete"):
        note = (" The measurement is marked incomplete — some probes did not "
                "produce the runs the scenario set asks for, so it may not be "
                "promoted to a baseline.")
    else:
        note = ""
    base_scope = (baseline or {}).get("scope", "full")
    if baseline is not None and base_scope != "full":
        note += (" The baseline is %s-scoped: only %s probes have anything to "
                 "compare against; a full `make measure` baseline supersedes "
                 "it." % (base_scope, base_scope))

    if crit:
        return ("fail", "Skill performance: BLOCKED (critical)",
                "%d critical finding(s). A documented user guarantee moved — "
                "see docs/PERFORMANCE.md. Do not cut a release from this "
                "build.%s" % (len(crit), note))
    if major:
        return ("fail", "Skill performance: BLOCKED",
                "%d finding(s) crossed an absolute floor: skills got less "
                "reliable, or ran out of the pipeline carrying blocking "
                "findings.%s" % (len(major), note))
    if baseline is None:
        return ("warn", "Skill performance: UNCOMPARED (baseline established)",
                "The absolute floors held, but this is the first measurement "
                "for this scenario set — there is nothing to compare cost, "
                "time or iteration counts against. Promote it to "
                "dataset/baselines/ and the next release gets a real "
                "comparison.%s" % note)
    if deferred:
        return ("warn", "Skill performance: PASSED (uncalibrated drift)",
                "%d relative finding(s) crossed a PROVISIONAL threshold. "
                "Nothing blocks, because a ratio nobody has calibrated against "
                "observed noise cannot fail a release — but each is a prompt "
                "to look. See `calibration_protocol` in "
                "dataset/thresholds.json.%s" % (len(deferred), note))
    return ("pass", "Skill performance: PASSED",
            "Every probe held its floors, and no axis regressed past its "
            "threshold against acs %s.%s"
            % ((baseline.get("build") or {}).get("version", "?"), note))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def load(path):
    if not path or not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def pick_baseline(measurement, explicit):
    """The baseline to compare against, or None.

    A baseline recorded under a different `scenario_set_version` is refused
    rather than used: the experiment changed, so the numbers are not
    comparable and pretending otherwise is worse than having no baseline.
    """
    if explicit:
        base = load(explicit)
        if base is None:
            raise SystemExit("error: no baseline at %s" % explicit)
    else:
        if not os.path.isdir(BASELINES):
            return None, None
        cands = sorted(glob_json(BASELINES))
        if not cands:
            return None, None
        base = load(cands[-1])
    reason = incomparable(measurement, base)
    if reason:
        return None, reason
    return base, None


def incomparable(measurement, base):
    """Why `base` cannot be compared against `measurement`, or None.

    When both documents carry `set_hashes`, comparability is decided per half:
    a routing-scoped baseline needs only the routing half unchanged, a
    pipeline-scoped one only the pipeline half, a full one both — so adding a
    pipeline scenario does not throw away a routing baseline. Documents
    without hashes fall back to the scenario_set_version label.
    """
    if base is None:
        return None
    mh, bh = measurement.get("set_hashes"), base.get("set_hashes")
    if mh and bh:
        scope = base.get("scope", "full")
        halves = {"routing": ["routing"], "pipeline": ["pipeline"]}.get(scope, ["routing", "pipeline"])
        stale = [h for h in halves if mh.get(h) != bh.get(h)]
        if stale:
            return ("baseline %s covers the %s half, whose content changed since it was "
                    "recorded (%s) — not comparable"
                    % ((base.get("build") or {}).get("version", "?"),
                       " and ".join(stale), ", ".join("%s %s -> %s" % (h, bh.get(h), mh.get(h)) for h in stale)))
        return None
    want = measurement.get("scenario_set_version")
    got = base.get("scenario_set_version")
    if want != got:
        return ("baseline %s was recorded under scenario set %s, this "
                "measurement under %s — not comparable" % (
                    (base.get("build") or {}).get("version", "?"), got, want))
    return None


def glob_json(directory):
    return [os.path.join(directory, n) for n in os.listdir(directory)
            if n.endswith(".json")]


def main():
    ap = argparse.ArgumentParser(description="tier 3 — skill performance gate")
    ap.add_argument("--measurement", default="results/measurements.json")
    ap.add_argument("--baseline", default=None,
                    help="default: the newest file in dataset/baselines/")
    ap.add_argument("--thresholds",
                    default=os.path.join(DATASET, "thresholds.json"))
    ap.add_argument("--json", dest="out", default=None,
                    help="write the machine-readable result here")
    args = ap.parse_args()

    thresholds = load(args.thresholds) or {}
    measurement = load(args.measurement)

    if measurement is None:
        state, headline, detail = verdict(None, None, thresholds, [])
        print(headline)
        print("  " + detail)
        print("\n  looked for: %s" % args.measurement)
        return 2

    baseline, refusal = pick_baseline(measurement, args.baseline)
    findings = compare(measurement, baseline, thresholds)
    state, headline, detail = verdict(measurement, baseline, thresholds,
                                      findings)

    print("acs skill performance  |  build under test: acs %s  |  scenario set %s"
          % ((measurement.get("build") or {}).get("version", "?"),
             measurement.get("scenario_set_version", "?")))
    if refusal:
        print("NOTE: %s" % refusal)
    if thresholds.get("basis") != "calibrated":
        print("NOTE: thresholds are PROVISIONAL — relative findings report, "
              "they do not block. See dataset/thresholds.json.")
    print()

    if findings:
        for f in findings:
            print("  %-8s %-22s %-12s %s"
                  % (f["severity"], f["probe"], f["axis"], f["summary"]))
        print()
    else:
        print("  no findings\n")

    print(headline)
    print("  " + detail)

    if args.out:
        directory = os.path.dirname(os.path.abspath(args.out))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump({
                "schema": "acs-evals/perf-result/1",
                "generated_at": datetime.datetime.now(datetime.timezone.utc)
                                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "build": measurement.get("build"),
                "scenario_set_version": measurement.get("scenario_set_version"),
                "baseline": (baseline or {}).get("build"),
                "baseline_refused": refusal,
                "thresholds_basis": thresholds.get("basis"),
                "state": state, "headline": headline, "detail": detail,
                "findings": findings,
            }, fh, indent=2)
            fh.write("\n")

    return 0 if state != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
