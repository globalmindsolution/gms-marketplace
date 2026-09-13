#!/usr/bin/env python3
"""Measure the CLI tier's coverage by mutating the plugin's decision code.

    python3 runner/mutation_cli.py                       # sample 40 mutants
    python3 runner/mutation_cli.py --max-mutants 0       # every mutant (slow)
    python3 runner/mutation_cli.py --module derive.py    # one module
    python3 runner/mutation_cli.py --threshold 0.6       # exit 1 below 60%

The schema tier's coverage is measured by `mutation_sweep.py`; this is the CLI
tier's counterpart, and it replaces the "hand-run spot check of seven
decision-table mutations" METHODOLOGY.md used to quote in its place. It asks
the same question in the same shape:

    if this decision in the plugin's own code quietly flipped, would any
    deterministic case notice?

A writable copy of the build is made, one site in one `acs_lib` module is
mutated (a comparison negated or moved by one, `and`/`or` swapped, a boolean
flipped, a `not` dropped, an `if` test negated, an integer nudged), the CLI
cases are run against the copy through `ACS_PLUGIN_ROOT`, and the mutant is
KILLED if any case fails. A mutant that survives is a hole — or an equivalent
mutant, which this tool cannot tell apart, so it lists every survivor for a
human to read rather than folding them into the number.

Mutants are enumerated deterministically and sampled with a seed, so two runs
of the same sample agree; `--max-mutants 0` runs them all. The unmutated copy
is run first as a control: a sweep whose control fails measures nothing and
says so.
"""

import argparse
import ast
import copy
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
from harness import BuildError, resolve_build  # noqa: E402

#: The modules that hold decisions the deterministic tier claims to pin.
DEFAULT_MODULES = ("derive.py", "verdict.py", "readiness.py", "gates.py",
                   "lanes.py", "filemap.py", "state.py", "settings.py")

#: The CLI cases: everything the schema and skill-manifest kinds do not drive.
CLI_CASE_GLOBS = ("GATE-*", "LANE-*", "READY-*", "VERDICT-*", "STAKES-*",
                  "FILEMAP-*", "LOCK-*", "TICKET-*", "MINT-*", "PRCONV-*",
                  "SLUG-*", "STRUCT-*", "CONTEXT-*", "STATUS-*", "METRICS-*",
                  "FANOUT-*", "DOCTOR-*", "SESSIONEND-*", "GUARD-*")

_NEGATE = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE,
           ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt,
           ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot,
           ast.IsNot: ast.Is}
_BOUNDARY = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}


# --------------------------------------------------------------------------
# Enumerating and applying mutants (pure: source in, source out)
# --------------------------------------------------------------------------

def _get(node, step):
    field, idx = step
    value = getattr(node, field)
    return value[idx] if idx is not None else value


def _set(node, step, new):
    field, idx = step
    if idx is None:
        setattr(node, field, new)
    else:
        getattr(node, field)[idx] = new


def _children(node):
    for field, value in ast.iter_fields(node):
        if isinstance(value, ast.AST):
            yield (field, None), value
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, ast.AST):
                    yield (field, i), item


def enumerate_sites(source):
    """Every mutation site in `source`, in a deterministic order.

    Each site is `{"kind", "path", "lineno", "detail"}`; `path` is the list of
    (field, index) steps from the module root to the node, so the same site
    can be found again in a freshly parsed tree.
    """
    tree = ast.parse(source)
    sites = []

    def visit(node, path, in_test):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = type(node.ops[0])
            if op in _NEGATE:
                sites.append({"kind": "negate-compare", "path": path,
                              "lineno": node.lineno,
                              "detail": "%s -> %s" % (op.__name__, _NEGATE[op].__name__)})
            if op in _BOUNDARY:
                sites.append({"kind": "boundary", "path": path,
                              "lineno": node.lineno,
                              "detail": "%s -> %s" % (op.__name__, _BOUNDARY[op].__name__)})
        elif isinstance(node, ast.BoolOp):
            sites.append({"kind": "swap-boolop", "path": path, "lineno": node.lineno,
                          "detail": "and <-> or"})
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append({"kind": "drop-not", "path": path, "lineno": node.lineno,
                          "detail": "not x -> x"})
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append({"kind": "flip-bool", "path": path, "lineno": node.lineno,
                          "detail": "%s -> %s" % (node.value, not node.value)})
        elif (isinstance(node, ast.Constant) and isinstance(node.value, int)
              and not isinstance(node.value, bool) and in_test):
            sites.append({"kind": "nudge-int", "path": path, "lineno": node.lineno,
                          "detail": "%d -> %d" % (node.value, node.value + 1)})
        for step, child in _children(node):
            child_in_test = in_test
            if isinstance(node, (ast.If, ast.While, ast.IfExp)) and step[0] == "test":
                child_in_test = True
                # A bare name or call as a condition can only be mutated by
                # negating the whole test; comparisons already have finer sites.
                if not isinstance(child, (ast.Compare, ast.BoolOp, ast.UnaryOp,
                                          ast.Constant)):
                    sites.append({"kind": "negate-test", "path": path + [step],
                                  "lineno": child.lineno, "detail": "if x -> if not x"})
            if isinstance(node, ast.Compare) or isinstance(node, ast.Return):
                child_in_test = True
            visit(child, path + [step], child_in_test)

    visit(tree, [], False)
    return sites


