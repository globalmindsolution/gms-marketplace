#!/usr/bin/env python3
"""Generate one reject case per schema constraint.

    python3 runner/gen_schema_cases.py            # write dataset/cases/11-schema-constraints.json
    python3 runner/gen_schema_cases.py --check    # fail if that file is out of date
    python3 runner/gen_schema_cases.py --report   # list what could NOT be generated, and why

Why this is generated rather than hand-written
----------------------------------------------
The hand-written schema cases in `08-schemas.json` pin the constraints a human
thought to name. Measured by constraint-deletion mutation, that was **9.3%** of
the 227 constraints the 12 shipped schemas declare — so the claim that "a schema
that loosens a constraint fails here" was not true of 90% of them.

Enumerating 200+ reject cases by hand is not the answer either: they would be
mechanical, and they would rot the moment a schema gained a field. So the
mechanical ones are derived from the schemas themselves, and `08-schemas.json`
keeps the cases that carry *judgement* — the ones whose titles say why a
constraint matters, like the verdict document's shape-versus-meaning split.

How a case is built
-------------------
Each schema has a VALID SEED (taken from that schema's accept case in
`08-schemas.json`, so the seeds stay in one place). For each constraint, the
generator walks from the schema location to the matching instance location,
plants a value that violates exactly that constraint, and asserts the schema
rejects it.

What it deliberately does not generate
--------------------------------------
Constraints it cannot reach with a single unambiguous instance path are
reported, never silently skipped:

  * branches under `oneOf`/`anyOf` — violating one branch usually leaves
    another matching, so the document stays valid and the "reject" case would
    be wrong;
  * `propertyNames` and constraints under `additionalProperties` where the seed
    carries no sample key to attach them to;
  * `required` on a subschema the seed never instantiates.

`--report` prints them. That list is the honest residue of this tier's
coverage, and it belongs in the report rather than in a footnote.
"""

import argparse
import copy
import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
CASES = os.path.join(REPO_ROOT, "dataset", "cases")
OUT = os.path.join(CASES, "11-schema-constraints.json")
SEED_FILE = os.path.join(CASES, "08-schemas.json")

sys.path.insert(0, HERE)
import jsonschema_mini as js  # noqa: E402
from harness import resolve_build  # noqa: E402

#: Constraints this generator knows how to violate.
HANDLED = ("enum", "const", "minimum", "maximum", "exclusiveMinimum",
           "exclusiveMaximum", "minLength", "maxLength", "minItems",
           "maxItems", "minProperties", "pattern", "required", "additionalProperties")

#: The message fragment each violation must produce, so a generated case pins
#: the CONSTRAINT and not merely "something was wrong".
REASON = {
    "enum": "is not one of", "const": "expected const",
    "minimum": "below minimum", "maximum": "above maximum",
    "exclusiveMinimum": "not above exclusiveMinimum",
    "exclusiveMaximum": "not below exclusiveMaximum",
    "minLength": "shorter than minLength", "maxLength": "longer than maxLength",
    "minItems": "fewer than minItems", "maxItems": "more than maxItems",
    "minProperties": "fewer than minProperties",
    "pattern": "does not match pattern",
    "required": "required property is missing",
    "additionalProperties": "additional properties are not allowed",
}


def seeds():
    """The valid instance per schema, read from that schema's accept case.

    Read RAW — clock tokens like `{{hours_ago:72}}` are deliberately left
    unexpanded. Expanding them here would bake the generation moment into every
    generated case, so two runs a second apart would produce different files and
    `make check` would report the tree as permanently stale. The runner expands
    them when the case actually runs, which is where a time-relative fixture
    means something.
    """
    with open(SEED_FILE) as fh:
        doc = json.load(fh)
    out = {}
    for case in doc["cases"]:
        if case.get("expect", {}).get("valid") is not True:
            continue
        if "fixture" in case:
            with open(os.path.join(REPO_ROOT, "dataset", "fixtures",
                                   case["fixture"])) as fh:
                value = json.load(fh)
        else:
            value = case.get("json")
        if value is not None:
            out.setdefault(case["schema"], value)
    return out


#: Candidate strings probed against a `pattern` when synthesising a value. The
#: shipped schemas constrain ticket ids, prefixes, dates, repo slugs and format
#: templates; probing a short list beats writing a regex-to-example generator.
_STRING_CANDIDATES = ("TKT-1", "TKT", "2026-01-01", "owner/acs-eval", "main",
                      "v1.0.0", "0.4.10", "docs/adr", "{ticket_id}",
                      "[{ticket_id}] {title}", "{type}/{ticket_id}-{slug}", "x")


