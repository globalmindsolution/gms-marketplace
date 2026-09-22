"""MAR-587 AC-6 — a golden case is deleted only when its subject is gone.

Reconciling a dataset against a redesigned surface offers two cheap ways to
turn a gate green that both destroy its value: delete the case whose subject
still exists, or keep a case pointed at a subject that no longer does. This
module refuses both, over the shipped dataset rather than over a list of ids
someone remembered to update.

Both directions are derived from the build itself:

  * what may be deleted -- a schema file that is not in `src/acs/schemas/`,
    or a subcommand `acs.py`'s own parser does not offer;
  * what may NOT be deleted -- the verdict rules `acs_lib.verdict` still
    enforces, each of which must stay pinned by a case that quotes the live
    refusal discriminatingly.

Run:  python3 -m unittest tests.acs.test_eval_deletions_are_justified -v
"""

import glob
import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import SCRIPTS  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = os.path.join(REPO, "src", "acs-evals", "dataset", "cases")
SCHEMAS = os.path.join(REPO, "src", "acs", "schemas")


def case_files():
    """Every case file, as (filename, document) pairs."""
    out = []
    for path in sorted(glob.glob(os.path.join(CASES, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            out.append((os.path.basename(path), json.load(fh)))
    return out


def acs_cli():
    """The shipped `acs.py`, loaded by path under a name of its own.

    A plain `import acs` binds the TEST package: under `unittest discover -s
    tests` this module is `acs.test_eval_deletions_are_justified`, so the CLI
    would be shadowed by the directory holding its own tests.
    """
    name = "acs_cli_under_test"
    mod = sys.modules.get(name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(SCRIPTS, "acs.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


def cli_surface():
    """`{verb: {subcommand, ...}}` as `acs.py`'s own parser declares it."""
    _parser, choices = acs_cli().build_parser()
    groups = {}
    for verb, sub in choices.items():
        names = set()
        nested = getattr(sub, "_subparsers", None)
        for action in (nested._group_actions if nested else ()):
            names.update(getattr(action, "choices", {}) or {})
        groups[verb] = names
    return groups


class DeadSubjectsLeaveNoCaseBehindTest(unittest.TestCase):
    """A case whose subject v0.5.0 removed pins nothing; it must be deleted,
    not re-pointed at whatever is nearest."""

    def test_no_case_names_a_schema_the_build_does_not_ship(self):
        orphans = []
        for name, doc in case_files():
            for case in doc.get("cases", []):
                schema = case.get("schema")
                if schema and not os.path.isfile(os.path.join(SCHEMAS, schema)):
                    orphans.append("%s %s -> %s" % (name, case["id"], schema))
        self.assertEqual(orphans, [],
                         "cases recorded against schemas the build does not "
                         "ship: %s" % orphans)

    def test_no_case_invokes_a_subcommand_its_surviving_verb_does_not_offer(self):
        surface = cli_surface()
        gone = []
        for name, doc in case_files():
            for case in doc.get("cases", []):
                invoke = case.get("invoke") or {}
                if invoke.get("script", "acs.py") != "acs.py":
                    continue
                argv = [str(a) for a in invoke.get("argv", [])]
                # A file whose whole verb is gone is a whole-file disposition;
                # this asserts within the families whose verb survived.
                if not argv or argv[0] not in surface:
                    continue
                if len(argv) > 1 and not argv[1].startswith("-") \
                        and surface[argv[0]] and argv[1] not in surface[argv[0]]:
                    gone.append("%s %s -> %s %s" % (name, case["id"], argv[0], argv[1]))
        self.assertEqual(gone, [],
                         "cases invoking subcommands acs.py no longer offers: "
                         "%s" % gone)


class SurvivingSubjectsKeepTheirCasesTest(unittest.TestCase):
    """The other direction: a rule the kernel still enforces may not lose its
    case to a reconciliation pass."""

    #: One rigged document per rule `acs_lib.verdict.validate_verdict` carries,
    #: named by the axis it breaks. The expected refusal is read off the live
    #: function, so a case pinned to wording the build no longer emits reads as
    #: an unpinned rule rather than as a pass.
    def live_refusals(self):
        def doc(**over):
            base = {"skill": "code", "run_id": "TKT-1", "iteration": 1,
                    "reviewed_sha": "abc1234", "lens": None,
                    "passed": True, "findings": []}
            base.update(over)
            return base

        blocking = [{"id": "F-1-1", "status": "confirmed", "severity": "blocking",
                     "kind": "defect", "claim": "x", "evidence": ["y"],
                     "resolved_when": "z"}]
        axes = {
            "passed-true-with-a-blocking-finding": (
                doc(passed=True, findings=blocking), {}),
            "passed-false-with-no-blocking-finding": (
                doc(passed=False), {}),
            "a-verdict-from-another-run": (
                doc(run_id="TKT-9"), {"run_id": "TKT-1"}),
            "a-verdict-from-another-iteration": (
                doc(iteration=1), {"iteration": 3}),
            "a-verdict-from-another-skill": (
                doc(skill="docs-sync"), {"skill": "code"}),
        }
        out = {}
        for axis, (instance, expected) in axes.items():
            errors = acs_lib.validate_verdict(instance, **expected)
            self.assertTrue(errors, "%s no longer refused by validate_verdict" % axis)
            out[axis] = errors[-1]
        return out

    def test_every_verdict_rule_the_kernel_enforces_is_pinned_by_a_case(self):
        refusals = self.live_refusals()
        needles = []
        for _name, doc in case_files():
            for case in doc.get("cases", []):
                needles.extend(case.get("expect", {}).get("stderr_contains", []))
        unpinned = []
        for axis, refusal in refusals.items():
            # A needle shared with another axis pins the family, not this rule:
            # only a needle unique to THIS refusal proves the case survived.
            others = [r for a, r in refusals.items() if a != axis]
            if not any(n in refusal and not any(n in o for o in others)
                       for n in needles if isinstance(n, str)):
                unpinned.append("%s (live refusal: %r)" % (axis, refusal))
        self.assertEqual(unpinned, [],
                         "verdict rules the kernel still enforces that no case "
                         "pins discriminatingly: %s" % unpinned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
