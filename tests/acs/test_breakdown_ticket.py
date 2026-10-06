"""ADR-0138 — /acs:breakdown-ticket breaks a ticket down; create-ticket no longer does.

The epic fan-out (MAR-78, `/acs:create-ticket <epic-id> --fan-out`) and the
oversized-ticket split (ADR-0069, `/acs:create-ticket split <id>`) were the same
operation behind two flags of a skill about making ONE ticket. ADR-0138 moved
both into /acs:breakdown-ticket, which absorbed `references/epic-fan-out.md`
and `references/split-ticket.md`. These pins are the MAR-78 and MAR-164 pins
of `test_epic_fan_out_mode.py`, moved to the skill that now says each thing:

- the breakdown's own contract (Start without --allocate, the mode by type,
  one confirmation before any child is minted, the design read and warned
  about but never a refusal, the plan's split seams, the conversion that
  keeps the id, the mint and criteria commands, the shared tracker sync, the
  Finish result document);
- create-ticket's half: the retired flags refuse with a pointer, a creation
  run mints no child, and the tracker-sync procedure is shared, not copied;
- behaviour through the real CLIs: a breakdown start allocates nothing, a
  split converts then mints under the same id, a child inherits the parent's
  features, and the post-hook closes the step.

Prose cases are section-scoped where a section exists; whole-contract reads
go through `skill_text.skill_contract` so a sentence that moves into a
reference keeps passing.

Run:
  python3 -m unittest tests.acs.test_breakdown_ticket -v
"""

import glob
import json
import os
import re
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")

sys.path.insert(0, TESTS_ACS)
sys.path.insert(0, HOOKS_DIR)

import acs_case  # noqa: E402
import acs_lib as lib  # noqa: E402
from skill_text import result_example, skill_contract  # noqa: E402

BREAKDOWN_SKILL = os.path.join(SKILLS_DIR, "breakdown-ticket", "SKILL.md")
CREATE_TICKET_SKILL = os.path.join(SKILLS_DIR, "create-ticket", "SKILL.md")
CT_REFERENCES = os.path.join(SKILLS_DIR, "create-ticket", "references")
MATERIALIZE_REF = os.path.join(CT_REFERENCES, "materialize.md")
TRACKER_SYNC_REF = os.path.join(CT_REFERENCES, "tracker-sync.md")
NEW_TICKET_PY = os.path.join(HOOKS_DIR, "new-ticket.py")

REPO_ID = "acme-shop"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse whitespace runs so a phrase can span a markdown line break."""
    return re.sub(r"\s+", " ", text)


def section(body, heading):
    """From `heading` up to the next heading of the same or a shallower level."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading not found: %r" % heading)
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    return body[m.start():m.end() + nxt.start() if nxt else len(body)]


def breakdown():
    return skill_contract("breakdown-ticket")


class BreakdownStartTest(unittest.TestCase):
    """The breakdown starts on the EXISTING ticket: its partition and id stay."""

    def test_start_names_the_step_and_the_ticket_and_never_allocates(self):
        start = section(read(BREAKDOWN_SKILL), "## Start")
        m = re.search(r"acs\.py\" step start[^\n`]*", start)
        self.assertIsNotNone(m, "Start must show the `acs step start` command")
        cmd = m.group(0)
        self.assertIn("--step breakdown-ticket", cmd)
        self.assertIn("--ticket", cmd)
        self.assertNotIn("--allocate", cmd)

    def test_a_missing_ticket_points_at_create_ticket(self):
        start = norm(section(read(BREAKDOWN_SKILL), "## Start"))
        self.assertRegex(start, r"(?i)no ticket id.{0,200}/acs:create-ticket")

    def test_the_mode_follows_the_parent_type(self):
        start = norm(section(read(BREAKDOWN_SKILL), "## Start"))
        self.assertRegex(start, r"`epic` → \*\*fan-out\*\*")
        self.assertRegex(start, r"`story` or `task` → \*\*split\*\*")
        self.assertRegex(start, r"(?i)epic keeping its id")
        self.assertRegex(start, r"(?i)not re-analyzed or rewritten")


