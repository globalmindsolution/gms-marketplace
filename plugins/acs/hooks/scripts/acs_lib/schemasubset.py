"""acs_lib.schemasubset — a stdlib subset of JSON Schema (draft 2020-12).

Hooks may not import third-party packages, so the two workflow schemas
(`ship-workflow.schema.json`, `phases.schema.json`) are enforced by this
hand-written validator rather than by `jsonschema`. It implements exactly the
keywords those schemas use and nothing else — an unknown keyword is IGNORED,
so a schema that grows one silently loses its check. That is the trade the
stdlib constraint forces, and it is why tests/acs/test_phases_registry.py and
tests/acs/test_workflow_resolution.py cross-check the SAME schema documents
with the real `jsonschema` package: the subset cannot drift from the thing it
stands in for without a test saying so.

An unsupported `$ref` is a defect in the SCHEMA, never in the document, and is
raised as `WorkflowError` — the one class both workflow documents fail with, so
a caller that already handles a bad `ship.yaml` handles this too.

`schema_errors` returns `[(pointer_path, message), ...]` — EVERY failure, not
the first — so a caller can report the one that names the value's own JSON
type (`branch_fits_type`) rather than a `oneOf`'s unhelpful summary. The
module owns no I/O and knows nothing about workflows: the caller loads the
schema document and decides what a failure means.
"""

import re

from ._common import WorkflowError


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def is_type(value, typ):
    if isinstance(typ, list):
        return any(is_type(value, t) for t in typ)
    if typ == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[typ])


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    for name, cls in (("object", dict), ("array", list), ("string", str), ("integer", int)):
        if isinstance(value, cls):
            return name
    return type(value).__name__


def equal(a, b):
    """JSON equality: a boolean never equals an integer, unlike Python."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b


def deref(root, ref):
    if not ref.startswith("#/"):
        raise WorkflowError("unsupported $ref %r in schema" % ref)
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def schema_errors(schema, value, root=None, path=()):
    """[(path, message)] for every violation, in traversal order."""
    root = schema if root is None else root
    if "$ref" in schema:
        schema = deref(root, schema["$ref"])
    typ = schema.get("type")
    if typ and not is_type(value, typ):
        return [(path, "expected %s, got %s" % (typ if isinstance(typ, str) else "/".join(typ),
                                                  type_name(value)))]
    errors = []
    if "const" in schema and not equal(value, schema["const"]):
        errors.append((path, "must be %r" % (schema["const"],)))
    if "enum" in schema and not any(equal(value, e) for e in schema["enum"]):
        errors.append((path, "%r is not one of %s" % (value, ", ".join(repr(e) for e in schema["enum"]))))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append((path + (key,), "missing required key %r" % key))
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors.extend(schema_errors(props[key], item, root, path + (key,)))
            elif schema.get("additionalProperties") is False:
                errors.append((path + (key,), "unknown key %r" % key))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(schema_errors(schema["additionalProperties"], item, root, path + (key,)))
            if "propertyNames" in schema:
                errors.extend(schema_errors(schema["propertyNames"], key, root, path + (key,)))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append((path, "needs at least %d item(s)" % schema["minItems"]))
        if schema.get("uniqueItems") and len({repr(v) for v in value}) != len(value):
            errors.append((path, "items must be unique"))
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(schema_errors(schema["items"], item, root, path + (index,)))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append((path, "must not be empty"))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append((path, "%r does not match %s" % (value, schema["pattern"])))
    if is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append((path, "must be >= %s" % schema["minimum"]))
    if "oneOf" in schema:
        branch_errors = [schema_errors(sub, value, root, path) for sub in schema["oneOf"]]
        matches = sum(1 for errs in branch_errors if not errs)
        if matches != 1:
            # Report the branch that best fits the value's own type rather than
            # the generic "matched no form". A per-path field is `oneOf` a
            # scalar and a mapping, and a reader who wrote a scalar wants the
            # scalar branch's complaint -- naming the allowed values -- not a
            # note that a mapping would also have been acceptable.
            specific = None
            for sub, errs in zip(schema["oneOf"], branch_errors):
                if not errs:
                    continue
                if branch_fits_type(sub, value, root):
                    specific = errs[0]
                    break
            errors.append(specific or
                          (path, "%r does not match exactly one of the allowed forms" % (value,)))
    return errors


def branch_fits_type(sub, value, root):
    """True when this `oneOf` branch describes values of `value`'s own JSON
    type -- the branch whose complaint is worth surfacing."""
    if "$ref" in sub:
        sub = deref(root, sub["$ref"])
    if "enum" in sub and not isinstance(value, (dict, list)):
        return True
    typ = sub.get("type")
    return bool(typ) and is_type(value, typ)


def pointer(path):
    out = ""
    for part in path:
        out += "[%d]" % part if isinstance(part, int) else (".%s" % part if out else str(part))
    return out or "(document)"
