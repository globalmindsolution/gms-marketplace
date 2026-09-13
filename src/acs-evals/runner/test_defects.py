#!/usr/bin/env python3
"""Self-test for the seeded-defect catalogue: every defect names a real verifier
dimension, applies to a fresh fixture, and leaves the suite in its declared state."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import defects as dx  # noqa: E402
from verifier_rates import DIMENSIONS  # noqa: E402


class CatalogueTest(unittest.TestCase):
    def test_every_defect_names_a_charter_dimension(self):
        for d in dx.load_all():
            self.assertEqual(DIMENSIONS[d["dimension_id"]], d["dimension"], d["id"])
            self.assertIn(d["expected_severity"], ("blocking", "info"))
            self.assertTrue(d.get("patch") or d.get("create"), d["id"])

    def test_the_catalogue_covers_the_planned_dimensions(self):
        dims = {d["dimension_id"] for d in dx.load_all()}
        for wanted in (2, 3, 4, 6, 10, 11, 12):
            self.assertIn(wanted, dims)

    def test_every_defect_applies_and_behaves_as_declared(self):
        failures = dx.selftest(log=lambda *_: None)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