def synthesize(schema, root):
    """A VALID value for this subschema, or None when one cannot be built.

    Used to grow each schema's hand-written seed into a maximal instance. A
    constraint on a property the seed never populates is unreachable, and an
    unreachable constraint is an unpinned one -- so the richer the seed, the
    more of the schema the generated cases actually cover.
    """
    if not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        try:
            target = root
            for part in schema["$ref"][2:].split("/"):
                target = target[part]
        except (KeyError, TypeError):
            return None
        return synthesize(target, root)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        for value in schema["enum"]:
            if value is not None:
                return value
        return schema["enum"][0]
    for choice in ("oneOf", "anyOf"):
        for branch in schema.get(choice) or []:
            value = synthesize(branch, root)
            if value is not None:
                return value
    types = schema.get("type")
    types = types if isinstance(types, list) else [types]
    types = [t for t in types if t and t != "null"] or [None]
    kind = types[0]
    if kind == "object":
        out = {}
        for name, sub in (schema.get("properties") or {}).items():
            value = synthesize(sub, root)
            if value is not None:
                out[name] = value
        for name in schema.get("required", []):
            out.setdefault(name, "x")
        return out
    if kind == "array":
        item = synthesize(schema.get("items") or {}, root)
        if item is None:
            item = "x"
        return [item] * max(schema.get("minItems", 1), 1)
    if kind == "boolean":
        return True
    if kind in ("integer", "number"):
        low = schema.get("minimum")
        if low is None and "exclusiveMinimum" in schema:
            low = schema["exclusiveMinimum"] + 1
        value = 1 if low is None else low
        high = schema.get("maximum")
        if high is not None and value > high:
            value = high
        return value if kind == "integer" else float(value)
    if kind == "string" or kind is None:
        pattern = schema.get("pattern")
        low = schema.get("minLength", 0)
        if pattern:
            for candidate in _STRING_CANDIDATES:
                if re.search(pattern, candidate) and len(candidate) >= low:
                    return candidate
            return None
        return "x" * max(low, 1)
    return None


def enrich(schema, seed, root=None, passes=4):
    """The hand seed, grown with every synthesised value that KEEPS IT VALID.

    Incremental and checked: each candidate is planted, the WHOLE instance is
    re-validated, and the addition is kept only if the instance still conforms.
    A seed that is itself invalid would make every case generated from it
    bogus — the schema would reject the instance for the seed's own defect
    rather than for the constraint the case means to pin, and the case would
    still "pass", for the wrong reason.

    Repeated to a fixpoint, because planting an object or an array element
    opens up its own children: a constraint under `runs[].tokens.input` is
    unreachable until `runs` has an element, and that element has a `tokens`.

    The hand seed stays authoritative wherever it has an opinion; synthesis
    only supplies what it left out.
    """
    root = root if root is not None else schema
    if not isinstance(seed, (dict, list)):
        return seed
    if js.validate(seed, root):
        return seed  # the hand seed is already invalid; leave it alone
    out = copy.deepcopy(seed)
    for _ in range(passes):
        grew = False
        for path, value in list(_gaps(schema, out, root)):
            candidate = copy.deepcopy(out)
            try:
                _plant(candidate, path, value)
            except (KeyError, IndexError, TypeError):
                continue
            try:
                if js.validate(candidate, root):
                    continue
            except js.UnsupportedKeyword:
                continue
            out = candidate
            grew = True
        if not grew:
            break
    return out


def _gaps(schema, instance, root, path=()):
    """(instance-path, value) for everything the instance has not populated."""
    schema = _deref(schema, root)
    if not isinstance(schema, dict):
        return
    for branch in (schema.get("oneOf") or []) + (schema.get("anyOf") or []):
        # Only descend a branch the instance already satisfies, so filling it
        # cannot flip which branch matches.
        try:
            if not js.validate(instance, _deref(branch, root)):
                yield from _gaps(branch, instance, root, path)
        except js.UnsupportedKeyword:
            continue
    if isinstance(instance, dict):
        for name, sub in sorted((schema.get("properties") or {}).items()):
            if name in instance:
                yield from _gaps(sub, instance[name], root, path + (name,))
            else:
                value = synthesize(sub, root)
                if value is not None:
                    yield path + (name,), value
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for name in sorted(instance):
                if name not in (schema.get("properties") or {}):
                    yield from _gaps(extra, instance[name], root, path + (name,))
    elif isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, dict):
            if not instance:
                value = synthesize(items, root)
                if value is not None:
                    yield path + (0,), value
            else:
                yield from _gaps(items, instance[0], root, path + (0,))


def _plant(doc, path, value):
    node = doc
    for step in path[:-1]:
        node = node[step]
    last = path[-1]
    if isinstance(node, list):
        if last == len(node):
            node.append(value)
        else:
            node[last] = value
    else:
        node[last] = value


