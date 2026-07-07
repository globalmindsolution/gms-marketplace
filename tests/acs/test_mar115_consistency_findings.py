"""Behavioral tests for plugins/acs/hooks/scripts/consistency_findings.py (spec 02).

Pure stdlib unittest, direct-function-call style (imports and calls the real
functions; the module is executable code, not agent prompt text). Cases map to
AC-H1..AC-H3 per tests/acs/../.. spec 02 Test plan. AC-H4 (90% coverage) is
proven separately by tests/acs/cov_consistency_findings.py.
"""

import ast
import importlib
import os
import sys
import unittest

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

consistency_findings = importlib.import_module("consistency_findings")  # noqa: E402

STRING_FIELDS = ("upstream", "downstream", "description", "recommendation")


def _well_formed(kind="gap"):
    return {
        "kind": kind,
        "upstream": "docs/product/prd.md#G8",
        "downstream": "docs/architecture/hld/overview.md",
        "description": "PRD gains G8 but architecture has no coverage entry",
        "recommendation": "Add architecture -> quality, architecture -> operations",
    }


class TestValidateFindingAccepts(unittest.TestCase):
    """AC-H1: accepts well-formed findings."""

    def test_accepts_well_formed_finding_kind_gap(self):
        ok, errors = consistency_findings.validate_finding(_well_formed(kind="gap"))
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_accepts_well_formed_finding_kind_staleness(self):
        ok, errors = consistency_findings.validate_finding(_well_formed(kind="staleness"))
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_accepts_well_formed_finding_with_extra_keys(self):
        finding = _well_formed()
        finding["extra_unrelated_key"] = "ignored"
        ok, errors = consistency_findings.validate_finding(finding)
        self.assertTrue(ok)
        self.assertEqual(errors, [])


class TestValidateFindingRejectsKind(unittest.TestCase):
    """AC-H2: bad/missing/None kind."""

    def test_rejects_wrong_case_kind(self):
        finding = _well_formed()
        finding["kind"] = "Gap"
        ok, errors = consistency_findings.validate_finding(finding)
        self.assertFalse(ok)
        self.assertTrue(any("kind" in e for e in errors))

    def test_rejects_near_miss_kind(self):
        finding = _well_formed()
        finding["kind"] = "stale"
        ok, errors = consistency_findings.validate_finding(finding)
        self.assertFalse(ok)
        self.assertTrue(any("kind" in e for e in errors))

    def test_rejects_none_kind(self):
        finding = _well_formed()
        finding["kind"] = None
        ok, errors = consistency_findings.validate_finding(finding)
        self.assertFalse(ok)
        self.assertTrue(any("kind" in e for e in errors))

    def test_rejects_missing_kind(self):
        finding = _well_formed()
        del finding["kind"]
        ok, errors = consistency_findings.validate_finding(finding)
        self.assertFalse(ok)
        self.assertTrue(any("kind" in e for e in errors))


class TestValidateFindingRejectsStringFields(unittest.TestCase):
    """AC-H2: missing/None/empty/whitespace/non-string for each of the four string fields."""

    def test_rejects_missing_or_empty_string_fields(self):
        for field in STRING_FIELDS:
            variants = {
                "omitted": "OMIT",
                "none": None,
                "empty": "",
                "whitespace": "   ",
                "non_string_int": 123,
                "non_string_list": [],
                "non_string_dict": {},
            }
            for label, value in variants.items():
                with self.subTest(field=field, variant=label):
                    finding = _well_formed()
                    if value == "OMIT":
                        del finding[field]
                    else:
                        finding[field] = value
                    ok, errors = consistency_findings.validate_finding(finding)
                    self.assertFalse(ok)
                    self.assertTrue(
                        any(field in e for e in errors),
                        "expected an error naming %r, got %r" % (field, errors),
                    )

    def test_rejects_multiple_bad_fields_reports_all(self):
        finding = _well_formed()
        finding["kind"] = "bogus"
        finding["upstream"] = ""
        ok, errors = consistency_findings.validate_finding(finding)
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("kind" in e for e in errors))
        self.assertTrue(any("upstream" in e for e in errors))


class TestValidateFindingRejectsNonDict(unittest.TestCase):
    """AC-H2: non-dict input never raises."""

    def test_rejects_none_input(self):
        ok, errors = consistency_findings.validate_finding(None)
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_rejects_string_input(self):
        ok, errors = consistency_findings.validate_finding("a string")
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_rejects_list_input(self):
        ok, errors = consistency_findings.validate_finding([1, 2])
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_rejects_int_input(self):
        ok, errors = consistency_findings.validate_finding(42)
        self.assertFalse(ok)
        self.assertTrue(errors)


class TestValidateFindingsListWrapper(unittest.TestCase):
    """validate_findings: mixed list, empty list, non-list."""

    def test_mixed_list(self):
        findings = [_well_formed(), _well_formed(kind="bogus")]
        ok, per_finding = consistency_findings.validate_findings(findings)
        self.assertFalse(ok)
        self.assertEqual(len(per_finding), 2)
        self.assertEqual(per_finding[0], consistency_findings.validate_finding(findings[0]))
        self.assertEqual(per_finding[1], consistency_findings.validate_finding(findings[1]))

    def test_all_valid_list(self):
        findings = [_well_formed(kind="gap"), _well_formed(kind="staleness")]
        ok, per_finding = consistency_findings.validate_findings(findings)
        self.assertTrue(ok)
        self.assertEqual(len(per_finding), 2)

    def test_empty_list(self):
        ok, per_finding = consistency_findings.validate_findings([])
        self.assertTrue(ok)
        self.assertEqual(per_finding, [])

    def test_non_list_input(self):
        ok, per_finding = consistency_findings.validate_findings({"not": "a list"})
        self.assertFalse(ok)
        self.assertEqual(per_finding, [])


class TestModuleIsStdlibOnlyAndImportable(unittest.TestCase):
    """AC-H3: stdlib-only, isolated, side-effect-free import."""

    def test_module_source_imports_are_stdlib_only(self):
        target = os.path.join(_SCRIPTS_DIR, "consistency_findings.py")
        with open(target, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=target)

        imported_top_levels = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_top_levels.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported_top_levels.add(node.module.split(".")[0])

        if hasattr(sys, "stdlib_module_names"):
            allowed = set(sys.stdlib_module_names)
        else:
            allowed = {
                "sys", "os", "json", "re", "ast", "typing", "collections",
                "itertools", "functools", "dataclasses", "enum", "abc",
            }

        non_stdlib = imported_top_levels - allowed
        self.assertEqual(
            non_stdlib, set(),
            "consistency_findings.py imports non-stdlib module(s): %r" % non_stdlib,
        )
        self.assertNotIn("acs_lib", imported_top_levels)

    def test_module_has_validate_finding_and_no_io_on_call(self):
        self.assertTrue(hasattr(consistency_findings, "validate_finding"))
        self.assertTrue(hasattr(consistency_findings, "validate_findings"))
        # No filesystem/network dependency: calling with a plain dict succeeds
        # with no tempfile/network setup in this test.
        ok, errors = consistency_findings.validate_finding(_well_formed())
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_module_has_no_main_entrypoint(self):
        self.assertFalse(hasattr(consistency_findings, "main"))


if __name__ == "__main__":
    unittest.main()
