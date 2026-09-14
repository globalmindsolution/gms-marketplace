#!/usr/bin/env python3
"""validate_xml.py — validate coordinator/subagent XML messages against acs-messages.xsd.

Skills validate every task/result/handoff message so malformed messages fail fast
instead of silently degrading the pipeline (docs/requirements/functional/reflection.md).

One declaration per contract (ADR-0093): `schemas/acs-messages.xsd` is the
ONLY statement of the message vocabulary. This module carries no parallel
copy of it. At import it parses the XSD with the stdlib `xml.etree` and
derives everything it enforces — the root elements, each element's child
sequence (order, minOccurs, maxOccurs), which elements are text-only leaves,
every attribute with its type and whether it is required, and every
enumeration and pattern (`skillName`, `phaseName`, `ticketId`,
`resultStatus`, `handoffStatus`, `verifyLens`, `severity`,
`constraintName`). Change the XSD and the validator changes with it; there is
no second table and nothing that can drift.

The module-level names `SKILLS`, `PHASES`, `RESULT_STATUSES`,
`HANDOFF_STATUSES`, `VERIFY_LENSES`, `CONSTRAINT_NAMES`, `CHILD_ORDER`,
`REQUIRED_CHILDREN`, `ALLOWED_ATTRS` and `TEXT_LEAVES` are DERIVED VIEWS of the
loaded schema, kept because callers and tests read them by those names. They
are computed, never written by hand.

Strategy (stdlib-only requirement):
  Default fast path: every message is validated IN-PROCESS by validate_structurally(),
  against the model derived from the XSD. No subprocess is spawned per message.

  Opt-in authoritative check: when the caller sets ACS_XML_AUTHORITATIVE=1 in the
  environment AND xmllint is found on PATH AND acs-messages.xsd is present,
  validate_with_xmllint() is invoked instead of the in-process engine.  xmllint
  absence never blocks a verdict — if the env var is set but xmllint is not on PATH,
  the in-process engine runs silently.  This preserves AC-5 (strict stdlib): no
  mandatory third-party dependency; a stdlib-only interpreter always gets a verdict.

  The AC-2 parity corpus (tests/acs/test_acs_plugin.py:TestValidators) is the
  binding proof that the in-process engine and xmllint agree: bad root element,
  missing/invalid attribute, bad ticket-id pattern, out-of-order children,
  wrong list-item tag, bad enumeration value, duplicate maxOccurs=1 children,
  undeclared attributes (the XSD declares no anyAttribute/wildcard), element
  children inside text-only leaves, and a constraint name outside the
  `constraintName` vocabulary.

Usage:
  validate_xml.py <file.xml> [more.xml ...]
  echo "<task ...>...</task>" | validate_xml.py -

  ACS_XML_AUTHORITATIVE=1 validate_xml.py <file.xml>   # opt-in xmllint check

Exit codes: 0 = valid, 1 = invalid (details on stderr).

Batch API (Python-callable; no subprocess):
  from validate_xml import validate_batch, batch_overall_ok

  results = validate_batch([msg1, msg2, msg3])
  # returns [(True, []), (False, ["<foo> root …"]), …] — one (ok, errors) per message

  if not batch_overall_ok(results):
      # at least one message is invalid
      ...

  validate_batch() calls validate_structurally() in a plain for-loop; no thread
  pool, no subprocess, no xmllint invocation.  An empty messages list returns [].
  The ACS_XML_AUTHORITATIVE env var is NOT honoured by the batch path (it is a
  per-message CLI concern); callers needing authoritative xmllint validation call
  validate_with_xmllint() directly.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XSD_PATH = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "schemas", "acs-messages.xsd")

XS = "{http://www.w3.org/2001/XMLSchema}"


# ---------------------------------------------------------------------------
# Schema model, derived from the XSD
# ---------------------------------------------------------------------------

def _simple_type(node):
    """{'enum': [...], 'patterns': [...]} for one xs:simpleType.

    Inline union members are flattened (a value is valid when it matches ANY
    member); named `memberTypes` are resolved by `_load_schema` afterwards.
    """
    enum, patterns = [], []
    for restriction in node.iter(XS + "restriction"):
        enum.extend(e.get("value") for e in restriction.findall(XS + "enumeration"))
        patterns.extend(p.get("value") for p in restriction.findall(XS + "pattern"))
    members = []
    for union in node.iter(XS + "union"):
        members.extend((union.get("memberTypes") or "").split())
    return {"enum": enum, "patterns": patterns, "members": members}


def _element_model(el, named_complex, elements):
    """Register the model of `el` (an xs:element) under its tag, recursing into
    the child elements its content model declares.

    A model is {"children": [(tag, min, max_or_None)], "attrs": {name: (type,
    required)}, "text_only": bool}.
    """
    tag = el.get("name")
    etype = el.get("type")
    model = {"children": [], "attrs": {}, "text_only": False}
    ctype = el.find(XS + "complexType")
    if ctype is None and etype in named_complex:
        ctype = named_complex[etype]
    if ctype is None:
        # A plain typed element (xs:string and friends) is a text-only leaf.
        model["text_only"] = True
        elements[tag] = model
        return model
    simple_content = ctype.find(XS + "simpleContent")
    if simple_content is not None:
        # simpleContent = text with attributes; element children are invalid.
        model["text_only"] = True
        for holder in simple_content.iter():
            for attr in holder.findall(XS + "attribute"):
                model["attrs"][attr.get("name")] = (attr.get("type"), attr.get("use") == "required")
    for attr in ctype.findall(XS + "attribute"):
        model["attrs"][attr.get("name")] = (attr.get("type"), attr.get("use") == "required")
    sequence = ctype.find(XS + "sequence")
    if sequence is not None:
        for child in sequence.findall(XS + "element"):
            lo = int(child.get("minOccurs", "1"))
            hi = child.get("maxOccurs", "1")
            model["children"].append((child.get("name"), lo, None if hi == "unbounded" else int(hi)))
            _element_model(child, named_complex, elements)
    elements[tag] = model
    return model


def _load_schema(path=XSD_PATH):
    """(simple_types, elements, roots) parsed from the XSD file."""
    root = ET.parse(path).getroot()
    simple = {}
    for node in root.findall(XS + "simpleType"):
        simple[node.get("name")] = _simple_type(node)
    for name, spec in simple.items():
        for member in spec.pop("members"):
            other = simple.get(member)
            if other is not None:
                spec["enum"].extend(v for v in other["enum"] if v not in spec["enum"])
                spec["patterns"].extend(p for p in other["patterns"] if p not in spec["patterns"])
    named_complex = {node.get("name"): node for node in root.findall(XS + "complexType")}
    elements = {}
    roots = []
    for el in root.findall(XS + "element"):
        _element_model(el, named_complex, elements)
        roots.append(el.get("name"))
    return simple, elements, roots


SIMPLE_TYPES, ELEMENTS, ROOTS = _load_schema()


def _enum(type_name):
    return list(SIMPLE_TYPES.get(type_name, {}).get("enum", []))


# Derived views of the schema (see the module docstring).
SKILLS = frozenset(_enum("skillName"))
PHASES = frozenset(_enum("phaseName"))
RESULT_STATUSES = frozenset(_enum("resultStatus"))
HANDOFF_STATUSES = frozenset(_enum("handoffStatus"))
VERIFY_LENSES = frozenset(_enum("verifyLens"))
CONSTRAINT_NAMES = frozenset(_enum("constraintName"))
CONSTRAINT_NAME_PATTERNS = tuple(SIMPLE_TYPES.get("constraintName", {}).get("patterns", []))
TICKET_RE = re.compile("^(?:%s)$" % "|".join(SIMPLE_TYPES["ticketId"]["patterns"]))
CHILD_ORDER = {tag: [c[0] for c in ELEMENTS[tag]["children"]] for tag in ROOTS}
REQUIRED_CHILDREN = {tag: [c[0] for c in ELEMENTS[tag]["children"] if c[1] > 0] for tag in ROOTS}
ALLOWED_ATTRS = {tag: frozenset(model["attrs"]) for tag, model in ELEMENTS.items() if model["attrs"]}
TEXT_LEAVES = frozenset(tag for tag, model in ELEMENTS.items()
                        if model["text_only"] and not model["attrs"])


# ---------------------------------------------------------------------------
# Value typing
# ---------------------------------------------------------------------------

def _is_xs_decimal(value):
    """Return True iff *value* conforms to the xs:decimal lexical space.

    xs:decimal allows: optional leading sign (+ or -), one or more decimal
    digits, and an optional single decimal point anywhere in the digit sequence.
    It does NOT allow exponent notation (1e5), inf, nan, underscores (1_000),
    or an empty string.  This matches the W3C XML Schema Part 2 definition and
    the behaviour of xmllint --schema when validating xs:decimal attributes.
    """
    return bool(re.fullmatch(r"[+-]?(\d+\.?\d*|\d*\.\d+)", value))


def _type_problem(type_name, value):
    """None when *value* is lexically valid for the schema type, else why not."""
    if type_name in (None, "xs:string"):
        return None
    if type_name == "xs:positiveInteger":
        return None if value.isdigit() and int(value) >= 1 else "must be a positive integer"
    if type_name == "xs:nonNegativeInteger":
        return None if value.isdigit() else "must be a non-negative integer"
    if type_name == "xs:decimal":
        return None if _is_xs_decimal(value) else (
            "must be a valid xs:decimal (digits with optional sign and/or decimal "
            "point; no exponent, no inf/nan, no underscores)")
    if type_name == "xs:boolean":
        return None if value in ("true", "false", "1", "0") else "must be true|false"
    spec = SIMPLE_TYPES.get(type_name)
    if spec is None:
        return None
    if value in spec["enum"]:
        return None
    if any(re.fullmatch(p, value) for p in spec["patterns"]):
        return None
    if spec["enum"] and spec["patterns"]:
        return "one of: %s, or matching %s" % (", ".join(sorted(spec["enum"])),
                                              " | ".join(spec["patterns"]))
    if spec["enum"]:
        return "one of: %s" % ", ".join(sorted(spec["enum"]))
    if type_name == "ticketId":
        return "pattern <PREFIX>-<n>, e.g. SHOP-123"
    return "must match %s" % " | ".join(spec["patterns"])


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def _validate_element(elem, errors):
    tag = elem.tag
    model = ELEMENTS.get(tag)
    if model is None:
        # An element the schema does not declare: its parent already reported
        # it; its attributes are all undeclared.
        errors.extend("<%s> has undeclared attribute %r (allowed: none)" % (tag, name)
                      for name in elem.keys())
        return
    for name, (atype, required) in model["attrs"].items():
        value = elem.get(name)
        if value is None:
            if required:
                errors.append("<%s> is missing required attribute %r" % (tag, name))
            continue
        problem = _type_problem(atype, value)
        if problem:
            errors.append("<%s %s=%r> is invalid (%s)" % (tag, name, value, problem))
    # Closed content model: the XSD declares no anyAttribute / wildcard.
    errors.extend("<%s> has undeclared attribute %r (allowed: %s)"
                  % (tag, name, ", ".join(sorted(model["attrs"])) or "none")
                  for name in elem.keys() if name not in model["attrs"])
    if model["text_only"]:
        if len(elem):
            errors.append("<%s> is a text-only element and may not contain child <%s>"
                          % (tag, list(elem)[0].tag))
        return
    allowed = [c[0] for c in model["children"]]
    seen = [child.tag for child in elem]
    is_list = len(model["children"]) == 1 and model["children"][0][2] is None
    for child_tag in seen:
        if child_tag not in allowed:
            if is_list:
                errors.append("<%s> may only contain <%s>; found <%s>"
                              % (tag, allowed[0], child_tag))
            else:
                errors.append("<%s> contains unexpected element <%s> (allowed: %s)"
                              % (tag, child_tag, ", ".join(allowed)))
    for child_tag, lo, hi in model["children"]:
        count = seen.count(child_tag)
        if count < lo:
            errors.append("<%s> is missing required element <%s>" % (tag, child_tag))
        if hi is not None and count > hi:
            errors.append("<%s> contains %d occurrences of <%s>; at most %d is allowed"
                          % (tag, count, child_tag, hi))
    positions = [allowed.index(t) for t in seen if t in allowed]
    if positions != sorted(positions):
        errors.append("<%s> children out of order; expected order: %s"
                      % (tag, ", ".join(allowed)))
    for child in elem:
        _validate_element(child, errors)


def validate_structurally(text):
    if not isinstance(text, str):
        return ["expected an XML string, got %s" % type(text).__name__]
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return ["not well-formed XML: %s" % exc]
    if root.tag not in ROOTS:
        return ["root element must be %s; found <%s>"
                % (", ".join("<%s>" % r for r in ROOTS[:-1]) + ", or <%s>" % ROOTS[-1], root.tag)]
    errors = []
    _validate_element(root, errors)
    return errors


def validate_with_xmllint(path):
    proc = subprocess.run(
        ["xmllint", "--noout", "--schema", XSD_PATH, path],
        capture_output=True, text=True, timeout=20,
    )
    return proc.returncode == 0, proc.stderr.strip()


def validate_batch(messages):
    """Validate a list of XML message strings in one call.

    Returns a list of (ok, errors) tuples — one per input message, in order.
    ``ok`` is True when the message is valid; ``errors`` is an empty list when
    ok and a non-empty list of error strings otherwise.

    No subprocess is spawned; each message is validated in-process via
    validate_structurally().  An empty messages list returns [].
    The ACS_XML_AUTHORITATIVE env var is NOT honoured here — this is strictly
    the in-process fast path.

    Args:
        messages: list[str] — XML message strings to validate.

    Returns:
        list[tuple[bool, list[str]]] — one (ok, errors) per input, in order.
    """
    results = []
    for text in messages:
        errors = validate_structurally(text)
        results.append((len(errors) == 0, errors))
    return results


def batch_overall_ok(batch_results):
    """Return True iff every (ok, errors) tuple in batch_results has ok=True.

    Args:
        batch_results: list[tuple[bool, list[str]]] — as returned by validate_batch().

    Returns:
        bool — True when all members are valid, False when any member is invalid.
        An empty batch_results returns True (vacuously true: no invalid members).
    """
    return all(ok for ok, _ in batch_results)


def main():
    args = sys.argv[1:]
    if not args:
        sys.stderr.write(__doc__)
        sys.exit(1)

    failures = 0
    for arg in args:
        if arg == "-":
            text = sys.stdin.read()
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                fh.write(text)
                path, label = fh.name, "<stdin>"
        else:
            path, label = arg, arg
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError as exc:
                sys.stderr.write("%s: cannot read (%s)\n" % (label, exc))
                failures += 1
                continue

        if os.environ.get("ACS_XML_AUTHORITATIVE") and shutil.which("xmllint") and os.path.isfile(XSD_PATH):
            ok, detail = validate_with_xmllint(path)
            if ok:
                print("%s: valid (xmllint, acs-messages.xsd)" % label)
            else:
                failures += 1
                sys.stderr.write("%s: INVALID per acs-messages.xsd\n%s\n" % (label, detail))
        else:
            errors = validate_structurally(text)
            if not errors:
                print("%s: valid (in-process, acs-messages.xsd)" % label)
            else:
                failures += 1
                for error in errors:
                    sys.stderr.write("%s: INVALID — %s\n" % (label, error))
        if arg == "-":
            os.unlink(path)

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
