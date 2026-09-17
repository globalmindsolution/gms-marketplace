"""One declaration per contract (ADR-0093).

`schemas/acs-messages.xsd` is the only statement of the message vocabulary:
`validate_xml.py` derives everything it enforces from the XSD at import and
carries no parallel table. This module pins that derivation against an
independent parse of the XSD, the typed delegation keys (`constraint/@name`
is the `constraintName` vocabulary), the retired `plan`/`coordinate` phases,
the `result/@lens` round trip, and the state-file schema's declaration of
the load-bearing members — each recomputed from the source files at run
time, never a frozen constant, so the guard cannot itself drift.

Run:  python3 -m unittest tests.acs.test_message_schema_derivation -v
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover - CI installs it; local runs may not
    HAS_JSONSCHEMA = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
XSD = os.path.join(PLUGIN, "schemas", "acs-messages.xsd")
STATE_SCHEMA = os.path.join(PLUGIN, "schemas", "skill-state.schema.json")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
VALIDATOR = os.path.join(HOOKS_SCRIPTS, "validate_xml.py")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
LIFECYCLE = os.path.join(HOOKS_SCRIPTS, "acs_lib", "lifecycle.py")

sys.path.insert(0, HOOKS_SCRIPTS)
import validate_xml  # noqa: E402

XS = "{http://www.w3.org/2001/XMLSchema}"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def simple_type(name):
    """(enum values, patterns) of a named simpleType, unions flattened —
    parsed here independently of validate_xml's own loader."""
    root = ET.parse(XSD).getroot()
    node = root.find("%ssimpleType[@name='%s']" % (XS, name))
    assert node is not None, "the XSD declares no simpleType %r" % name
    enum = [e.get("value") for e in node.iter("%senumeration" % XS)]
    patterns = [p.get("value") for p in node.iter("%spattern" % XS)]
    return enum, patterns


def root_sequence(name):
    root = ET.parse(XSD).getroot()
    el = root.find("%selement[@name='%s']" % (XS, name))
    seq = el.find("%scomplexType/%ssequence" % (XS, XS))
    return [c.get("name") for c in seq.findall("%selement" % XS)]


def prose_files():
    return (glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md"))
            + glob.glob(os.path.join(PLUGIN, "agents", "*.md")))


def vocabulary_accepts(name):
    enum, patterns = simple_type("constraintName")
    return name in enum or any(re.fullmatch(p, name) for p in patterns)


def task_with_constraint(name):
    return ('<task skill="code" phase="execute" ticket-id="MAR-1">'
            '<objective>x</objective><constraints>'
            '<constraint name="%s">v</constraint></constraints></task>' % name)


def xmllint_ok(message):
    proc = subprocess.run(["xmllint", "--noout", "--schema", XSD, "-"],
                          input=message, capture_output=True, text=True, timeout=20)
    return proc.returncode == 0


class ValidatorIsDerivedFromTheXsdTest(unittest.TestCase):

    def test_the_validator_names_no_vocabulary_member_itself(self):
        """The one place a mirror could hide is a literal in the source.

        Enumeration members, root child names and attribute names appear in
        validate_xml.py only if someone wrote a table again; the loader has
        no reason to spell any of them."""
        source = read(VALIDATOR)
        for literal in ('"analyze-ticket"', '"create-spec"', '"needs_input"',
                        '"handed_off"', '"blocking"', '"execute"', '"verify"',
                        '"ticket-id"', '"objective"', '"stop-reason"',
                        '"verify_lens"', '"coverage_target"'):
            self.assertNotIn(literal, source,
                             "%s is spelled in validate_xml.py: a mirror is back" % literal)
        self.assertNotRegex(source, r"(?i)keep .{0,20}in sync")

    def test_derived_views_match_an_independent_parse(self):
        self.assertEqual(set(validate_xml.SKILLS), set(simple_type("skillName")[0]))
        self.assertEqual(set(validate_xml.PHASES), set(simple_type("phaseName")[0]))
        self.assertEqual(set(validate_xml.RESULT_STATUSES), set(simple_type("resultStatus")[0]))
        self.assertEqual(set(validate_xml.HANDOFF_STATUSES), set(simple_type("handoffStatus")[0]))
        self.assertEqual(set(validate_xml.VERIFY_LENSES), set(simple_type("verifyLens")[0]))
        self.assertEqual(set(validate_xml.CONSTRAINT_NAMES), set(simple_type("constraintName")[0]))
        self.assertEqual(tuple(validate_xml.CONSTRAINT_NAME_PATTERNS),
                         tuple(simple_type("constraintName")[1]))
        for root in ("task", "result", "handoff"):
            self.assertEqual(validate_xml.CHILD_ORDER[root], root_sequence(root))
        self.assertEqual(validate_xml.REQUIRED_CHILDREN,
                         {"task": ["objective"], "result": [], "handoff": ["summary"]})
        self.assertEqual(validate_xml.TEXT_LEAVES,
                         frozenset({"objective", "context", "stop-reason", "summary",
                                    "next-step", "file", "question", "error"}))

    def test_ticket_id_pattern_is_the_xsds(self):
        _enum, patterns = simple_type("ticketId")
        self.assertEqual(validate_xml.TICKET_RE.pattern, "^(?:%s)$" % "|".join(patterns))


