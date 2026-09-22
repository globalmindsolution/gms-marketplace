"""MAR-587 -- `make mutation` must not count a fixture that fails unmutated.

`release.pre_release_gate[2]` is `make -C src/acs-evals mutation`, and it
printed 141/141 100% while five `verdict.schema.json` cases failed against the
UNMUTATED shipped schema. A case that fails unconditionally "detects" every
mutant, so those five inflated that schema to a fake 19/19 and the release gate
reported a pass it had not earned (AC-7).

This drives `runner/mutation_sweep.py` end to end against the checkout's own
`src/acs` schemas -- the build `make mutation` points at -- and re-derives the
defective set independently of the sweep, so it keeps holding once the fixtures
are repaired and the honest number climbs back up.

Run:  python3 -m unittest tests.acs.test_eval_mutation_honest_denominator -v
"""

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVALS = os.path.join(REPO_ROOT, "src", "acs-evals")
BUILD = os.path.join(REPO_ROOT, "src", "acs")

#: The defective set, re-derived from the dataset and the shipped schemas.
#: Deliberately not `mutation_sweep`'s own definition of the defect: checking
#: the sweep against itself would say nothing about whether that definition is
#: right. Deliberately in a child process too -- `runner/` and
#: `behavioural/acs/` both ship a `harness` module, and whichever sibling test
#: module imports one first decides what `run_golden` would bind to here.
DERIVE = r'''
import glob, json, os, sys
sys.path.insert(0, "runner")
import jsonschema_mini as js
from run_golden import seed_content

build = os.environ["ACS_PLUGIN_ROOT"]
out = []
for path in sorted(glob.glob(os.path.join("dataset", "cases", "*.json"))):
    with open(path) as fh:
        for case in json.load(fh)["cases"]:
            if case.get("kind") != "schema":
                continue
            schema_path = os.path.join(build, "schemas", case["schema"])
            if not os.path.exists(schema_path):
                continue          # the sweep never consults it: see the CLI
            with open(schema_path) as sfh:
                schema = json.load(sfh)
            try:
                errors = js.validate(seed_content(case), schema)
            except js.UnsupportedKeyword:
                out.append(case["id"])
                continue
            if (not errors) != case["expect"]["valid"] or any(
                    not any(n in e for e in errors)
                    for n in case["expect"].get("errors_contain", [])):
                out.append(case["id"])
print(json.dumps(sorted(out)))
'''


def run_python(*args):
    """A child rooted at src/acs-evals, pointed at this checkout's own build."""
    return subprocess.run([sys.executable] + list(args), cwd=EVALS,
                          env=dict(os.environ, ACS_PLUGIN_ROOT=BUILD),
                          capture_output=True, text=True)


def dataset_cases():
    """Every schema-tier case, read straight from dataset/cases/."""
    out = []
    cases_dir = os.path.join(EVALS, "dataset", "cases")
    for name in sorted(os.listdir(cases_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(cases_dir, name)) as fh:
            out.extend(c for c in json.load(fh)["cases"]
                       if c.get("kind") == "schema")
    return out


def named_ids(stdout):
    """The case ids the run reported as defective fixtures."""
    ids, inside = [], False
    for line in stdout.splitlines():
        if "DEFECTIVE fixture" in line:
            inside = True
        elif inside:
            if not line.strip():
                break
            ids.append(line.split()[0])
    return ids


class MutationSweepRefusesADefectiveFixtureTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = run_python(os.path.join(EVALS, "runner", "mutation_sweep.py"),
                                "--threshold", "0.9")
        derived = run_python("-c", DERIVE)
        assert derived.returncode == 0, derived.stderr
        cls.defective = json.loads(derived.stdout)

    def test_every_fixture_that_fails_unmutated_is_named_by_id(self):
        self.assertEqual(sorted(named_ids(self.result.stdout)), self.defective,
                         self.result.stdout)

    def test_a_defective_fixture_fails_the_run(self):
        # Silence would leave the next broken fixture free to recreate the
        # false pass, so the run stops while one is outstanding -- and says so
        # on stderr, which is the half a CI log keeps.
        self.assertEqual("DEFECTIVE FIXTURES" in self.result.stderr,
                         bool(self.defective), self.result.stderr)
        if self.defective:
            self.assertNotEqual(self.result.returncode, 0, self.result.stdout)

    def test_no_schema_with_cases_is_dropped_from_the_denominator(self):
        # Excluding a defective case must not empty a schema's case list and
        # so retire the whole schema from the total -- one false number traded
        # for another.
        named = {c["schema"] for c in dataset_cases()}
        reported = {}
        for line in self.result.stdout.splitlines():
            parts = line.split()
            if parts and parts[0].endswith(".schema.json"):
                reported[parts[0]] = parts[1]
        for schema in sorted(named & set(os.listdir(os.path.join(BUILD, "schemas")))):
            self.assertIn("/", reported.get(schema, "no"),
                          "%s has cases but reported %r"
                          % (schema, reported.get(schema)))

    def test_the_printed_total_is_the_arithmetic_of_its_own_table(self):
        rows, total = [], None
        for line in self.result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 3 and "/" in parts[1]:
                pair = tuple(int(n) for n in parts[1].split("/"))
                if parts[0] == "TOTAL":
                    total = pair
                else:
                    rows.append(pair)
        self.assertIsNotNone(total, self.result.stdout)
        self.assertEqual(total, (sum(c for c, _t in rows), sum(t for _c, t in rows)))

    def test_the_threshold_still_governs_the_exit_code(self):
        strict = run_python(os.path.join(EVALS, "runner", "mutation_sweep.py"),
                            "--threshold", "1.0")
        self.assertIn("BELOW THRESHOLD", strict.stderr)
        self.assertNotEqual(strict.returncode, 0)


if __name__ == "__main__":
    unittest.main()
