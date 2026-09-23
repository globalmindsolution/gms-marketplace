"""Unit/integration tests for the acs plugin's deterministic layer.

Covers the hook library (acs_lib), the named pre/post hooks via the
dispatcher, the helper CLIs (skill-start, new-ticket, handoff, clarify,
validate_xml), and the status-line scripts — everything that gates and
persists the pipeline. Each test drives the real scripts in a throwaway
git repo + workspace, asserting on exit codes and the JSON state files
(the same artifacts the pipeline itself trusts).

Run:  python3 -m unittest discover -s tests -v
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402


sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


class TestDispatcher(AcsWorkspaceCase):
    def test_non_acs_skill_passes_through(self):
        payload = json.dumps({"cwd": self.repo, "tool_input": {"skill": "other:thing"}})
        result = self.run_script("dispatch.py", "pre", stdin=payload)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unhooked_acs_skills_pass_through(self):
        for skill in ("setup", "ship", "handoff", "metrics", "usage"):
            self.assertEqual(self.pre(skill).returncode, 0, skill)

    def test_garbage_stdin_does_not_crash(self):
        result = self.run_script("dispatch.py", "pre", stdin="not json")
        self.assertEqual(result.returncode, 0, result.stderr)


class TestGates(AcsWorkspaceCase):
    def test_uninitialized_repo_blocks_with_setup_message(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        subprocess.run(["git", "init", "-q", plain], check=True)
        result = self.pre("create-ticket", cwd=plain)
        self.assertEqual(result.returncode, 2)
        self.assertIn("setup", result.stderr)

    def test_the_prd_precondition_is_the_skills_not_the_hooks(self):
        """ADR-0102: no setting says where the PRD lives, so the hook cannot
        look for it. /acs:create-architecture finds it itself and stops."""
        result = self.pre("create-architecture")
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "skills", "create-architecture",
                               "SKILL.md"), encoding="utf-8") as fh:
            body = " ".join(fh.read().split())
        self.assertIn("no PRD found — run /acs:create-prd first", body)

    def test_code_requires_resolvable_ticket(self):
        result = self.pre("code")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ticket id", result.stderr)

    def test_unknown_placeholder_rejected(self):
        self.write_settings({"ticket_prefix": "SHOP",
                             "formats": {"branch_name": "{nope}/{ticket_id}"}})
        result = self.pre("create-ticket")
        self.assertEqual(result.returncode, 2)
        self.assertIn("placeholder", result.stderr)

    def test_pr_title_ticket_ref_placeholder_accepted(self):
        """MAR-80: {ticket_ref} is a valid pr_title-scoped placeholder (renders
        the tracker's native reference when synced, the local ticket id when
        not) -- validate_formats/FORMAT_PLACEHOLDERS must accept it in
        formats.pr_title."""
        self.write_settings({"ticket_prefix": "SHOP",
                             "formats": {"pr_title": "[{ticket_ref}] {title}"}})
        result = self.pre("create-ticket")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ticket_ref_rejected_in_branch_name(self):
        """Scope fence (AC-4): {ticket_ref} is pr_title-scoped only -- it must
        stay rejected in branch_name (and, by the same vocabulary table,
        commit_message)."""
        self.write_settings({"ticket_prefix": "SHOP",
                             "formats": {"branch_name": "{type}/{ticket_ref}-{slug}"}})
        result = self.pre("create-ticket")
        self.assertEqual(result.returncode, 2)
        self.assertIn("placeholder", result.stderr)

    def test_branch_name_must_embed_ticket_id(self):
        self.write_settings({"ticket_prefix": "SHOP",
                             "formats": {"branch_name": "{type}/{slug}"}})
        result = self.pre("create-ticket")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ticket_id", result.stderr)

    def test_e2e_settings_validation(self):
        self.write_settings({"ticket_prefix": "SHOP", "e2e": {"setup": "x"}})
        result = self.pre("create-ticket")
        self.assertEqual(result.returncode, 2)
        self.assertIn("e2e", result.stderr)
        self.write_settings({"ticket_prefix": "SHOP",
                             "e2e": {"command": "make e2e", "per_iteration": False}})
        self.assertEqual(self.pre("create-ticket").returncode, 0)

    def plan(self, ticket):
        """The one input gate_code has since the skills-independence refactor:
        a plan.md (create-impl-plan's artifact) in the ticket's docs folder
        or partition. Nothing about the run ledger is consulted."""
        with open(os.path.join(self.tdir(ticket), "plan.md"), "w") as fh:
            fh.write("# plan\n")

    def test_gate_code_never_requires_create_spec(self):
        # AC-4: gate_code no longer requires a completed create-spec step or a
        # non-empty specs/ directory -- given a plan it is a pass-through; no
        # predecessor run (create-ticket or otherwise) is checked, the order
        # lives in ship.yaml.
        #
        # This used to sweep the four size/stakes combinations that produced the
        # four lanes. ADR-0095 retired the axes, and the gate never branched on
        # them anyway: it is one gate for one step, and its four delivery-path
        # legs all run through it unchanged.
        cases = [("X", []), ("Y", []), ("Z", []), ("W", [])]
        for title, args in cases:
            with self.subTest(title=title):
                t = self.new_ticket(title, "task", *args)
                # No create-spec, no specs/ directory.
                self.plan(t)
                result = self.pre("code", t)
                self.assertEqual(result.returncode, 0, result.stderr)

        # Absent "lane" key (legacy ticket) also passes -- gate_code no longer
        # derives or inspects the lane at all.
        t = self.new_ticket("V", "task")
        self.plan(t)
        tdir = self.tdir(t)
        ticket_path = os.path.join(tdir, "ticket.json")
        with open(ticket_path) as fh:
            doc = json.load(fh)
        doc.pop("lane", None)
        with open(ticket_path, "w") as fh:
            json.dump(doc, fh)
        result = self.pre("code", t)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gate_code_pass_through_regardless_of_specs_presence(self):
        # AC-8 gate-level companion: gate_code's pass/fail is unaffected by
        # whether specs/ already has content -- the fold (self-author vs.
        # read-existing) is entirely the planner's concern now, never the
        # gate's. A pre-existing, non-empty specs/ must not change the
        # outcome versus the specs-absent case already proven above.
        t = self.new_ticket("HasSpecs", "task")
        self.plan(t)
        specs_dir = os.path.join(self.tdir(t), "specs")
        os.makedirs(specs_dir, exist_ok=True)
        with open(os.path.join(specs_dir, "01-existing.md"), "w") as fh:
            fh.write("# Scope\n\nExisting spec content.\n")
        result = self.pre("code", t)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestCreateSpecSurfaceDeleted(unittest.TestCase):
    """AC-1/AC-5: /acs:create-spec (skill, 3 agent files, both hook scripts, its
    GATES/WORKFLOW_SKILLS entries) no longer exists on disk or in acs_lib's
    registries; the run.json and settings.json schemas no longer
    carry its footprint."""

    DELETED_PATHS = [
        os.path.join("plugins", "acs", "skills", "create-spec", "SKILL.md"),
        os.path.join("plugins", "acs", "agents", "create-spec-planner.md"),
        os.path.join("plugins", "acs", "agents", "create-spec-executor.md"),
        os.path.join("plugins", "acs", "agents", "create-spec-verifier.md"),
        os.path.join("plugins", "acs", "hooks", "scripts", "pre-create-spec.py"),
        os.path.join("plugins", "acs", "hooks", "scripts", "post-create-spec.py"),
    ]

    def test_create_spec_absent_from_registries(self):
        self.assertNotIn("create-spec", lib.WORKFLOW_SKILLS)
        self.assertNotIn("create-spec", lib.registered_skills())

    def test_create_spec_paths_absent_from_disk(self):
        for rel in self.DELETED_PATHS:
            path = os.path.join(REPO_ROOT, rel)
            with self.subTest(path=rel):
                self.assertFalse(os.path.exists(path), "%s must not exist on disk" % path)

    def test_the_run_schema_names_no_skills_at_all(self):
        """The 18-name enum this used to filter create-spec out of is gone.
        `steps` is OPEN: step names validate against the resolved workflow and
        skill names against the skill directories, which is what makes a new
        workflow a YAML file and a new skill a directory (§4.3 I5)."""
        schema_path = os.path.join(
            REPO_ROOT, "plugins", "acs", "schemas", "run.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("propertyNames", schema["properties"]["steps"])
        self.assertNotIn("create-spec", json.dumps(schema))

    def test_settings_schema_drops_spec_template_and_sections(self):
        schema_path = os.path.join(
            REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("spec_template", schema["properties"]["formats"]["properties"])
        self.assertNotIn("spec_sections", schema["properties"]["enforcement"]["properties"])
        overrides_enum = schema["properties"]["models"]["properties"]["overrides"][
            "propertyNames"]["enum"]
        self.assertNotIn("create-spec", overrides_enum)

    def test_settings_schema_overrides_enum_tracks_hooked_skills(self):
        """The schema enum and acs_lib.HOOKED_SKILLS are two copies of one list.

        The schema half is hand-maintained, so nothing but this test notices
        when a skill is hooked (or unhooked) and only one copy is updated --
        which is the drift MAR-516 exists to close.
        """
        schema_path = os.path.join(
            REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        overrides_enum = schema["properties"]["models"]["properties"]["overrides"][
            "propertyNames"]["enum"]
        self.assertEqual(sorted(overrides_enum), sorted(lib.HOOKED_SKILLS))
        for field in ("e2e",):
            self.assertNotIn(
                "/create-spec", schema["properties"][field]["description"],
                "%s description must not reference the deleted /create-spec" % field)


class TestProducerDocSetGates(AcsWorkspaceCase):
    """MAR-122: the four doc-set producer skills (create-quality,
    create-operations, create-principles, create-standards) had no GATES
    entry, so run_pre's bare GATES[skill] subscript raised KeyError, caught
    by the fail-closed handler as exit 2 "unexpected error in gate" -- these
    drive the real dispatcher end-to-end and prove that failure mode is gone."""

    PRODUCERS = ("create-docs",)

    def test_passes_with_architecture_present(self):
        hld = os.path.join(self.repo, "docs", "architecture", "hld")
        os.makedirs(hld)
        with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
            fh.write("# tech stack")
        for skill in self.PRODUCERS:
            with self.subTest(skill=skill):
                result = self.pre(skill)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("KeyError", result.stderr)

    def test_without_architecture_the_skill_stops_not_the_hook(self):
        """ADR-0102: the architecture precondition moved into the skill, which
        can find a set wherever the repo keeps it; the hook passes."""
        for skill in self.PRODUCERS:
            with self.subTest(skill=skill):
                result = self.pre(skill)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("KeyError", result.stderr)
                with open(os.path.join(REPO_ROOT, "plugins", "acs", "skills", skill,
                                       "SKILL.md"), encoding="utf-8") as fh:
                    self.assertIn("run /acs:create-architecture first", " ".join(fh.read().split()))


class TestOrderAdvisoryAndPrBrake(AcsWorkspaceCase):
    """Order is `ship.yaml`'s, not a gate's: running a step before its
    neighbours prints ONE stderr advisory and exits 0 (§2.1, §5). The one thing
    that still REFUSES is the /acs:create-pr brake, and it reads the review's
    DERIVED verdict rather than any skill's self-report."""

    def _advisories(self, stderr):
        return [line for line in stderr.splitlines() if lib.ADVISORY_MARK in line]

    # ------------------------------------------------------------ the advisory

    def test_a_step_at_the_cursor_is_advised_of_nothing(self):
        ticket = self.new_ticket("Bulk import", "task")
        self.ensure_run(ticket)
        result = self.pre("analyze-requirements", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._advisories(result.stderr), [])

    def test_a_step_run_early_is_advised_once_and_still_runs(self):
        ticket = self.new_ticket("No code yet", "task")
        self.ensure_run(ticket)
        result = self.pre("docs-sync", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self._advisories(result.stderr),
            ["acs: docs-sync normally follows run-e2e-tests in ship.yaml; "
             "the cursor for %s is analyze-requirements" % ticket])

    def test_the_advisory_names_the_cursor_not_a_needs_list(self):
        """v2 named the step's unsatisfied `needs`. There are none now — the
        list IS the order — so the line names the one step the run waits on."""
        ticket = self.new_ticket("Half done", "task")
        self.walk_to(ticket, "create-impl-plan")
        result = self.pre("create-pr", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("the cursor for %s is create-api-contract" % ticket,
                      result.stderr)

    def test_the_advisory_can_be_switched_off(self):
        ticket = self.new_ticket("Quiet please", "task")
        self.ensure_run(ticket)
        settings = json.load(open(os.path.join(self.repo, ".acs", "settings.json")))
        settings["workflow"] = {"advisories": False}
        self.write_settings(settings)
        result = self.pre("docs-sync", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._advisories(result.stderr), [])

    # ------------------------------------------------------------ the pr brake

    def test_create_pr_is_refused_when_the_review_did_not_pass(self):
        """The one order-independent BRAKE: a review that found something
        never becomes a PR. `verifier_passed` is DERIVED from review-code's
        verdict, so writing `true` in a result document opens nothing."""
        ticket = self.new_ticket("Needs fixups", "task")
        self.walk_to(ticket, "create-test-docs")
        self.start("code", ticket)
        self.post("code", ticket, {"status": "completed",
                                   "states": {"verifier_passed": True}})
        self.start("review-code", ticket)
        self.seed_verdict(ticket, passed=False)
        self.post("review-code", ticket, {"status": "completed",
                                          "outcome": "blocking_findings"})
        result = self.pre("create-pr", ticket)
        self.assertEqual(result.returncode, 2)
        self.assertIn("verifier_passed", result.stderr)

    def test_create_pr_passes_quietly_after_a_passing_review(self):
        ticket = self.new_ticket("Bulk import", "task")
        self.walk_to(ticket, "docs-sync")
        result = self.pre("create-pr", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._advisories(result.stderr), [])

    def test_create_pr_is_not_braked_by_a_review_that_never_ran(self):
        """The brake reads the review STEP: a run that has not reviewed yet is
        out of order, which the advisory says — it is not a failed review."""
        ticket = self.new_ticket("No review yet", "task")
        self.walk_to(ticket, "code")
        result = self.pre("create-pr", ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self._advisories(result.stderr)), 1)

    # ---------------------------------------------------------------- registry

    def test_the_workflow_steps_are_hooked_skills(self):
        for step in ("code", "review-code", "docs-sync", "create-pr"):
            with self.subTest(step=step):
                self.assertIn(step, lib.HOOKED_SKILLS)

    def test_the_run_schema_constrains_shape_not_step_names(self):
        """The 18-name enum is gone: step names validate against the RESOLVED
        WORKFLOW, so a new workflow is a YAML file and touches no schema."""
        schema_path = os.path.join(
            REPO_ROOT, "plugins", "acs", "schemas", "run.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("enum", schema["properties"]["steps"].get("propertyNames", {}))


class TestConcurrencyAndRecovery(AcsWorkspaceCase):
    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("X", "task")
        self.start("code", self.ticket)

    def test_lock_blocks_other_checkout(self):
        other = os.path.join(self.tmp, "worktree-b")
        shutil.copytree(self.repo, other)
        result = self.pre("code", self.ticket, cwd=other)
        self.assertEqual(result.returncode, 2)
        self.assertIn("locked", result.stderr)

    def test_session_end_interrupts_the_step_and_counts_metrics(self):
        """`interrupted` is the one resumable state, and `session_end` is the
        stop_reason that says which kind of ending it was (§4.3)."""
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            before = json.load(fh).get("totals", {}).get("runs", 0)
        result = self.run_script("dispatch.py", "session-end",
                                 stdin=json.dumps({"cwd": self.repo}))
        self.assertEqual(result.returncode, 0, result.stderr)
        rdir = self.rdir(self.ticket)
        state = lib.load_step_state(rdir, "code", self.ticket)
        self.assertEqual(state["invocations"][-1]["status"], "interrupted")
        entry = lib.step_entry(lib.load_run(rdir), "code")
        self.assertEqual(entry["status"], "interrupted")
        self.assertEqual(entry["stop_reason"], "session_end")
        self.assertFalse(os.path.exists(os.path.join(rdir, ".lock")))
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            after = json.load(fh)["totals"]["runs"]
        self.assertEqual(after, before + 1)

    def test_handoff_and_resume(self):
        out = self.run_script("handoff.py", "--run", self.ticket,
                              "--summary", "done: analysis; next: task 02")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["continue_with"], "/acs:code %s" % self.ticket)
        self.assertEqual(body["stop_reason"], "context_pressure")
        rdir = self.rdir(self.ticket)
        state = lib.load_step_state(rdir, "code", self.ticket)
        self.assertEqual(state["invocations"][-1]["status"], "interrupted")
        self.assertIn("analysis", state["invocations"][-1]["handoff_summary"])
        resumed = json.loads(self.start("code", self.ticket).stdout)
        self.assertTrue(resumed["reconcile"])
        self.assertTrue(resumed["handoff_summary"])


class TestClarifications(AcsWorkspaceCase):
    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Bulk import", "story")

    def clarify(self, *args):
        return self.run_script("clarify.py", *args, "--ticket", self.ticket)

    def test_lifecycle(self):
        entry = json.loads(self.clarify(
            "add", "--skill", "create-ticket",
            "--question", "CSV and JSON?", "--answer", "CSV only").stdout)
        self.assertEqual((entry["id"], entry["status"]), ("C-1", "answered"))

        opened = json.loads(self.clarify(
            "add", "--skill", "create-design", "--question", "Duplicates?").stdout)
        self.assertEqual(opened["status"], "open")
        answered = json.loads(self.clarify(
            "answer", "--id", "C-2", "--answer", "reject with 409").stdout)
        self.assertEqual(answered["status"], "answered")

        # assumptions need both an answer and a rationale
        result = self.clarify("add", "--skill", "code", "--question", "Retries?",
                              "--source", "assumption")
        self.assertEqual(result.returncode, 2)
        assumed = json.loads(self.clarify(
            "add", "--skill", "code", "--question", "Retries?",
            "--source", "assumption", "--answer", "3",
            "--rationale", "matches retry.py:12").stdout)
        self.assertEqual(assumed["status"], "assumed")

        listing = json.loads(self.clarify("list").stdout)
        self.assertEqual(listing["count"], 3)
        self.assertEqual(json.loads(self.clarify("list", "--open").stdout)["count"], 0)


class TestNoStatusLine(unittest.TestCase):
    """ADR-0103: acs ships no status line -- and so no cost sampler, the only
    thing its payload fed."""

    def test_the_scripts_are_gone(self):
        for name in ("statusline.py", "subagent-statusline.py", "cost_sampler.py"):
            with self.subTest(script=name):
                self.assertFalse(os.path.exists(os.path.join(SCRIPTS, name)))


class ToolchainTests(unittest.TestCase):
    """check_toolchain backs /setup Step 0b — the full-workflow dependency preflight."""

    def test_reports_every_known_tool(self):
        names = [r["name"] for r in lib.check_toolchain()]
        self.assertEqual(set(names), {"git", "python3", "gh", "pre-commit", "acli"})

    def test_core_tools_present_and_required(self):
        rows = {r["name"]: r for r in lib.check_toolchain()}
        for name in ("git", "python3"):  # the test runner can't exist without these
            self.assertTrue(rows[name]["present"], name)
            self.assertEqual(rows[name]["kind"], "required", name)
            self.assertTrue(rows[name]["version"], "%s should report a version" % name)

    def test_tracker_bumps_conditional_tools_to_required(self):
        gh = {r["name"]: r for r in lib.check_toolchain({"tracker": {"provider": "github"}})}["gh"]
        self.assertEqual(gh["kind"], "required")
        acli = {r["name"]: r for r in lib.check_toolchain({"tracker": {"provider": "jira"}})}["acli"]
        self.assertEqual(acli["kind"], "required")
        # local tracker leaves them at their baseline kinds
        base = {r["name"]: r for r in lib.check_toolchain()}
        self.assertEqual(base["gh"]["kind"], "recommended")
        self.assertEqual(base["acli"]["kind"], "optional")

    def test_missing_tools_excludes_present_and_optional(self):
        missing = lib.missing_tools()  # required + recommended by default
        self.assertNotIn("git", missing)
        self.assertNotIn("python3", missing)
        self.assertNotIn("acli", missing)  # optional, never offered by default
        for name in missing:
            self.assertIn(name, {"gh", "pre-commit"})


# ---------------------------------------------------------------------------
# MAR-9 — pipeline-default CLAUDE.md guidance + exempt non-ticket merge-pr --pr
# ---------------------------------------------------------------------------

TEMPLATE_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "templates")


