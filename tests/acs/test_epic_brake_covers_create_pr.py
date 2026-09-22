"""One epic brake, one answer: the query refuses `code` and `create-pr` alike.

Originating ticket: MAR-587 (AC-12). Two recorded goldens disagreed about the
same mechanism. GATE-042 requires `acs gate --skill code` on an epic to exit 2
-- the proof that the query SEES the brake -- while GATE-044 required
`acs gate --skill create-pr` on that same epic to exit 0. `_EPIC_VERBS`
(`acs_lib/brakes.py`) holds both verbs and the gate applies the brake to every
skill in that table, so one mechanism cannot point both ways: satisfying one
golden necessarily breaks the other, and whichever case was re-recorded last
would have settled the contradiction silently. ADR-0101 (Consequences) decided
it in GATE-042's favour; re-recording GATE-044 is only the dataset half of
that decision.

This module is the durable half. It pins the behaviour of both skills to the
one table, and it pins the recorded goldens to the same table -- derived from
`_EPIC_VERBS` at run time, never from a hard-coded list of case ids -- so a
future change cannot make one golden green by quietly breaking the other.

Stdlib-only. Run:  python3 -m unittest tests.acs.test_epic_brake_covers_create_pr -v
"""

import json
import os
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

from acs_lib import brakes  # noqa: E402

#: The goldens whose contradiction this module resolves, and the surface they
#: are recorded against.
GATES_CASES = os.path.join(
    acs_case.REPO_ROOT, "src", "acs-evals", "dataset", "cases", "06-gates.json")

#: What the refusal says, per skill, in that skill's own words. Read from the
#: live table so this file cannot drift from it.
EPIC_VERBS = brakes._EPIC_VERBS


def refusal(verb):
    """The sentence `_refuse_epic` builds for one verb."""
    return "epics are never %s directly" % verb


class EpicBrakeIsOneMechanismTest(acs_case.AcsWorkspaceCase):
    """`code` and `create-pr` are two rows of one table, so they answer alike."""

    def query(self, skill, ticket):
        return self.run_script("acs.py", "gate", "--skill", skill,
                               "--ticket", ticket)

    def test_code_and_create_pr_on_an_epic_agree(self):
        """Both exit 2, each naming its own verb -- the resolution itself."""
        epic = self.new_ticket("Checkout revamp", "epic")
        for skill in ("code", "create-pr"):
            with self.subTest(skill=skill):
                out = self.query(skill, epic)
                self.assertEqual(
                    out.returncode, 2,
                    "acs gate --skill %s exited %s on an epic; %s is in "
                    "_EPIC_VERBS, so the brake must be visible through the "
                    "query too\nstderr: %r"
                    % (skill, out.returncode, skill, out.stderr))
                self.assertIn("acs pre-%s: blocked" % skill, out.stderr)
                self.assertIn(refusal(EPIC_VERBS[skill]), out.stderr)
                self.assertEqual(json.loads(out.stdout),
                                 {"ok": False, "skill": skill, "exit_code": 2})

    def test_both_skills_are_rows_of_the_same_table(self):
        """The reason they cannot disagree: one table, not two gate functions."""
        self.assertIn("code", EPIC_VERBS)
        self.assertIn("create-pr", EPIC_VERBS)


class RecordedGoldensAgreeWithTheBrakeTest(unittest.TestCase):
    """The dataset half: no epic golden may expect a braked skill to open."""

    def setUp(self):
        with open(GATES_CASES, encoding="utf-8") as fh:
            self.doc = json.load(fh)
        self.cases = self.doc["cases"]

    def epic_gate_cases(self):
        """(case, skill) for every epic-profile `acs gate` case on a braked
        skill. Derived from `_EPIC_VERBS`, so adding a row to that table pulls
        its goldens into this assertion without editing this file."""
        for case in self.cases:
            if case.get("profile") != "epic":
                continue
            argv = (case.get("invoke") or {}).get("argv") or []
            if len(argv) < 3 or argv[0] != "gate" or argv[1] != "--skill":
                continue
            if argv[2] in EPIC_VERBS:
                yield case, argv[2]

    def test_every_epic_golden_for_a_braked_skill_expects_the_refusal(self):
        """GATE-044 expected exit 0 where GATE-042 required exit 2."""
        disagreeing = []
        for case, skill in self.epic_gate_cases():
            expect = case.get("expect") or {}
            needles = expect.get("stderr_contains") or []
            if expect.get("exit_code") != 2:
                disagreeing.append(
                    "%s: expects exit %r for --skill %s, but %s is in "
                    "_EPIC_VERBS and the brake refuses"
                    % (case["id"], expect.get("exit_code"), skill, skill))
            elif not any(refusal(EPIC_VERBS[skill]) in n for n in needles):
                disagreeing.append(
                    "%s: exits 2 but never names the epic refusal (%r)"
                    % (case["id"], refusal(EPIC_VERBS[skill])))
        self.assertEqual(
            disagreeing, [],
            "epic goldens that contradict the one epic brake: %s" % disagreeing)

    def test_both_contradicting_goldens_are_still_recorded(self):
        """The contradiction may not be resolved by deleting a case: the
        subject of both survives in v0.5.0 (AC-6)."""
        pinned = {skill: case["id"] for case, skill in self.epic_gate_cases()}
        self.assertEqual(sorted(pinned), ["code", "create-pr"],
                         "an epic gate golden for a braked skill went missing: "
                         "%s" % pinned)


if __name__ == "__main__":
    unittest.main()
