"""Bidirectional drift guard for validate_xml.py's ALLOWED_ATTRS mirror.

`validate_xml.py` enforces the XSD's closed content model in process, using a
hand-written `ALLOWED_ATTRS` table. Its own module docstring says that table
"mirrors acs-messages.xsd and MUST be kept in sync with it" -- but only the
`SKILLS` mirror had a guard recomputing it live
(`test_message_schema_skill_enum.py`). `ALLOWED_ATTRS` had none, and it drifted:
the XSD gained `lens` on `<result>` (the attribute that tells the post-hook
which of the four full-depth review lenses a verdict belongs to) and the mirror
never learned about it, so every lens-tagged result a verifier emitted was
refused as having an undeclared attribute.

Every expected value here is recomputed from the XSD at run time -- never a
frozen constant -- so the guard cannot itself re-drift from either side.
"""

import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
XSD = os.path.join(PLUGIN, "schemas", "acs-messages.xsd")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
VALIDATOR = os.path.join(HOOKS_SCRIPTS, "validate_xml.py")

sys.path.insert(0, HOOKS_SCRIPTS)
import validate_xml  # noqa: E402

XS = "{http://www.w3.org/2001/XMLSchema}"


def _own_attrs(node):
    """Attribute names declared for this element, however deeply nested.

    An attribute can sit directly under the `xs:complexType` (`<result>`) or
    under `xs:simpleContent/xs:extension` (`<finding>`, `<constraint>`), so a
    shallow `findall` misses half of them. Descend everything EXCEPT a nested
    `xs:element`, whose attributes belong to that element and not this one.
    """
    found = set()
    for child in node:
        if child.tag == "%selement" % XS:
            continue
        if child.tag == "%sattribute" % XS and child.get("name"):
            found.add(child.get("name"))
        found |= _own_attrs(child)
    return found


def declared_attrs():
    """{element name: {attribute names}} for every element the XSD gives one."""
    root = ET.parse(XSD).getroot()
    out = {}
    for elem in root.iter("%selement" % XS):
        name = elem.get("name")
        if not name:
            continue
        attrs = _own_attrs(elem)
        if attrs:
            out[name] = attrs
    return out


def enum_values(type_name):
    root = ET.parse(XSD).getroot()
    for st in root.iter("%ssimpleType" % XS):
        if st.get("name") != type_name:
            continue
        return [e.get("value") for e in st.iter("%senumeration" % XS)]
    return []


def check(xml):
    proc = subprocess.run([sys.executable, VALIDATOR, "-"], input=xml,
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


class AllowedAttrsMirrorsTheXsdTest(unittest.TestCase):

    def test_every_xsd_declared_attribute_is_allowed_by_the_validator(self):
        for element, attrs in sorted(declared_attrs().items()):
            mirrored = validate_xml.ALLOWED_ATTRS.get(element, frozenset())
            missing = attrs - set(mirrored)
            self.assertFalse(
                missing,
                "validate_xml.ALLOWED_ATTRS[%r] is missing %s, which "
                "acs-messages.xsd declares. A message using it is refused as "
                "undeclared." % (element, sorted(missing)),
            )

    def test_the_validator_allows_no_attribute_the_xsd_does_not_declare(self):
        declared = declared_attrs()
        for element, mirrored in sorted(validate_xml.ALLOWED_ATTRS.items()):
            extra = set(mirrored) - declared.get(element, set())
            self.assertFalse(
                extra,
                "validate_xml.ALLOWED_ATTRS[%r] allows %s, which the XSD does "
                "not declare -- the in-process check is looser than the schema "
                "it claims to mirror." % (element, sorted(extra)),
            )


class LensAttributeIsAcceptedTest(unittest.TestCase):
    """The drift above, stated as the behaviour a caller actually depends on."""

    def _result(self, lens_attr=""):
        return ('<result skill="code" phase="verify" ticket-id="MAR-1" '
                'status="completed"%s><findings/></result>' % lens_attr)

    def test_a_result_without_a_lens_is_valid(self):
        code, out = check(self._result())
        self.assertEqual(code, 0, out)

    def test_a_lens_tagged_result_is_valid_for_every_declared_lens(self):
        values = enum_values("verifyLens")
        self.assertTrue(values, "the XSD declares no verifyLens enumeration")
        for value in values:
            code, out = check(self._result(' lens="%s"' % value))
            self.assertEqual(code, 0, "lens=%r was refused:\n%s" % (value, out))

    def test_a_lens_outside_the_enumeration_is_refused(self):
        code, out = check(self._result(' lens="not-a-lens"'))
        self.assertEqual(code, 1, "an undeclared lens value was accepted:\n%s" % out)
        self.assertIn("lens", out)


if __name__ == "__main__":
    unittest.main()