class TestBackfillDistinctPRCount(AcsWorkspaceCase):
    """AC-4: idempotent backfill of inflated prs.created."""

    def _write_create_pr_state(self, ws, repo_id, ticket_id, pr_number, archived=False):
        """Seed one run's create-pr step state. A ticket's PRs are its RUNS'
        PRs, and a ticket-subject run's id IS the ticket id (§4.2), which is
        what keeps the bridge a path join."""
        repo = os.path.join(ws, repo_id)
        rdir = (os.path.join(repo, "archive", ticket_id) if archived
                else lib.run_dir(repo, ticket_id))
        os.makedirs(rdir, exist_ok=True)
        lib.write_json(lib.state_path(rdir, "create-pr"), {
            "skill": "create-pr", "run_id": ticket_id, "invocations": [],
            "findings": [], "errors": [],
            "states": {"pr": {"number": pr_number,
                              "url": "https://example.com/pull/%d" % pr_number}},
        })
        return rdir

    def _seed_workspace(self):
        """Build a workspace with two ticket partitions (one active, one archived)
        and an inflated metrics.json (created=99).  Returns (ws, repo_id)."""
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        # tickets-index with two entries
        lib.write_json(lib.index_path(ws, repo_id), {
            "tickets": {
                "SHOP-1": {"id": "SHOP-1", "status": "done", "type": "story"},
                "SHOP-2": {"id": "SHOP-2", "status": "done", "type": "story"},
            }
        })
        # active partition: SHOP-1 → PR 7
        self._write_create_pr_state(ws, repo_id, "SHOP-1", pr_number=7, archived=False)
        # archived partition: SHOP-2 → PR 8
        self._write_create_pr_state(ws, repo_id, "SHOP-2", pr_number=8, archived=True)
        # inflated metrics
        lib.write_json(lib.metrics_path(ws, repo_id), {
            "prs": {"created": 99, "merged": 3, "created_pr_numbers": []},
            "tickets": {},
            "totals": {},
        })
        return ws, repo_id

    # AC-4: backfill heals inflated count
    def test_ac4_backfill_heals_inflated_count(self):
        ws, repo_id = self._seed_workspace()
        lib.backfill_distinct_pr_count(ws, repo_id)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 2)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7, 8])

    # AC-4: double run is idempotent (R1 mitigation)
    def test_ac4_backfill_idempotent_on_double_run(self):
        ws, repo_id = self._seed_workspace()
        lib.backfill_distinct_pr_count(ws, repo_id)
        lib.backfill_distinct_pr_count(ws, repo_id)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 2)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7, 8])

    # AC-4: backfill reads only metrics.json as a write (other files untouched)
    def test_ac4_backfill_writes_only_metrics_json(self):
        ws, repo_id = self._seed_workspace()
        # record mtimes before
        repo_dir = os.path.join(ws, repo_id)
        before = {}
        for fname in os.listdir(repo_dir):
            p = os.path.join(repo_dir, fname)
            if os.path.isfile(p):
                before[fname] = os.path.getmtime(p)
        # slight delay so mtime change is detectable
        import time as _time
        _time.sleep(0.05)

        lib.backfill_distinct_pr_count(ws, repo_id)

        after = {}
        for fname in os.listdir(repo_dir):
            p = os.path.join(repo_dir, fname)
            if os.path.isfile(p):
                after[fname] = os.path.getmtime(p)

        for fname, mtime in before.items():
            if fname == "metrics.json":
                continue  # this one IS allowed to change
            if fname in after:
                self.assertAlmostEqual(after[fname], mtime, places=1,
                                       msg="unexpected write to %s" % fname)

    # AC-4: ticket with no create-pr-state.json contributes 0 numbers
    def test_ac4_backfill_skips_ticket_with_no_state(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        # Only one ticket, no create-pr-state.json for it
        lib.write_json(lib.index_path(ws, repo_id), {
            "tickets": {"SHOP-1": {"id": "SHOP-1", "status": "done", "type": "story"}}
        })
        os.makedirs(os.path.join(ws, repo_id, "SHOP-1"), exist_ok=True)
        lib.write_json(lib.metrics_path(ws, repo_id), {
            "prs": {"created": 5, "merged": 0},
        })
        lib.backfill_distinct_pr_count(ws, repo_id)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 0)
        self.assertEqual(m["prs"]["created_pr_numbers"], [])

    # AC-4: ticket with states.pr.number=null is skipped gracefully
    def test_ac4_backfill_skips_null_pr_number(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {
            "tickets": {"SHOP-1": {"id": "SHOP-1", "status": "done", "type": "story"}}
        })
        tdir = os.path.join(ws, repo_id, "SHOP-1")
        os.makedirs(tdir, exist_ok=True)
        lib.write_json(lib.state_path(tdir, "create-pr"),
                       {"runs": [], "states": {"pr": {"number": None}}})
        lib.write_json(lib.metrics_path(ws, repo_id), {
            "prs": {"created": 5, "merged": 0},
        })
        lib.backfill_distinct_pr_count(ws, repo_id)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 0)
        self.assertEqual(m["prs"]["created_pr_numbers"], [])


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# MAR-15 spec 01 — due_date schema + write path
# ---------------------------------------------------------------------------

