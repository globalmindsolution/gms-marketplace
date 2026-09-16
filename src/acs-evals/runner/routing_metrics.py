#!/usr/bin/env python3
"""Per-skill routing metrics: a confusion matrix, precision, recall, F1.

Routing is a multi-class classification problem the suite was only ever
scoring one way. A probe asks "given this prompt, which skill gets invoked?";
the truth is the probe's expected skill and the prediction is the run's
`routed_to`. The gate reads that as a per-probe hit rate, which answers
**recall** and is blind to **precision**: when a prompt for A is answered by
B, A's probe fails and B is never named, so a skill whose description has
grown too broad shows up only as its neighbours' failures.

These are DIAGNOSTIC, not a gate. The suite's rule -- every positive probe
must route correctly on every run -- is strictly stricter than any average:
micro and macro means both survive one skill failing outright, and a release
rule that averages over skills is a release rule that ships a broken skill.
Precision and F1 say WHERE to look once something has gone red; they do not
decide whether it is red. `dataset/thresholds.json` reads none of this.

Scoring rules, which the label space forces:

- Only POSITIVE probes enter the matrix (`expect.must_route` true and not a
  control). A negative probe asserts "must not route to X", which is a
  constraint, not a class: on the 2026-09-15 data both negative probes
  correctly routed to `/acs:project` (the entry point that coordinates the
  leg), and folding that into the matrix scored 10 runs as errors when every
  one of them was the desired outcome.
- Controls test the instrument, not the plugin, and are reported apart.
- A run that routed nowhere is the label `(none)`, a real class: it is what
  the off-domain control expects and what a description failure produces.
- Precision is undefined for a label nothing was routed to. It is reported as
  null and left out of the macro mean rather than counted as 1.0, which would
  quietly reward a skill nothing ever reaches.
"""

import collections


#: The label for a run that invoked no skill at all.
NO_ROUTE = "(none)"


def _is_positive(probe):
    expect = probe.get("expect") or {}
    return bool(expect.get("must_route")) and not expect.get("control")


def _is_control(probe):
    return bool((probe.get("expect") or {}).get("control"))


def routing_probes(measurement):
    return [p for p in (measurement.get("probes") or [])
            if p.get("kind") == "routing"]


def confusion(measurement):
    """{(truth, predicted): count} over the positive probes' runs."""
    matrix = collections.Counter()
    for probe in routing_probes(measurement):
        if not _is_positive(probe):
            continue
        truth = (probe.get("expect") or {}).get("skill") or NO_ROUTE
        for run in probe.get("runs") or []:
            matrix[(truth, run.get("routed_to") or NO_ROUTE)] += 1
    return matrix


def _divide(num, den):
    return (float(num) / den) if den else None


def per_label(matrix):
    """Per-label tp/fp/fn with precision, recall and F1. Sorted by label."""
    labels = set()
    for truth, predicted in matrix:
        labels.add(truth)
        labels.add(predicted)

    rows = []
    for label in sorted(labels):
        tp = matrix.get((label, label), 0)
        fp = sum(c for (t, p), c in matrix.items() if p == label and t != label)
        fn = sum(c for (t, p), c in matrix.items() if t == label and p != label)
        precision = _divide(tp, tp + fp)
        recall = _divide(tp, tp + fn)
        if precision and recall:
            f1 = 2 * precision * recall / (precision + recall)
        elif precision is None or recall is None:
            f1 = None
        else:
            f1 = 0.0
        rows.append({"label": label, "tp": tp, "fp": fp, "fn": fn,
                     "precision": precision, "recall": recall, "f1": f1,
                     "support": tp + fn})
    return rows