def _deref(schema, root):
    if isinstance(schema, dict) and "$ref" in schema:
        try:
            target = root
            for part in schema["$ref"][2:].split("/"):
                target = target[part]
            return target
        except (KeyError, TypeError):
            return {}
    return schema if isinstance(schema, dict) else {}


def walk(schema, spath=(), ipath=(), inside_choice=False):
    """Yield (constraint, schema_node, instance_path, reachable, why).

    `instance_path` is where in the INSTANCE this constraint applies.
    `reachable` is False when the location cannot be addressed unambiguously.
    """
    if not isinstance(schema, dict):
        return
    for key in HANDLED:
        if key in schema:
            yield (key, schema, ipath, not inside_choice,
                   "under oneOf/anyOf" if inside_choice else "")
    for name, sub in (schema.get("properties") or {}).items():
        yield from walk(sub, spath + ("properties", name), ipath + (name,),
                        inside_choice)
    if isinstance(schema.get("items"), dict):
        yield from walk(schema["items"], spath + ("items",), ipath + (0,),
                        inside_choice)
    for choice in ("oneOf", "anyOf"):
        for i, sub in enumerate(schema.get(choice) or []):
            yield from walk(sub, spath + (choice, i), ipath, True)
    for key in ("allOf",):
        for i, sub in enumerate(schema.get(key) or []):
            yield from walk(sub, spath + (key, i), ipath, inside_choice)
    extra = schema.get("additionalProperties")
    if isinstance(extra, dict):
        yield from walk(extra, spath + ("additionalProperties",),
                        ipath + (_ANY_KEY,), inside_choice)
    if isinstance(schema.get("propertyNames"), dict):
        for key in HANDLED:
            if key in schema["propertyNames"]:
                yield (key, schema["propertyNames"], ipath, False,
                       "propertyNames constrains keys, not values")


class _AnyKey(str):
    """Marker for 'whatever key the seed happens to carry here'."""


_ANY_KEY = _AnyKey("*")


def resolve(instance, ipath):
    """Walk an instance path, resolving the any-key marker against the seed."""
    node = instance
    concrete = []
    for step in ipath:
        if isinstance(step, _AnyKey):
            if not isinstance(node, dict) or not node:
                return None, None
            step = sorted(node)[0]
        if isinstance(step, int):
            if not isinstance(node, list) or not node:
                return None, None
        elif not isinstance(node, dict) or step not in node:
            return None, None
        node = node[step]
        concrete.append(step)
    return node, concrete


def violate(constraint, schema, value):
    """A value that breaks exactly this constraint, or None if impossible."""
    if constraint == "enum":
        allowed = schema["enum"]
        for candidate in ("__acs_evals_not_in_enum__", -987654321, False):
            if candidate not in allowed:
                return candidate
        return None
    if constraint == "const":
        return "__acs_evals_not_the_const__"
    if constraint == "minimum":
        return schema["minimum"] - 1
    if constraint == "maximum":
        return schema["maximum"] + 1
    if constraint == "exclusiveMinimum":
        return schema["exclusiveMinimum"]
    if constraint == "exclusiveMaximum":
        return schema["exclusiveMaximum"]
    if constraint == "minLength":
        # A zero minimum cannot be violated from below — there is no shorter
        # string than the empty one, so this constraint has nothing to pin.
        if schema["minLength"] <= 0:
            return None
        return "x" * (schema["minLength"] - 1)
    if constraint == "maxLength":
        return "x" * (schema["maxLength"] + 1)
    if constraint == "minItems":
        if schema["minItems"] <= 0:
            return None
        return [None] * (schema["minItems"] - 1)
    if constraint == "maxItems":
        return [None] * (schema["maxItems"] + 1)
    if constraint == "minProperties":
        if schema["minProperties"] <= 0:
            return None
        return {}
    if constraint == "pattern":
        return " not-a-match "
    return None