class TestDueDateSchema(unittest.TestCase):
    """AC-1: due_date is an optional, back-compatible addition to ticket.schema.json.

    The repo is stdlib-only (no third-party runtime/test deps), so instead of a
    full JSON-Schema validator these tests assert the specific contract the
    schema declares for due_date, reading the rule live from the schema file:
      - due_date is NOT in `required` (so an absent key conforms);
      - due_date is `oneOf [{type:string, pattern}, {type:null}]`, so null and a
        pattern-matching string conform while a non-matching string does not.
    The string-branch `pattern` is extracted from the loaded schema (not copied)
    and applied with `re.match`, so the tests track the real schema rule.
    """

    SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "ticket.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)
        due = cls.schema["properties"]["due_date"]
        branches = due["oneOf"]
        # Extract the string branch's pattern and confirm a null branch exists.
        cls.string_pattern = next(
            b["pattern"] for b in branches if b.get("type") == "string"
        )
        cls.allows_null = any(b.get("type") == "null" for b in branches)

    def _due_date_conforms(self, value, *, present=True):
        """Validate a candidate due_date against the schema's real contract.

        `present=False` models a ticket dict that omits the key entirely.
        """
        if not present:
            # Absent key conforms iff due_date is not required.
            return "due_date" not in self.schema["required"]
        if value is None:
            return self.allows_null
        if isinstance(value, str):
            return re.match(self.string_pattern, value) is not None
        return False

    def test_ticket_without_due_date_validates(self):
        """Absent due_date must remain schema-valid (back-compat)."""
        self.assertNotIn("due_date", self.schema["required"])
        self.assertTrue(self._due_date_conforms(None, present=False))

    def test_ticket_with_due_date_null_validates(self):
        """due_date: null must validate."""
        self.assertTrue(self._due_date_conforms(None))

    def test_ticket_with_valid_date_validates(self):
        """due_date: '2026-07-01' must validate."""
        self.assertTrue(self._due_date_conforms("2026-07-01"))

    def test_ticket_with_malformed_due_date_fails_validation(self):
        """due_date: 'not-a-date' must fail the schema's pattern rule."""
        self.assertFalse(self._due_date_conforms("not-a-date"))


