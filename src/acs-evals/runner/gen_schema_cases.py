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

Every candidate is verified
---------------------------
The mutant is validated against the schema before its case is emitted, and the
case ships only if the schema actually rejects it AND says so naming this
constraint. A case that does not bite is worse than a missing one: it counts
toward coverage while pinning nothing.

That check is also what lets this generator stop refusing things in advance.
It used to skip, unexamined, every constraint under a `oneOf`/`anyOf` (on the
reasoning that violating one branch leaves another matching, so the document
stays valid), every `propertyNames` (which constrains keys, not values), and
everything behind a `$ref`. Each was a statement about a mutant nobody built.
Now they are built and the validator answers. Where a choice collapses into
"matched 0 oneOf branches" with no branch named, the case asserts that message
WITH its instance path: restore the constraint and the mutant matches its
branch again, which is exactly what being pinned means, and
`runner/mutation_sweep.py` measures it directly.

What is still not generated
---------------------------
  * constraints inside an `if`/`then` — deleting one changes WHEN a rule
    applies rather than what it allows, so there is no single value to plant;
  * anything the enriched seed still cannot instantiate.

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
_STRING_CANDIDATES = ("TKT-1", "TKT", "C-1", "2026-01-01", "owner/acs-eval",
                      "main", "v1.0.0", "0.4.10", "docs/adr", "{ticket_id}",
                      "[{ticket_id}] {title}", "{type}/{ticket_id}-{slug}", "x")


def _richness(value):
    """How much structure a synthesised value carries, for branch selection."""
    if isinstance(value, dict):
        return 2 + sum(_richness(v) for v in value.values())
    if isinstance(value, list):
        return 2 + sum(_richness(v) for v in value)
    return 1


def _sample_key(names):
    """A key an open map's `propertyNames` accepts, or None."""
    if not isinstance(names, dict):
        return "sample"
    if "enum" in names:
        return next((v for v in names["enum"] if isinstance(v, str)), None)
    if "const" in names and isinstance(names["const"], str):
        return names["const"]
    pattern = names.get("pattern")
    if pattern:
        return next((c for c in _STRING_CANDIDATES if re.search(pattern, c)), None)
    return "sample"


def synthesize(schema, root):
    """A VALID value for this subschema, or None when one cannot be built.

    Used to grow each schema's hand-written seed into a maximal instance. A
    constraint on a property the seed never populates is unreachable, and an
    unreachable constraint is an unpinned one -- so the richer the seed, the
    more of the schema the generated cases actually cover.

    The result is CHECKED against the subschema before it is returned, so this
    never hands back a value it already knows is wrong. It used to: an object
    whose required property could not be synthesised got `"x"` planted for it,
    and `clarifications[].id` (pattern `^C-[0-9]+$`) rejected that -- which
    `enrich` then discovered, discarded the whole item, and left every
    constraint under `clarifications[]` reported as "the seed has no value
    here". The cause was invisible because the guess was made in one place and
    thrown away in another.
    """
    value = _synthesize(schema, root)
    if value is None:
        return None
    try:
        if js.validate(value, schema, root):
            return None
    except js.UnsupportedKeyword:
        return None
    return value


