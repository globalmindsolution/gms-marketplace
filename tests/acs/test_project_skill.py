"""/acs:project — the design-phase fold's unhooked umbrella over the two
project legs, and the legs' own internal-leg frontmatter.

Prose-contract tests in the same discipline as `test_create_docs_skill.py`:
whitespace-normalized substring/regex checks over the prose, never line-number
assertions. The umbrella owns no agents, no gate, no hook scripts and no
reflection loop of its own -- it states the mode `acs_lib.project_mode` chose,
with the evidence, and dispatches to `create-project` or `standardize-project`
by a genuine Skill-tool call so each leg's own hooks and gate fire unchanged.

Run:  python3 -m unittest tests.acs.test_project_skill -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
SKILL_PATH = os.path.join(SKILLS_DIR, "project", "SKILL.md")

sys.path.insert(0, HOOKS_DIR)
import acs_lib  # noqa: E402

#: The two internal legs /acs:project dispatches to, by mode.
LEGS = ("create-project", "standardize-project")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


def frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---\n", read(path), re.DOTALL)
    assert m, "%s must open with a front-matter block" % path
    return m.group(1)


class SkillDirectoryTest(unittest.TestCase):
    def test_the_skill_file_exists(self):
        self.assertTrue(os.path.isfile(SKILL_PATH), SKILL_PATH)

    def test_frontmatter_name_matches_the_directory(self):
        self.assertRegex(frontmatter(SKILL_PATH), r"(?m)^name: project$")

    def test_the_description_names_both_modes_and_neither_leg_as_the_entry(self):
        fm = frontmatter(SKILL_PATH)
        m = re.search(r"(?m)^description: (.+)$", fm)
        self.assertIsNotNone(m, "project/SKILL.md needs a description")
        description = m.group(1)
        self.assertRegex(description, r"(?i)greenfield")
        self.assertRegex(description, r"(?i)existing|brownfield")
        self.assertRegex(description, r"(?i)detect|auto-detect|chooses|decides")

    def test_the_umbrella_is_model_invocable(self):
        """The entry point stays routable; it is the LEGS that stop being
        user-facing, not the umbrella."""
        self.assertNotIn("disable-model-invocation", frontmatter(SKILL_PATH))


class UnhookedUmbrellaTest(unittest.TestCase):
    """The create-docs shape: no gate, no hook scripts, no agents, no
    skill-start.py, no reflection loop of its own."""

    def test_registered_in_unhooked_skills_only(self):
        self.assertIn("project", acs_lib.UNHOOKED_SKILLS)
        self.assertNotIn("project", acs_lib.HOOKED_SKILLS)
        self.assertNotIn("project", acs_lib.PRODUCT_SKILLS)
        self.assertNotIn("project", acs_lib.WORKFLOW_SKILLS)
        self.assertNotIn("project", acs_lib.PLANNING_SKILLS)

    def test_no_gate_is_registered(self):
        self.assertNotIn("project", acs_lib.GATES)
        self.assertNotIn("project", acs_lib.GATE_INPUTS)

    def test_no_pre_or_post_hook_script_on_disk(self):
        for name in ("pre-project.py", "post-project.py"):
            self.assertFalse(os.path.isfile(os.path.join(HOOKS_DIR, name)),
                             "%s must not exist -- project is unhooked" % name)

    def test_no_project_agent_files_on_disk(self):
        strays = [p for p in glob.glob(os.path.join(AGENTS_DIR, "project-*.md"))]
        self.assertEqual(strays, [], "no plugins/acs/agents/project-*.md -- no new triad")

    def test_no_skill_start_and_no_own_reflection_loop(self):
        body = read(SKILL_PATH)
        self.assertNotIn("skill-start.py", body,
                         "the umbrella allocates nothing -- each leg's own Start does")
        self.assertNotIn("--skill project", body)
        self.assertNotIn("project-planner", body)
        self.assertNotIn("project-executor", body)
        self.assertNotIn("project-verifier", body)
        self.assertNotRegex(norm(body), r"## Reflection loop")

    def test_it_names_itself_an_unhooked_umbrella_like_its_precedents(self):
        body_norm = norm(read(SKILL_PATH))
        self.assertRegex(body_norm, r"(?i)unhooked umbrella")
        self.assertIn("/acs:create-docs", body_norm)


class ModeDetectionIsDeclaredTest(unittest.TestCase):
    """The mode is `acs_lib.project_mode`'s answer, restated with its evidence
    -- never a prose heuristic the model re-derives per run."""

    def test_it_calls_project_mode_through_acs_lib(self):
        body = read(SKILL_PATH)
        self.assertIn("project_mode", body)
        self.assertIn("import acs_lib as lib", body)
        self.assertIn("lib.checkout_root", body)

    def test_it_states_the_mode_and_the_evidence_to_the_user(self):
        body_norm = norm(read(SKILL_PATH))
        self.assertRegex(body_norm, r"(?i)evidence")
        self.assertIn("bootstrap", body_norm)
        self.assertIn("standardize", body_norm)

    def test_it_never_re_derives_the_mode_in_prose(self):
        body = read(SKILL_PATH)
        self.assertIsNone(re.search(r"(?i)\bgit ls-files\b", body),
                          "mode detection is declared data, not a repo scan in this skill")
        self.assertRegex(norm(body), r"(?i)declared")

    def test_the_declared_tables_are_named_so_widening_is_a_data_change(self):
        body = read(SKILL_PATH)
        self.assertIn("PROJECT_MODE_SENTINEL", body)
        self.assertIn("PROJECT_MODE_SETTINGS_KEY", body)


class DispatchTest(unittest.TestCase):
    """Each leg is invoked as a genuine Skill-tool call, so its own pre/post
    hooks and gate fire exactly as they would standalone."""

    def test_both_legs_are_dispatched_as_skill_tool_calls(self):
        body_norm = norm(read(SKILL_PATH))
        for leg in LEGS:
            self.assertIn("Skill(acs:%s)" % leg, body_norm,
                          "%s must be dispatched as a real Skill-tool call" % leg)

    def test_the_hook_firing_guarantee_is_stated(self):
        body_norm = norm(read(SKILL_PATH))
        self.assertIn("PreToolUse(Skill)", body_norm)
        self.assertRegex(body_norm, r"(?i)never bypass, simulate, or duplicate")

    def test_exactly_one_leg_runs_per_invocation(self):
        body_norm = norm(read(SKILL_PATH))
        self.assertRegex(body_norm, r"(?i)exactly one leg|one leg, never both|never both legs")

    def test_the_completion_report_is_normative(self):
        self.assertIn("## Completion report (normative)", read(SKILL_PATH))


class InternalLegFrontmatterTest(unittest.TestCase):
    """Brief section 4, for the two project legs: each stays Skill-invocable
    with its body, agents, hooks and gate unchanged, but stops being
    user-facing -- model invocation off, description naming its entry point."""

    def test_each_leg_disables_model_invocation(self):
        for leg in LEGS:
            with self.subTest(leg=leg):
                fm = frontmatter(os.path.join(SKILLS_DIR, leg, "SKILL.md"))
                self.assertRegex(fm, r"(?m)^disable-model-invocation: true$")

    def test_each_leg_description_names_the_project_entry_point(self):
        for leg in LEGS:
            with self.subTest(leg=leg):
                fm = frontmatter(os.path.join(SKILLS_DIR, leg, "SKILL.md"))
                m = re.search(r"(?m)^description: (.+)$", fm)
                self.assertIsNotNone(m)
                description = m.group(1)
                self.assertIn("/acs:project", description,
                              "the description must point a reader at the entry point")
                self.assertRegex(description, r"(?i)internal leg")

    def test_each_leg_description_still_describes_the_work(self):
        """The routing evals read these: still a real description, not a stub."""
        expectations = {"create-project": r"(?i)scaffold",
                        "standardize-project": r"(?i)audit"}
        for leg in LEGS:
            with self.subTest(leg=leg):
                fm = frontmatter(os.path.join(SKILLS_DIR, leg, "SKILL.md"))
                description = re.search(r"(?m)^description: (.+)$", fm).group(1)
                self.assertGreater(len(description), 120, description)
                self.assertRegex(description, expectations[leg])

    def test_the_legs_keep_their_hooks_gate_agents_and_start(self):
        """The fold is an ENTRY-POINT fold: nothing else about a leg moves."""
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertIn(leg, acs_lib.HOOKED_SKILLS)
                self.assertIn(leg, acs_lib.GATES)
                self.assertTrue(os.path.isfile(os.path.join(HOOKS_DIR, "pre-%s.py" % leg)))
                self.assertTrue(os.path.isfile(os.path.join(HOOKS_DIR, "post-%s.py" % leg)))
                for role in ("planner", "executor", "verifier"):
                    self.assertTrue(
                        os.path.isfile(os.path.join(AGENTS_DIR, "%s-%s.md" % (leg, role))),
                        "%s-%s.md must survive the fold" % (leg, role))
                body = read(os.path.join(SKILLS_DIR, leg, "SKILL.md"))
                self.assertIn("skill-start.py", body)
                self.assertIn("--skill %s" % leg, body)

    def test_each_leg_is_registered_as_an_internal_leg_of_project(self):
        legs = acs_lib.skill_legs()
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertEqual(legs.get(leg), "project")
                self.assertEqual(acs_lib.entry_point_of(leg), "project")


class NextStepSurfacesNameTheEntryPointTest(unittest.TestCase):
    """The fold is only real if the surfaces that tell a user what to run next
    name the ENTRY POINT.

    `/acs:setup` and `/acs:create-architecture` both hand the user a next-step
    line, and on a greenfield repo both of them pointed at
    `/acs:create-project` -- which the fold made an internal leg whose entry
    point is `/acs:project`. `/acs:setup`'s line is not even prose: the wizard
    computes it (`setup_wizard.render_next_steps` / `PIPELINE_ORDER`) and
    `setup/SKILL.md` Step 5 says it reports that rather than re-deriving one,
    so the fix has to land in the wizard as well as in the two skills.

    The leg names come from the registry, never a literal list here.
    """

    NEXT_LINE = re.compile(r"(?m)^- \*\*Next\*\*:.*$")

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, HOOKS_DIR)
        import setup_wizard  # noqa: E402
        cls.wizard = setup_wizard
        cls.legs = sorted(acs_lib.skill_legs())

    def _routing_text(self, skill):
        """A skill's user-facing next-step surfaces: every `- **Next**:` line
        plus any arrow-joined pipeline chain in its prose."""
        body = read(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
        chunks = self.NEXT_LINE.findall(body)
        chunks += [line for line in body.splitlines() if "\u2192" in line and "/acs:" in line]
        chunks += [line for line in body.splitlines()
                   if "next step" in line.lower() and "/acs:" in line]
        return "\n".join(chunks)

    def test_the_wizard_pipeline_names_the_entry_point(self):
        self.assertIn("project", self.wizard.PIPELINE_ORDER)
        for leg in self.legs:
            with self.subTest(leg=leg):
                self.assertNotIn(leg, self.wizard.PIPELINE_ORDER)

    def test_the_wizard_next_steps_never_send_a_user_to_a_leg(self):
        for greenfield in (True, False):
            rendered = self.wizard.render_next_steps(greenfield)
            flat = "\n".join(rendered["first"] + rendered["pipeline"] + [rendered["then"]])
            for leg in self.legs:
                with self.subTest(greenfield=greenfield, leg=leg):
                    self.assertNotIn("/acs:%s" % leg, flat)
        self.assertIn("/acs:project", self.wizard.render_next_steps(True)["first"])

    def test_the_skills_that_route_onward_name_the_entry_point(self):
        for skill in ("setup", "create-architecture"):
            text = self._routing_text(skill)
            self.assertIn("/acs:project", text, skill)
            for leg in self.legs:
                with self.subTest(skill=skill, leg=leg):
                    self.assertNotIn("/acs:%s" % leg, text)


if __name__ == "__main__":
    unittest.main()
