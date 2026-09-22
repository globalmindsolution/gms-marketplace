#!/usr/bin/env python3
"""Self-test for the CLI-tier mutation sweep's pure half (no build, no run).

The sweep's value rests on two things this checks without spending a second
on the CLI tier: that every site it enumerates can be applied and still
compiles, and that a seeded sample is the same sample twice.

`HonestDenominatorTest` covers the schema-tier sweep's denominator rule, which
answers the same question about `mutation_sweep.py`: a number nobody can trust
measures nothing.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mutation_cli import apply_mutation, enumerate_sites, sample_sites  # noqa: E402
import mutation_sweep  # noqa: E402

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


#: Three mutable constraints: `required` and `additionalProperties` at the
#: root, `minLength` under /properties/a. `type` is never mutated.
HONEST_SCHEMA = {
    "type": "object",
    "required": ["a"],
    "properties": {"a": {"type": "string", "minLength": 1}},
    "additionalProperties": False,
}


def schema_case(case_id, schema, instance, valid, errors_contain=()):
    """One schema-tier case, shaped as dataset/cases/*.json records them."""
    expect = {"valid": valid}
    if errors_contain:
        expect["errors_contain"] = list(errors_contain)
    return {"id": case_id, "kind": "schema", "schema": schema,
            "json": instance, "expect": expect}


class HonestDenominatorTest(unittest.TestCase):
    """A fixture that fails against the UNMUTATED schema detects nothing.

    It fails for every mutant too, so counting it credits the dataset with
    detection it never performed -- which is how `verdict.schema.json` reported
    a fake 19/19 while five of its cases could not hold unmutated.
    """

    #: Pins `minLength` honestly: the empty string is rejected, and stops being
    #: rejected the moment that one constraint is deleted.
    PINNED = schema_case("PIN-1", "pinned.schema.json", {"a": ""}, False,
                         ["shorter than minLength"])
    #: Rigged: expects valid, cannot ever be valid. Detects all three.
    RIGGED = schema_case("RIG-1", "pinned.schema.json", {"b": 1}, True)

    def setUp(self):
        root = tempfile.mkdtemp(prefix="acs-mutation-denominator-")
        self.addCleanup(shutil.rmtree, root, True)
        os.mkdir(os.path.join(root, "schemas"))
        for name in ("pinned.schema.json", "only-rigged.schema.json"):
            with open(os.path.join(root, "schemas", name), "w") as fh:
                json.dump(HONEST_SCHEMA, fh)
        self.root = root

    def test_a_fixture_that_fails_unmutated_is_named_by_id(self):
        defects = mutation_sweep.defective_fixtures(
            self.root, [self.PINNED, self.RIGGED])
        self.assertEqual([(cid, name) for cid, name, _why in defects],
                         [("RIG-1", "pinned.schema.json")])
        self.assertIn("valid", defects[0][2])

    def test_the_rig_inflates_the_schema_until_it_is_excluded(self):
        cases = [self.PINNED, self.RIGGED]
        counted, _holes, _skipped = mutation_sweep.sweep(self.root, cases)
        self.assertEqual(counted["pinned.schema.json"], (3, 3))
        honest, holes, _skipped = mutation_sweep.sweep(self.root, cases,
                                                       {"RIG-1"})
        self.assertEqual(honest["pinned.schema.json"], (1, 3))
        self.assertEqual(sorted(k for _n, k, _p in holes),
                         ["additionalProperties", "required"])

    def test_an_excluded_case_never_shrinks_the_denominator(self):
        # sweep() drops a schema no case names to 0/0, which would leave the
        # percentage untouched while a whole schema stopped being measured:
        # one false number traded for another. A schema whose only case is
        # defective is reported 0/3 -- unpinned, and still counted.
        only_rigged = schema_case("RIG-2", "only-rigged.schema.json",
                                  {"b": 1}, True)
        results, _holes, _skipped = mutation_sweep.sweep(
            self.root, [only_rigged], {"RIG-2"})
        self.assertEqual(results["only-rigged.schema.json"], (0, 3))


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
