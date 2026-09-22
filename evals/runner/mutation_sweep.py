#!/usr/bin/env python3
"""Measure the schema tier's coverage by deleting constraints.

    make mutation                                    # per-schema coverage table
    make mutation MUTATION_ARGS=--holes              # every unpinned constraint

Run it through `make`, not directly: a bare invocation resolves the newest
INSTALLED acs build, while `make mutation` points it at this checkout's
plugin source -- the tree you are editing, and the one whose schemas the
cases were generated from. The two answer differently whenever source is
ahead of the last release, which is most of the time.

    ACS_PLUGIN_ROOT=... python3 runner/mutation_sweep.py [--holes] [--inert]
    python3 runner/mutation_sweep.py --threshold 0.9 # exit 1 below 90%

A passing suite says nothing about how much it would catch. This asks the only
question that matters of a schema case set:

    if this constraint simply vanished from the schema, would any case notice?

Every constraint in every shipped schema is deleted in turn, the schema cases
for that schema are re-evaluated in process, and a constraint whose deletion
leaves every case still passing is a HOLE — the dataset does not pin it, and a
release that loosened it would go out green.

This is why `dataset/cases/11-schema-constraints.json` is generated: the
hand-written cases alone pinned 9.3% of 227 constraints, which did not support
the claim the dataset was making about itself. Run this after changing either
the schemas or the cases.

Deliberately schema-tier only. The CLI tier's equivalent is mutating the
plugin's own decision tables, which needs a writable copy of the build and a
full subprocess run per mutation; `docs/EVALUATION-PROCESS.md` describes how to
do that by hand.
"""

import argparse
import copy
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
import jsonschema_mini as js  # noqa: E402
from harness import resolve_build  # noqa: E402
from run_golden import seed_content  # noqa: E402

#: Keywords treated as constraints. `type` is excluded on purpose: deleting it
#: usually cascades into every other keyword on the same node, so it would
#: inflate the score without pinning anything extra.
CONSTRAINTS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
               "minLength", "maxLength", "minItems", "maxItems", "pattern",
               "minProperties", "maxProperties",
               "enum", "const", "required", "additionalProperties",
               "propertyNames"}


def inert(key, value, schema=None, pointer=""):
    """Why deleting this constraint cannot change any verdict, or None.

    Some keyword occurrences restrict nothing: `additionalProperties: true`
    says exactly what its own absence says, and a zero `minLength`/`minItems`/
    `minProperties` admits every value the type already admits. Deleting one
    produces a schema that is not merely equivalent in practice but IDENTICAL
    in meaning, so no instance exists that any case could use to notice.

    Such an occurrence is not a hole. Counting it as one asks the reader to
    close a gap that cannot be closed, and understates the coverage of the
    cases that do exist -- which is the opposite of what this tool is for.

    It is excluded from the denominator and reported separately rather than
    dropped: a denominator that quietly shrinks is how a coverage number stops
    meaning anything, and the whole argument for generating these cases was
    that 9.3%% was the honest number.

    The last rule needs the whole schema, not just the keyword: a `required`
    inside an `if` decides only whether the condition matches a document
    LACKING those properties -- and when the enclosing schema requires the same
    ones, no such document is ever valid to begin with. lock-events declares
    `required: ["event"]` at the root and again in both `if` clauses, so
    deleting either copy leaves every verdict unchanged. Narrow on purpose:
    only `required` directly under an `if`, only against the root's own
    `required`. Anything subtler stays a hole, which is the safe direction.
    """
    if key == "additionalProperties" and value is True:
        return "additionalProperties: true is what its own absence means"
    if key == "required" and value == []:
        return "required: [] requires nothing"
    if key in ("minLength", "minItems", "minProperties") and value == 0:
        return "%s: 0 admits every value of the type" % key
    if (key == "required" and schema is not None
            and pointer.endswith("/if") and isinstance(value, list)):
        root_required = schema.get("required")
        if isinstance(root_required, list) and set(value) <= set(root_required):
            return ("required %s inside an if, already required at the root: "
                    "no valid document can omit them" % sorted(value))
    return None