def _synthesize(schema, root):
    """synthesize() without the self-check -- call synthesize(), not this."""
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
        branches = schema.get(choice) or []
        if not branches:
            continue
        # Take the RICHEST branch, not the first. The shipped schemas spell
        # optional structure as `oneOf: [{type: null}, {the real thing}]`, and
        # first-match returned the null branch -- so `release`, `adr_path` and
        # friends were seeded as nothing and every constraint beneath them was
        # reported unreachable. Enrichment exists to reach constraints, and a
        # null reaches none.
        best = None
        for branch in branches:
            value = synthesize(branch, root)
            if value is None:
                continue
            if best is None or _richness(value) > _richness(best):
                best = value
        if best is not None:
            return best
    types = schema.get("type")
    types = types if isinstance(types, list) else [types]
    concrete = [t for t in types if t and t != "null"]
    if not concrete and any(t == "null" for t in types):
        # A null-only subschema instantiates nothing. Saying so is the point:
        # falling through to the string branch below used to return "x" here,
        # a value the branch itself rejects, which `enrich` then planted,
        # re-validated, and silently discarded.
        return None
    kind = (concrete or [None])[0]
    if kind == "object":
        out = {}
        for name, sub in (schema.get("properties") or {}).items():
            value = synthesize(sub, root)
            if value is not None:
                out[name] = value
        for name in schema.get("required", []):
            out.setdefault(name, "x")
        extra = schema.get("additionalProperties")
        names = schema.get("propertyNames")
        if isinstance(extra, dict) and not out:
            # An open map (`suites`, `models.overrides`, `formats.tickets`):
            # every constraint it declares hangs off a key that does not exist
            # until the seed carries one, so supply a sample key its own
            # propertyNames accepts.
            sample = _sample_key(names)
            value = synthesize(extra, root)
            if sample is not None and value is not None:
                out[sample] = value
        # An object can also be constrained purely by SIZE, with nothing said
        # about what goes in it -- `release.extra_refs[].selector.match` is
        # `{type: object, minProperties: 1}` and declares no properties at all.
        # Built empty it violates its own constraint, so the whole selector,
        # the extra_ref around it and every constraint beneath went unreachable.
        need = schema.get("minProperties", 0)
        if need and len(out) < need and not isinstance(names, dict):
            filler = synthesize(extra, root) if isinstance(extra, dict) else "x"
            while len(out) < need:
                out["acs_evals_fill_%d" % len(out)] = (
                    copy.deepcopy(filler) if filler is not None else "x")
        return out
    if kind == "array":
        item = synthesize(schema.get("items") or {}, root)
        if item is None:
            # No valid element can be built, so no valid array can be either.
            # Filling with "x" here produced `[{"file": ...}]`-shaped arrays
            # whose elements the item schema rejects -- a value synthesize
            # already knew was wrong, handed back for enrich to discard.
            return None
        return [copy.deepcopy(item)
                for _ in range(max(schema.get("minItems", 1), 1))]
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
    branches = (schema.get("oneOf") or []) + (schema.get("anyOf") or [])
    for branch in branches:
        # Descend a branch the instance already satisfies, so filling it in
        # cannot flip which branch matches.
        try:
            if not js.validate(instance, _deref(branch, root)):
                yield from _gaps(branch, instance, root, path)
        except js.UnsupportedKeyword:
            continue
    if instance is None and branches:
        # A null here satisfies the `{type: null}` branch and pins nothing:
        # `ticket.external` and `settings.models.*` are spelled that way, and
        # every constraint in their real branch was unreachable because the
        # seed said null. Offer the richest branch as a REPLACEMENT. Flipping
        # which branch matches is exactly the point, and it is safe for the
        # same reason everything else here is: `enrich` plants the candidate,
        # re-validates the whole instance, and keeps it only if it still
        # conforms. Guarded on null so a value the seed actually chose is
        # never overwritten.
        best = None
        for branch in branches:
            value = synthesize(_deref(branch, root), root)
            if value is None:
                continue
            if best is None or _richness(value) > _richness(best):
                best = value
        if best is not None:
            yield path, best
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
            if not any(n not in (schema.get("properties") or {}) for n in instance):
                # An open map the seed left EMPTY (`pipeline-state.steps` is
                # `{}`): synthesize only supplies a sample key when the whole
                # property is absent, so an empty one stayed empty and every
                # constraint under its keys stayed unreachable.
                sample = _sample_key(schema.get("propertyNames"))
                value = synthesize(extra, root)
                if sample is not None and value is not None and sample not in instance:
                    yield path + (sample,), value
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


def walk(schema, spath=(), ipath=(), inside_choice=False, _root=None, _seen=None):
    """Yield (constraint, schema_node, instance_path, mode, note).

    `instance_path` is where in the INSTANCE this constraint applies.
    `mode` is "value" when the constraint restricts the value at that path, or
    "key" when it restricts the KEYS of the object there (`propertyNames`).

    Nothing is refused here any more. A constraint under `oneOf`/`anyOf` used to
    be dropped unseen, on the reasoning that violating one branch usually leaves
    a sibling branch matching, so the document stays valid and a "reject" case
    would be wrong. That reasoning is sound but the conclusion was too strong:
    it is a statement about a mutant nobody built. `build` now builds the mutant
    and asks the validator, which answers the question directly and for every
    constraint, not only the ones outside a choice. `note` carries the context
    into the skip reason when the validator does say the mutation does not bite.
    """
    if not isinstance(schema, dict):
        return
    if "$ref" in schema:
        # Follow it. `settings.models.<role>` is `{"$ref": "#/$defs/roleModel"}`
        # and every constraint roleModel declares was invisible from the
        # instance side, so four of them sat unpinned with nothing in the
        # report to say why -- they were never walked at all. `seen` guards
        # against a self-referential schema walking forever.
        target = _deref(schema, _root or schema)
        if target and id(target) not in (_seen or frozenset()):
            yield from walk(target, spath, ipath, inside_choice,
                            _root=_root, _seen=(_seen or frozenset()) | {id(target)})
        return
    for key in HANDLED:
        if key in schema:
            yield (key, schema, ipath, "value",
                   "under oneOf/anyOf" if inside_choice else "")
    kw = {"_root": _root, "_seen": _seen}
    for name, sub in (schema.get("properties") or {}).items():
        yield from walk(sub, spath + ("properties", name), ipath + (name,),
                        inside_choice, **kw)
    if isinstance(schema.get("items"), dict):
        yield from walk(schema["items"], spath + ("items",), ipath + (0,),
                        inside_choice, **kw)
    for choice in ("oneOf", "anyOf"):
        for i, sub in enumerate(schema.get(choice) or []):
            yield from walk(sub, spath + (choice, i), ipath, True, **kw)
    for key in ("allOf",):
        for i, sub in enumerate(schema.get(key) or []):
            yield from walk(sub, spath + (key, i), ipath, inside_choice, **kw)
    extra = schema.get("additionalProperties")
    if isinstance(extra, dict):
        yield from walk(extra, spath + ("additionalProperties",),
                        ipath + (_ANY_KEY,), inside_choice, **kw)
    names = schema.get("propertyNames")
    if isinstance(names, dict):
        # Deref, for the same reason the top of this function does: `phases`
        # spells both its open maps as `propertyNames: {$ref: skillName}`, and
        # reading the ref node directly finds no constraint to violate, so both
        # went unpinned with nothing in --report to say why.
        names = _deref(names, _root or schema) or names
        for key in HANDLED:
            if key in names:
                yield (key, names, ipath, "key",
                       "under oneOf/anyOf" if inside_choice else "")


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


