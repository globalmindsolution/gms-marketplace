#!/usr/bin/env python3
"""Per-dimension finding rates from the verdicts acs's verifier already wrote.

    python3 runner/verifier_rates.py --workspace <workspace>/<repo_id>
    python3 runner/verifier_rates.py --workspace ... --json results/verifier-rates.json

Free: no model, no sandbox. It reads every `phases/<skill>/iter-<n>-verdict.json`
under the given workspace root — active partitions and `archive/` alike — and
counts, per verifier dimension, how often the dimension failed, was reported
n/a, or carried a blocking or info finding.

Why it exists: the 16-dimension code-verifier is the plugin's quality
mechanism, and nothing measures whether it works. A dimension that has never
produced a finding across the whole corpus is either perfect or dead, and the
corpus cannot tell which — so the report names those dimensions rather than
letting a zero read as a pass. The catch-rate measurement that *can* tell
(seeded defects, see docs/PERFORMANCE.md) is paid; this is the free reading
that says where to spend it.
"""

import argparse
import collections
import glob
import json
import os
import sys

#: The charter's dimension names by id (plugins/acs/agents/code-verifier.md,
#: mirrored in acs_lib/verdict.py), so a dimension no verdict ever reported
#: still appears in the table (as "never reported"). A verdict's own names win
#: when they differ.
DIMENSIONS = {
    1: "Acceptance-criteria conformance", 2: "Tests", 3: "Coverage",
    4: "Business logic", 5: "Features", 6: "Quality",
    7: "Technical standards", 8: "Architecture", 9: "System design",
    10: "Security", 11: "Documentation", 12: "Simplicity & scope",
    13: "Audience-style", 14: "Regression-risk (git-history)",
    15: "Plan conformance", 16: "Approval-audit",
}


def find_verdicts(root):
    pattern = os.path.join(root, "**", "phases", "*", "iter-*-verdict.json")
    return sorted(glob.glob(pattern, recursive=True))


def read(path):
    with open(path) as fh:
        return json.load(fh)


def tally(verdict_docs):
    """Aggregate a list of (path, doc) into the per-dimension table."""
    dims = collections.OrderedDict()
    for ident, name in DIMENSIONS.items():
        dims[ident] = {"id": ident, "name": name, "reported": 0, "pass": 0,
                       "fail": 0, "n/a": 0, "blocking": 0, "info": 0}
    by_name = {}
    totals = {"verdicts": 0, "passed": 0, "failed": 0, "blocking": 0,
              "info": 0, "iterations": collections.Counter(),
              "skills": collections.Counter(), "unmapped_findings": []}
    for path, doc in verdict_docs:
        totals["verdicts"] += 1
        totals["passed" if doc.get("passed") else "failed"] += 1
        totals["iterations"][str(doc.get("iteration"))] += 1
        totals["skills"][str(doc.get("skill"))] += 1
        for d in doc.get("dimensions") or []:
            ident = d.get("id")
            if ident not in dims:
                continue
            row = dims[ident]
            row["reported"] += 1
            result = d.get("result")
            if result in ("pass", "fail", "n/a"):
                row[result] += 1
            name = (d.get("name") or "").lower()
            if name:
                by_name[name] = ident
                by_name[name.split(" ")[0]] = ident
                if d.get("name") != row["name"]:
                    row["name"] = d["name"]
        for f in doc.get("findings") or []:
            sev = f.get("severity")
            if sev not in ("blocking", "info"):
                continue
            totals[sev] += 1
            key = str(f.get("dimension") or "").lower()
            ident = by_name.get(key) or by_name.get(key.split(" ")[0])
            if ident is None:
                for d_ident, name in DIMENSIONS.items():
                    if key and key in name.lower():
                        ident = d_ident
                        break
            if ident is None:
                totals["unmapped_findings"].append(
                    {"path": path, "dimension": f.get("dimension"), "severity": sev})
                continue
            dims[ident][sev] += 1
    for row in dims.values():
        row["never_failed"] = row["reported"] > 0 and row["fail"] == 0 and row["blocking"] == 0
        row["never_reported"] = row["reported"] == 0
    return dims, totals


def render(dims, totals, root):
    lines = ["Verifier dimension rates — %d verdict(s) under %s" % (totals["verdicts"], root),
             "  passed %d, failed %d; blocking findings %d, info findings %d"
             % (totals["passed"], totals["failed"], totals["blocking"], totals["info"]),
             "  iterations: %s; skills: %s"
             % (dict(totals["iterations"]), dict(totals["skills"])), "",
             "  %-3s %-36s %8s %5s %5s %5s %8s %5s  %s"
             % ("id", "dimension", "reported", "pass", "fail", "n/a", "blocking", "info", "note")]
    for row in dims.values():
        note = ("never reported" if row["never_reported"]
                else "never failed — perfect or dead" if row["never_failed"] else "")
        lines.append("  %-3d %-36s %8d %5d %5d %5d %8d %5d  %s"
                     % (row["id"], row["name"][:36], row["reported"], row["pass"],
                        row["fail"], row["n/a"], row["blocking"], row["info"], note))
    if totals["unmapped_findings"]:
        lines.append("")
        lines.append("  %d finding(s) named a dimension this table could not map:"
                     % len(totals["unmapped_findings"]))
        for u in totals["unmapped_findings"][:10]:
            lines.append("    %s: %r (%s)" % (u["path"], u["dimension"], u["severity"]))
    if totals["verdicts"] < 20:
        lines.append("")
        lines.append("  NOTE: %d verdict(s) is too few to call any dimension dead; "
                     "run this against the full workspace (archive/ included)."
                     % totals["verdicts"])
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True,
                    help="<workspace>/<repo_id> root holding ticket partitions and archive/")
    ap.add_argument("--json", metavar="PATH", help="also write the table as JSON")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.workspace))
    paths = find_verdicts(root)
    docs = []
    for p in paths:
        try:
            docs.append((os.path.relpath(p, root), read(p)))
        except (OSError, ValueError) as exc:
            print("skip %s: %s" % (p, exc), file=sys.stderr)
    dims, totals = tally(docs)
    print(render(dims, totals, root))
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w") as fh:
            json.dump({"schema": "acs-evals/verifier-rates/1", "workspace": root,
                       "verdicts": totals["verdicts"], "passed": totals["passed"],
                       "failed": totals["failed"], "blocking": totals["blocking"],
                       "info": totals["info"],
                       "iterations": dict(totals["iterations"]),
                       "skills": dict(totals["skills"]),
                       "dimensions": list(dims.values()),
                       "unmapped_findings": totals["unmapped_findings"]},
                      fh, indent=2)
            fh.write("\n")
    return 0 if docs else 1


if __name__ == "__main__":
    sys.exit(main())