class BreakdownConfirmationTest(unittest.TestCase):
    """MAR-78 AC-1's gate, kept: the children are confirmed ONCE, before any
    is minted, in one grouped interaction."""

    def test_no_child_is_minted_before_the_one_confirmation(self):
        gate = norm(section(read(BREAKDOWN_SKILL), "## The confirmation"))
        self.assertIn("ONE grouped interaction", gate)
        self.assertIn("no child is minted before the user confirms", gate)
        self.assertIn("never skipped", gate)

    def test_a_flagged_criterion_needs_the_users_word(self):
        gate = norm(section(read(BREAKDOWN_SKILL), "## The confirmation"))
        self.assertRegex(gate, r"(?i)flagged criterion is minted only once the user "
                               r"revised it or explicitly kept it")

    def test_an_up_front_confirmation_is_the_confirmation(self):
        gate = norm(section(read(BREAKDOWN_SKILL), "## The confirmation"))
        self.assertIn("A request that confirms up front IS the confirmation", gate)
        self.assertIn("--source assumption --rationale", gate)
        self.assertIn('status="needs_input"', gate)


class BreakdownInputsTest(unittest.TestCase):
    """The children come from documents another skill reviewed."""

    def test_reads_the_tech_design_and_its_legacy_name(self):
        inputs = norm(section(read(BREAKDOWN_SKILL), "## Inputs"))
        self.assertIn('artifacts["tech-design.md"]', inputs)
        self.assertIn("legacy `design.md`", inputs)
        self.assertIn("acs.py design check <path>", inputs)

    def test_an_unapproved_design_warns_and_never_blocks(self):
        inputs = norm(section(read(BREAKDOWN_SKILL), "## Inputs"))
        self.assertIn("warn, never block", inputs)
        self.assertIn("design_not_approved", inputs)

    def test_reads_the_plans_split_seams(self):
        """ADR-0069 lever 2: the plan's oversize signal is the split's evidence."""
        inputs = norm(section(read(BREAKDOWN_SKILL), "## Inputs"))
        self.assertIn('artifacts["plan.md"]', inputs)
        self.assertIn("split seams (ADR-0069)", inputs)

    def test_reads_the_feature_analysis(self):
        inputs = norm(section(read(BREAKDOWN_SKILL), "## Inputs"))
        self.assertIn("feature_analysis", inputs)
        self.assertIn("ADR-0133", inputs)

    def test_the_breakdown_derives_from_the_design_slices(self):
        """MAR-78 AC-5: the seams come from the design's own content."""
        derive = norm(section(read(BREAKDOWN_SKILL), "## Deriving the children"))
        self.assertIn("`## LLD` snapshots", derive)
        self.assertIn("### Rollout & migration", derive)
        self.assertRegex(derive, r"legacy `design\.md`.{0,80}`## Architecture`")

    def test_every_child_is_one_pr_and_covers_the_parent(self):
        derive = norm(section(read(BREAKDOWN_SKILL), "## Deriving the children"))
        self.assertIn("create-ticket/SKILL.md", derive)
        self.assertIn("The sizing rubric", derive)
        self.assertIn("coverage table", derive)
        self.assertIn("`needs_design` | `false`", derive)


class BreakdownMaterializeTest(unittest.TestCase):

    def setUp(self):
        self.mat = section(read(BREAKDOWN_SKILL), "## Materialize")
        self.norm = norm(self.mat)

    def test_a_split_converts_the_parent_before_minting(self):
        convert = self.mat.index('{"type": "epic", "needs_design": true')
        mint = self.mat.index('new-ticket.py" --title')
        self.assertLess(convert, mint, "the conversion must come before the first mint")
        self.assertIn("refuses a parent that is not an epic", self.norm)

    def test_the_mint_command_names_the_parent_and_no_design(self):
        m = re.search(r'new-ticket\.py" --title[^\n]*', self.mat)
        self.assertIsNotNone(m)
        self.assertIn("--parent", m.group(0))
        self.assertIn("--needs-design false", m.group(0))
        self.assertNotIn("--features", m.group(0), "features are inherited by default")
        self.assertIn("copies the parent's `features`", self.norm)

    def test_child_criteria_are_written_after_minting(self):
        """MAR-78 F2-b, moved: the criteria go through `acs.py ticket save`."""
        self.assertRegex(self.norm, r"acs\.py\W+ticket save --ticket <child-id>")
        self.assertIn("--acceptance-criteria", self.norm)
        self.assertRegex(self.norm, r"(?i)never in the repo")

    def test_resume_never_re_mints(self):
        self.assertIn("not already in the parent's `children`", self.norm)
        resume = norm(section(read(BREAKDOWN_SKILL), "## Resume & reconcile"))
        self.assertIn("Never re-mint a child the parent's `children` already lists", resume)

    def test_tracker_sync_is_shared_not_copied(self):
        self.assertIn("skills/create-ticket/references/tracker-sync.md", self.norm)
        self.assertFalse(os.path.exists(os.path.join(
            SKILLS_DIR, "breakdown-ticket", "references", "tracker-sync.md")),
            "breakdown-ticket points at create-ticket's tracker sync; it keeps no copy")

    def test_a_split_updates_the_parents_remote_issue(self):
        self.assertRegex(self.norm, r"(?i)on a split, the parent's remote issue is \*\*updated\*\*")