#: A validator message that says a choice failed without naming which keyword
#: inside the branch did it -- the one rejection shape a generated case cannot
#: attribute from the message alone. See `build`.
_CHOICE_FAIL = re.compile(r"matched 0 (?:oneOf|anyOf) branches")


def build(schema_name, schema, seed):
    """(cases, skipped) for one schema.

    Every candidate is VERIFIED before it is emitted: the mutant is validated
    against the schema, and the case ships only if the schema actually rejects
    it and says so naming this constraint. That check is what lets the walk stop
    refusing `oneOf`/`anyOf` branches on principle -- and it is worth having on
    its own account, because until now a case was emitted on the ASSUMPTION that
    planting a bad value made the document invalid. A case that does not bite is
    worse than a missing one: it counts toward coverage while pinning nothing.
    """
    cases, skipped, seen = [], [], set()
    for constraint, node, ipath, mode, why in walk(schema, _root=schema):
        key = (constraint, tuple(str(p) for p in ipath), mode, id(node))
        if key in seen:
            continue
        seen.add(key)
        where = ".".join(str(p) for p in ipath) or "(root)"
        target, concrete = resolve(seed, ipath)
        if concrete is None:
            skipped.append((schema_name, constraint, where,
                            "the seed instance has no value at this path"))
            continue
        mutant = copy.deepcopy(seed)

        if mode == "key":
            if not isinstance(target, dict) or not target:
                skipped.append((schema_name, constraint, where,
                                "the seed carries no object of keys here"))
                continue
            bad = violate(constraint, node, next(iter(target)))
            if not isinstance(bad, str):
                skipped.append((schema_name, constraint, where,
                                "no string key violates this constraint alone"))
                continue
            # Reuse a value the seed already has under this object, so the only
            # thing wrong with the mutant is the KEY. A freshly synthesised
            # value could fail its own subschema and the case would then pin
            # that failure instead of propertyNames.
            _at(mutant, concrete)[bad] = copy.deepcopy(next(iter(target.values())))
            label = "%s rejects a property NAME that violates %s" % (where, constraint)
            detail = "property name"
        elif constraint == "required":
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

        # VERIFY, then emit. The schema must actually reject the mutant, and
        # the rejection must name this constraint -- a document rejected for
        # some unrelated reason would ship a green case that pins nothing.
        expected = [REASON[constraint]] + ([detail] if detail else [])
        try:
            errors = js.validate(mutant, schema)
        except js.UnsupportedKeyword as exc:
            skipped.append((schema_name, constraint, where,
                            "the validator cannot check this schema: %s" % exc))
            continue
        if not errors:
            skipped.append((schema_name, constraint, where,
                            ("the schema still accepts the mutant" +
                             (" (%s)" % why if why else ""))))
            continue
        missing = [n for n in expected if not any(n in e for e in errors)]
        if missing and len(errors) == 1 and _CHOICE_FAIL.search(errors[0]):
            # The constraint sits inside a `oneOf`/`anyOf`, and this validator
            # collapses a choice failure into one message without naming the
            # branch keyword that failed. The rejection is still caused by
            # exactly this constraint -- restore it and the mutant matches its
            # branch again, so the document becomes valid and this case fails.
            # That is what "pinned" means, and mutation_sweep measures it
            # directly. Assert the whole message, path included, so the case is
            # tied to a choice failing HERE rather than anywhere in the
            # document.
            expected = [errors[0]]
            label += " (its branch, and so the choice here, stops matching)"
            missing = []
        if missing:
            skipped.append((schema_name, constraint, where,
                            "rejected, but not for this constraint (no %r in "
                            "the errors)" % missing[0]))
            continue

        cases.append({
            "id": "SC-%s-%03d" % (_slug(schema_name), len(cases) + 1),
            "kind": "schema",
            "schema": schema_name,
            "title": label,
            "constraint": constraint,
            "instance_path": where,
            "json": mutant,
            "expect": {"valid": False, "errors_contain": expected},
        })
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
            "Every case is VERIFIED before it is emitted: the mutant is "
            "validated against the schema, and the case ships only if the "
            "schema rejects it naming this constraint.\n\nRegenerate with "
            "`make generate`. Do not hand-edit: edits are overwritten. What "
            "is still not generated (if/then conditionals, and paths the "
            "enriched seed cannot instantiate) is listed by "
            "`python3 runner/gen_schema_cases.py --report`."),
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
