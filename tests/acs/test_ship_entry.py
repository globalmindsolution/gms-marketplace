"""Contract tests for /acs:ship's entry contract and its ship.yaml-driven loop.

The skills-independence refactor made /acs:ship a thin loop over
`acs.py workflow next`: its entry is a ticket id and nothing else, the order
lives in `plugins/acs/workflows/ship.yaml`, and the two things the skill may
still decide for itself are the two REFUSALS -- a non-id argument and an epic.

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
    """A ticket id, and nothing else -- the `new request` path is gone."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.norm = norm(cls.body)

    def test_argument_hint_is_a_ticket_id_only(self):
        self.assertRegex(frontmatter(self.body),
                         r'(?m)^argument-hint: "<ticket-id>"$')

    def test_description_no_longer_promises_create_ticket_through_create_pr(self):
        fm = frontmatter(self.body)
        self.assertNotIn("create-ticket through create-pr", fm)
        self.assertIn("ship.yaml", fm,
                      "the description must say the pipeline is the declared one")

    def test_start_parses_a_single_ticket_id_token(self):
        start = section(self.body, "## Start")
        self.assertIn("[A-Z][A-Z0-9]*-[0-9]+", start,
                      "ship must recognise a ticket id by the same pattern "
                      "pipeline-state.schema.json uses")

    def test_no_new_request_path_survives(self):
        for token in ("new request", "new_request"):
            self.assertNotIn(token, self.norm,
                             "the prompt-as-argument path is removed: %r" % token)

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

    def test_ship_yaml_admits_no_design_phase_skill(self):
        """The prose claim above is the workflow's, not the skill's: ship.yaml
        may name build/test/ship skills only."""
        doc = lib.load_workflow(lib.default_workflow_path())[0]
        allowed = set(lib.allowed_ship_skills())
        for step in doc["steps"]:
            self.assertIn(step["skill"], allowed)
        self.assertNotIn("create-ticket", allowed)
        self.assertNotIn("create-design", allowed)


class RefusalPointerTest(unittest.TestCase):
    """The two refusals /acs:ship still owns, each with its pointer."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.norm = norm(cls.body)

    def test_non_id_argument_refusal_pointer(self):
        self.assertIn(
            "ship takes a ticket id; run `/acs:create-ticket \"<prompt>\"` "
            "(Design phase) and then `/acs:ship <id>`",
            self.norm,
            "a non-id argument must be refused with the create-ticket pointer")

    def test_epic_refusal_pointer_names_design_then_fan_out_then_ship(self):
        epic = section(self.body, "## Epic fan-out")
        self.assertIn("--fan-out", epic)
        self.assertIn("/acs:create-design", epic)
        self.assertIn("/acs:ship <child-id>", epic)
        self.assertIsNotNone(
            re.search(r"(?i)never shipped|refuse", norm(epic)),
            "the epic section must state that an epic is refused")

    def test_epic_refusal_is_the_walks_verdict_not_ships_own_guess(self):
        epic = norm(section(self.body, "## Epic fan-out"))
        self.assertIn("workflow next", epic)
        self.assertIn('"error": "epic"', epic)

    def test_prose_matches_the_pointer_workflow_next_actually_emits(self):
        """The skill surfaces `workflow next`'s epic pointer verbatim, so the
        two must name the same three commands."""
        source = read(os.path.join(PLUGIN, "hooks", "scripts", "acs_lib", "workflow.py"))
        pointer = re.search(r"(?s)is an epic — epics are never shipped.*?on each child\.", source)
        self.assertIsNotNone(pointer, "workflow.py must carry the epic pointer")
        pointer_text = norm(pointer.group(0))
        epic = norm(section(self.body, "## Epic fan-out"))
        for command in ("/acs:create-design", "/acs:create-ticket", "--fan-out", "/acs:ship"):
            self.assertIn(command, pointer_text, command)
            self.assertIn(command, epic, command)


class LoopDelegationTest(unittest.TestCase):
    """The order is read, never restated."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.loop = section(cls.body, "## The loop")

    def test_loop_invokes_the_cli(self):
        self.assertIsNotNone(
            re.search(r"acs\.py\"? workflow next --ticket", self.loop),
            "the loop must call `acs.py workflow next --ticket <ticket-id>`")
        self.assertIn("CLAUDE_PLUGIN_ROOT", self.loop,
                      "hooks/scripts is not on PATH: the fenced call must "
                      "resolve through CLAUDE_PLUGIN_ROOT")

    def test_loop_consumes_every_field_workflow_next_returns(self):
        for field in ("mode", "ready", "done", "blocked_by", "statuses", "workflow"):
            self.assertIn(field, self.loop, field)

    def test_both_modes_have_a_section(self):
        self.assertIn("## Single mode", self.body)
        self.assertIn("## Parallel mode", self.body)

    def test_parallel_mode_uses_a_worktree_and_branch_per_leg(self):
        parallel = section(self.body, "## Parallel mode")
        self.assertIn("git worktree add", parallel)
        self.assertIn("git worktree remove", parallel)
        self.assertIn("git merge", parallel)
        self.assertIsNotNone(
            re.search(r"(?i)conflict.{0,200}(STOPS|stop)", norm(parallel)),
            "a leg-merge conflict must stop the pipeline")
        self.assertIsNotNone(
            re.search(r"(?i)failed leg never cancels|failed leg.{0,200}ready again",
                      norm(parallel)),
            "a failed leg must leave its step ready again, not cancel its siblings")

    def test_parallel_mode_reuses_the_create_docs_fan_out_shape(self):
        parallel = norm(section(self.body, "## Parallel mode"))
        self.assertIn("create-docs", parallel,
                      "the fan-out mechanism is cited, not reinvented")

    def test_on_replan_and_on_fail_are_keyed_on_the_step_fields(self):
        self.assertIn("## Replan", self.body)
        self.assertIn("## Fix loop", self.body)
        replan = section(self.body, "## Replan")
        self.assertIn("plan_superseded", replan)
        self.assertIn("on_replan", replan)

    def test_never_merges(self):
        body = norm(self.body)
        self.assertIn("Never run /acs:merge-pr", body)
        self.assertIn("stop_after", body,
                      "the stop before merge is the workflow's stop_after, "
                      "not a hard-coded final step")


if __name__ == "__main__":
    unittest.main()