def apply_mutation(source, site):
    """The mutated source for one site. Raises if the result does not compile."""
    tree = ast.parse(source)
    path = site["path"]
    parent = tree
    for step in path[:-1]:
        parent = _get(parent, step)
    target = _get(parent, path[-1])
    kind = site["kind"]
    if kind == "negate-compare":
        new = copy.deepcopy(target)
        new.ops = [_NEGATE[type(target.ops[0])]()]
    elif kind == "boundary":
        new = copy.deepcopy(target)
        new.ops = [_BOUNDARY[type(target.ops[0])]()]
    elif kind == "swap-boolop":
        new = copy.deepcopy(target)
        new.op = ast.Or() if isinstance(target.op, ast.And) else ast.And()
    elif kind == "drop-not":
        new = copy.deepcopy(target.operand)
    elif kind == "flip-bool":
        new = ast.Constant(value=not target.value)
    elif kind == "nudge-int":
        new = ast.Constant(value=target.value + 1)
    elif kind == "negate-test":
        new = ast.UnaryOp(op=ast.Not(), operand=copy.deepcopy(target))
    else:
        raise ValueError("unknown mutation kind %r" % kind)
    ast.copy_location(new, target)
    _set(parent, path[-1], new)
    ast.fix_missing_locations(tree)
    out = ast.unparse(tree)
    compile(out, "<mutant>", "exec")
    return out


def sample_sites(sites_by_module, max_mutants, seed):
    """A deterministic sample across modules; `max_mutants` 0 means all."""
    flat = [(m, s) for m in sorted(sites_by_module)
            for s in sites_by_module[m]]
    if not max_mutants or max_mutants >= len(flat):
        return flat
    rng = random.Random(seed)
    picked = rng.sample(flat, max_mutants)
    picked.sort(key=lambda ms: (ms[0], ms[1]["lineno"], ms[1]["kind"]))
    return picked


# --------------------------------------------------------------------------
# Running the CLI tier against a mutant
# --------------------------------------------------------------------------

