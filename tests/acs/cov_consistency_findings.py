#!/usr/bin/env python3
"""Reproducible stdlib-`trace` line-coverage harness for consistency_findings.py (MAR-115 spec 02).

The repo is Python 3.9+ stdlib-only (no pip; CLAUDE.md forbids it) — the pip `coverage` package
is NOT installed — so coverage is measured with the stdlib `trace` module. This harness drives
validate_finding/validate_findings across every branch (dict-check fail/pass, kind missing/
invalid/valid, each of the four string fields' missing/None/empty/whitespace/non-string/valid
arms, and the list-wrapper's empty/non-list/mixed-list arms), then reports:

    executed executable lines / total executable lines  ->  percentage  (gate: >= 90%)

and the missed-line list (the trace .cover annotation marks each unexecuted executable line with
the `>>>>>>` marker). Run:  python3 tests/acs/cov_consistency_findings.py   (exit 0 iff >= GATE).

Note on measurement: the target module is imported FROM SOURCE inside the traced driver, so its
module-level statements and every `def` signature line execute under trace.Trace and are counted.
An import that happened before tracing started would otherwise leave the top-level body and the
signatures marked as missed (trace counts a line only when it runs during the traced call).
"""

import importlib.util
import os
import re
import shutil
import sys
import tempfile
import trace

GATE = 90.0

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_TESTS_DIR))
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "plugins", "acs", "hooks", "scripts")
_TARGET = os.path.join(_SCRIPTS_DIR, "consistency_findings.py")

if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_target_fresh():
    """Import consistency_findings from source as a fresh module object (inside the tracer)."""
    sys.modules.pop("consistency_findings", None)
    spec = importlib.util.spec_from_file_location("consistency_findings", _TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules["consistency_findings"] = module
    spec.loader.exec_module(module)
    return module


def _well_formed(kind="gap"):
    return {
        "kind": kind,
        "upstream": "docs/product/prd.md#G8",
        "downstream": "docs/architecture/hld/overview.md",
        "description": "PRD gains G8 but architecture has no coverage entry",
        "recommendation": "Add architecture -> quality, architecture -> operations",
    }


def _drive():
    """Fresh-import the target and exercise every branch — all inside the traced call."""
    mod = _load_target_fresh()

    # 1) validate_finding: non-dict inputs (the immediate-return branch).
    mod.validate_finding(None)
    mod.validate_finding("a string")
    mod.validate_finding([1, 2])
    mod.validate_finding(42)

    # 2) validate_finding: well-formed, both kind values, plus extra keys.
    mod.validate_finding(_well_formed(kind="gap"))
    mod.validate_finding(_well_formed(kind="staleness"))
    extra = _well_formed()
    extra["extra_unrelated_key"] = "ignored"
    mod.validate_finding(extra)

    # 3) validate_finding: kind branches — missing, None, wrong-case, near-miss.
    missing_kind = _well_formed()
    del missing_kind["kind"]
    mod.validate_finding(missing_kind)

    none_kind = _well_formed()
    none_kind["kind"] = None
    mod.validate_finding(none_kind)

    bad_kind = _well_formed()
    bad_kind["kind"] = "Gap"
    mod.validate_finding(bad_kind)

    near_miss_kind = _well_formed()
    near_miss_kind["kind"] = "stale"
    mod.validate_finding(near_miss_kind)

    # 4) validate_finding: each string field — omitted, None, empty, whitespace, non-string.
    for field in mod.REQUIRED_STRING_FIELDS:
        omitted = _well_formed()
        del omitted[field]
        mod.validate_finding(omitted)

        none_val = _well_formed()
        none_val[field] = None
        mod.validate_finding(none_val)

        empty_val = _well_formed()
        empty_val[field] = ""
        mod.validate_finding(empty_val)

        whitespace_val = _well_formed()
        whitespace_val[field] = "   "
        mod.validate_finding(whitespace_val)

        non_string_val = _well_formed()
        non_string_val[field] = 123
        mod.validate_finding(non_string_val)

    # 5) validate_finding: multiple simultaneous violations (no short-circuit).
    multi_bad = _well_formed()
    multi_bad["kind"] = "bogus"
    multi_bad["upstream"] = ""
    mod.validate_finding(multi_bad)

    # 6) validate_findings: empty list, non-list, mixed list (valid + invalid).
    mod.validate_findings([])
    mod.validate_findings({"not": "a list"})
    mod.validate_findings([_well_formed(), _well_formed(kind="bogus")])
    mod.validate_findings([_well_formed(kind="gap"), _well_formed(kind="staleness")])


def _count_from_cover(cover_path):
    """Parse a trace .cover file: count executed/total executable lines and collect misses."""
    executed = 0
    total = 0
    missed = []
    line_no = 0
    with open(cover_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line_no += 1
            # trace lines look like ">>>>>> code" (missed), "    N: code" (hit N times),
            # or "       code" (non-executable: blank/comment/continuation).
            if raw.startswith(">>>>>>"):
                total += 1
                missed.append((line_no, raw[6:].rstrip("\n")))
            else:
                m = re.match(r"\s*(\d+):", raw)
                if m:
                    total += 1
                    executed += 1
    return executed, total, missed


def main():
    covdir = tempfile.mkdtemp(prefix="acs-cov-")
    try:
        tracer = trace.Trace(count=1, trace=0)
        tracer.runfunc(_drive)
        results = tracer.results()
        results.write_results(summary=False, coverdir=covdir)

        cover_file = None
        for name in os.listdir(covdir):
            if name.endswith(".cover") and "consistency_findings" in name:
                cover_file = os.path.join(covdir, name)
                break
        if cover_file is None:
            print("ERROR: no consistency_findings .cover produced in %s" % covdir)
            return 2

        executed, total, missed = _count_from_cover(cover_file)
        pct = (executed * 100.0 / total) if total else 0.0
        print("consistency_findings.py coverage: %d/%d executable lines = %.1f%% (gate %.0f%%)"
              % (executed, total, pct, GATE))
        if missed:
            print("missed lines (>>>>>> in trace .cover):")
            for ln, src in missed:
                print("  L%d: %s" % (ln, src.strip()))
        else:
            print("missed lines: none")
        return 0 if pct >= GATE else 1
    finally:
        shutil.rmtree(covdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