class NoPlanPhaseTest(unittest.TestCase):
    """ADR-0092 retired the planner; ADR-0093 retired the phase it filed
    under, and the /ship-brief `coordinate` phase with it (ADR-0089)."""

    def test_phase_enumeration_is_execute_and_verify(self):
        self.assertEqual(set(simple_type("phaseName")[0]), {"execute", "verify"})

    def test_a_plan_task_is_refused_in_process(self):
        errors = validate_xml.validate_structurally(
            '<task skill="code" phase="plan" ticket-id="MAR-1"><objective>x</objective></task>')
        self.assertTrue(any("phase" in e for e in errors), errors)

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_a_plan_task_is_refused_by_xmllint_too(self):
        self.assertFalse(xmllint_ok(
            '<task skill="code" phase="plan" ticket-id="MAR-1"><objective>x</objective></task>'))

    def test_no_role_table_names_a_planner(self):
        sys.path.insert(0, HOOKS_SCRIPTS)
        import claude_code_adapter  # noqa: E402
        from acs_lib import lifecycle  # noqa: E402
        self.assertEqual(set(lifecycle.ROLE_PHASES), {"executor", "verifier"})
        self.assertEqual({role for _, role in claude_code_adapter.ROLE_SUFFIXES},
                         {"executor", "verifier"})


class TypedDelegationKeysTest(unittest.TestCase):

    def test_every_vocabulary_name_is_accepted(self):
        enum, _patterns = simple_type("constraintName")
        self.assertTrue(enum)
        for name in enum:
            with self.subTest(name=name):
                self.assertEqual(validate_xml.validate_structurally(task_with_constraint(name)), [])

    def test_the_per_file_sections_form_is_accepted(self):
        self.assertEqual(validate_xml.validate_structurally(
            task_with_constraint("required_sections:hld/overview.md")), [])

    def test_a_name_outside_the_vocabulary_is_refused(self):
        for name in ("coverage-target", "coverage-threshold", "e2e_cmd", "verifyLens", ""):
            with self.subTest(name=name):
                errors = validate_xml.validate_structurally(task_with_constraint(name))
                self.assertTrue(any("<constraint name=" in e for e in errors), errors)

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_xmllint_agrees_on_the_vocabulary(self):
        self.assertTrue(xmllint_ok(task_with_constraint("coverage_target")))
        self.assertTrue(xmllint_ok(task_with_constraint("required_sections:hld/overview.md")))
        self.assertFalse(xmllint_ok(task_with_constraint("coverage-target")))

    def test_every_constraint_the_prose_emits_is_in_the_vocabulary(self):
        """A SKILL.md example or an agent charter naming a constraint outside
        the vocabulary would ship a message the validator refuses."""
        offenders = []
        for path in prose_files():
            for name in re.findall(r'<constraint name="([^"]+)"', read(path)):
                if not vocabulary_accepts(name):
                    offenders.append((os.path.relpath(path, REPO_ROOT), name))
        self.assertEqual(offenders, [])

    def test_every_vocabulary_name_is_consumed_by_some_prose(self):
        """A name nothing emits or reads is a dead declaration — the class of
        defect ADR-0093 decision 4 forbids."""
        bodies = "\n".join(read(p) for p in prose_files())
        dead = [name for name in simple_type("constraintName")[0]
                if ('name="%s"' % name) not in bodies and ("`%s`" % name) not in bodies]
        self.assertEqual(dead, [])

    def test_the_coverage_constraint_has_one_spelling(self):
        bodies = "\n".join(read(p) for p in prose_files())
        self.assertIn('name="coverage_target"', bodies)
        for stale in ('name="coverage-target"', 'name="coverage-threshold"'):
            self.assertNotIn(stale, bodies)