def build(schema_name, schema, seed):
    """(cases, skipped) for one schema."""
    cases, skipped, seen = [], [], set()
    for constraint, node, ipath, reachable, why in walk(schema):
        key = (constraint, tuple(str(p) for p in ipath), id(node))
        if key in seen:
            continue
        seen.add(key)
        where = ".".join(str(p) for p in ipath) or "(root)"
        if not reachable:
            skipped.append((schema_name, constraint, where, why))
            continue
        target, concrete = resolve(seed, ipath)
        if concrete is None:
            skipped.append((schema_name, constraint, where,
                            "the seed instance has no value at this path"))
            continue
        mutant = copy.deepcopy(seed)

        if constraint == "required":
            if not isinstance(target, dict):
                skipped.append((schema_name, constraint, where,
                                "the seed value here is not an object"))
                continue
            missing = next((n for n in node["required"] if n in target), None)
            if missing is None:
                skipped.append((schema_name, constraint, where,
                                "the seed omits every required property already"))
                continue
            _at(mutant, concrete).pop(missing)
            label = "%s.%s is required" % (where, missing)
            detail = missing
        elif constraint == "additionalProperties":
            if node.get("additionalProperties") is not False:
                continue
            if not isinstance(target, dict):
                skipped.append((schema_name, constraint, where,
                                "the seed value here is not an object"))
                continue
            _at(mutant, concrete)["__acs_evals_extra__"] = 1
            label = "%s rejects an undeclared property" % where
            detail = "__acs_evals_extra__"
        else:
            bad = violate(constraint, node, target)
            if bad is None:
                skipped.append((schema_name, constraint, where,
                                "no value violates this constraint alone"))
                continue
            _set(mutant, concrete, bad)
            label = "%s violates %s" % (where, constraint)
            detail = None

        cases.append({
            "id": "SC-%s-%03d" % (_slug(schema_name), len(cases) + 1),
            "kind": "schema",
            "schema": schema_name,
            "title": label,
            "constraint": constraint,
            "instance_path": where,
            "json": mutant,
            "expect": {"valid": False, "errors_contain": [REASON[constraint]]},
        })
        if detail:
            cases[-1]["expect"]["errors_contain"].append(detail)
    return cases, skipped


def _at(doc, path):
    node = doc
    for step in path:
        node = node[step]
    return node


def _set(doc, path, value):
    if not path:
        raise ValueError("cannot replace the root instance")
    _at(doc, path[:-1])[path[-1]] = value


def _slug(name):
    return name.replace(".schema.json", "").replace("-", "").upper()[:9]


def render(build_root):
    schema_dir = os.path.join(build_root, "schemas")
    seed_by_schema = seeds()
    cases, skipped = [], []
    for name in sorted(seed_by_schema):
        path = os.path.join(schema_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path) as fh:
            schema = json.load(fh)
        seed = enrich(schema, seed_by_schema[name])
        got, miss = build(name, schema, seed)
        cases.extend(got)
        skipped.extend(miss)
    doc = {
        "group": "schema constraints (generated)",
        "description": (
            "One reject case per reachable constraint in the 12 shipped JSON "
            "schemas, DERIVED FROM THE SCHEMAS THEMSELVES by "
            "runner/gen_schema_cases.py. Each takes that schema's valid seed "
            "instance (the accept case in 08-schemas.json), breaks exactly one "
            "constraint, and asserts the schema rejects it naming that "
            "constraint.\n\nThis exists because the hand-written cases pinned "
            "only 9.3%% of declared constraints, measured by constraint-deletion "
            "mutation (runner/mutation_sweep.py). Judgement-carrying cases stay "
            "hand-written in 08-schemas.json; the mechanical ones live here.\n\n"
            "Regenerate with `make generate`. Do not hand-edit: edits are "
            "overwritten. Constraints that cannot be reached with one "
            "unambiguous instance path (oneOf/anyOf branches, propertyNames, "
            "paths the seed does not instantiate) are NOT generated and are "
            "listed by `python3 runner/gen_schema_cases.py --report`."),
        "surface": "schemas/*.json",
        "covers": ["MAR-527", "MAR-530"],
        "profile": "bare",
        "severity": "minor",
        "generated_by": "runner/gen_schema_cases.py",
        "cases": cases,
    }
    return doc, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the generated file is missing or stale")
    ap.add_argument("--report", action="store_true",
                    help="list the constraints that could not be generated")
    args = ap.parse_args()

    build_obj = resolve_build()
    doc, skipped = render(build_obj.root)
    body = json.dumps(doc, indent=2) + "\n"

    if args.report:
        print("Constraints NOT generated (%d):\n" % len(skipped))
        for name, constraint, where, why in skipped:
            print("  %-30s %-22s %-46s %s" % (name, constraint, where[:44], why))
        return 0

    current = None
    if os.path.isfile(OUT):
        with open(OUT) as fh:
            current = fh.read()
    if args.check:
        if current != body:
            print("dataset/cases/11-schema-constraints.json is out of date — "
                  "re-run `make generate`", file=sys.stderr)
            return 1
        print("11-schema-constraints.json is up to date (%d cases)"
              % len(doc["cases"]))
        return 0

    with open(OUT, "w") as fh:
        fh.write(body)
    print("generated %d constraint cases from acs %s (%d not reachable — see "
          "--report)" % (len(doc["cases"]), build_obj.version, len(skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
