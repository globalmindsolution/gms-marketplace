"""Contract tests for /acs:ship's entry contract and its cursor-driven loop.

v0.5.0 made /acs:ship a PURE ORCHESTRATOR over `acs.py run next`: the
workflow is a flat list with one loop and no predicates, so there is no
ready-set, no parallel mode and no skipping -- the cursor names one step, ship
runs it, and asks again.

Its entry widened with the run's subject (4.9): no argument resumes this
checkout's run, a ticket id / prompt / document names a subject, and `--run`
is the only form that names an id. The one refusal it still owns is the epic,
and the pointer it surfaces is the gate's own.

These are prose-contract checks over `plugins/acs/skills/ship/SKILL.md` (stdlib
re, the shape every other SKILL.md test in this package uses), cross-checked
against the live workflow so the prose cannot drift away from the mechanism it
describes. Run:
  python3 -m unittest tests.acs.test_ship_entry -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
import acs_lib as lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Whitespace-collapsed, with markdown blockquote markers dropped so a
    quoted refusal can wrap across lines like the rest of the prose."""
    return re.sub(r"\s+", " ", re.sub(r"(?m)^[ \t]*>[ \t]?", "", text))


def section(body, heading):
    """The text of a markdown section: from the line that starts with
    `heading` up to the next same-or-higher-level heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def frontmatter(body):
    m = re.match(r"(?s)^---\n(.*?)\n---\n", body)
    assert m is not None, "ship/SKILL.md must open with YAML frontmatter"
    return m.group(1)


class EntryContractTest(unittest.TestCase):
    """A SUBJECT, resolved the way `--continue` / `--resume` resolves one."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.norm = norm(cls.body)

    def test_argument_hint_names_the_subject_forms(self):
        """The entry is a SUBJECT (4.9), not a run id: no argument resumes
        this checkout's run, a ticket id / prompt / document names one, and
        `--run` is the only form that names an id."""
        hint = frontmatter(self.body)
        self.assertRegex(hint, r'(?m)^argument-hint: "\[.*\]"$')
        for form in ("ticket-id", "prompt", "document", "--run"):
            with self.subTest(form=form):
                self.assertIn(form, hint)

    def test_description_no_longer_promises_create_ticket_through_create_pr(self):
        fm = frontmatter(self.body)
        self.assertNotIn("create-ticket through create-pr", fm)
        self.assertIn("ship.yaml", fm,
                      "the description must say the pipeline is the declared one")

    def test_start_recognises_a_ticket_id_by_the_shared_pattern(self):
        start = section(self.body, "## Start")
        self.assertIn("[A-Z][A-Z0-9]*-[0-9]+", start,
                      "ship must recognise a ticket id by the same pattern "
                      "run.schema.json uses")

    def test_start_resolves_every_subject_form(self):
        start = norm(section(self.body, "## Start"))
        for form in ("the run this checkout is on", "a new run from that prompt",
                     "a new run from that document", "exactly that run"):
            with self.subTest(form=form):
                self.assertIn(form, start)

    def test_no_product_flow_refusal_survives(self):
        """`flow: ticket|product` is retired: a run has a SUBJECT, and the
        product skills are not steps of this workflow, so the cursor never
        offers one."""
        self.assertNotIn('"flow": "product"', self.body)
        self.assertIn("There is no `flow: product` refusal any more", self.body)

    def test_the_prompt_path_is_a_run_subject_not_a_ticket_shortcut(self):
        """A prompt starts a RUN over that prompt (4.2/4.9); it never mints a
        ticket behind the user's back."""
        self.assertIn("a new run from that prompt", self.norm)
        self.assertNotIn("new_request", self.norm)

    def test_create_ticket_is_not_one_of_ships_steps(self):
        """create-ticket is Design-phase work that runs before ship. It may be
        named as a POINTER (what to run first), never as a step ship runs."""
        self.assertNotIn("## Pipeline order", self.body)
        for line in self.body.splitlines():
            if "create-ticket" not in line:
                continue
            self.assertIsNotNone(
                re.search(r"/acs:create-ticket", line),
                "create-ticket may only appear as the /acs:create-ticket "
                "pointer, never as a bare step name: %r" % line)

    def test_ship_yaml_names_no_design_phase_skill(self):
        """The prose claim above is the workflow's, not the skill's.

        There is no allowed-skill ENUM any more: a step names a skill, a skill
        is a directory, and the schema checks shape. So the pin is membership
        in the list itself — the design and product skills are simply not
        steps, which is also what makes them independently invocable."""
        wf = lib.validate_workflow_file(lib.default_workflow_path())
        steps = lib.steps_of(wf)
        for retired in ("create-ticket", "create-design", "create-prd",
                        "create-architecture", "merge-pr", "release"):
            with self.subTest(skill=retired):
                self.assertNotIn(retired, steps)

    def test_no_step_is_an_internal_delivery_leg(self):
        """A leg is reached only through the plan's recorded delivery path, so
        naming one as a step would invite the hand pick ADR-0095 took away."""
        wf = lib.validate_workflow_file(lib.default_workflow_path())
        self.assertEqual(set(lib.steps_of(wf)) & set(lib.CODE_PATH_LEGS), set())