def schema_cases():
    out = []
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "dataset", "cases", "*.json"))):
        with open(path) as fh:
            for case in json.load(fh)["cases"]:
                if case.get("kind") == "schema":
                    out.append(case)
    return out


def holds(cases, schema_name, schema):
    """Do all cases for this schema still hold against a mutated schema?"""
    for case in cases:
        if case["schema"] != schema_name:
            continue
        try:
            errors = js.validate(seed_content(case), schema)
        except js.UnsupportedKeyword:
            return False
        if (not errors) != case["expect"]["valid"]:
            return False
        for needle in case["expect"].get("errors_contain", []):
            if not any(needle in e for e in errors):
                return False
    return True


def points(node, path=""):
    """(pointer-to-parent, keyword) for every constraint in a schema."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CONSTRAINTS:
                yield path, key
            else:
                yield from points(value, "%s/%s" % (path, key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from points(value, "%s/%d" % (path, i))


def at(doc, pointer):
    node = doc
    for step in [s for s in pointer.split("/") if s]:
        node = node[int(step)] if isinstance(node, list) else node[step]
    return node


def sweep(build_root, cases):
    results, holes, skipped = {}, [], []
    for path in sorted(glob.glob(os.path.join(build_root, "schemas", "*.json"))):
        name = os.path.basename(path)
        if not any(c["schema"] == name for c in cases):
            results[name] = (0, 0)
            continue
        with open(path) as fh:
            base = json.load(fh)
        caught = total = 0
        for pointer, key in points(base):
            mutant = copy.deepcopy(base)
            parent = at(mutant, pointer)
            if key not in parent:
                continue
            why = inert(key, parent[key], base, pointer)
            if why:
                skipped.append((name, key, pointer or "(root)", why))
                continue
            del parent[key]
            total += 1
            if holds(cases, name, mutant):
                holes.append((name, key, pointer or "(root)"))
            else:
                caught += 1
        results[name] = (caught, total)
    return results, holes, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holes", action="store_true",
                    help="list every constraint no case pins")
    ap.add_argument("--inert", action="store_true",
                    help="list keyword occurrences that restrict nothing, and "
                         "so are excluded from the denominator")
    ap.add_argument("--threshold", type=float,
                    help="exit 1 if total coverage falls below this (0..1)")
    args = ap.parse_args()

    build = resolve_build()
    cases = schema_cases()
    results, holes, skipped = sweep(build.root, cases)

    caught = sum(c for c, _t in results.values())
    total = sum(t for _c, t in results.values())
    pct = (100.0 * caught / total) if total else 0.0

    print("Schema constraint coverage — acs %s, %d schema cases\n"
          % (build.version, len(cases)))
    for name in sorted(results):
        c, t = results[name]
        if not t:
            print("  %-32s     no cases" % name)
        else:
            print("  %-32s %3d/%-3d  %5.1f%%" % (name, c, t, 100.0 * c / t))
    print("\n  %-32s %3d/%-3d  %5.1f%%" % ("TOTAL", caught, total, pct))
    uncovered = sorted(n for n, (_c, t) in results.items() if not t)
    print("\n  %d constraint(s) pinned by no case." % len(holes))
    if uncovered:
        # These contribute 0/0, so they cannot pull the percentage down and a
        # reader sees a high number with no hint that a whole schema is
        # unpinned. Same failure as counting inert constraints, mirrored: one
        # inflates the denominator, this one quietly leaves it.
        print("  %d schema(s) have NO cases at all and are absent from the "
              "total, not counted as covered: %s"
              % (len(uncovered), ", ".join(uncovered)))
    if skipped:
        print("  %d keyword occurrence(s) restrict nothing and are not counted "
              "(--inert lists them)." % len(skipped))

    if args.holes:
        print()
        for name, key, pointer in holes:
            print("  %-30s %-22s %s" % (name, key, pointer))

    if args.inert:
        print()
        for name, key, pointer, why in skipped:
            print("  %-30s %-22s %-46s %s" % (name, key, pointer, why))

    if args.threshold is not None and total:
        if caught / total < args.threshold:
            print("\nBELOW THRESHOLD: %.1f%% < %.1f%%"
                  % (pct, args.threshold * 100), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
