"""The plugin's `claude plugin eval` suite, checked for free -- locally.

Nothing about the eval suite runs in CI (ADR-0022, ADR-0108): this module is
named `check_*.py` under tests/evals/ so `unittest discover -s tests` never
loads it. It runs from the `acs-eval-checks` pre-commit hook when a commit
touches the suite or a skill, and as the release gate's first step. Nothing
else catches a malformed case before someone pays to run it -- the CLI reports
an unknown frontmatter key, a bad grader type or a case that fails to load only
at run time. These tests read the case files as data
(tests/evals/eval_cases.py) and assert three things:

1. SHAPE -- every case and grader uses only the keys and values the reference
   (https://code.claude.com/docs/en/plugin-evals) documents.
2. COVERAGE -- every shipped skill carries a routing case, and no case names a
   skill that does not ship. This is the guard that, pointed at the old
   dataset, found `acs:test` probed after its deletion and `review-code` never
   probed at all.
3. GRADERS DO WHAT THEY SAY -- each routing grader's first-Skill-call pattern
   is run against traces shaped like the CLI's, so a regex that can never match
   (or that matches a neighbour, or a later Skill call) fails here rather than
   scoring 0.00 on a paid run for a probe that routed perfectly well.

Pure: no `claude`, no network, no cost.
"""

import json
import os
import re
import stat
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_ACS = HERE  # the strict case reader lives beside these checks
sys.path.insert(0, TESTS_ACS)
import eval_cases as ec  # noqa: E402

sys.path.insert(0, os.path.join(ec.PLUGIN, "hooks", "scripts"))
import acs_lib as lib  # noqa: E402  (the registry is the single source for legs)