def averages(rows, matrix):
    """Micro (pooled over runs) and macro (unweighted over labels)."""
    tp = sum(c for (t, p), c in matrix.items() if t == p)
    total = sum(matrix.values())
    micro = _divide(tp, total)

    def mean(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return (sum(vals) / len(vals)) if vals else None

    return {
        # Single-label, every run predicts exactly one class, so micro
        # precision, micro recall and accuracy are the same number.
        "micro_precision": micro,
        "micro_recall": micro,
        "micro_f1": micro,
        "macro_precision": mean("precision"),
        "macro_recall": mean("recall"),
        "macro_f1": mean("f1"),
        "labels": len([r for r in rows if r["precision"] is not None
                       or r["recall"] is not None]),
        "runs": total,
    }


def constraint_probes(measurement):
    """Negative and control probes, scored by their own rule rather than the matrix."""
    out = []
    for probe in routing_probes(measurement):
        if _is_positive(probe):
            continue
        expect = probe.get("expect") or {}
        must_route = bool(expect.get("must_route"))
        target = expect.get("skill")
        runs = probe.get("runs") or []
        seen = collections.Counter(
            (run.get("routed_to") or NO_ROUTE) for run in runs)
        if must_route:
            held = sum(c for label, c in seen.items() if label == target)
        else:
            held = sum(c for label, c in seen.items() if label != target)
        out.append({
            "id": probe.get("id"),
            "kind": "control" if _is_control(probe) else "negative",
            "rule": ("must route to %s" % target) if must_route
                    else ("must NOT route to %s" % (target or "any skill")),
            "held": held,
            "runs": len(runs),
            "routed_to": dict(seen),
        })
    return out


def report(measurement):
    """Everything above, in one document, for a renderer to print."""
    matrix = confusion(measurement)
    rows = per_label(matrix)
    return {
        "per_label": rows,
        "averages": averages(rows, matrix),
        "constraints": constraint_probes(measurement),
        "confusions": sorted(
            ({"truth": t, "predicted": p, "count": c}
             for (t, p), c in matrix.items() if t != p),
            key=lambda d: (-d["count"], d["truth"], d["predicted"])),
        "note": ("Diagnostic only. The gate is unanimity per positive probe, "
                 "which is stricter than any average here."),
    }


def per_skill(measurement, golden=None):
    """One row per skill: its routing result, and its pipeline scenario if it has one.

    `golden` is `run_golden.py --json` output; when given, each skill also
    carries the count of deterministic cases whose `surface` names it.
    """
    skills = {}

    for probe in routing_probes(measurement):
        name = probe.get("skill")
        if not name:
            continue
        expect = probe.get("expect") or {}
        agg = probe.get("aggregate") or {}
        rel = agg.get("reliability") or {}
        row = skills.setdefault(name, {
            "skill": name, "routing": [], "pipeline": [], "golden_cases": 0})
        row["routing"].append({
            "probe": probe.get("id"),
            "kind": ("control" if _is_control(probe)
                     else "positive" if _is_positive(probe) else "negative"),
            "hits": rel.get("hits"),
            "runs": rel.get("total"),
            "rate": rel.get("rate"),
        })

    for probe in (measurement.get("probes") or []):
        if probe.get("kind") != "pipeline":
            continue
        name = probe.get("skill")
        if not name:
            continue
        agg = probe.get("aggregate") or {}
        rel = agg.get("reliability") or {}
        row = skills.setdefault(name, {
            "skill": name, "routing": [], "pipeline": [], "golden_cases": 0})
        row["pipeline"].append({
            "scenario": probe.get("id"),
            "completed": rel.get("hits"),
            "runs": rel.get("total"),
            "cost_median": (agg.get("cost_usd") or {}).get("median"),
            "seconds_median": (agg.get("seconds") or {}).get("median"),
            "unmeasured": agg.get("unmeasured"),
        })

    if golden:
        for case in golden.get("cases") or []:
            surface = case.get("surface") or ""
            for name in skills:
                bare = name.split(":", 1)[-1]
                if bare and bare in surface:
                    skills[name]["golden_cases"] += 1

    lookup = per_label_lookup(measurement)
    for name, row in skills.items():
        stats = lookup.get(name)
        row["precision"] = stats["precision"] if stats else None
        row["recall"] = stats["recall"] if stats else None
        row["f1"] = stats["f1"] if stats else None

    return [skills[k] for k in sorted(skills)]


def per_label_lookup(measurement):
    return {row["label"]: row for row in per_label(confusion(measurement))}