class TestDueDateWritePath(AcsWorkspaceCase):
    """AC-2 + C-3: new-ticket.py --due-date sets ticket.json and tickets-index.json."""

    def test_due_date_written_to_ticket_json(self):
        """--due-date 2026-07-01 must appear in ticket.json.due_date."""
        ticket_id = self.new_ticket("T", "task", "--due-date", "2026-07-01")
        ticket = lib.load_ticket(self.tdir(ticket_id))
        self.assertEqual(ticket["due_date"], "2026-07-01")

    def test_due_date_propagated_to_index(self):
        """--due-date 2026-07-01 must propagate into tickets-index.json (C-3)."""
        ticket_id = self.new_ticket("T", "task", "--due-date", "2026-07-01")
        with open(lib.index_path(self.ws, "acme-shop")) as fh:
            index = __import__("json").load(fh)
        self.assertEqual(index["tickets"][ticket_id]["due_date"], "2026-07-01")

    def test_omitting_due_date_yields_null(self):
        """Omitting --due-date must write due_date: null in ticket.json."""
        ticket_id = self.new_ticket("T2", "task")
        ticket = lib.load_ticket(self.tdir(ticket_id))
        self.assertIsNone(ticket["due_date"])

    def test_malformed_due_date_rejected_non_zero_exit(self):
        """2026/07/01 (wrong separator) must exit non-zero with 'YYYY-MM-DD' in stderr."""
        result = self.run_script(
            "new-ticket.py", "--title", "T3", "--type", "task",
            "--due-date", "2026/07/01",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("YYYY-MM-DD", result.stderr)

    def test_datetime_string_rejected(self):
        """2026-07-01T00:00:00Z (datetime, not bare date) must exit non-zero."""
        result = self.run_script(
            "new-ticket.py", "--title", "T4", "--type", "task",
            "--due-date", "2026-07-01T00:00:00Z",
        )
        self.assertNotEqual(result.returncode, 0)
class TestRecordExternal(AcsWorkspaceCase):
    """MAR-84 spec 01: record-external.py — the deterministic write seam that
    stamps external={provider,key} into one ticket's ticket.json. Drives the
    real script as a subprocess via run_script, so os.getcwd()/build_context
    resolve against this fixture's throwaway repo (self.repo)."""

    def record(self, ticket_id, provider, key):
        return self.run_script("record-external.py", "--ticket", ticket_id,
                               "--provider", provider, "--key", key)

    def test_ac1_non_epic_task_gets_external_written(self):
        """AC-1 regression guard: a standard non-epic ticket ends up with
        external={provider,key} recorded via record-external.py."""
        t = self.new_ticket("Add health endpoint", "task")
        out = self.record(t, "github", "123")
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["ticket_id"], t)
        self.assertEqual(payload["external"], {"provider": "github", "key": "123"})
        ticket = lib.load_ticket(self.tdir(t))
        self.assertEqual(ticket["external"], {"provider": "github", "key": "123"})

    def test_ac6_fanout_children_all_written_parent_untouched(self):
        """AC-6: an epic + 2-3 children via --parent; invoke the helper once
        per child with distinct keys; every child ends non-null and matching,
        the parent epic's own ticket.json is untouched by those writes."""
        epic = self.new_ticket("Wishlist", "epic")
        children = [
            self.new_ticket("Wishlist API", "story", "--parent", epic,
                            "--needs-design", "false"),
            self.new_ticket("Wishlist UI", "story", "--parent", epic,
                            "--needs-design", "false"),
            self.new_ticket("Wishlist notifications", "task", "--parent", epic,
                            "--needs-design", "false"),
        ]
        epic_json = os.path.join(self.tdir(epic), "ticket.json")
        epic_stat_before = os.stat(epic_json)

        for i, child in enumerate(children):
            key = str(200 + i)
            out = self.record(child, "github", key)
            self.assertEqual(out.returncode, 0, out.stderr)
            ticket = lib.load_ticket(self.tdir(child))
            self.assertEqual(ticket["external"], {"provider": "github", "key": key})

        epic_after = lib.load_ticket(self.tdir(epic))
        self.assertIsNone(epic_after.get("external"),
                          "the parent epic's own external must stay untouched by "
                          "child-scoped writes (AC-6)")
        epic_stat_after = os.stat(epic_json)
        self.assertEqual(
            (epic_stat_after.st_mtime_ns, epic_stat_after.st_ino),
            (epic_stat_before.st_mtime_ns, epic_stat_before.st_ino),
            "writing a child's external must not touch the parent epic's ticket.json "
            "at all (AC-6); st_mtime_ns/st_ino detect a re-save that acs_lib.now_iso()'s "
            "second-resolution updated_at cannot (acs_lib/_common.py)")

    def test_ac4_product_flow_title_refused(self):
        """AC-4 defense-in-depth: a ticket titled exactly a PRODUCT_TICKET_TITLES
        value is refused by the helper itself — non-zero exit, external stays null."""
        t = self.new_ticket("Product definition (PRD)", "task")
        out = self.record(t, "github", "999")
        self.assertNotEqual(out.returncode, 0)
        self.assertTrue(out.stderr.strip(), "must print a clear stderr refusal")
        ticket = lib.load_ticket(self.tdir(t))
        self.assertIsNone(ticket.get("external"))

    def test_not_found_ticket_refused_with_clear_stderr(self):
        """Invoking against a nonexistent ticket id: non-zero exit + clear stderr,
        mirroring the new-ticket.py:78-82 not-found/archived idiom."""
        out = self.record("SHOP-9999", "github", "1")
        self.assertNotEqual(out.returncode, 0)
        self.assertTrue(out.stderr.strip())
        self.assertIn("SHOP-9999", out.stderr)