def _trace(*skills, look_first=True):
    """A run's trace as the `trace` target shows it: compact JSON, one message
    per line, with the Skill calls in the order given (an optional look at the
    repo first, as a three-turn run may take)."""
    msgs = [{"type": "user", "message": {"content": "the prompt"}}]
    if look_first:
        msgs.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t0", "name": "Glob", "input": {"pattern": "**/*"}}]}})
    for i, name in enumerate(skills):
        msgs.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t%d" % (i + 1), "name": "Skill",
             "input": {"skill": name, "args": "TKT-1"}}]}})
    return "\n".join(json.dumps(m, separators=(",", ":")) for m in msgs)


def _internal_legs():
    """The legs an entry point dispatches: phases.yaml's `internal` map, read
    through the plugin's own registry rather than restated here, so a new leg
    cannot drift out of these guards. Not read off a `disable-model-invocation`
    flag: no skill sets one, because the CLI enforces it by refusing the Skill
    call, and every leg is dispatched by its entry point with a real
    `Skill(acs:<leg>)` call."""
    return set(lib.skill_legs())


class ShapeTest(unittest.TestCase):
    """Every case and grader is one the CLI will load."""

    def setUp(self):
        self.cases = ec.all_cases()

    def test_the_suite_is_not_empty(self):
        self.assertGreater(len(self.cases), 0, "no cases found under %s" % ec.EVALS)

    def test_every_case_has_a_prompt(self):
        for c in self.cases:
            with self.subTest(case=c.name):
                self.assertTrue(os.path.isfile(os.path.join(c.path, "prompt.md")),
                                "case has no prompt.md")
                self.assertTrue(c.prompt, "prompt.md has an empty body")

    def test_prompt_frontmatter_uses_only_documented_keys(self):
        for c in self.cases:
            with self.subTest(case=c.name):
                unknown = set(c.fm) - ec.PROMPT_KEYS
                self.assertEqual(unknown, set(),
                                 "the CLI rejects an unknown prompt.md key at run time")

    def test_case_yaml_is_versioned_and_named_for_its_directory(self):
        for c in self.cases:
            if c.case_yaml is None:
                continue
            with self.subTest(case=c.name):
                self.assertEqual(c.case_yaml.get("schema_version"), "1.1")
                self.assertEqual(c.case_yaml.get("name"), c.name,
                                 "--case globs match the name, and the report keys on it")

    def test_every_scaffold_exists_and_is_executable(self):
        for c in self.cases:
            script = ((c.case_yaml or {}).get("context") or {}).get("scaffold_script")
            if not script:
                continue
            with self.subTest(case=c.name):
                path = os.path.join(c.path, script)
                self.assertTrue(os.path.isfile(path), "scaffold_script names a missing file")
                self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR,
                                "scaffold_script is not executable")

    def test_every_case_has_a_grader(self):
        for c in self.cases:
            with self.subTest(case=c.name):
                self.assertTrue(c.graders, "a case with no grader scores nothing")

    def test_every_grader_is_a_documented_type_with_documented_keys(self):
        for c in self.cases:
            for g in c.graders:
                with self.subTest(case=c.name, grader=g.name):
                    self.assertIn(g.type, ec.GRADER_TYPE_KEYS)
                    allowed = ec.GRADER_COMMON_KEYS | ec.GRADER_TYPE_KEYS[g.type]
                    self.assertEqual(set(g.fm) - allowed, set())
                    if "arm" in g.fm:
                        self.assertIn(g.fm["arm"], ec.ARMS)

    def test_no_tool_used_grader_asserts_an_impossible_range(self):
        """`min` defaults to 1. A lone `max: 0` therefore asserts 1..0 -- a
        grader that can never pass, which reads as a plugin failure forever."""
        for c in self.cases:
            for g in c.graders:
                if g.type != "tool_used":
                    continue
                with self.subTest(case=c.name, grader=g.name):
                    lo, hi = g.fm.get("min", 1), g.fm.get("max")
                    if hi is not None:
                        self.assertLessEqual(lo, hi, "min %s > max %s" % (lo, hi))

    def test_every_regex_grader_compiles(self):
        """JavaScript and Python regex differ at the edges; the patterns here
        stay in the shared subset, and a pattern Python cannot compile is
        almost certainly broken in the CLI too."""
        for c in self.cases:
            for g in c.graders:
                pattern = g.fm.get("pattern") if g.type == "regex" else g.fm.get("input_match")
                if pattern is None:
                    continue
                with self.subTest(case=c.name, grader=g.name):
                    re.compile(pattern)


class RoutingShapeTest(unittest.TestCase):
    """The conventions that make a routing case's score its verdict."""

    def setUp(self):
        self.cases = ec.routing_cases()

    def test_every_routing_case_has_exactly_one_kind(self):
        for c in self.cases:
            with self.subTest(case=c.name):
                self.assertIsNotNone(
                    c.kind, "tag exactly one of %s beside `routing`" % (ec.ROUTING_KINDS,))

    def test_every_routing_case_has_exactly_one_grader(self):
        """One grader, so the case score IS the routing verdict: 1.00 or 0.00.
        A second grader would turn every wrong route into a 0.50."""
        for c in self.cases:
            with self.subTest(case=c.name):
                self.assertEqual(len(c.graders), 1)

    def test_routing_cases_grant_only_the_skill_tool(self):
        """Routing is decided from the prompt and the descriptions. A case that
        can Read the workspace first measures what it found, not the routing."""
        for c in self.cases:
            with self.subTest(case=c.name):
                self.assertEqual(c.fm.get("allowed_tools"), ["Skill"])

    def test_routing_runs_have_the_routing_turn_budget(self):
        """The ROUTE is graded, not the first move (ADR-0110): a run may look
        at the repo before routing, so it gets ec.ROUTING_TURNS turns, and the
        grader reads only the FIRST Skill call. Skills call skills -- /acs:ship
        invokes each step, /acs:code dispatches its leg -- and the first-call
        pattern cannot see those later calls, so extra turns cannot turn a
        misroute to ship into a pass or a correct route to code into a leg
        negative's failure. The CLI grades a run that stops at the limit: it
        passes `--max-turns` to the child and scores the trace whatever the
        exit status."""
        for c in self.cases:
            with self.subTest(case=c.name):
                self.assertEqual(c.fm.get("max_turns"), ec.ROUTING_TURNS)

    def test_every_probe_grades_the_first_skill_call(self):
        for c in ec.probe_cases():
            with self.subTest(case=c.name):
                g = c.routing_grader()
                self.assertEqual((g.type, g.fm.get("target")), ("regex", "trace"))
                self.assertEqual(g.fm.get("match", "contains"),
                                 "not_contains" if c.kind == "negative" else "contains")

    def test_every_probe_names_its_skill_in_the_canonical_form(self):
        for c in ec.probe_cases():
            with self.subTest(case=c.name):
                self.assertIsNotNone(c.skill, "no first-Skill-call grader naming a skill")

    def test_negatives_are_scored_in_both_arms(self):
        """The reference names `arm: both` for exactly this shape: a "must not
        invoke" check is a real assertion without the plugin too."""
        for c in self.cases:
            if c.kind not in ("negative", "control"):
                continue
            with self.subTest(case=c.name):
                g = c.graders[0]
                self.assertEqual(g.fm.get("arm"), "both")
                if c.kind == "control":
                    self.assertEqual((g.fm.get("min"), g.fm.get("max")), (0, 0))

    def test_the_kind_tag_agrees_with_the_grader(self):
        for c in ec.probe_cases():
            with self.subTest(case=c.name):
                self.assertEqual(c.must_route, c.kind in ("description", "explicit"))
                self.assertEqual(c.explicit, c.kind == "explicit" or (
                    c.kind == "negative" and c.explicit))

    def test_every_off_domain_control_counts_every_skill_call(self):
        """With no input_match the grader counts EVERY Skill call, which is the
        point: any skill firing on a poem, or on a git question answered in
        prose, is over-triggering. The poem alone proved little -- nothing in
        it resembles delivery work -- so the controls include requests that
        sit next to acs's vocabulary and must still route nowhere."""
        controls = [c for c in self.cases if c.kind == "control"]
        self.assertGreaterEqual(len(controls), 4)
        for c in controls:
            with self.subTest(case=c.name):
                g = c.graders[0]
                self.assertEqual(g.fm.get("tool"), "Skill")
                self.assertNotIn("input_match", g.fm)


class GraderMatchesTest(unittest.TestCase):
    """Each first-Skill-call pattern, run against traces shaped like the CLI's."""

    def rx(self, case):
        return re.compile(case.routing_grader().fm["pattern"])

    def test_each_grader_matches_its_own_skill_as_the_first_call(self):
        for c in ec.probe_cases():
            rx = self.rx(c)
            with self.subTest(case=c.name):
                self.assertRegex(_trace("acs:" + c.skill), rx)
                self.assertRegex(_trace(c.skill), rx)
                self.assertRegex(_trace("acs:" + c.skill, look_first=False), rx)
                self.assertRegex(_trace("acs:" + c.skill, "acs:create-ticket"), rx,
                                 "a later Skill call must not undo the route")

    def test_no_grader_matches_a_different_first_skill(self):
        """The closing quote keeps `code` from matching `code-small`, and the
        tempered token keeps a LATER call to the case's skill from counting:
        /acs:ship reaching a step, /acs:code dispatching a leg. Checked against
        every shipped skill, and against a built-in one."""
        shipped = ec.shipped_skills()
        for c in ec.probe_cases():
            rx = self.rx(c)
            for other in shipped + ["code-review"]:
                if other == c.skill:
                    continue
                with self.subTest(case=c.name, other=other):
                    self.assertIsNone(rx.search(_trace("acs:" + other)))
                    self.assertIsNone(rx.search(_trace("acs:" + other, "acs:" + c.skill)))

    def test_no_skill_call_matches_nothing(self):
        for c in ec.probe_cases():
            with self.subTest(case=c.name):
                self.assertIsNone(self.rx(c).search(_trace()))


class CoverageTest(unittest.TestCase):
    """Every shipped skill is probed, and the probes stay honest."""

    #: Skills added by the docs-set fold, which must expect themselves rather
    #: than the entry point that used to answer for them.
    NEW_CASES = {"create-docs", "create-requirements", "docs-sync"}

    #: Shipped skills with no routing case, each for a stated reason. Empty,
    #: and it should stay empty.
    UNPROBED = set()

    def test_every_shipped_skill_has_a_routing_case(self):
        probed = {c.skill for c in ec.probe_cases()}
        shipped = set(ec.shipped_skills())
        self.assertEqual(probed, shipped - self.UNPROBED)
        self.assertEqual(self.UNPROBED & shipped, self.UNPROBED,
                         "UNPROBED names a skill that no longer ships")

    def test_no_case_names_a_skill_that_is_not_shipped(self):
        """The failure this caught: a renamed skill leaves its old name asserted,
        and the case reads as a routing failure forever."""
        missing = sorted({c.skill for c in ec.probe_cases()} - set(ec.shipped_skills()))
        self.assertEqual(missing, [])

    def test_every_skill_carries_a_positive_case(self):
        """A negative alone proves only that nothing routes there."""
        positive = {c.skill for c in ec.probe_cases() if c.must_route}
        self.assertEqual(positive, set(ec.shipped_skills()) - self.UNPROBED)

    def test_only_the_internal_legs_are_probed_negatively(self):
        negative = {c.skill for c in ec.probe_cases() if c.kind == "negative"}
        self.assertEqual(negative, _internal_legs())

    def test_only_directly_typed_skills_are_probed_explicitly(self):
        """Two kinds earn an explicit case: the internal legs, which a user types
        to resume a run already judged onto that path, and the two user actions
        (`install-hooks`, `update`) that are commands rather than pipeline steps."""
        explicit = {c.skill for c in ec.probe_cases() if c.kind == "explicit"}
        self.assertEqual(explicit, _internal_legs() | {"install-hooks", "update"})

    #: Phrasings per skill with a description positive. One prompt per skill
    #: measures one sentence; ten measure the description. The release gate
    #: pools a skill's cases (ADR-0107) at ten runs each (ADR-0109), so a
    #: skill is judged on 100 runs.
    MIN_PHRASINGS = 10

    def _description_cases(self):
        by_skill = {}
        for c in ec.probe_cases():
            if c.kind == "description":
                by_skill.setdefault(c.skill, []).append(c)
        return by_skill

    def test_every_described_skill_has_several_phrasings(self):
        for skill, cases in sorted(self._description_cases().items()):
            with self.subTest(skill=skill):
                self.assertGreaterEqual(len(cases), self.MIN_PHRASINGS)
                prompts = [c.prompt for c in cases]
                self.assertEqual(len(set(prompts)), len(prompts), "duplicate prompt")

    def test_every_described_skill_has_a_confusable_phrasing(self):
        """A prompt that borrows a neighbour's vocabulary -- "merge" in a
        request to OPEN a PR, "design" in a request for the architecture set --
        is where routing actually fails. Every described skill carries one,
        tagged `confusable`, and its description names the neighbour it borrows
        from, which must be a skill that ships."""
        shipped = set(ec.shipped_skills())
        for skill, cases in sorted(self._description_cases().items()):
            confusable = [c for c in cases if "confusable" in c.tags]
            with self.subTest(skill=skill):
                self.assertTrue(confusable, "no confusable phrasing")
            for c in confusable:
                with self.subTest(case=c.name):
                    m = re.search(r"/acs:([a-z0-9-]+)", c.fm.get("description", ""))
                    self.assertIsNotNone(m, "the description must name the neighbour")
                    self.assertIn(m.group(1), shipped)
                    self.assertNotEqual(m.group(1), skill)

    def test_the_new_cases_expect_their_own_skill(self):
        positive = {c.skill for c in ec.probe_cases() if c.kind == "description"}
        for name in sorted(self.NEW_CASES):
            self.assertIn(name, positive)

    def test_description_prompts_do_not_name_their_own_skill(self):
        """Otherwise the case grades the prompt, not the description. Scoped to
        the probe's OWN skill, on word boundaries: "The code change is done"
        names no skill, but contains the word `code`.

        This used to guard only three hand-picked probes. Applied to all of
        them, it found route-release ending "open the release PR"."""
        for c in ec.probe_cases():
            if c.kind != "description":
                continue
            text = c.prompt.lower()
            for form in sorted({c.skill, c.skill.replace("-", " ")}):
                with self.subTest(case=c.name, form=form):
                    self.assertIsNone(re.search(r"\b%s\b" % re.escape(form), text))

    def test_every_explicit_prompt_is_exactly_its_command(self):
        for c in ec.probe_cases():
            if c.kind != "explicit":
                continue
            with self.subTest(case=c.name):
                self.assertEqual(c.prompt, "/acs:" + c.skill)


if __name__ == "__main__":
    unittest.main()
