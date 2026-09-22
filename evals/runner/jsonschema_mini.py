"""A JSON Schema 2020-12 subset validator, stdlib only.

The acs plugin ships 13 schemas and no validator — `jsonschema` is not a
dependency anywhere in the plugin, and this dataset keeps the same stdlib-only
constraint. So the schema tier validates against exactly the keyword set those
13 schemas actually use:

    type, required, properties, additionalProperties, propertyNames,
    enum, const, minLength, minimum, maximum, exclusiveMinimum,
    minItems, minProperties, items, pattern, allOf, oneOf, if/then,
    $ref (local $defs)

`format` is parsed and ignored, which matches the 2020-12 default (format is an
annotation, not an assertion, unless a vocabulary opts in). Anything outside
this set raises rather than silently passing — a schema that grows a keyword
this module cannot check must not quietly start validating everything.
"""

import re

SUPPORTED = frozenset({
    "$schema", "$id", "$defs", "$ref", "$comment", "title", "description",
    "default", "examples", "deprecated", "readOnly", "writeOnly", "format",
    "type", "required", "properties", "additionalProperties", "propertyNames",
    "enum", "const", "minLength", "maxLength", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems",
    "minProperties", "maxProperties", "items",
    "pattern", "allOf", "anyOf", "oneOf", "not", "if", "then", "else",
    "uniqueItems",
})

TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "null": type(None),
}


class UnsupportedKeyword(Exception):
    """The schema uses a keyword this validator does not implement."""


def _is_type(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    expected = TYPES.get(name)
    if expected is None:
        raise UnsupportedKeyword("unknown type %r" % name)
    if expected is dict or expected is list or expected is str:
        return isinstance(value, expected)
    return isinstance(value, expected)


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise UnsupportedKeyword("only local $ref is supported, got %r" % ref)
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return node


def validate(instance, schema, root=None, path="$"):
    """Every way `instance` fails `schema`. An empty list means it conforms."""
    root = root if root is not None else schema
    if schema is True or schema == {}:
        return []
    if schema is False:
        return ["%s: schema forbids any value" % path]

    unknown = set(schema) - SUPPORTED
    if unknown:
        raise UnsupportedKeyword(
            "%s: schema uses %s, which this validator does not implement"
            % (path, ", ".join(sorted(unknown))))

    errs = []
    if "$ref" in schema:
        errs.extend(validate(instance, _resolve(schema["$ref"], root), root, path))

    if "type" in schema:
        names = schema["type"]
        names = names if isinstance(names, list) else [names]
        if not any(_is_type(instance, n) for n in names):
            errs.append("%s: expected type %s, got %s"
                        % (path, "/".join(names), type(instance).__name__))
            return errs  # every other keyword would just repeat this

    if "enum" in schema and instance not in schema["enum"]:
        errs.append("%s: %r is not one of %r" % (path, instance, schema["enum"]))
    if "const" in schema and instance != schema["const"]:
        errs.append("%s: expected const %r" % (path, schema["const"]))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append("%s: shorter than minLength %s" % (path, schema["minLength"]))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errs.append("%s: longer than maxLength %s" % (path, schema["maxLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append("%s: %r does not match pattern %s"
                        % (path, instance, schema["pattern"]))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append("%s: below minimum %s" % (path, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append("%s: above maximum %s" % (path, schema["maximum"]))
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errs.append("%s: not above exclusiveMinimum %s"
                        % (path, schema["exclusiveMinimum"]))
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errs.append("%s: not below exclusiveMaximum %s"
                        % (path, schema["exclusiveMaximum"]))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append("%s: fewer than minItems %s" % (path, schema["minItems"]))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append("%s: more than maxItems %s" % (path, schema["maxItems"]))
        if "uniqueItems" in schema and schema["uniqueItems"]:
            seen = [repr(i) for i in instance]
            if len(set(seen)) != len(seen):
                errs.append("%s: items are not unique" % path)
        if "items" in schema:
            for i, item in enumerate(instance):
                errs.extend(validate(item, schema["items"], root, "%s[%d]" % (path, i)))

    if isinstance(instance, dict):
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errs.append("%s: fewer than minProperties %s"
                        % (path, schema["minProperties"]))
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errs.append("%s: more than maxProperties %s"
                        % (path, schema["maxProperties"]))
        for name in schema.get("required", []):
            if name not in instance:
                errs.append("%s.%s: required property is missing" % (path, name))
        props = schema.get("properties", {})
        for name, value in instance.items():
            if name in props:
                errs.extend(validate(value, props[name], root, "%s.%s" % (path, name)))
        if "propertyNames" in schema:
            for name in instance:
                errs.extend(validate(name, schema["propertyNames"], root,
                                     "%s: property name %r" % (path, name)))
        extra = schema.get("additionalProperties")
        if extra is False:
            for name in instance:
                if name not in props:
                    errs.append("%s.%s: additional properties are not allowed"
                                % (path, name))
        elif isinstance(extra, dict):
            for name, value in instance.items():
                if name not in props:
                    errs.extend(validate(value, extra, root, "%s.%s" % (path, name)))

    for sub in schema.get("allOf", []):
        errs.extend(validate(instance, sub, root, path))
    if "anyOf" in schema:
        if not any(not validate(instance, s, root, path) for s in schema["anyOf"]):
            errs.append("%s: matches none of the anyOf branches" % path)
    if "oneOf" in schema:
        matched = sum(1 for s in schema["oneOf"]
                      if not validate(instance, s, root, path))
        if matched != 1:
            errs.append("%s: matched %d oneOf branches, expected exactly 1"
                        % (path, matched))
    if "not" in schema and not validate(instance, schema["not"], root, path):
        errs.append("%s: matches a schema it must not" % path)
    if "if" in schema:
        taken = "then" if not validate(instance, schema["if"], root, path) else "else"
        if taken in schema:
            errs.extend(validate(instance, schema[taken], root, path))
    return errs