class LensRoundTripTest(unittest.TestCase):
    """`result/@lens` is declared, emitted, and read (ADR-0093 decision 4)."""

    def test_the_verifier_carries_the_lens_back(self):
        body = read(CODE_VERIFIER)
        self.assertIn('lens="A|B|C|D"', body)
        self.assertIn("verify_lens", body)

    def test_the_coordinator_expects_it_on_lens_results(self):
        """The multi-lens review is the `complex` delivery path's alone, so the
        coordinator half of the round trip lives in that leg (ADR-0095), not in
        the dispatcher every path goes through."""
        leg = os.path.join(PLUGIN, "skills", "code-complex", "SKILL.md")
        self.assertIn('lens="<A|B|C|D>"', read(leg))

    def test_the_hook_reads_it(self):
        self.assertIn('root.get("lens")', read(LIFECYCLE))

    def test_a_lens_result_validates_and_a_bad_lens_does_not(self):
        good = ('<result skill="code" phase="verify" ticket-id="MAR-1" status="completed" '
                'lens="B"><findings/></result>')
        self.assertEqual(validate_xml.validate_structurally(good), [])
        self.assertTrue(validate_xml.validate_structurally(good.replace('lens="B"', 'lens="E"')))


class StateSchemaDeclaresLoadBearingStateTest(unittest.TestCase):
    #: The one per-run event array the schema still declares. `escalations`
    #: stood here with a thirteen-field event (from_lane/to_lane, both axes on
    #: each side, the ceiling before and after, a direction); ADR-0095 retired
    #: mid-flight escalation, so there is no lane to move and no event to
    #: record. `guard_events` is what remains: file-map guard denials, which
    #: describe something that happened rather than something that was decided.
    GUARD_EVENT_FIELDS = ["ts", "skill", "iteration", "tool", "target",
                          "reason", "declared_count"]

    @classmethod
    def setUpClass(cls):
        with open(STATE_SCHEMA, encoding="utf-8") as fh:
            cls.schema = json.load(fh)

    def test_states_declares_the_gate_inputs(self):
        props = self.schema["properties"]["states"]["properties"]
        for key in ("verifier_passed", "plan_approved", "pr", "review", "tests",
                    "merged", "readiness"):
            self.assertIn(key, props)
        self.assertEqual(props["verifier_passed"]["type"], "boolean")
        self.assertEqual(props["pr"]["required"], ["number", "url", "branch", "base"])
        self.assertTrue(self.schema["properties"]["states"]["additionalProperties"])

    def test_guard_events_declare_the_seven_field_denial(self):
        items = self.schema["properties"]["runs"]["items"]["properties"]["guard_events"]["items"]
        self.assertEqual(items["required"], self.GUARD_EVENT_FIELDS)
        self.assertEqual(items["properties"]["reason"]["enum"],
                         ["outside_map", "control_input", "unreadable_payload"])

    def test_the_retired_escalation_array_is_gone_from_the_schema(self):
        """Not merely unused: a schema that still declared it would keep
        validating documents no writer can produce any more."""
        self.assertNotIn(
            "escalations",
            self.schema["properties"]["runs"]["items"]["properties"])

    def test_findings_carry_a_severity(self):
        items = self.schema["properties"]["findings"]["items"]
        self.assertEqual(items["required"], ["severity"])
        self.assertEqual(items["properties"]["severity"]["enum"], ["blocking", "info"])

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_a_recorded_guard_denial_and_a_bare_finding_validate_as_the_writers_shape_them(self):
        event = {"ts": "2026-09-14T00:00:00Z", "skill": "code", "iteration": "1",
                 "tool": "Write", "target": "auth/session.py",
                 "reason": "outside_map", "declared_count": 3}
        state = {"skill": "code", "ticket_id": "MAR-1",
                 "states": {"verifier_passed": True,
                            "pr": {"number": 42, "url": "u", "branch": "b", "base": "main"},
                            "tests": {"passed": 3, "failed": 0, "coverage_percent": 91.5}},
                 "findings": [{"severity": "blocking", "dimension": "coverage", "detail": "x"}],
                 "errors": [],
                 "runs": [{"started_at": "2026-09-14T00:00:00Z", "status": "completed",
                           "guard_events": [event]}]}
        jsonschema.validate(state, self.schema)
        state["findings"] = [{"dimension": "coverage"}]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(state, self.schema)
        state["findings"] = []
        state["runs"][0]["guard_events"] = [dict(event, reason="felt_like_it")]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(state, self.schema)


if __name__ == "__main__":
    unittest.main()