def run_cli_tier(build_root, case_globs, timeout=900):
    """(exit_code, failed_case_ids, seconds) for one run of the CLI cases."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        out = fh.name
    cmd = [sys.executable, os.path.join(HERE, "run_golden.py"),
           "--case", *case_globs, "--json", out]
    env = dict(os.environ, ACS_PLUGIN_ROOT=build_root)
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, env=env, cwd=REPO_ROOT)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        code = 124
    failed = []
    try:
        with open(out) as fh:
            doc = json.load(fh)
        failed = [c["id"] for c in doc.get("cases", []) if c.get("status") != "pass"]
    except (OSError, ValueError):
        pass
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass
    return code, failed, round(time.time() - started, 1)


def sweep(build, modules, max_mutants, seed, case_globs, log=print, sites=None):
    copy_root = tempfile.mkdtemp(prefix="acs-mutant-")
    shutil.rmtree(copy_root)
    shutil.copytree(build.root, copy_root,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".in_use"))
    lib = os.path.join(copy_root, "hooks", "scripts", "acs_lib")
    try:
        sources = {}
        sites_by_module = {}
        for name in modules:
            path = os.path.join(lib, name)
            if not os.path.isfile(path):
                raise BuildError("no %s under %s" % (name, lib))
            with open(path) as fh:
                sources[name] = fh.read()
            sites_by_module[name] = enumerate_sites(sources[name])
        total_sites = sum(len(v) for v in sites_by_module.values())

        log("control run (unmutated copy) ...")
        code, failed, secs = run_cli_tier(copy_root, case_globs)
        if code != 0 or failed:
            raise BuildError("control run failed (exit %d, %d failing case(s): %s) "
                             "— the sweep would measure nothing"
                             % (code, len(failed), ", ".join(failed[:5])))
        log("control run passed in %.0fs; %d mutation site(s) across %d module(s)"
            % (secs, total_sites, len(modules)))

        if sites:
            wanted = {(m, int(l)) for m, l in (s.split(":", 1) for s in sites)}
            picked = [(m, s) for m in sorted(sites_by_module) for s in sites_by_module[m]
                      if (m, s["lineno"]) in wanted]
            if not picked:
                raise BuildError("no mutation site matches %s" % ", ".join(sites))
        else:
            picked = sample_sites(sites_by_module, max_mutants, seed)
        log("running %d mutant(s)%s\n"
            % (len(picked), "" if len(picked) == total_sites
               else " (seed %d)" % seed))
        results = []
        for i, (name, site) in enumerate(picked, 1):
            path = os.path.join(lib, name)
            line = sources[name].splitlines()[site["lineno"] - 1].strip()
            try:
                mutated = apply_mutation(sources[name], site)
            except (SyntaxError, ValueError) as exc:
                results.append(dict(site, module=name, line=line,
                                    outcome="error", error=repr(exc)))
                continue
            with open(path, "w") as fh:
                fh.write(mutated)
            try:
                code, failed, secs = run_cli_tier(copy_root, case_globs)
            finally:
                with open(path, "w") as fh:
                    fh.write(sources[name])
            outcome = "killed" if (code != 0 or failed) else "survived"
            results.append(dict(site, module=name, line=line, outcome=outcome,
                                exit_code=code, killed_by=failed[:8],
                                seconds=secs))
            log("  [%3d/%d] %-8s %s:%d %-15s %s"
                % (i, len(picked), outcome, name, site["lineno"], site["kind"],
                   line[:60]))
        return results, total_sites
    finally:
        shutil.rmtree(copy_root, ignore_errors=True)


def summarize(results):
    per_module = {}
    for r in results:
        m = per_module.setdefault(r["module"], {"killed": 0, "survived": 0, "error": 0})
        m[r["outcome"]] += 1
    killed = sum(1 for r in results if r["outcome"] == "killed")
    judged = sum(1 for r in results if r["outcome"] in ("killed", "survived"))
    return {"killed": killed, "judged": judged,
            "rate": (killed / judged) if judged else None,
            "per_module": per_module,
            "survivors": [r for r in results if r["outcome"] == "survived"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", action="append",
                    help="acs_lib module to mutate (repeatable; default: the decision modules)")
    ap.add_argument("--max-mutants", type=int, default=40,
                    help="sample size across modules; 0 runs every mutant")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--threshold", type=float,
                    help="exit 1 if the kill rate falls below this (0..1)")
    ap.add_argument("--list", action="store_true",
                    help="list mutation sites and exit, running nothing")
    ap.add_argument("--site", action="append", metavar="MODULE:LINE",
                    help="run only the mutants at these sites (repeatable); the way to "
                         "prove a survivor is now killed after adding a case")
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "results", "mutation-cli.json"))
    args = ap.parse_args()

    try:
        build = resolve_build()
    except BuildError as exc:
        print("mutation-cli: %s" % exc, file=sys.stderr)
        return 3
    modules = tuple(args.module) if args.module else DEFAULT_MODULES

    if args.list:
        lib = os.path.join(build.root, "hooks", "scripts", "acs_lib")
        total = 0
        for name in modules:
            with open(os.path.join(lib, name)) as fh:
                sites = enumerate_sites(fh.read())
            total += len(sites)
            print("%-14s %4d site(s)" % (name, len(sites)))
        print("%-14s %4d" % ("TOTAL", total))
        return 0

    print("CLI-tier mutation coverage — acs %s\n" % build.version)
    started = time.time()
    try:
        results, total_sites = sweep(build, modules, args.max_mutants, args.seed,
                                     CLI_CASE_GLOBS, sites=args.site)
    except BuildError as exc:
        print("mutation-cli: %s" % exc, file=sys.stderr)
        return 2
    summary = summarize(results)

    print("\n  %-14s %s" % ("module", "killed/judged"))
    for name in modules:
        m = summary["per_module"].get(name)
        if not m:
            print("  %-14s     not sampled" % name)
            continue
        judged = m["killed"] + m["survived"]
        print("  %-14s %3d/%-3d %s" % (name, m["killed"], judged,
                                      ("%5.1f%%" % (100.0 * m["killed"] / judged)) if judged else "",))
    rate = summary["rate"]
    print("\n  %-14s %3d/%-3d %s   (%d of %d sites sampled)"
          % ("TOTAL", summary["killed"], summary["judged"],
             ("%5.1f%%" % (100.0 * rate)) if rate is not None else "n/a",
             len(results), total_sites))
    if summary["survivors"]:
        print("\n  %d survivor(s) — holes, or equivalent mutants; read each:"
              % len(summary["survivors"]))
        for r in summary["survivors"]:
            print("    %s:%d %-15s %s   [%s]"
                  % (r["module"], r["lineno"], r["kind"], r["line"][:70], r["detail"]))

    doc = {"schema": "acs-evals/mutation-cli/1",
           "build": {"version": build.version, "root": build.root},
           "modules": list(modules), "seed": args.seed,
           "max_mutants": args.max_mutants, "sites_total": total_sites,
           "sampled": len(results), "killed": summary["killed"],
           "judged": summary["judged"], "rate": rate,
           "per_module": summary["per_module"], "results": results,
           "seconds": round(time.time() - started, 1)}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print("\nwritten to %s  (%.0fs)" % (args.out, doc["seconds"]))

    if args.threshold is not None and rate is not None and rate < args.threshold:
        print("\nBELOW THRESHOLD: %.1f%% < %.1f%%"
              % (rate * 100, args.threshold * 100), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