class BreakdownFinishTest(unittest.TestCase):

    def test_the_result_example_carries_exactly_the_declared_states(self):
        example = result_example(section(read(BREAKDOWN_SKILL), "## Finish"))
        self.assertIsNotNone(example)
        payload = json.loads(example)
        schema = json.loads(read(os.path.join(SKILLS_DIR, "breakdown-ticket",
                                              "state.schema.json")))
        self.assertEqual(set(payload["states"]),
                         set(schema["properties"]["states"]["properties"]))
        self.assertEqual(payload["states"]["type"], "epic")
        self.assertEqual(payload["states"]["converted_from"], "story")

    def test_the_post_hook_closes_the_step(self):
        self.assertIn('post-breakdown-ticket.py" --result-file',
                      section(read(BREAKDOWN_SKILL), "## Finish"))

    def test_it_spawns_no_subagent(self):
        self.assertNotRegex(read(BREAKDOWN_SKILL), r"acs:breakdown-ticket-[a-z]")
        self.assertEqual(glob.glob(os.path.join(PLUGIN, "agents", "breakdown-ticket-*.md")), [])


class CreateTicketRetiredModesTest(unittest.TestCase):
    """ADR-0138: the two flags refuse, naming /acs:breakdown-ticket, for one
    release; the references they read are gone."""

    def test_both_retired_modes_refuse_with_the_pointer(self):
        start = norm(section(read(CREATE_TICKET_SKILL), "## Start"))
        self.assertIn("**Retired modes — refuse BEFORE `step start`.**", start)
        self.assertIn("`--fan-out`", start)
        self.assertIn("split or restructure an existing ticket", start)
        self.assertIn("moved to `/acs:breakdown-ticket <id>`", start)
        self.assertIn("<next-step>/acs:breakdown-ticket <id></next-step>", start)

    def test_the_absorbed_references_are_gone(self):
        for name in ("epic-fan-out.md", "split-ticket.md"):
            self.assertFalse(os.path.exists(os.path.join(CT_REFERENCES, name)), name)

    def test_a_creation_run_mints_no_child(self):
        body = norm(read(CREATE_TICKET_SKILL))
        self.assertIn("Every creation run ends with `children: []`", body)
        step4 = norm(section(read(CREATE_TICKET_SKILL), "### Step 4"))
        self.assertIn("No creation run mints a child", step4)
        self.assertIn("/acs:breakdown-ticket <id>", step4)
        for path in (CREATE_TICKET_SKILL, MATERIALIZE_REF):
            self.assertNotRegex(read(path), r'new-ticket\.py" --title', path)
        mat = norm(read(MATERIALIZE_REF))
        self.assertIn("Minting an epic's children is `/acs:breakdown-ticket`'s", mat)

    def test_the_epic_path_names_design_then_breakdown(self):
        body = read(CREATE_TICKET_SKILL)
        report = norm(body[body.index("## Completion report (normative)"):])
        self.assertRegex(report, r"/acs:create-tech-design <id>` \(when `needs_design`\) → "
                                 r"`/acs:breakdown-ticket <id>`")
        finish = norm(section(read(CREATE_TICKET_SKILL), "## Finish"))
        summary = re.search(r"<summary>(.*?)</summary>", finish).group(1)
        self.assertIn("/acs:breakdown-ticket SHOP-123", summary)
        self.assertIsNone(re.search(r"children SHOP-\d+", summary))

    def test_the_finish_example_is_an_epic_with_no_children(self):
        payload = json.loads(result_example(section(read(CREATE_TICKET_SKILL), "## Finish")))
        self.assertEqual(payload["states"]["type"], "epic")
        self.assertEqual(payload["states"]["children"], [])


class SharedTrackerSyncTest(unittest.TestCase):
    """The one tracker-sync procedure both skills follow (MAR-69's duplicate
    guard, F2-a, kept)."""

    def test_it_names_both_skills(self):
        body = norm(read(TRACKER_SYNC_REF))
        self.assertIn("/acs:create-ticket", body)
        self.assertIn("/acs:breakdown-ticket", body)
        self.assertNotIn("--fan-out` run", body)

    def test_an_already_synced_ticket_is_excluded_in_both_files(self):
        for name, path in (("tracker-sync", TRACKER_SYNC_REF), ("materialize", MATERIALIZE_REF)):
            self.assertRegex(norm(read(path)),
                             r"(?i)exclud.{0,200}external.{0,120}non-null", name)


