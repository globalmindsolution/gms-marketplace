"""MAR-71 (slice 1b of MAR-69) — /acs:code's reflection loop is execute ->
verify only. The skills-independence refactor completed what MAR-71 started:
the plan phase left this skill entirely for /acs:create-impl-plan, so the
one-planner-spawn-per-run and plan-section contracts now live in
tests/acs/test_create_impl_plan.py, and what is pinned here is the loop that
remains. Verifier findings on iteration 2+ route straight to the executor's
<context>, with no intervening planner spawn. Mid-flight escalation's
detection point and monotone-ceiling guarantee are unaffected and are pinned
here as regressions.

Every assertion is by file + substring/regex over whitespace-normalized text,
never by line number (line numbers drift as prose is revised). Stdlib-only
(os, re, unittest). Run:
  python3 -m unittest tests.acs.test_code_loop_topology -v
"""

import glob
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts"))

from acs_lib import workflow  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
IMPL_PLAN_PLANNER = os.path.join(PLUGIN, "agents", "create-impl-plan-executor.md")  # the plan charter lives in the executor's survey since ADR-0092
CODE_EXECUTOR = os.path.join(PLUGIN, "agents", "code-executor.md")


def _code_contract():
    """/acs:code's contract: the dispatcher, the four delivery-path legs, and
    the references they share.

    ADR-0095 split one 750-line body this way. These assertions pin what the
    SKILL SAYS, never which of its files says it, so reading the concatenation
    keeps the pin honest while the layout stays free to change -- and a rule
    that genuinely vanishes still fails.
    """
    import glob as _glob
    base = os.path.join(PLUGIN, "skills")
    parts = []
    for name in ("code", "code-trivial", "code-small", "code-standard", "code-complex"):
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            with io.open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    for path in sorted(_glob.glob(os.path.join(base, "code", "references", "*.md"))):
        with io.open(path, encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


def section(body, start_heading, end_heading):
    return body[body.index(start_heading):body.index(end_heading)]


class NoPlanPhaseInCodeTest(unittest.TestCase):
    """AC-1, after the carve-out: /acs:code spawns no planner and carries no
    plan phase at all. The "exactly one planner spawn per run" contract moved
    with the phase — see tests/acs/test_create_impl_plan.py::LaneForkTest."""

    @classmethod
    def setUpClass(cls):
        cls.body = _code_contract()
        cls.norm = norm(cls.body)

    def test_no_planner_spawn_remains(self):
        self.assertNotIn("acs:code-planner", self.body)

    def test_no_plan_section_heading_remains(self):
        self.assertNotIn("### Plan (per iteration)", self.body)
        self.assertNotRegex(self.body, r"(?m)^### Plan \(once[^)]*\)$")

    def test_no_unnegated_replan_instruction(self):
        # \b anchors the match to the word "re-plan"/"replan" itself, so the
        # ship.yaml edge name `on_replan` (an identifier, not an instruction)
        # is not read as one.
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)\bre-?plan\w*", self.body):
            window = self.body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(
                window, negating,
                "un-negated 're-plan' instruction found: %r" % window)


class FindingsRouteStraightToExecutorTest(unittest.TestCase):
    """AC-2: review findings on iteration 2+ go straight to the executor's
    <context>, with no intervening planner spawn.

    v0.5.0 moved the review itself out of /acs:code into /acs:review-code,
    so the findings now arrive as that step's verdict rather than from a
    verifier inside this skill. The routing property the AC pinned is
    unchanged and is what is asserted here."""

    def test_findings_feed_the_executor_context_with_no_planner_in_between(self):
        body_norm = norm(_code_contract())
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", body_norm):
            window = body_norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "code/SKILL.md must co-locate 'findings', 'executor', "
            "'<context>' and a no-planner clause within ~300 chars")

    def test_executor_input_contract_still_carries_iteration_2plus_findings(self):
        body_norm = norm(read(CODE_EXECUTOR))
        self.assertIn(
            "on iteration 2+ the review's confirmed findings assigned to you",
            body_norm)
        self.assertIn("<context>", body_norm)

    def test_planner_is_no_longer_promised_verifier_findings(self):
        body_norm = norm(read(IMPL_PLAN_PLANNER))
        self.assertNotRegex(
            body_norm, r"(?i)verifier findings from the previous iteration")
        self.assertNotIn("## Findings remediation", read(IMPL_PLAN_PLANNER))


class IterationCapCountsExecuteVerifyRoundsTest(unittest.TestCase):
    """An iteration is one execute -> verify round, not a plan+execute+verify
    triad, and each delivery path states its own cap.

    ADR-0095 replaced the verify-depth section this used to slice: there is no
    depth to compute and no table to look a ceiling up in.

    v0.5.0 finished the move. The review left /acs:code for /acs:review-code,
    so a leg has no verify phase of its own to cap, and the one ceiling that
    remains is the workflow loop's: ship.yaml's `loops[].max_iterations`,
    counting code -> review-code rounds. Each leg must SAY that rather than
    restate a number, because a per-leg number is a second copy of a cap the
    workflow already owns -- exactly the drift the per-path ceilings were
    introduced to avoid and then became."""

    LEGS = ("code-trivial", "code-small", "code-standard", "code-complex")

    def test_no_path_states_a_ceiling_of_its_own(self):
        for leg in self.LEGS:
            with self.subTest(leg=leg):
                body = read(os.path.join(PLUGIN, "skills", leg, "SKILL.md"))
                self.assertNotRegex(
                    norm(body), r"(?i)\*\*\d+\*\* execute -> verify rounds",
                    "%s must not restate a per-path iteration ceiling" % leg)

    def test_every_path_defers_the_ceiling_to_the_workflow_loop(self):
        for leg in self.LEGS:
            with self.subTest(leg=leg):
                body_norm = norm(read(os.path.join(PLUGIN, "skills", leg, "SKILL.md")))
                self.assertRegex(
                    body_norm,
                    r"(?i)iteration ceiling.{0,80}ship\.yaml.{0,40}max_iterations")
                self.assertRegex(body_norm, r"(?i)same cap on every path")

    def test_the_workflow_owns_exactly_one_such_ceiling(self):
        wf = workflow.validate_workflow_file(workflow.default_workflow_path())
        loops = [l for l in workflow.loops_of(wf) if l["back_to"] == "code"]
        self.assertEqual(len(loops), 1, loops)
        self.assertIsInstance(loops[0]["max_iterations"], int)

    def test_no_path_reintroduces_a_computed_depth(self):
        for leg in self.LEGS:
            body = read(os.path.join(PLUGIN, "skills", leg, "SKILL.md"))
            for token in ("verify_depth", "VERIFY_ITERATION_CAP", "derive_lane"):
                with self.subTest(leg=leg, symbol=token):
                    self.assertNotIn(token, body)

    def test_there_is_no_plan_phase_inside_an_iteration(self):
        contract_norm = norm(_code_contract())
        self.assertRegex(
            contract_norm,
            r"(?i)no planner runs between the review and the fix")
class ExecutorScopeEscapeHatchTest(unittest.TestCase):
    """AC-2 corollary: the executor's out-of-map escape hatch no longer
    promises a coordinator re-plan."""

    def test_out_of_map_escape_hatch_does_not_promise_a_replan(self):
        body_norm = norm(read(CODE_EXECUTOR))
        self.assertNotRegex(body_norm, r"(?i)coordinator\s+re-?plans")
        self.assertRegex(
            body_norm,
            r"(?i)coordinator.{0,60}(adjusts|updates).{0,40}(file map|scope)")


if __name__ == "__main__":
    unittest.main()
