#!/usr/bin/env python3
"""Self-test for the CLI-tier mutation sweep's pure half (no build, no run).

The sweep's value rests on two things this checks without spending a second
on the CLI tier: that every site it enumerates can be applied and still
compiles, and that a seeded sample is the same sample twice.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mutation_cli import apply_mutation, enumerate_sites, sample_sites  # noqa: E402

SOURCE = '''
LIMIT = 400

def lane(size, stakes, needs_design):
    if needs_design:
        return "COMPLEX"
    if size == "large" or stakes == "high":
        return "STANDARD"
    if not needs_design and size in ("small", "medium"):
        return "SMALL"
    return "TRIVIAL"

def under_cap(lines):
    return lines <= LIMIT and lines >= 0

def passed(findings):
    return all(f.get("severity") != "blocking" for f in findings)

def retries(n):
    if n > 3:
        return False
    return True
'''


class EnumerateTest(unittest.TestCase):
    def setUp(self):
        self.sites = enumerate_sites(SOURCE)
        self.kinds = [s["kind"] for s in self.sites]

    def test_every_operator_finds_a_site(self):
        for kind in ("negate-compare", "boundary", "swap-boolop", "drop-not",
                     "flip-bool", "nudge-int", "negate-test"):
            self.assertIn(kind, self.kinds, kind)

    def test_sites_are_ordered_and_carry_lines(self):
        linenos = [s["lineno"] for s in self.sites]
        self.assertTrue(all(isinstance(n, int) and n > 0 for n in linenos))
        self.assertEqual(self.sites, enumerate_sites(SOURCE))

    def test_the_bare_name_condition_is_negated_only_as_a_whole(self):
        # `if needs_design:` has no comparison to flip, so its only mutant is
        # negating the test; a Compare condition must not get that extra site.
        neg = [s for s in self.sites if s["kind"] == "negate-test"]
        self.assertEqual([s["lineno"] for s in neg], [5])

    def test_integers_are_only_nudged_where_they_decide_something(self):
        nudged = [s["lineno"] for s in self.sites if s["kind"] == "nudge-int"]
        self.assertIn(20, nudged)       # `n > 3`
        self.assertNotIn(2, nudged)     # the module constant itself


class ApplyTest(unittest.TestCase):
    def test_every_site_applies_and_compiles(self):
        for site in enumerate_sites(SOURCE):
            out = apply_mutation(SOURCE, site)
            self.assertNotEqual(out.strip(), SOURCE.strip(), site)
            compile(out, "<m>", "exec")

    def test_a_negated_comparison_changes_the_decision(self):
        site = [s for s in enumerate_sites(SOURCE)
                if s["kind"] == "negate-compare" and s["lineno"] == 20][0]
        ns = {}
        exec(apply_mutation(SOURCE, site), ns)
        self.assertTrue(ns["retries"](5))       # was False before the mutant
        self.assertFalse(ns["retries"](1))

    def test_a_boundary_mutant_moves_the_edge_by_one(self):
        site = [s for s in enumerate_sites(SOURCE)
                if s["kind"] == "boundary" and s["lineno"] == 14
                and s["detail"].startswith("LtE")][0]
        ns = {}
        exec(apply_mutation(SOURCE, site), ns)
        self.assertFalse(ns["under_cap"](400))  # `<=` became `<`
        self.assertTrue(ns["under_cap"](399))

    def test_dropping_a_not_inverts_the_branch(self):
        site = [s for s in enumerate_sites(SOURCE) if s["kind"] == "drop-not"][0]
        ns = {}
        exec(apply_mutation(SOURCE, site), ns)
        self.assertEqual(ns["lane"]("small", "low", False), "TRIVIAL")

    def test_a_flipped_bool_changes_a_return(self):
        site = [s for s in enumerate_sites(SOURCE)
                if s["kind"] == "flip-bool" and s["lineno"] == 21][0]
        ns = {}
        exec(apply_mutation(SOURCE, site), ns)
        self.assertTrue(ns["retries"](5))


class SampleTest(unittest.TestCase):
    def test_seeded_sample_is_deterministic_and_sorted(self):
        by_module = {"a.py": enumerate_sites(SOURCE), "b.py": enumerate_sites(SOURCE)}
        one = sample_sites(by_module, 5, seed=7)
        two = sample_sites(by_module, 5, seed=7)
        self.assertEqual(one, two)
        self.assertEqual(len(one), 5)
        keys = [(m, s["lineno"], s["kind"]) for m, s in one]
        self.assertEqual(keys, sorted(keys))

    def test_zero_means_every_mutant(self):
        by_module = {"a.py": enumerate_sites(SOURCE)}
        self.assertEqual(len(sample_sites(by_module, 0, seed=1)),
                         len(by_module["a.py"]))


if __name__ == "__main__":
    unittest.main()