class NewTicketChildPipelineCommentNamesCodeTest(unittest.TestCase):
    """MAR-78 AC-4, kept: new-ticket.py carries no create-spec token and its
    child-pipeline comment names /acs:code."""

    def test_new_ticket_child_pipeline_comment_names_code(self):
        body = read(NEW_TICKET_PY)
        self.assertNotIn("create-spec", body)
        self.assertRegex(norm(body), r"(?i)pipeline starts at.{0,40}/acs:code")


class BreakdownStartOnAnExistingEpicCase(acs_case.AcsWorkspaceCase):
    """A breakdown start resolves the existing epic: no new id, no new partition."""

    def test_breakdown_start_allocates_no_new_id(self):
        epic = self.new_ticket("Wishlist epic", "epic")
        before = set((lib.read_json(lib.index_path(self.ws, REPO_ID)) or {}).get("tickets", {}))
        result = self.start("breakdown-ticket", epic)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["ticket_id"], epic)
        after = set((lib.read_json(lib.index_path(self.ws, REPO_ID)) or {}).get("tickets", {}))
        self.assertEqual(after, before)


class SplitConvertsThenMintsUnderTheSameIdCase(acs_case.AcsWorkspaceCase):
    """The split's order, through the real CLIs: `--parent` refuses a story,
    the `ticket save` conversion keeps the id, and the children then mint under
    it, inheriting its features."""

    def test_split_converts_then_mints_and_children_inherit_features(self):
        story = self.new_ticket("Order management", "story", "--features", "order-management")
        refused = self.run_script("new-ticket.py", "--title", "Refunds", "--type", "story",
                                  "--parent", story)
        self.assertEqual(refused.returncode, 2, "--parent must refuse a story")

        saved = self.run_script("acs.py", "ticket", "save", "--ticket", story, "--from", "-",
                                stdin=json.dumps({"type": "epic", "needs_design": True,
                                                  "title": "[EPIC] Order management"}))
        self.assertEqual(saved.returncode, 0, saved.stderr)

        minted = self.run_script("new-ticket.py", "--title", "Refunds", "--type", "story",
                                 "--parent", story, "--needs-design", "false")
        self.assertEqual(minted.returncode, 0, minted.stderr)
        child = json.loads(minted.stdout)["ticket_id"]

        parent = lib.read_json(os.path.join(self.tdir(story), "ticket.json"))
        self.assertEqual(parent["id"], story)
        self.assertEqual(parent["type"], "epic")
        self.assertEqual(parent["children"], [child])
        kid = lib.read_json(os.path.join(self.tdir(child), "ticket.json"))
        self.assertEqual(kid["parent"], story)
        self.assertEqual(kid.get("features"), ["order-management"])


class BreakdownRunLeavesItsStepCompletedCase(acs_case.AcsWorkspaceCase):
    """MAR-78's ledger rule, kept: the breakdown's own invocation ends
    `completed` through its post-hook, on the step machine (it is not a step
    of ship.yaml)."""

    def test_breakdown_run_leaves_its_step_completed(self):
        epic = self.new_ticket("Wishlist epic", "epic")
        start = self.start("breakdown-ticket", epic)
        self.assertEqual(start.returncode, 0, start.stderr)
        post = self.post("breakdown-ticket", epic, {
            "status": "completed",
            "summary": "breakdown run: no new children confirmed",
            "states": {"ticket_id": epic, "type": "epic", "converted_from": None,
                       "children": [], "minted": [], "design_status": None},
        })
        self.assertEqual(post.returncode, 0, post.stderr)
        rdir = self.rdir(epic)
        self.assertEqual(lib.last_status(rdir, "breakdown-ticket"), "completed")
        self.assertNotIn("breakdown-ticket", lib.load_run(rdir)["steps"])


class FannedOutChildNeverRunsCreateTicketCase(acs_case.AcsWorkspaceCase):
    """MAR-78 AC-3, kept: a child minted under a parent has no run of its own;
    its pipeline starts at /acs:code (or /acs:ship)."""

    def test_a_minted_child_has_no_run(self):
        epic = self.new_ticket("Wishlist epic", "epic")
        child = self.new_ticket("Wishlist API", "story", "--parent", epic,
                                "--needs-design", "false")
        self.assertTrue(os.path.isdir(self.tdir(child)))
        self.assertIsNone(lib.load_run(self.rdir(child)))
        self.assertIn("No run ledger is written here", read(NEW_TICKET_PY))


if __name__ == "__main__":
    unittest.main()