class RefusalPointerTest(unittest.TestCase):
    """The refusals /acs:ship still surfaces, each with its pointer."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.norm = norm(cls.body)

    def test_an_unresolvable_subject_asks_rather_than_guesses(self):
        start = norm(section(self.body, "## Start"))
        self.assertIn("ask the user what to ship rather than guessing", start)

    def test_epic_refusal_pointer_names_design_then_fan_out_then_ship(self):
        epic = section(self.body, "## Epic fan-out")
        self.assertIn("--fan-out", epic)
        self.assertIn("/acs:create-design", epic)
        self.assertIn("/acs:ship <child-id>", epic)
        self.assertIsNotNone(
            re.search(r"(?i)never shipped|refuse", norm(epic)),
            "the epic section must state that an epic is refused")

    def test_epic_refusal_is_the_gates_verdict_not_ships_own_guess(self):
        epic = norm(section(self.body, "## Epic fan-out"))
        self.assertIn("epic brake", epic)
        self.assertIn("verbatim", epic)

    def test_prose_matches_the_pointer_the_epic_brake_actually_emits(self):
        """The skill surfaces the brake's pointer verbatim, so the two must
        name the same three commands. The brake is `_refuse_epic`, which runs
        for EVERY implementation step now, not a `workflow next` verdict."""
        source = read(os.path.join(PLUGIN, "hooks", "scripts", "acs_lib",
                                   "gate_inputs.py"))
        pointer = re.search(r"(?s)is an epic — epics are never .*?on a child\.", source)
        self.assertIsNotNone(pointer, "gate_inputs.py must carry the epic pointer")
        pointer_text = norm(pointer.group(0))
        epic = norm(section(self.body, "## Epic fan-out"))
        for command in ("/acs:create-design", "/acs:create-ticket", "fan-out"):
            self.assertIn(command, pointer_text, command)
            self.assertIn(command, epic, command)
        self.assertIn("/acs:ship <child-id>", epic)


class LoopDelegationTest(unittest.TestCase):
    """The order is read, never restated."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.loop = section(cls.body, "## The loop")

    def test_loop_invokes_the_cli(self):
        self.assertIsNotNone(
            re.search(r"acs\.py\"? run next", self.loop),
            "the loop must call `acs.py run next`")
        self.assertIn("CLAUDE_PLUGIN_ROOT", self.loop,
                      "hooks/scripts is not on PATH: the fenced call must "
                      "resolve through CLAUDE_PLUGIN_ROOT")

    def test_loop_consumes_every_field_run_next_returns(self):
        for field in ("run_id", "next", "status", "done"):
            self.assertIn(field, self.loop, field)

    def test_there_is_no_mode_and_no_parallel_section(self):
        """A flat list with no `needs:` graph has no ready-set to fan out."""
        for heading in ("## Single mode", "## Parallel mode"):
            with self.subTest(heading=heading):
                self.assertNotIn(heading, self.body)
        self.assertNotIn("git worktree add", self.body)

    def test_the_cursor_offers_one_step(self):
        self.assertIsNotNone(
            re.search(r"(?i)there is one step at a time", norm(self.body)))
        self.assertIsNotNone(
            re.search(r"(?i)the first step that is not\s+`?completed`?",
                      norm(self.body)))

    def test_a_no_op_step_is_the_pre_hooks_call_not_ships(self):
        """2.2: a step owing nothing is completed by its own pre-hook from
        the plan's `## Contract` block. Silence is not permission to skip."""
        body = norm(self.body)
        self.assertIn("evidenced no-op", body)
        self.assertIn("Silence is not permission to skip", body)

    def test_never_merges(self):
        body = norm(self.body)
        self.assertIn("Never run /acs:merge-pr", body)
        self.assertIsNotNone(
            re.search(r"(?i)the list ends at `create-pr`", body),
            "the stop before merge is the workflow list's end, not a "
            "hard-coded final step")
        self.assertNotIn("stop_after", body)


if __name__ == "__main__":
    unittest.main()
