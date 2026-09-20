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
import time
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "src", "acs", "hooks", "scripts")
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

    def test_create_architecture_requires_prd(self):
        result = self.pre("create-architecture")
        self.assertEqual(result.returncode, 2)
        self.assertIn("create-prd", result.stderr)

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
        os.path.join("src", "acs", "skills", "create-spec", "SKILL.md"),
        os.path.join("src", "acs", "agents", "create-spec-planner.md"),
        os.path.join("src", "acs", "agents", "create-spec-executor.md"),
        os.path.join("src", "acs", "agents", "create-spec-verifier.md"),
        os.path.join("src", "acs", "hooks", "scripts", "pre-create-spec.py"),
        os.path.join("src", "acs", "hooks", "scripts", "post-create-spec.py"),
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
            REPO_ROOT, "src", "acs", "schemas", "run.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("propertyNames", schema["properties"]["steps"])
        self.assertNotIn("create-spec", json.dumps(schema))

    def test_settings_schema_drops_spec_template_and_sections(self):
        schema_path = os.path.join(
            REPO_ROOT, "src", "acs", "schemas", "settings.schema.json")
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
            REPO_ROOT, "src", "acs", "schemas", "settings.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        overrides_enum = schema["properties"]["models"]["properties"]["overrides"][
            "propertyNames"]["enum"]
        self.assertEqual(sorted(overrides_enum), sorted(lib.HOOKED_SKILLS))
        for field in ("requirements_path", "e2e"):
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

    def test_blocks_without_architecture_gateerror_not_keyerror(self):
        for skill in self.PRODUCERS:
            with self.subTest(skill=skill):
                result = self.pre(skill)
                self.assertEqual(result.returncode, 2)
                self.assertIn("create-architecture", result.stderr)
                self.assertNotIn("KeyError", result.stderr)
                self.assertNotIn("unexpected error in gate", result.stderr)


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
            REPO_ROOT, "src", "acs", "schemas", "run.schema.json")
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


class TestStatusLines(AcsWorkspaceCase):
    def payload(self, cwd):
        return json.dumps({"model": {"display_name": "Opus"},
                           "workspace": {"current_dir": cwd}})

    def test_statusline_states(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        out = self.run_script("statusline.py", stdin=self.payload(plain), cwd=plain)
        self.assertEqual(out.returncode, 0)
        self.assertIn("plain", out.stdout)

        ticket = self.new_ticket("Fix rounding", "task")
        self.start("code", ticket)
        out = self.run_script("statusline.py", stdin=self.payload(self.repo))
        self.assertEqual(out.returncode, 0, out.stderr)
        for expected in (ticket, "code"):
            self.assertIn(expected, out.stdout)

    def test_subagent_statusline_rows(self):
        """The row names the RUN, and the skill/role vocabulary is read from
        the tree — a hard-coded list outlived two of its own entries."""
        ticket = self.new_ticket("X", "task")
        self.start("review-code", ticket)
        payload = json.dumps({"columns": 80, "tasks": [
            {"id": "a1", "type": "acs:review-code-lens", "status": "running",
             "startTime": (time.time() - 95) * 1000, "tokenCount": 45200, "cwd": self.repo},
            {"id": "a2", "type": "Explore", "description": "unrelated", "cwd": self.repo},
        ]})
        out = self.run_script("subagent-statusline.py", stdin=payload)
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [json.loads(line) for line in out.stdout.splitlines()]
        self.assertEqual([row["id"] for row in rows], ["a1"])  # non-acs row untouched
        self.assertIn(ticket, rows[0]["content"])
        self.assertIn("review-code-lens", rows[0]["content"])

    def test_a_retired_agent_name_no_longer_matches(self):
        """`code-verifier` left with the verifier (§3.5); a row for it is not
        an acs subagent row any more."""
        payload = json.dumps({"columns": 80, "tasks": [
            {"id": "a1", "type": "acs:code-verifier", "status": "running",
             "cwd": self.repo}]})
        out = self.run_script("subagent-statusline.py", stdin=payload)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "")

    def test_statusline_never_crashes(self):
        for bad in ("", "not json", '{"tasks": [{"id": "x", "type": 5}]}'):
            for script in ("statusline.py", "subagent-statusline.py"):
                out = self.run_script(script, stdin=bad)
                self.assertEqual(out.returncode, 0, (script, bad, out.stderr))


class ToolchainTests(unittest.TestCase):
    """check_toolchain backs /setup Step 0b — the full-workflow dependency preflight."""

    def test_reports_every_known_tool(self):
        names = [r["name"] for r in lib.check_toolchain()]
        self.assertEqual(set(names), {"git", "python3", "gh", "pre-commit", "xmllint", "acli"})

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
        self.assertNotIn("xmllint", missing)  # optional, never offered by default
        for name in missing:
            self.assertIn(name, {"gh", "pre-commit"})


# ---------------------------------------------------------------------------
# MAR-9 — pipeline-default CLAUDE.md guidance + exempt non-ticket merge-pr --pr
# ---------------------------------------------------------------------------

TEMPLATE_DIR = os.path.join(REPO_ROOT, "src", "acs", "templates")


class TestManagedBlock(unittest.TestCase):
    """Spec 01 — the pure CLAUDE.md managed-block helpers in acs_lib (no fixture
    needed; these are pure string functions)."""

    def test_fresh_write_appends_block_and_preserves_user_prose(self):
        # (a) Fresh write into surrounding user content.
        existing = "# My project\n\nSome user notes.\n"
        body = "Ship via /acs:ship."
        out = lib.upsert_managed_block(existing, body)
        self.assertIn(lib.ACS_BLOCK_BEGIN, out)
        self.assertIn(lib.ACS_BLOCK_END, out)
        self.assertIn(body, out)
        # the original user prose survives byte-for-byte as a prefix
        self.assertTrue(out.startswith(existing))
        # exactly one blank line separates prior content from the BEGIN marker
        before_marker = out.split(lib.ACS_BLOCK_BEGIN, 1)[0]
        self.assertTrue(before_marker.endswith("\n\n"))
        self.assertFalse(before_marker.endswith("\n\n\n"))

    def test_idempotent_rerun_byte_identical(self):
        # (b) AC-2 run-twice property.
        existing = "# My project\n\nSome user notes.\n"
        body = "Ship via /acs:ship."
        first = lib.upsert_managed_block(existing, body)
        second = lib.upsert_managed_block(first, body)
        self.assertEqual(first, second)

    def test_replace_changed_block_leaves_surrounding_bytes_intact(self):
        # (c) Replace with a changed block; only the marker span changes.
        prefix = "# Top\n\nintro prose\n"
        suffix = "\n\n## Footer\n\ntrailing user text\n"
        first = lib.upsert_managed_block(prefix, "label acs-exempt")
        # add user content AFTER the block, then re-upsert with a different body
        with_suffix = first + suffix
        replaced = lib.upsert_managed_block(with_suffix, "label custom-exempt")
        # surrounding content (before BEGIN and after END) is byte-identical
        self.assertEqual(replaced.split(lib.ACS_BLOCK_BEGIN, 1)[0],
                         with_suffix.split(lib.ACS_BLOCK_BEGIN, 1)[0])
        self.assertEqual(replaced.split(lib.ACS_BLOCK_END, 1)[1],
                         with_suffix.split(lib.ACS_BLOCK_END, 1)[1])
        # the new body replaced the old one inside the span
        self.assertIn("label custom-exempt", replaced)
        self.assertNotIn("label acs-exempt", replaced)

    def test_empty_existing_emits_just_block(self):
        out = lib.upsert_managed_block("", "body text")
        self.assertTrue(out.startswith(lib.ACS_BLOCK_BEGIN))
        self.assertIn("body text", out)

    def test_render_substitutes_both_placeholders(self):
        # (d) render_managed_block fills {ticket_prefix} + {exempt_label}.
        template = "prefix {ticket_prefix} and label {exempt_label} done"
        rendered = lib.render_managed_block(template, "SHOP", "acs-exempt")
        self.assertIn("SHOP", rendered)
        self.assertIn("acs-exempt", rendered)
        self.assertNotIn("{ticket_prefix}", rendered)
        self.assertNotIn("{exempt_label}", rendered)

    def test_template_exists_with_markers_and_placeholders(self):
        # (e) AC-1 — template file content assertion.
        path = os.path.join(TEMPLATE_DIR, "CLAUDE.acs.md")
        self.assertTrue(os.path.isfile(path), path)
        with open(path) as fh:
            text = fh.read()
        self.assertIn(lib.ACS_BLOCK_BEGIN, text)
        self.assertIn(lib.ACS_BLOCK_END, text)
        self.assertIn("{ticket_prefix}", text)
        self.assertIn("{exempt_label}", text)
        # guidance content: steer everyday work to /acs:ship and exempt PRs to --pr
        self.assertIn("/acs:ship", text)
        self.assertIn("/acs:merge-pr --pr", text)

    # -- MAR-70 regression: doubling / non-idempotency of the /acs:setup writer ----
    # The template ships a COMPLETE block (maintainer header + its own BEGIN/END);
    # the writer must inject only the inner body wrapped in exactly ONE marker pair.

    HEADER_MARKER = "CLAUDE.acs.md — acs managed block"

    def _template_text(self):
        with open(os.path.join(TEMPLATE_DIR, "CLAUDE.acs.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_managed_body_from_template_drops_header_and_markers(self):
        # The rendered body carries the guidance but NEITHER the maintainer header
        # NOR the template's own markers (the writer owns the markers).
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        self.assertIn("/acs:ship", body)
        self.assertIn("SHOP", body)
        self.assertIn("acs-exempt", body)
        self.assertNotIn(self.HEADER_MARKER, body)
        self.assertNotIn(lib.ACS_BLOCK_BEGIN, body)
        self.assertNotIn(lib.ACS_BLOCK_END, body)

    def test_ac1_fresh_write_single_pair_no_header(self):
        # AC-1: a fresh write from the real template yields EXACTLY one BEGIN/END
        # pair around the body only; the maintainer header is never injected.
        existing = "# My project\n\nSome user notes.\n"
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        out = lib.upsert_managed_block(existing, body)
        self.assertEqual(out.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(out.count(lib.ACS_BLOCK_END), 1)
        self.assertNotIn(self.HEADER_MARKER, out)
        self.assertIn("/acs:ship", out)
        self.assertTrue(out.startswith(existing))  # AC-4: prior content preserved

    def test_ac2_idempotent_double_run_from_template(self):
        # AC-2: running the writer twice is byte-identical (whole real-template path).
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        existing = "# My project\n\nSome user notes.\n"
        first = lib.upsert_managed_block(existing, body)
        second = lib.upsert_managed_block(first, body)
        self.assertEqual(first, second)
        self.assertEqual(second.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(second.count(lib.ACS_BLOCK_END), 1)

    def _legacy_doubled_file(self, prefix_user, suffix_user):
        """Reconstruct the pre-fix (buggy) artifact: the OLD writer wrapped the
        WHOLE substituted template (header + inner BEGIN/END) in a second marker
        pair, producing two BEGIN + two END with the header sandwiched between the
        outer and inner BEGIN."""
        whole_template = lib.render_managed_block(self._template_text(), "SHOP", "acs-exempt")
        doubled = "%s\n%s\n%s" % (lib.ACS_BLOCK_BEGIN, whole_template, lib.ACS_BLOCK_END)
        return prefix_user + doubled + suffix_user

    def test_ac3_self_heals_legacy_doubled_block(self):
        # AC-3 + AC-4: running the writer against an already-doubled/legacy block
        # collapses it to a single clean pair with no orphaned markers, and the
        # surrounding user content is preserved byte-for-byte.
        prefix_user = "# My project\n\nSome user notes.\n\n"
        suffix_user = "\n\n## More\n\ntrailing user text\n"
        legacy = self._legacy_doubled_file(prefix_user, suffix_user)
        # precondition: the fixture really is doubled
        self.assertEqual(legacy.count(lib.ACS_BLOCK_BEGIN), 2)
        self.assertEqual(legacy.count(lib.ACS_BLOCK_END), 2)

        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        healed = lib.upsert_managed_block(legacy, body)
        self.assertEqual(healed.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(healed.count(lib.ACS_BLOCK_END), 1)
        self.assertNotIn(self.HEADER_MARKER, healed)          # header no longer leaked
        self.assertTrue(healed.startswith(prefix_user))       # AC-4 surrounding bytes
        self.assertTrue(healed.endswith(suffix_user))         # AC-4 surrounding bytes
        # and the heal is itself idempotent thereafter
        self.assertEqual(lib.upsert_managed_block(healed, body), healed)

    def test_ac3_self_heal_no_orphaned_marker_via_old_find_bug(self):
        # Pin the specific non-idempotency root cause: a naive find(END) would match
        # the INNER end and leave the OUTER end orphaned after the block. rfind(END)
        # must consume the whole doubled span so the healed file is a single clean
        # block immediately followed by the untouched user suffix.
        legacy = self._legacy_doubled_file("intro\n\n", "\n\noutro\n")
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        healed = lib.upsert_managed_block(legacy, body)
        self.assertEqual(healed.count(lib.ACS_BLOCK_END), 1)
        # exactly one END, and the text after it is the user suffix — no orphan.
        self.assertEqual(healed.split(lib.ACS_BLOCK_END, 1)[1], "\n\noutro\n")

    def test_upsert_defensively_strips_body_that_carries_markers(self):
        # Even a buggy caller that passes a body already wrapped in markers (the
        # original defect) cannot cause doubling: the reducer strips them.
        body_with_markers = "%s\nguidance\n%s" % (lib.ACS_BLOCK_BEGIN, lib.ACS_BLOCK_END)
        out = lib.upsert_managed_block("", body_with_markers)
        self.assertEqual(out.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(out.count(lib.ACS_BLOCK_END), 1)
        self.assertIn("guidance", out)

    # -- MAR-74 (Deliverable 2): detect & self-heal a CLAUDE.md an earlier buggy
    # run corrupted (doubled markers, accumulated orphan END markers) and report
    # the repair. managed_block_is_malformed is the detector; upsert_managed_block
    # (rfind span + _strip_stray_markers) is the repair; both are idempotent. ----

    def _real_corrupted_file(self, prefix_user, suffix_user, n_orphan_end=1):
        """Reconstruct the artifact a buggy /acs:setup actually produced and then
        degraded: the WHOLE substituted template (maintainer header + its own
        inner BEGIN/END) wrapped in an OUTER marker pair, followed by N orphaned
        trailing END markers that accumulated on subsequent re-runs (the old
        find(END) matched the inner END, leaving each outer END orphaned)."""
        whole_template = lib.render_managed_block(self._template_text(), "SHOP", "acs-exempt")
        doubled = "%s\n%s\n%s" % (lib.ACS_BLOCK_BEGIN, whole_template, lib.ACS_BLOCK_END)
        orphans = ("\n" + lib.ACS_BLOCK_END) * n_orphan_end
        return prefix_user + doubled + orphans + suffix_user

    def test_managed_block_is_malformed_detector(self):
        # The detector: exactly one BEGIN and one END -> well-formed; anything else
        # (doubled, orphaned, or absent) -> malformed. True/false cases.
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        clean = lib.upsert_managed_block("# Repo\n\nnotes\n", body)
        self.assertFalse(lib.managed_block_is_malformed(clean))                          # 1/1 clean
        self.assertTrue(lib.managed_block_is_malformed(self._legacy_doubled_file("", ""))) # 2/2 doubled
        self.assertTrue(lib.managed_block_is_malformed(clean + "\n" + lib.ACS_BLOCK_END))  # 1/2 orphan END
        self.assertTrue(lib.managed_block_is_malformed(lib.ACS_BLOCK_BEGIN + "\nx\n"))     # lone BEGIN
        self.assertTrue(lib.managed_block_is_malformed("# Repo\n\njust user prose\n"))     # absent (0/0)

    def test_ac5_self_heal_doubled_plus_orphan_end_markers(self):
        # AC-5 (+ AC-6, AC-7): a doubled block PLUS several accumulated orphan END
        # markers collapses to exactly one clean pair with no orphan left behind,
        # surrounding user content is preserved byte-for-byte, and the heal is a
        # byte-identical no-op on the next run.
        prefix_user = "# My project\n\nintro\n\n"
        suffix_user = "\n\n## Footer\n\ntrailing\n"
        corrupt = self._real_corrupted_file(prefix_user, suffix_user, n_orphan_end=3)
        # precondition: genuinely corrupted (2 BEGIN; inner+outer+3 orphan = 5 END)
        self.assertTrue(lib.managed_block_is_malformed(corrupt))
        self.assertEqual(corrupt.count(lib.ACS_BLOCK_BEGIN), 2)
        self.assertEqual(corrupt.count(lib.ACS_BLOCK_END), 5)

        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        healed = lib.upsert_managed_block(corrupt, body)
        self.assertEqual(healed.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(healed.count(lib.ACS_BLOCK_END), 1)
        self.assertFalse(lib.managed_block_is_malformed(healed))
        self.assertNotIn(self.HEADER_MARKER, healed)                 # header no longer leaked
        self.assertTrue(healed.startswith(prefix_user))              # AC-6 user bytes before
        self.assertTrue(healed.endswith(suffix_user))                # AC-6 user bytes after
        self.assertEqual(lib.upsert_managed_block(healed, body), healed)  # AC-7 idempotent

    def test_heal_scrubs_orphan_marker_outside_the_span(self):
        # Belt-and-suspenders: a lone orphan END *before* the block and a lone
        # BEGIN *after* it fall outside [firstBEGIN..lastEND], so the rfind span
        # replacement alone would leave them. _strip_stray_markers scrubs them too,
        # so no orphan survives, while the user's actual text is preserved.
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        clean_block = "%s\n%s\n%s" % (lib.ACS_BLOCK_BEGIN, "old body", lib.ACS_BLOCK_END)
        existing = (lib.ACS_BLOCK_END + "\n\nuser-before\n\n"
                    + clean_block + "\n\nuser-after\n\n" + lib.ACS_BLOCK_BEGIN)
        self.assertTrue(lib.managed_block_is_malformed(existing))
        healed = lib.upsert_managed_block(existing, body)
        self.assertEqual(healed.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(healed.count(lib.ACS_BLOCK_END), 1)
        self.assertFalse(lib.managed_block_is_malformed(healed))
        self.assertIn("user-before", healed)
        self.assertIn("user-after", healed)
        self.assertEqual(lib.upsert_managed_block(healed, body), healed)  # idempotent

    def test_deliverable2_full_matrix(self):
        # One parametrized sweep over the whole fresh-write/heal matrix: every input
        # (absent, user-prose, already-clean, doubled, doubled+orphans) converges to
        # a single clean well-formed pair, never leaks the header, keeps the
        # guidance, and is a byte-identical no-op on the immediate re-run.
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        cases = [
            ("fresh_no_file", ""),
            ("fresh_user_prose", "# Repo\n\nuser notes\n"),
            ("already_clean", lib.upsert_managed_block("# Repo\n\nn\n", body)),
            ("doubled", self._legacy_doubled_file("# Repo\n\nA\n\n", "\n\nB\n")),
            ("doubled_plus_orphans", self._real_corrupted_file("# Repo\n\nA\n\n", "\n\nB\n", 2)),
        ]
        for name, existing in cases:
            with self.subTest(case=name):
                out = lib.upsert_managed_block(existing, body)
                self.assertEqual(out.count(lib.ACS_BLOCK_BEGIN), 1, name)
                self.assertEqual(out.count(lib.ACS_BLOCK_END), 1, name)
                self.assertFalse(lib.managed_block_is_malformed(out), name)
                self.assertNotIn(self.HEADER_MARKER, out)
                self.assertIn("/acs:ship", out)
                self.assertEqual(lib.upsert_managed_block(out, body), out, name)

    # -- MAR-104: every upsert_managed_block return path ends with exactly one
    # trailing newline, so /acs:setup Step 7e never writes a CLAUDE.md missing an
    # EOF newline (which trips pre-commit's end-of-file-fixer in consumer CI). --

    def _assert_single_trailing_newline(self, out):
        self.assertTrue(out.endswith("\n"))
        self.assertFalse(out.endswith("\n\n"))

    def test_mar104_empty_insert_ends_with_single_newline(self):
        # AC-1: fresh/empty-existing insert path (`return block`).
        out = lib.upsert_managed_block("", "body text")
        self._assert_single_trailing_newline(out)

    def test_mar104_append_after_content_ends_with_single_newline(self):
        # AC-1: append-after-content path (no existing markers).
        out = lib.upsert_managed_block("# Repo\n\nnotes\n", "body text")
        self._assert_single_trailing_newline(out)
        self.assertIn("body text", out)

    def test_mar104_replace_span_empty_after_ends_with_single_newline(self):
        # AC-1: replace-span path where `after` (text past END) is empty — the
        # path the pre-fix code left with no EOF newline at all.
        first = lib.upsert_managed_block("# Top\n\nintro\n", "b1")
        out = lib.upsert_managed_block(first, "b2")
        self._assert_single_trailing_newline(out)
        self.assertIn("b2", out)
        self.assertNotIn("b1", out)

    def test_mar104_self_heal_ends_with_single_newline(self):
        # AC-1: self-heal path with no user suffix after the last END.
        legacy = self._legacy_doubled_file("intro\n\n", "")
        body = lib.managed_body_from_template(self._template_text(), "SHOP", "acs-exempt")
        healed = lib.upsert_managed_block(legacy, body)
        self._assert_single_trailing_newline(healed)
        self.assertFalse(lib.managed_block_is_malformed(healed))

    def test_mar104_collapses_multiple_trailing_newlines_to_one(self):
        # AC-1 guard: exactly one trailing newline, never more, even when the
        # surrounding content would otherwise yield several.
        first = lib.upsert_managed_block("# Top\n\nintro\n", "b1")
        out = lib.upsert_managed_block(first + "\n\n\n", "b2")
        self._assert_single_trailing_newline(out)

    def test_mar104_newline_guarantee_is_idempotent(self):
        # AC-2: the newline normalization is a fixed point (rstrip + one "\n"),
        # so re-running the writer stays byte-identical.
        existing = "# My project\n\nSome user notes.\n"
        body = "Ship via /acs:ship."
        first = lib.upsert_managed_block(existing, body)
        second = lib.upsert_managed_block(first, body)
        self.assertEqual(first, second)
        self._assert_single_trailing_newline(second)

    def test_mar104_changelog_entry_present(self):
        # AC-4: durable-invariant CHANGELOG assertion — findable anywhere in the
        # file body, never pinned to the `[Unreleased]` heading (that pinned
        # style breaks at the next release cut).
        changelog_path = os.path.join(REPO_ROOT, "src", "acs", "CHANGELOG.md")
        with open(changelog_path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("(MAR-104)", body)

    def test_mar106_changelog_entry_present(self):
        # AC-7: durable-invariant CHANGELOG assertion — findable anywhere in
        # the file body, never pinned to [Unreleased] or a line window (the
        # anti-pattern that broke at the v0.3.5 and v0.3.6 release cuts).
        changelog_path = os.path.join(REPO_ROOT, "src", "acs", "CHANGELOG.md")
        with open(changelog_path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("(MAR-106)", body)


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

    SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "ticket.schema.json")

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
class TestQualityPathSettings(unittest.TestCase):
    """AC-2/AC-3 (MAR-112): quality_path settings key mirrors adr_path's
    oneOf string|null shape; DEFAULT_SETTINGS seeds it; load_settings resolves
    the default when absent; validate_settings accepts both a string and an
    explicit null without raising GateError.

    Uses the same stdlib-only approach as TestDueDateSchema/
    TestHighStakesPathsSettings (no jsonschema import).
    """

    SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "settings.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)

    def test_quality_path_in_schema(self):
        """settings.schema.json must define quality_path."""
        self.assertIn("quality_path", self.schema["properties"])

    def test_quality_path_oneof_mirrors_adr_path(self):
        """quality_path's oneOf must have exactly two branches: a non-empty
        string branch and a null branch — the same shape as adr_path, read
        live from the schema so the test tracks the real rule."""
        prop = self.schema["properties"]["quality_path"]
        branches = prop["oneOf"]
        self.assertEqual(len(branches), 2)
        self.assertIn({"type": "string", "minLength": 1}, branches)
        self.assertIn({"type": "null"}, branches)

    def test_quality_path_schema_default(self):
        """The schema's default for quality_path must be 'docs/quality'."""
        prop = self.schema["properties"]["quality_path"]
        self.assertEqual(prop.get("default"), "docs/quality")

    def test_default_settings_has_quality_path_seed(self):
        """DEFAULT_SETTINGS['quality_path'] must equal 'docs/quality'."""
        self.assertEqual(lib.DEFAULT_SETTINGS["quality_path"], "docs/quality")

    def test_load_settings_resolves_default_when_absent(self):
        """When quality_path is absent from every settings scope,
        load_settings must resolve it to the DEFAULT_SETTINGS seed."""
        tmp = tempfile.mkdtemp(prefix="acs-quality-path-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(repo, ".acs"))
        with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
            json.dump({"ticket_prefix": "SHOP"}, fh)
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["quality_path"], "docs/quality")

    def test_validate_settings_accepts_string_quality_path(self):
        """A settings dict with an explicit non-empty string quality_path
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "quality_path": "docs/quality"}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a string quality_path: %s" % exc)

    def test_validate_settings_accepts_null_quality_path(self):
        """A settings dict with quality_path explicitly set to null (disabled)
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "quality_path": None}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a null quality_path: %s" % exc)


class TestOperationsPathSettings(unittest.TestCase):
    """AC-2/AC-3 (MAR-113): operations_path settings key mirrors quality_path's
    oneOf string|null shape; DEFAULT_SETTINGS seeds it; load_settings resolves
    the default when absent; validate_settings accepts both a string and an
    explicit null without raising GateError.

    Uses the same stdlib-only approach as TestQualityPathSettings (no
    jsonschema import).
    """

    SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "settings.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)

    def test_operations_path_in_schema(self):
        """settings.schema.json must define operations_path."""
        self.assertIn("operations_path", self.schema["properties"])

    def test_operations_path_oneof_mirrors_quality_path(self):
        """operations_path's oneOf must have exactly two branches: a non-empty
        string branch and a null branch — the same shape as quality_path's/
        adr_path's existing branches, read live from the schema so the test
        tracks the real rule."""
        prop = self.schema["properties"]["operations_path"]
        branches = prop["oneOf"]
        self.assertEqual(len(branches), 2)
        self.assertIn({"type": "string", "minLength": 1}, branches)
        self.assertIn({"type": "null"}, branches)

    def test_operations_path_schema_default(self):
        """The schema's default for operations_path must be 'docs/operations'."""
        prop = self.schema["properties"]["operations_path"]
        self.assertEqual(prop.get("default"), "docs/operations")

    def test_default_settings_has_operations_path_seed(self):
        """DEFAULT_SETTINGS['operations_path'] must equal 'docs/operations'."""
        self.assertEqual(lib.DEFAULT_SETTINGS["operations_path"], "docs/operations")

    def test_load_settings_resolves_default_when_absent(self):
        """When operations_path is absent from every settings scope,
        load_settings must resolve it to the DEFAULT_SETTINGS seed."""
        tmp = tempfile.mkdtemp(prefix="acs-operations-path-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(repo, ".acs"))
        with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
            json.dump({"ticket_prefix": "SHOP"}, fh)
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["operations_path"], "docs/operations")

    def test_validate_settings_accepts_string_operations_path(self):
        """A settings dict with an explicit non-empty string operations_path
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "operations_path": "docs/operations"}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a string operations_path: %s" % exc)

    def test_validate_settings_accepts_null_operations_path(self):
        """A settings dict with operations_path explicitly set to null (disabled)
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "operations_path": None}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a null operations_path: %s" % exc)


class TestPrinciplesPathSettings(unittest.TestCase):
    """AC-5/AC-6 (MAR-117): principles_path settings key mirrors quality_path's/
    operations_path's oneOf string|null shape; DEFAULT_SETTINGS seeds it;
    load_settings resolves the default when absent; validate_settings accepts
    both a string and an explicit null without raising GateError.

    Uses the same stdlib-only approach as TestQualityPathSettings/
    TestOperationsPathSettings (no jsonschema import).
    """

    SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "settings.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)

    def test_principles_path_in_schema(self):
        """settings.schema.json must define principles_path."""
        self.assertIn("principles_path", self.schema["properties"])

    def test_principles_path_oneof_mirrors_quality_path(self):
        """principles_path's oneOf must have exactly two branches: a non-empty
        string branch and a null branch — the same shape as quality_path's/
        operations_path's existing branches, read live from the schema so the
        test tracks the real rule."""
        prop = self.schema["properties"]["principles_path"]
        branches = prop["oneOf"]
        self.assertEqual(len(branches), 2)
        self.assertIn({"type": "string", "minLength": 1}, branches)
        self.assertIn({"type": "null"}, branches)

    def test_principles_path_schema_default(self):
        """The schema's default for principles_path must be 'docs/principles'."""
        prop = self.schema["properties"]["principles_path"]
        self.assertEqual(prop.get("default"), "docs/principles")

    def test_default_settings_has_principles_path_seed(self):
        """DEFAULT_SETTINGS['principles_path'] must equal 'docs/principles'."""
        self.assertEqual(lib.DEFAULT_SETTINGS["principles_path"], "docs/principles")

    def test_load_settings_resolves_default_when_absent(self):
        """When principles_path is absent from every settings scope,
        load_settings must resolve it to the DEFAULT_SETTINGS seed."""
        tmp = tempfile.mkdtemp(prefix="acs-principles-path-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(repo, ".acs"))
        with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
            json.dump({"ticket_prefix": "SHOP"}, fh)
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["principles_path"], "docs/principles")

    def test_validate_settings_accepts_string_principles_path(self):
        """A settings dict with an explicit non-empty string principles_path
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "principles_path": "docs/principles"}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a string principles_path: %s" % exc)

    def test_validate_settings_accepts_null_principles_path(self):
        """A settings dict with principles_path explicitly set to null (disabled)
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "principles_path": None}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a null principles_path: %s" % exc)


class TestStandardsPathSettings(unittest.TestCase):
    """AC-5/AC-6 (MAR-118): standards_path settings key mirrors principles_path's
    oneOf string|null shape; DEFAULT_SETTINGS seeds it; load_settings resolves
    the default when absent; validate_settings accepts both a string and an
    explicit null without raising GateError.

    Uses the same stdlib-only approach as TestPrinciplesPathSettings (no
    jsonschema import).
    """

    SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "settings.schema.json")

    @classmethod
    def setUpClass(cls):
        with open(cls.SCHEMA_PATH) as fh:
            cls.schema = json.load(fh)

    def test_standards_path_in_schema(self):
        """settings.schema.json must define standards_path."""
        self.assertIn("standards_path", self.schema["properties"])

    def test_standards_path_oneof_mirrors_principles_path(self):
        """standards_path's oneOf must have exactly two branches: a non-empty
        string branch and a null branch — the same shape as principles_path's
        existing branches, read live from the schema so the test tracks the
        real rule."""
        prop = self.schema["properties"]["standards_path"]
        branches = prop["oneOf"]
        self.assertEqual(len(branches), 2)
        self.assertIn({"type": "string", "minLength": 1}, branches)
        self.assertIn({"type": "null"}, branches)

    def test_standards_path_schema_default(self):
        """The schema's default for standards_path must be 'docs/standards'."""
        prop = self.schema["properties"]["standards_path"]
        self.assertEqual(prop.get("default"), "docs/standards")

    def test_default_settings_has_standards_path_seed(self):
        """DEFAULT_SETTINGS['standards_path'] must equal 'docs/standards'."""
        self.assertEqual(lib.DEFAULT_SETTINGS["standards_path"], "docs/standards")

    def test_load_settings_resolves_default_when_absent(self):
        """When standards_path is absent from every settings scope,
        load_settings must resolve it to the DEFAULT_SETTINGS seed."""
        tmp = tempfile.mkdtemp(prefix="acs-standards-path-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(repo, ".acs"))
        with open(os.path.join(repo, ".acs", "settings.json"), "w") as fh:
            json.dump({"ticket_prefix": "SHOP"}, fh)
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["standards_path"], "docs/standards")

    def test_validate_settings_accepts_string_standards_path(self):
        """A settings dict with an explicit non-empty string standards_path
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "standards_path": "docs/standards"}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a string standards_path: %s" % exc)

    def test_validate_settings_accepts_null_standards_path(self):
        """A settings dict with standards_path explicitly set to null (disabled)
        passes validate_settings without raising GateError."""
        settings = {"test_coverage_percent": 90, "standards_path": None}
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must not reject a null standards_path: %s" % exc)
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
