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

    def test_gate_code_never_requires_create_spec_any_lane(self):
        # AC-4: gate_code no longer requires a completed create-spec step or a
        # non-empty specs/ directory, on ANY lane -- given a plan it is a
        # pass-through; no predecessor run (create-ticket or otherwise) is
        # checked, the order lives in ship.yaml.
        cases = [
            ("X", ["--size", "trivial", "--stakes", "low"]),
            ("Y", ["--size", "small", "--stakes", "normal"]),
            ("Z", []),  # default size=standard, stakes=normal -> STANDARD
            ("W", ["--size", "large"]),  # -> COMPLEX
        ]
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
    registries; the pipeline-state.json and settings.json schemas no longer
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
        self.assertNotIn("create-spec", lib.GATES)

    def test_create_spec_paths_absent_from_disk(self):
        for rel in self.DELETED_PATHS:
            path = os.path.join(REPO_ROOT, rel)
            with self.subTest(path=rel):
                self.assertFalse(os.path.exists(path), "%s must not exist on disk" % path)

    def test_pipeline_state_schema_drops_create_spec(self):
        schema_path = os.path.join(
            REPO_ROOT, "src", "acs", "schemas", "pipeline-state.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        enum = schema["properties"]["steps"]["propertyNames"]["enum"]
        self.assertNotIn("create-spec", enum)

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


class TestStandardizeProjectDelivery(AcsWorkspaceCase):
    """MAR-121 spec 01: standardize-project gate + delivery-ticket routing
    (allocate/in_review/pr_created/merge-pr), and the R1 non-reproduction proof."""

    def test_gate_blocks_without_architecture(self):
        result = self.pre("standardize-project")
        self.assertEqual(result.returncode, 2)
        self.assertIn("create-architecture", result.stderr)

    def test_gate_passes_and_does_not_reproduce_r1(self):
        hld = os.path.join(self.repo, "docs", "architecture", "hld")
        os.makedirs(hld)
        with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
            fh.write("# tech stack")
        result = self.pre("standardize-project")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("KeyError", result.stderr)

    def test_allocate_works_for_standardize_project(self):
        out = self.run_script("skill-start.py", "--skill", "standardize-project", "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        ticket_id = json.loads(out.stdout)["ticket_id"]
        ticket = lib.load_ticket(self.tdir(ticket_id))
        self.assertEqual(ticket["type"], "task")
        self.assertEqual(ticket["title"], lib.DELIVERY_TICKET_TITLES["standardize-project"])
        self.assertEqual(ticket["title"], "Brownfield project standardization")

    def test_allocate_rejected_for_a_non_delivery_skill(self):
        out = self.run_script("skill-start.py", "--skill", "code", "--allocate")
        self.assertEqual(out.returncode, 2)
        self.assertIn("only valid for", out.stderr)

    def test_post_flips_ticket_in_review(self):
        t = self.new_ticket("Audit", "task")
        self.start("standardize-project", t)
        self.post("standardize-project", t,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        ticket = lib.load_ticket(self.tdir(t))
        self.assertEqual(ticket["status"], "in_review")

    def test_post_bumps_pr_created_metric(self):
        t = self.new_ticket("Audit", "task")
        self.start("standardize-project", t)
        self.post("standardize-project", t,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            metrics = json.load(fh)
        self.assertEqual(metrics["prs"]["created"], 1)
        self.assertIn(1, metrics["prs"]["created_pr_numbers"])

    def test_merge_pr_finds_standardize_project_pr(self):
        t = self.new_ticket("Audit", "task")
        self.start("standardize-project", t)
        self.post("standardize-project", t,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        result = self.pre("merge-pr", args_text=t)
        self.assertEqual(result.returncode, 0, result.stderr)


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


class TestPipelineSequence(AcsWorkspaceCase):
    """The full gate chain: epic -> child -> design -> code -> pr -> merge.

    Since the skills-independence refactor the gates check INPUTS and BRAKES
    only: the order (code before docs-sync before create-pr) lives in
    workflows/ship.yaml and is advised on stderr, never refused."""

    def test_full_chain(self):
        out = self.run_script("skill-start.py", "--skill", "create-ticket",
                              "--allocate", "--type", "epic", "--title", "Wishlist")
        self.assertEqual(out.returncode, 0, out.stderr)
        epic = json.loads(out.stdout)["ticket_id"]
        self.assertEqual(epic, "SHOP-1")
        self.assertTrue(json.loads(out.stdout)["ticket"]["needs_design"])
        self.assertEqual(self.post("create-ticket", epic, {"status": "completed"}).returncode, 0)

        child = self.new_ticket("Wishlist API", "story", "--parent", epic,
                                "--needs-design", "false")
        epic_doc = lib.load_ticket(self.tdir(epic))
        self.assertIn(child, epic_doc["children"])

        # the child is not design-significant itself: create-design refuses it
        result = self.pre("create-design", child)
        self.assertEqual(result.returncode, 2)
        self.assertIn("needs_design", result.stderr)
        # gate_code's one input is a plan (create-impl-plan's artifact): no
        # create-spec/specs/ precondition, no design precondition, and no
        # predecessor-completed check -- run ahead of ship.yaml's order it
        # passes with an advisory line instead of a refusal.
        result = self.pre("code", child)
        self.assertEqual(result.returncode, 2)
        self.assertIn("/acs:create-impl-plan %s" % child, result.stderr)
        with open(os.path.join(self.tdir(child), "plan.md"), "w") as fh:
            fh.write("# plan")
        result = self.pre("code", child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("normally follows create-test-docs in ship.yaml", result.stderr)

        with open(os.path.join(self.tdir(epic), "design.md"), "w") as fh:
            fh.write("# design")
        self.start("create-design", epic)
        self.post("create-design", epic, {"status": "completed"})
        self.assertEqual(self.pre("code", child).returncode, 0)

        # create-pr's BRAKE: a code run whose verifier did not pass is refused
        self.start("code", child)
        self.post("code", child, {"status": "completed", "states": {"verifier_passed": False}})
        self.assertEqual(self.pre("create-pr", child).returncode, 2)
        self.start("code", child)
        # MAR-523: verifier_passed is DERIVED from the verifier's verdict, so
        # the fixture seeds the verdict instead of asserting the conclusion.
        self.seed_verdict(child)
        self.post("code", child, {"status": "completed"})
        # docs-sync is ship.yaml's concern, not create-pr's gate: without it
        # the gate passes and the advisory names the pending need
        result = self.pre("create-pr", child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs-sync has not completed for %s" % child, result.stderr)
        self.start("docs-sync", child)
        self.post("docs-sync", child, {"status": "completed"})
        result = self.pre("create-pr", child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("normally follows", result.stderr)

        # merge gate needs a PR reference
        self.assertEqual(self.pre("merge-pr", child).returncode, 2)
        self.start("create-pr", child)
        self.post("create-pr", child, {"status": "completed",
                                       "states": {"pr": {"number": 7, "url": "https://github.com/acme/shop/pull/7"}}})
        self.assertEqual(self.pre("merge-pr", child).returncode, 0)

        # merge: archive + epic auto-done
        self.start("merge-pr", child)
        out = self.post("merge-pr", child, {"status": "completed", "states": {"merged": True}})
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertIn(child, data["archived_to"])
        self.assertEqual(data["epic_marked_done"], epic)
        with open(lib.index_path(self.ws, "acme-shop")) as fh:
            index = json.load(fh)
        self.assertEqual(index["tickets"][child]["status"], "done")
        self.assertTrue(index["tickets"][child]["archived"])
        self.assertEqual(index["tickets"][epic]["status"], "done")

        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            metrics = json.load(fh)
        self.assertEqual(metrics["prs"], {"created": 1, "merged": 1, "created_pr_numbers": [7]})

    def test_docs_only_flag_minted(self):
        ticket = self.new_ticket("Fix README", "task", "--docs-only", "true")
        self.assertTrue(lib.load_ticket(self.tdir(ticket))["docs_only"])
        default = self.new_ticket("Real change", "task")
        self.assertFalse(lib.load_ticket(self.tdir(default))["docs_only"])

    def test_docs_only_relaxation_section_present_in_code_skill(self):
        """MAR-65 AC-6: 'docs_only' must appear in code/SKILL.md to anchor the
        docs_only relaxation section so it cannot be silently dropped."""
        import os
        plugin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src", "acs")
        skill_path = os.path.join(plugin, "skills", "code", "SKILL.md")
        with open(skill_path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("docs_only", body,
                      "code/SKILL.md must contain 'docs_only' (docs_only relaxation section "
                      "must not be silently dropped) (MAR-65 AC-6)")


class TestDocsSyncGates(AcsWorkspaceCase):
    """MAR-160 spec 02's gate_docs_sync (a)-(d) and gate_create_pr cases, as
    they read after the skills-independence refactor: the ORDER checks (code
    before docs-sync, the post-code test step, docs-sync before create-pr)
    are ship.yaml's and surface as one stderr advisory with exit 0; the
    verifier_passed BRAKE survives unchanged."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Bulk import", "task")
        self.start("code", self.ticket)
        # MAR-523: verifier_passed is DERIVED from the verifier's verdict, so
        # the fixture seeds the verdict instead of asserting the conclusion.
        self.seed_verdict(self.ticket)
        self.post("code", self.ticket, {"status": "completed"})

    # ---------------------------------------------------------------- gate_docs_sync

    def test_docs_sync_gate_passes_when_no_test_step_entry(self):
        # (a) code completed, no "test" step entry in pipeline-state.json -> 0
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_docs_sync_gate_passes_when_test_step_present_not_completed(self):
        # (b) code completed, "test" step present but not completed -> 0: the
        # post-code test step is not a docs-sync need in ship.yaml (docs-sync
        # needs only code), so nothing is refused and nothing is advised.
        lib.update_pipeline(self.tdir(self.ticket), self.ticket, "test", "in_progress")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("normally follows", result.stderr)

    def test_docs_sync_gate_passes_when_test_step_completed(self):
        # (c) code completed, "test" step present and completed -> 0
        lib.update_pipeline(self.tdir(self.ticket), self.ticket, "test", "completed")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_docs_sync_gate_passes_with_an_advisory_when_code_not_completed(self):
        # (d) code not completed -> 0 with ONE advisory line naming code
        other = self.new_ticket("No code yet", "task")
        result = self.pre("docs-sync", other)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [line for line in result.stderr.splitlines() if "normally follows" in line],
            ["acs: docs-sync normally follows code in ship.yaml; code has not completed for %s"
             % other])

    # ---------------------------------------------------------------- gate_create_pr

    def test_create_pr_gate_passes_with_an_advisory_when_docs_sync_not_completed(self):
        # (a) code verifier_passed true but docs-sync never run -> 0; the
        # advisory names docs-sync as the pending need
        result = self.pre("create-pr", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs-sync has not completed for %s" % self.ticket, result.stderr)

    def test_create_pr_gate_keeps_verifier_passed_check(self):
        # (b) docs-sync completed but the underlying code run's verifier_passed is
        # false -> 2, still names verifier_passed (the existing check survives)
        t = self.new_ticket("Needs fixups", "task")
        self.start("code", t)
        self.post("code", t, {"status": "completed", "states": {"verifier_passed": False}})
        self.start("docs-sync", t)
        self.post("docs-sync", t, {"status": "completed"})
        result = self.pre("create-pr", t)
        self.assertEqual(result.returncode, 2)
        self.assertIn("verifier_passed", result.stderr)

    def test_create_pr_gate_passes_quietly_in_order(self):
        self.start("docs-sync", self.ticket)
        self.post("docs-sync", self.ticket, {"status": "completed"})
        result = self.pre("create-pr", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("normally follows", result.stderr)

    # ---------------------------------------------------------------- registry

    def test_docs_sync_registered_in_workflow_skills_and_gates(self):
        self.assertIn("docs-sync", lib.WORKFLOW_SKILLS)
        self.assertIn("docs-sync", lib.GATES)

    def test_pipeline_state_schema_includes_docs_sync(self):
        schema_path = os.path.join(
            REPO_ROOT, "src", "acs", "schemas", "pipeline-state.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        enum = schema["properties"]["steps"]["propertyNames"]["enum"]
        self.assertIn("docs-sync", enum)


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

    def test_session_end_finalizes_interrupted_and_counts_metrics(self):
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            before = json.load(fh).get("totals", {}).get("runs", 0)
        result = self.run_script("dispatch.py", "session-end",
                                 stdin=json.dumps({"cwd": self.repo}))
        self.assertEqual(result.returncode, 0, result.stderr)
        state = lib.load_state(self.tdir(self.ticket), "code")
        self.assertEqual(state["runs"][-1]["status"], "interrupted")
        self.assertFalse(os.path.exists(os.path.join(self.tdir(self.ticket), ".lock")))
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            after = json.load(fh)["totals"]["runs"]
        self.assertEqual(after, before + 1)

    def test_handoff_and_resume(self):
        out = self.run_script("handoff.py", "--ticket", self.ticket,
                              "--summary", "done: analysis; next: spec 02")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["continue_with"],
                         "/acs:code %s" % self.ticket)
        state = lib.load_state(self.tdir(self.ticket), "code")
        self.assertEqual(state["runs"][-1]["status"], "handed_off")
        self.assertIn("analysis", state["runs"][-1]["handoff_summary"])
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


class TestValidators(AcsWorkspaceCase):
    def test_xml_valid_and_invalid(self):
        good = ('<task skill="code" phase="execute" ticket-id="SHOP-9">'
                '<objective>x</objective></task>')
        bad = ('<task skill="nope" phase="execute" ticket-id="9">'
               '<objective>x</objective></task>')
        self.assertEqual(self.run_script("validate_xml.py", "-", stdin=good).returncode, 0)
        result = self.run_script("validate_xml.py", "-", stdin=bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID", result.stderr)

    def test_xml_handoff_shape(self):
        good = ('<handoff skill="create-spec" ticket-id="SHOP-1" status="needs_input">'
                '<summary>s</summary><questions><question>q</question></questions></handoff>')
        self.assertEqual(self.run_script("validate_xml.py", "-", stdin=good).returncode, 0)

    # -----------------------------------------------------------------------
    # AC-2 Parity corpus (T1, keystone) — written FIRST per TDD discipline.
    # Every XSD violation class is represented; assertions are unconditional
    # (no xmllint on PATH required).  The xmllint parity leg is conditional.
    # -----------------------------------------------------------------------

    # Corpus fixture strings — valid messages (one per root element)
    VALID_TASK = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<objective>Implement feature X</objective>'
        '<inputs><file>/src/foo.py</file></inputs>'
        '<constraints><constraint name="coverage_target">90</constraint><constraint name="required_sections:hld/overview.md">Goals; Constraints</constraint></constraints>'
        '<context>background info</context>'
        '</task>'
    )
    VALID_RESULT = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<outputs><file>/src/foo.py</file></outputs>'
        '<findings><finding severity="info">all clear</finding></findings>'
        '<stop-reason>done</stop-reason>'
        '</result>'
    )
    VALID_HANDOFF = (
        '<handoff skill="create-spec" ticket-id="SHOP-1" status="needs_input">'
        '<summary>Summarised progress</summary>'
        '<questions><question>What priority?</question></questions>'
        '<next-step>resume after user answers</next-step>'
        '</handoff>'
    )

    # Corpus fixture strings — malformed messages (one per XSD violation class)
    # (i) bad root element — root not in {task, result, handoff}
    MALFORMED_BAD_ROOT = '<foo skill="code" phase="execute" ticket-id="SHOP-1"/>'

    # (ii) missing required attribute — missing 'skill'
    MALFORMED_MISSING_SKILL = (
        '<task phase="execute" ticket-id="SHOP-1">'
        '<objective>obj</objective>'
        '</task>'
    )

    # (ii) invalid attribute value — skill not in enum
    MALFORMED_INVALID_SKILL = (
        '<task skill="nope" phase="execute" ticket-id="SHOP-1">'
        '<objective>obj</objective>'
        '</task>'
    )

    # (ii) bad ticket-id pattern — must match [A-Z][A-Z0-9]*-[0-9]+
    MALFORMED_BAD_TICKET_ID = (
        '<task skill="code" phase="execute" ticket-id="123">'
        '<objective>obj</objective>'
        '</task>'
    )

    # (iii) out-of-order children — constraints before objective in task
    MALFORMED_OUT_OF_ORDER = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<constraints><constraint name="coverage_target">90</constraint></constraints>'
        '<objective>obj</objective>'
        '</task>'
    )

    # (iv) wrong list item — <bar/> inside <inputs> instead of <file>
    MALFORMED_WRONG_LIST_ITEM = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<objective>obj</objective>'
        '<inputs><bar/></inputs>'
        '</task>'
    )

    # (v) bad enum — status not in {completed, failed, needs_input}
    MALFORMED_BAD_STATUS_ENUM = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="bad_status"/>'
    )

    # (v) bad enum — severity not in {blocking, info}
    MALFORMED_BAD_SEVERITY_ENUM = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<findings><finding severity="critical">something bad</finding></findings>'
        '</result>'
    )

    # (vi) CARDINALITY: duplicate maxOccurs=1 sequence children
    # xs:sequence in acs-messages.xsd has maxOccurs=1 (default) for every element;
    # duplicate children must be rejected (XSD rejects them via xs:sequence constraint).

    # duplicate <objective> in <task> (required, maxOccurs=1)
    MALFORMED_DUP_OBJECTIVE = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<objective>first</objective>'
        '<objective>second</objective>'
        '</task>'
    )

    # duplicate <summary> in <handoff> (required, maxOccurs=1)
    MALFORMED_DUP_SUMMARY = (
        '<handoff skill="create-spec" ticket-id="SHOP-1" status="completed">'
        '<summary>first</summary>'
        '<summary>second</summary>'
        '</handoff>'
    )

    # <metrics> was removed from the schema outright (D5-A): any occurrence
    # (let alone a duplicate) is now rejected as an unrecognized <result>
    # child via CHILD_ORDER/ALLOWED_ATTRS, not via a maxOccurs=1 cardinality
    # check. Retained in MALFORMED_CORPUS (still non-empty errors); dropped
    # from the cardinality-specific case lists below since it no longer
    # exercises that violation class.
    MALFORMED_DUP_METRICS = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics tokens-input="100" tokens-output="50" cost-usd="0.01"/>'
        '<metrics tokens-input="200" tokens-output="100" cost-usd="0.02"/>'
        '</result>'
    )

    # duplicate <inputs> container in <task> (optional, maxOccurs=1)
    MALFORMED_DUP_INPUTS = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<objective>obj</objective>'
        '<inputs><file>/a.py</file></inputs>'
        '<inputs><file>/b.py</file></inputs>'
        '</task>'
    )

    # duplicate <next-step> in <handoff> (optional, maxOccurs=1)
    MALFORMED_DUP_NEXT_STEP = (
        '<handoff skill="create-spec" ticket-id="SHOP-1" status="completed">'
        '<summary>s</summary>'
        '<next-step>step one</next-step>'
        '<next-step>step two</next-step>'
        '</handoff>'
    )

    # (vii) xs:decimal grammar for <metrics cost-usd>. <metrics> was removed
    # from the schema outright (D5-A) — cost-usd is no longer a live contract
    # attribute, and every case below is now rejected primarily because
    # <metrics> itself is an unrecognized <result> child. validate_xml.py's
    # decimal-grammar check (_is_xs_decimal) is left in place as defense in
    # depth for any lingering caller and still fires as an additional error,
    # so these fixtures still exercise that code path and still match
    # xmllint (which now rejects them for "unknown element" instead of a
    # decimal violation — both engines agree on INVALID either way).
    # Each of these is accepted by Python float() but rejected by xs:decimal.
    MALFORMED_COST_USD_INF = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics tokens-input="100" tokens-output="50" cost-usd="inf"/>'
        '</result>'
    )
    MALFORMED_COST_USD_NAN = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics tokens-input="100" tokens-output="50" cost-usd="nan"/>'
        '</result>'
    )
    MALFORMED_COST_USD_EXPONENT = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics tokens-input="100" tokens-output="50" cost-usd="1e5"/>'
        '</result>'
    )
    MALFORMED_COST_USD_UNDERSCORE = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics tokens-input="100" tokens-output="50" cost-usd="1_000"/>'
        '</result>'
    )
    MALFORMED_COST_USD_EMPTY = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics tokens-input="100" tokens-output="50" cost-usd=""/>'
        '</result>'
    )

    # (viii) closed content model — the XSD declares no anyAttribute / wildcard,
    # so an undeclared attribute on any element is invalid (xmllint rejects it;
    # the in-process validator must too).
    MALFORMED_UNDECLARED_ATTR_ROOT = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1" bogus="y">'
        '<objective>x</objective></task>'
    )
    # <metrics> was removed from the schema outright (D5-A): this is no
    # longer specifically an "undeclared attribute" case — <metrics> itself
    # is now an unrecognized <result> child, so the whole element is
    # rejected regardless of which attributes it carries. Retained in
    # MALFORMED_CORPUS (still non-empty errors); dropped from
    # CLOSED_CONTENT_CASES below since it no longer isolates that specific
    # violation class.
    MALFORMED_UNDECLARED_ATTR_METRICS = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<metrics cost-usd="0.1" bogus="1"/></result>'
    )
    MALFORMED_UNDECLARED_ATTR_FINDING = (
        '<result skill="code" phase="execute" ticket-id="SHOP-1" status="completed">'
        '<findings><finding severity="info" bogus="z">m</finding></findings></result>'
    )
    MALFORMED_UNDECLARED_ATTR_CONSTRAINT = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1"><objective>x</objective>'
        '<constraints><constraint name="branch" extra="z">c</constraint></constraints></task>'
    )
    # (ix) text-only (xs:string) leaves admit no element children.
    MALFORMED_CHILD_IN_FILE = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1"><objective>x</objective>'
        '<inputs><file>a<sub/></file></inputs></task>'
    )
    MALFORMED_CHILD_IN_OBJECTIVE = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<objective>x<nested/></objective></task>'
    )

    # (x) typed delegation keys (ADR-0093): constraint/@name is the
    # constraintName vocabulary, so a misspelled key fails at the coordinator
    # instead of reaching the executor as an absent value.
    MALFORMED_UNKNOWN_CONSTRAINT_NAME = (
        '<task skill="code" phase="execute" ticket-id="SHOP-1">'
        '<objective>obj</objective>'
        '<constraints><constraint name="coverage-tgt">90</constraint></constraints>'
        '</task>'
    )
    # (xi) the planner role and phase are gone (ADR-0092, ADR-0093): a plan
    # message is no longer part of the vocabulary.
    MALFORMED_PLAN_PHASE = (
        '<task skill="code" phase="plan" ticket-id="SHOP-1">'
        '<objective>obj</objective>'
        '</task>'
    )

    VALID_CORPUS = [
        ("valid_task", VALID_TASK),
        ("valid_result", VALID_RESULT),
        ("valid_handoff", VALID_HANDOFF),
    ]
    MALFORMED_CORPUS = [
        ("bad_root", MALFORMED_BAD_ROOT),
        ("missing_skill", MALFORMED_MISSING_SKILL),
        ("invalid_skill", MALFORMED_INVALID_SKILL),
        ("bad_ticket_id", MALFORMED_BAD_TICKET_ID),
        ("out_of_order", MALFORMED_OUT_OF_ORDER),
        ("wrong_list_item", MALFORMED_WRONG_LIST_ITEM),
        ("bad_status_enum", MALFORMED_BAD_STATUS_ENUM),
        ("bad_severity_enum", MALFORMED_BAD_SEVERITY_ENUM),
        # (vi) cardinality — duplicate maxOccurs=1 sequence elements
        ("dup_objective", MALFORMED_DUP_OBJECTIVE),
        ("dup_summary", MALFORMED_DUP_SUMMARY),
        ("dup_metrics", MALFORMED_DUP_METRICS),
        ("dup_inputs", MALFORMED_DUP_INPUTS),
        ("dup_next_step", MALFORMED_DUP_NEXT_STEP),
        # (vii) xs:decimal grammar — cost-usd values Python float() accepts but xs:decimal rejects
        ("cost_usd_inf", MALFORMED_COST_USD_INF),
        ("cost_usd_nan", MALFORMED_COST_USD_NAN),
        ("cost_usd_exponent", MALFORMED_COST_USD_EXPONENT),
        ("cost_usd_underscore", MALFORMED_COST_USD_UNDERSCORE),
        ("cost_usd_empty", MALFORMED_COST_USD_EMPTY),
        # (viii) closed content model — undeclared attributes
        ("undeclared_attr_root", MALFORMED_UNDECLARED_ATTR_ROOT),
        ("undeclared_attr_metrics", MALFORMED_UNDECLARED_ATTR_METRICS),
        ("undeclared_attr_finding", MALFORMED_UNDECLARED_ATTR_FINDING),
        ("undeclared_attr_constraint", MALFORMED_UNDECLARED_ATTR_CONSTRAINT),
        # (ix) text-only leaves admit no element children
        ("child_in_file", MALFORMED_CHILD_IN_FILE),
        ("child_in_objective", MALFORMED_CHILD_IN_OBJECTIVE),
        # (x) typed delegation keys; (xi) no plan phase
        ("unknown_constraint_name", MALFORMED_UNKNOWN_CONSTRAINT_NAME),
        ("plan_phase", MALFORMED_PLAN_PHASE),
    ]

    def _load_validate_xml(self):
        """Import validate_xml in-process (SCRIPTS is already on sys.path)."""
        import importlib
        import importlib.util
        _target = os.path.join(SCRIPTS, "validate_xml.py")
        spec = importlib.util.spec_from_file_location("validate_xml", _target)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_ac2_parity_valid_corpus_in_process(self):
        """Valid corpus messages return [] from validate_structurally (AC-2)."""
        mod = self._load_validate_xml()
        for name, xml in self.VALID_CORPUS:
            errors = mod.validate_structurally(xml)
            self.assertEqual(errors, [],
                             "Expected no errors for %s but got: %s" % (name, errors))

    def test_ac2_parity_malformed_corpus_in_process(self):
        """Malformed corpus messages return non-empty errors from validate_structurally (AC-2)."""
        mod = self._load_validate_xml()
        for name, xml in self.MALFORMED_CORPUS:
            errors = mod.validate_structurally(xml)
            self.assertTrue(errors,
                            "Expected errors for %s but got empty list" % name)

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_ac2_parity_corpus_xmllint_matches_in_process(self):
        """xmllint and in-process paths agree on every corpus message (AC-2 parity)."""
        mod = self._load_validate_xml()
        all_cases = list(self.VALID_CORPUS) + list(self.MALFORMED_CORPUS)
        for name, xml in all_cases:
            in_process_errors = mod.validate_structurally(xml)
            in_process_ok = (in_process_errors == [])

            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                fh.write(xml)
                tmp_path = fh.name
            try:
                xmllint_ok, xmllint_detail = mod.validate_with_xmllint(tmp_path)
            finally:
                os.unlink(tmp_path)

            self.assertEqual(
                in_process_ok, xmllint_ok,
                "PARITY GAP on %r: in-process=%s xmllint=%s detail=%r errors=%r"
                % (name, in_process_ok, xmllint_ok, xmllint_detail, in_process_errors)
            )

    # -----------------------------------------------------------------------
    # AC-2 parity: cardinality (maxOccurs=1 on sequence members)
    # -----------------------------------------------------------------------

    def test_ac2_cardinality_duplicate_children_rejected_in_process(self):
        """Duplicate maxOccurs=1 sequence children must be rejected by validate_structurally.

        xs:sequence in acs-messages.xsd has maxOccurs=1 (default) for every element.
        Two <objective>, two <summary>, two <inputs>, two <next-step>
        must each produce at least one error (AC-2 cardinality gap closure).
        (<metrics> was removed from the schema outright per D5-A, so a
        duplicate <metrics> case no longer exercises this cardinality class —
        see MALFORMED_DUP_METRICS's own comment.)
        """
        mod = self._load_validate_xml()
        cardinality_cases = [
            ("dup_objective", self.MALFORMED_DUP_OBJECTIVE),
            ("dup_summary", self.MALFORMED_DUP_SUMMARY),
            ("dup_inputs", self.MALFORMED_DUP_INPUTS),
            ("dup_next_step", self.MALFORMED_DUP_NEXT_STEP),
        ]
        for name, xml in cardinality_cases:
            errors = mod.validate_structurally(xml)
            self.assertTrue(
                errors,
                "Expected cardinality error for %s but validate_structurally returned []. "
                "Duplicate maxOccurs=1 child must be rejected." % name,
            )

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_ac2_cardinality_parity_with_xmllint(self):
        """Cardinality violations: in-process and xmllint must both return INVALID."""
        mod = self._load_validate_xml()
        cardinality_cases = [
            ("dup_objective", self.MALFORMED_DUP_OBJECTIVE),
            ("dup_summary", self.MALFORMED_DUP_SUMMARY),
            ("dup_inputs", self.MALFORMED_DUP_INPUTS),
            ("dup_next_step", self.MALFORMED_DUP_NEXT_STEP),
        ]
        for name, xml in cardinality_cases:
            in_process_ok = (mod.validate_structurally(xml) == [])
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                fh.write(xml)
                tmp_path = fh.name
            try:
                xmllint_ok, xmllint_detail = mod.validate_with_xmllint(tmp_path)
            finally:
                os.unlink(tmp_path)
            self.assertEqual(
                in_process_ok, xmllint_ok,
                "PARITY GAP on cardinality case %r: in-process=%s xmllint=%s detail=%r"
                % (name, in_process_ok, xmllint_ok, xmllint_detail),
            )
            self.assertFalse(
                xmllint_ok,
                "xmllint should reject duplicate child %r (maxOccurs=1 violation)" % name,
            )

    # -----------------------------------------------------------------------
    # AC-2 parity: xs:decimal grammar for cost-usd
    # -----------------------------------------------------------------------

    def test_ac2_cost_usd_decimal_grammar_rejected_in_process(self):
        """cost-usd values valid for Python float() but invalid for xs:decimal must be rejected.

        xs:decimal lexical space: optional sign, digits, optional single decimal point.
        No exponent (1e5), no inf, no nan, no underscores (1_000), no empty string.
        """
        mod = self._load_validate_xml()
        decimal_cases = [
            ("cost_usd_inf", self.MALFORMED_COST_USD_INF),
            ("cost_usd_nan", self.MALFORMED_COST_USD_NAN),
            ("cost_usd_exponent", self.MALFORMED_COST_USD_EXPONENT),
            ("cost_usd_underscore", self.MALFORMED_COST_USD_UNDERSCORE),
            ("cost_usd_empty", self.MALFORMED_COST_USD_EMPTY),
        ]
        for name, xml in decimal_cases:
            errors = mod.validate_structurally(xml)
            self.assertTrue(
                errors,
                "Expected xs:decimal error for %s but validate_structurally returned []. "
                "Python float()-parseable but xs:decimal-invalid values must be rejected." % name,
            )

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_ac2_cost_usd_decimal_parity_with_xmllint(self):
        """cost-usd xs:decimal violations: in-process and xmllint must both return INVALID."""
        mod = self._load_validate_xml()
        decimal_cases = [
            ("cost_usd_inf", self.MALFORMED_COST_USD_INF),
            ("cost_usd_nan", self.MALFORMED_COST_USD_NAN),
            ("cost_usd_exponent", self.MALFORMED_COST_USD_EXPONENT),
            ("cost_usd_underscore", self.MALFORMED_COST_USD_UNDERSCORE),
            ("cost_usd_empty", self.MALFORMED_COST_USD_EMPTY),
        ]
        for name, xml in decimal_cases:
            in_process_ok = (mod.validate_structurally(xml) == [])
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                fh.write(xml)
                tmp_path = fh.name
            try:
                xmllint_ok, xmllint_detail = mod.validate_with_xmllint(tmp_path)
            finally:
                os.unlink(tmp_path)
            self.assertEqual(
                in_process_ok, xmllint_ok,
                "PARITY GAP on xs:decimal case %r: in-process=%s xmllint=%s detail=%r"
                % (name, in_process_ok, xmllint_ok, xmllint_detail),
            )
            self.assertFalse(
                xmllint_ok,
                "xmllint should reject cost-usd=%r (xs:decimal violation)" % name,
            )

    # -----------------------------------------------------------------------
    # AC-1: No per-message subprocess on the default path
    # -----------------------------------------------------------------------

    def test_ac1_no_subprocess_on_default_path(self):
        """Default path (ACS_XML_AUTHORITATIVE unset) spawns zero subprocesses (AC-1)."""
        mod = self._load_validate_xml()
        messages = [self.VALID_TASK, self.MALFORMED_BAD_ROOT, self.VALID_RESULT]
        env_without = {k: v for k, v in os.environ.items()
                       if k != "ACS_XML_AUTHORITATIVE"}
        with mock.patch.dict(os.environ, env_without, clear=True):
            with mock.patch("subprocess.run") as mock_run:
                for xml in messages:
                    mod.validate_structurally(xml)
                self.assertEqual(mock_run.call_count, 0,
                                 "subprocess.run was called on the default (in-process) path")

    def test_ac1_cli_default_path_is_in_process_not_xmllint(self):
        """Default CLI path (ACS_XML_AUTHORITATIVE unset) uses in-process engine, not xmllint.
        The stdout output for a valid message must NOT say 'xmllint' on the default fast path
        (AC-1: no per-message subprocess spawn on the default path)."""
        env = self._env_no_authoritative()
        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_TASK, env=env)
        self.assertEqual(result.returncode, 0,
                         "Expected exit 0. stderr=%r" % result.stderr)
        # The in-process fast path should say "in-process" in stdout, NOT "xmllint"
        self.assertIn("in-process", result.stdout,
                      "Expected 'in-process' marker in stdout on default path. stdout=%r" % result.stdout)
        self.assertNotIn("xmllint", result.stdout,
                         "Default fast path must NOT invoke xmllint. stdout=%r" % result.stdout)

    # -----------------------------------------------------------------------
    # AC-1/AC-5: Opt-in xmllint via ACS_XML_AUTHORITATIVE
    # -----------------------------------------------------------------------

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_ac1_optin_xmllint_with_xmllint_present(self):
        """ACS_XML_AUTHORITATIVE=1 + xmllint on PATH: valid message exits 0 with xmllint marker
        in stdout (AC-1 opt-in path)."""
        env = dict(os.environ, ACS_XML_AUTHORITATIVE="1")
        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_TASK, env=env)
        self.assertEqual(result.returncode, 0, "Expected exit 0 for valid message with xmllint. "
                         "stderr=%r stdout=%r" % (result.stderr, result.stdout))
        # The xmllint opt-in path prints "valid (xmllint, ...)"
        self.assertIn("xmllint", result.stdout,
                      "Expected 'xmllint' in stdout when ACS_XML_AUTHORITATIVE=1 and xmllint present")

    def test_ac5_optin_without_xmllint_still_validates(self):
        """ACS_XML_AUTHORITATIVE=1 with xmllint absent from PATH: valid message still exits 0
        (env var has no effect when xmllint absent — AC-5)."""
        # Strip xmllint from PATH by providing a minimal PATH
        minimal_path = "/usr/bin:/bin"
        env = dict(os.environ, ACS_XML_AUTHORITATIVE="1", PATH=minimal_path)
        # Ensure xmllint is genuinely absent from the minimal PATH
        import shutil as _shutil
        orig_path = os.environ.get("PATH", "")
        os.environ["PATH"] = minimal_path
        try:
            xmllint_in_minimal = _shutil.which("xmllint")
        finally:
            os.environ["PATH"] = orig_path
        if xmllint_in_minimal:
            self.skipTest("xmllint found in minimal PATH %r; can't test absent case" % minimal_path)

        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_TASK, env=env)
        self.assertEqual(result.returncode, 0,
                         "Expected exit 0 even when ACS_XML_AUTHORITATIVE=1 and xmllint absent. "
                         "stderr=%r" % result.stderr)
        self.assertNotIn("Traceback", result.stderr,
                         "Unexpected traceback when xmllint absent")

    # -----------------------------------------------------------------------
    # AC-3: CLI fail-fast on in-process path (no xmllint required)
    # -----------------------------------------------------------------------

    def _env_no_authoritative(self):
        """Return env dict without ACS_XML_AUTHORITATIVE (default fast path)."""
        return {k: v for k, v in os.environ.items() if k != "ACS_XML_AUTHORITATIVE"}

    def test_ac3_bad_xml_exits_1_with_invalid_marker(self):
        """<bad/> piped to stdin exits 1 with INVALID in stderr on the in-process path (AC-3)."""
        env = self._env_no_authoritative()
        result = self.run_script("validate_xml.py", "-", stdin="<bad/>", env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID", result.stderr)

    def test_ac3_valid_task_exits_0(self):
        """Valid <task> piped to stdin exits 0 on the in-process path (AC-3)."""
        env = self._env_no_authoritative()
        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_TASK, env=env)
        self.assertEqual(result.returncode, 0,
                         "Expected exit 0 for valid task. stderr=%r" % result.stderr)

    def test_ac3_valid_result_exits_0(self):
        """Valid <result> piped to stdin exits 0 on the in-process path (AC-3)."""
        env = self._env_no_authoritative()
        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_RESULT, env=env)
        self.assertEqual(result.returncode, 0,
                         "Expected exit 0 for valid result. stderr=%r" % result.stderr)

    def test_ac3_valid_handoff_exits_0(self):
        """Valid <handoff> piped to stdin exits 0 on the in-process path (AC-3)."""
        env = self._env_no_authoritative()
        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_HANDOFF, env=env)
        self.assertEqual(result.returncode, 0,
                         "Expected exit 0 for valid handoff. stderr=%r" % result.stderr)

    # -----------------------------------------------------------------------
    # AC-6: Back-compat CLI signature
    # -----------------------------------------------------------------------

    def test_ac6_positional_file_arg(self):
        """validate_xml.py <file> exits 0 for a valid XML file (AC-6)."""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(self.VALID_TASK)
            tmp = fh.name
        try:
            result = self.run_script("validate_xml.py", tmp)
            self.assertEqual(result.returncode, 0,
                             "Expected exit 0. stderr=%r" % result.stderr)
        finally:
            os.unlink(tmp)

    def test_ac6_multiple_file_args_all_valid(self):
        """validate_xml.py <file1> <file2> exits 0 when both are valid (AC-6)."""
        files = []
        try:
            for xml in (self.VALID_TASK, self.VALID_RESULT):
                with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                    fh.write(xml)
                    files.append(fh.name)
            result = self.run_script("validate_xml.py", *files)
            self.assertEqual(result.returncode, 0,
                             "Expected exit 0. stderr=%r" % result.stderr)
        finally:
            for p in files:
                os.unlink(p)

    def test_ac6_mixed_file_args_exits_1_with_invalid(self):
        """validate_xml.py <valid> <invalid> exits 1 with INVALID in stderr (AC-6)."""
        files = []
        try:
            for xml in (self.VALID_TASK, self.MALFORMED_BAD_ROOT):
                with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                    fh.write(xml)
                    files.append(fh.name)
            result = self.run_script("validate_xml.py", *files)
            self.assertEqual(result.returncode, 1)
            self.assertIn("INVALID", result.stderr)
        finally:
            for p in files:
                os.unlink(p)

    def test_ac6_stdin_form(self):
        """validate_xml.py - with valid task exits 0 (AC-6 back-compat pin for stdin form)."""
        result = self.run_script("validate_xml.py", "-", stdin=self.VALID_TASK)
        self.assertEqual(result.returncode, 0,
                         "Expected exit 0. stderr=%r" % result.stderr)

    def test_ac6_no_args_exits_1_with_usage(self):
        """validate_xml.py with no arguments exits 1 and prints usage (AC-6)."""
        result = self.run_script("validate_xml.py")
        self.assertEqual(result.returncode, 1)
        # Usage text goes to stderr (the __doc__ string)
        self.assertIn("validate_xml.py", result.stderr)

    # -----------------------------------------------------------------------
    # AC-4: Batched validation entry point (T2, Spec 02)
    # Tests written FIRST (TDD RED step) — validate_batch / batch_overall_ok
    # do not exist yet when these tests are added.
    # -----------------------------------------------------------------------

    def test_ac4_mixed_batch_correct_per_message_verdicts(self):
        """Mixed batch returns correct per-message (ok, errors) tuples (AC-4).

        A 4-message batch [valid_task, bad_root, valid_result, missing_skill]:
        - index 0: (True, [])
        - index 1: (False, non-empty errors)
        - index 2: (True, [])
        - index 3: (False, non-empty errors)
        batch_overall_ok must be False when any member is invalid.
        """
        mod = self._load_validate_xml()
        messages = [
            self.VALID_TASK,
            self.MALFORMED_BAD_ROOT,
            self.VALID_RESULT,
            self.MALFORMED_MISSING_SKILL,
        ]
        results = mod.validate_batch(messages)

        # One result per input
        self.assertEqual(len(results), 4)

        # Index 0: valid task
        self.assertEqual(results[0], (True, []),
                         "Expected (True, []) for valid_task, got %r" % (results[0],))

        # Index 1: bad root
        self.assertFalse(results[1][0],
                         "Expected ok=False for MALFORMED_BAD_ROOT")
        self.assertGreater(len(results[1][1]), 0,
                           "Expected non-empty errors for MALFORMED_BAD_ROOT")

        # Index 2: valid result
        self.assertEqual(results[2], (True, []),
                         "Expected (True, []) for valid_result, got %r" % (results[2],))

        # Index 3: missing skill
        self.assertFalse(results[3][0],
                         "Expected ok=False for MALFORMED_MISSING_SKILL")
        self.assertGreater(len(results[3][1]), 0,
                           "Expected non-empty errors for MALFORMED_MISSING_SKILL")

        # Overall must be False (at least one member invalid)
        self.assertFalse(mod.batch_overall_ok(results),
                         "batch_overall_ok should be False when any member is invalid")

    def test_ac4_all_valid_batch_overall_ok_true(self):
        """All-valid batch: all ok=True tuples and batch_overall_ok returns True (AC-4)."""
        mod = self._load_validate_xml()
        all_valid = [self.VALID_TASK, self.VALID_RESULT, self.VALID_HANDOFF]
        all_results = mod.validate_batch(all_valid)

        self.assertTrue(all(ok for ok, _ in all_results),
                        "Expected all ok=True in all-valid batch, got: %r" % all_results)
        self.assertTrue(mod.batch_overall_ok(all_results),
                        "batch_overall_ok should be True for all-valid batch")

    def test_ac4_per_message_parity_with_validate_structurally(self):
        """validate_batch([msg])[0] matches (len(vs)==0, vs) from validate_structurally (AC-4)."""
        mod = self._load_validate_xml()
        for name, xml in list(self.VALID_CORPUS) + list(self.MALFORMED_CORPUS):
            vs_errors = mod.validate_structurally(xml)
            expected = (len(vs_errors) == 0, vs_errors)
            batch_result = mod.validate_batch([xml])[0]
            self.assertEqual(batch_result, expected,
                             "Parity mismatch for %s: batch=%r vs_expected=%r"
                             % (name, batch_result, expected))

    def test_ac4_no_subprocess_in_batch_path(self):
        """validate_batch spawns zero subprocesses on the default (in-process) path (AC-1/AC-4)."""
        mod = self._load_validate_xml()
        messages = [self.VALID_TASK, self.MALFORMED_BAD_ROOT, self.VALID_RESULT]
        with mock.patch("validate_xml.subprocess.run") as mock_run:
            mod.validate_batch(messages)
        self.assertEqual(mock_run.call_count, 0,
                         "validate_batch must not call subprocess.run; got %d call(s)"
                         % mock_run.call_count)

    def test_ac4_single_call_atomicity_n5(self):
        """validate_batch with N=5 messages returns exactly 5 entries in one call (AC-4)."""
        mod = self._load_validate_xml()
        messages = [
            self.VALID_TASK,
            self.VALID_RESULT,
            self.VALID_HANDOFF,
            self.MALFORMED_BAD_ROOT,
            self.MALFORMED_MISSING_SKILL,
        ]
        # The whole batch is processed in a single expression — no iteration at the call site
        results = mod.validate_batch(messages)
        self.assertEqual(len(results), 5,
                         "Expected exactly 5 results for N=5 batch, got %d" % len(results))

    def test_ac4_empty_input_returns_empty_list(self):
        """validate_batch([]) returns [] (empty, no error); batch_overall_ok([]) is True (AC-4)."""
        mod = self._load_validate_xml()
        results = mod.validate_batch([])
        self.assertEqual(results, [],
                         "Expected [] for empty input, got %r" % results)
        self.assertTrue(mod.batch_overall_ok([]),
                        "batch_overall_ok([]) should be True (vacuously)")

    def test_ac4_error_detail_is_meaningful(self):
        """validate_batch returns meaningful error strings for known malformed messages (AC-4)."""
        mod = self._load_validate_xml()
        # MALFORMED_MISSING_SKILL is missing required attribute 'skill'
        results = mod.validate_batch([self.MALFORMED_MISSING_SKILL])
        ok, errors = results[0]
        self.assertFalse(ok, "Expected ok=False for MALFORMED_MISSING_SKILL")
        self.assertGreater(len(errors), 0, "Expected non-empty errors list")
        # The error should mention 'skill' or 'attribute' or 'missing' or 'INVALID'
        joined = " ".join(errors).lower()
        self.assertTrue(
            any(kw in joined for kw in ("skill", "attribute", "missing", "invalid")),
            "Error detail should mention a relevant keyword; got: %r" % errors
        )

    # -----------------------------------------------------------------------
    # Closed content model — undeclared attributes + intrusive children
    # (the XSD has no anyAttribute/wildcard; in-process must match xmllint).
    # -----------------------------------------------------------------------

    # (<metrics> was removed from the schema outright per D5-A, so
    # undeclared_attr_metrics no longer isolates this violation class — see
    # MALFORMED_UNDECLARED_ATTR_METRICS's own comment.)
    CLOSED_CONTENT_CASES = [
        ("undeclared_attr_root", MALFORMED_UNDECLARED_ATTR_ROOT),
        ("undeclared_attr_finding", MALFORMED_UNDECLARED_ATTR_FINDING),
        ("undeclared_attr_constraint", MALFORMED_UNDECLARED_ATTR_CONSTRAINT),
        ("child_in_file", MALFORMED_CHILD_IN_FILE),
        ("child_in_objective", MALFORMED_CHILD_IN_OBJECTIVE),
    ]

    def test_closed_content_model_rejected_in_process(self):
        """Undeclared attributes and intrusive children must be rejected in-process."""
        mod = self._load_validate_xml()
        for name, xml in self.CLOSED_CONTENT_CASES:
            errors = mod.validate_structurally(xml)
            self.assertTrue(
                errors,
                "Expected a closed-content-model error for %s but got []; the XSD "
                "declares no anyAttribute/wildcard, so this must be rejected." % name,
            )

    @unittest.skipUnless(shutil.which("xmllint"), "xmllint not on PATH")
    def test_closed_content_model_parity_with_xmllint(self):
        """Closed-content violations: in-process and xmllint must both return INVALID."""
        mod = self._load_validate_xml()
        for name, xml in self.CLOSED_CONTENT_CASES:
            in_process_ok = (mod.validate_structurally(xml) == [])
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
                fh.write(xml)
                tmp_path = fh.name
            try:
                xmllint_ok, xmllint_detail = mod.validate_with_xmllint(tmp_path)
            finally:
                os.unlink(tmp_path)
            self.assertEqual(
                in_process_ok, xmllint_ok,
                "PARITY GAP on closed-content case %r: in-process=%s xmllint=%s detail=%r"
                % (name, in_process_ok, xmllint_ok, xmllint_detail),
            )
            self.assertFalse(xmllint_ok, "xmllint should reject %r" % name)

    def test_validate_batch_isolates_non_string_element(self):
        """A non-string (e.g. None) batch element yields a per-message error, not a crash."""
        mod = self._load_validate_xml()
        results = mod.validate_batch([self.VALID_TASK, None])
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0][0], "valid message should pass")
        self.assertFalse(results[1][0], "None element should be reported invalid, not crash")
        self.assertFalse(mod.batch_overall_ok(results))


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
        # Simulate a legacy/in-flight ticket (minted before create-spec was
        # deleted) that already recorded a create-spec pipeline step.
        lib.update_pipeline(self.tdir(ticket), ticket, "create-spec", "in_progress")
        out = self.run_script("statusline.py", stdin=self.payload(self.repo))
        self.assertEqual(out.returncode, 0, out.stderr)
        for expected in (ticket, "spec", "ticket"):
            self.assertIn(expected, out.stdout)

    def test_subagent_statusline_rows(self):
        ticket = self.new_ticket("X", "task")
        self.start("code", ticket)
        payload = json.dumps({"columns": 80, "tasks": [
            {"id": "a1", "type": "acs:code-verifier", "status": "running",
             "startTime": (time.time() - 95) * 1000, "tokenCount": 45200, "cwd": self.repo},
            {"id": "a2", "type": "Explore", "description": "unrelated", "cwd": self.repo},
        ]})
        out = self.run_script("subagent-statusline.py", stdin=payload)
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [json.loads(line) for line in out.stdout.splitlines()]
        self.assertEqual([row["id"] for row in rows], ["a1"])  # non-acs row untouched
        self.assertIn(ticket, rows[0]["content"])

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


class TestExemptPrMerge(AcsWorkspaceCase):
    """Spec 02 + 03 — exempt non-ticket merge-pr --pr path: the classifier, the
    gate_merge_pr short-circuit, skill-start --pr mode (gh STUBBED), and the
    post-merge-pr --pr metrics-only bump."""

    # ---- spec 02: classifier --------------------------------------------

    def test_classifier_table_ac4(self):
        # (a) AC-4 — the exact five cases.
        self.assertEqual(lib.classify_merge_pr_arg("--pr 87"), ("exempt-pr", "87"))
        self.assertEqual(lib.classify_merge_pr_arg("#87"), ("exempt-pr", "87"))
        self.assertEqual(
            lib.classify_merge_pr_arg("https://github.com/acme/shop/pull/87"),
            ("exempt-pr", "87"))
        self.assertEqual(lib.classify_merge_pr_arg("87", ticket_resolves=False),
                         ("exempt-pr", "87"))
        self.assertEqual(lib.classify_merge_pr_arg("MAR-9", ticket_prefix="MAR"),
                         ("ticket", None))

    def test_classifier_bare_number_disambiguation_c3(self):
        # (b) C-3 — bare integer prefers ticket when one resolves.
        self.assertEqual(lib.classify_merge_pr_arg("87", ticket_resolves=True),
                         ("ticket", None))
        self.assertEqual(lib.classify_merge_pr_arg("87", ticket_resolves=False),
                         ("exempt-pr", "87"))

    def test_classifier_explicit_forms_always_exempt(self):
        # explicit forms are exempt even when a ticket would resolve.
        self.assertEqual(lib.classify_merge_pr_arg("--pr 87", ticket_resolves=True),
                         ("exempt-pr", "87"))
        self.assertEqual(lib.classify_merge_pr_arg("#87", ticket_resolves=True),
                         ("exempt-pr", "87"))
        self.assertEqual(
            lib.classify_merge_pr_arg("https://github.com/acme/shop/pull/87",
                                      ticket_resolves=True),
            ("exempt-pr", "87"))

    def test_classifier_ticket_id_default_prefix(self):
        # a ticket-shaped token is ticket-backed even without an explicit prefix.
        self.assertEqual(lib.classify_merge_pr_arg("SHOP-1"), ("ticket", None))

    def test_classifier_empty_or_unrecognized_is_ticket(self):
        self.assertEqual(lib.classify_merge_pr_arg(""), ("ticket", None))
        self.assertEqual(lib.classify_merge_pr_arg("garbage text"), ("ticket", None))

    def test_pr_labels_normalizes_dicts_and_strings(self):
        # gh emits [{"name": ...}]; tolerate bare strings too.
        self.assertEqual(
            lib._pr_labels({"labels": [{"name": "acs-exempt"}, "ACS", {"x": 1}]}),
            ["acs-exempt", "ACS"])
        self.assertEqual(lib._pr_labels({}), [])

    def test_merge_pr_arg_text_defaults_empty(self):
        # no args/arguments/argument key -> empty string (the ticket gate then
        # produces its own "could not resolve" error).
        self.assertEqual(lib._merge_pr_arg_text({}), "")
        self.assertEqual(lib._merge_pr_arg_text({"tool_input": {"other": 1}}), "")
        self.assertEqual(lib._merge_pr_arg_text({"tool_input": {"arguments": "#9"}}), "#9")

    # ---- spec 02: gate short-circuit ------------------------------------

    def test_gate_exempt_pr_flag_passes_through(self):
        # (c) AC-3 — --pr 87 allows where a ticket arg would block.
        result = self.pre("merge-pr", "--pr 87")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gate_exempt_hash_and_url_pass_through(self):
        # (d) explicit #N and PR-URL forms always allowed.
        self.assertEqual(self.pre("merge-pr", "#87").returncode, 0)
        self.assertEqual(
            self.pre("merge-pr", "https://github.com/acme/shop/pull/87").returncode, 0)

    def test_gate_ticket_arg_still_blocks_unchanged(self):
        # (e) AC-3/AC-8 regression — a ticket arg with no partition still blocks.
        result = self.pre("merge-pr", "SHOP-1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("SHOP-1", result.stderr)

    # ---- spec 03: a fake gh on PATH (never the real GitHub) -------------

    def _gh_env(self, gh_body):
        """Return an env dict whose PATH carries a fake `gh` shim emitting gh_body.

        gh_body is the shell after the shebang; for the `pr view` path it should
        echo a JSON object and exit 0, or write to stderr and exit non-zero to
        simulate an error. The shim dir is PREPENDED to a real PATH so `git` (used
        by build_context) still resolves while our fake `gh` shadows any real one.
        `gh_body is None` means: provide NO gh at all (simulate the binary being
        absent) — PATH is set to the system dirs that hold git but not gh, so the
        script hits FileNotFoundError."""
        bindir = tempfile.mkdtemp(prefix="acs-fakebin-", dir=self.tmp)
        # A minimal real PATH that has git (/usr/bin) + sh (/bin) but NOT gh
        # (which lives in /opt/homebrew/bin or /usr/local/bin on dev machines).
        base_path = "/usr/bin:/bin"
        env = dict(os.environ)
        if gh_body is None:
            env["PATH"] = base_path
            return env
        gh = os.path.join(bindir, "gh")
        with open(gh, "w") as fh:
            fh.write("#!/bin/sh\n" + gh_body + "\n")
        os.chmod(gh, 0o755)
        env["PATH"] = bindir + os.pathsep + base_path
        return env

    def _pr_json(self, **over):
        data = {"number": 87, "state": "OPEN", "headRefName": "chore/cleanup",
                "baseRefName": "main", "labels": [{"name": "acs-exempt"}],
                "isDraft": False, "url": "https://github.com/acme/shop/pull/87"}
        data.update(over)
        return json.dumps(data)

    def _ws_untouched(self):
        """No ticket dir, no sessions pointer, no lock, no index, no pipeline were
        written by an exempt-pr --pr run."""
        repo_root = lib.repo_dir(self.ws, "acme-shop")
        self.assertFalse(os.path.isdir(lib.sessions_dir(self.ws, "acme-shop")))
        if os.path.isdir(repo_root):
            for name in os.listdir(repo_root):
                # only metrics.json may appear (post-merge-pr --pr bumps it)
                self.assertIn(name, {"metrics.json", "counters.json"}, name)

    # ---- spec 03: post-merge-pr --pr metrics-only ----------------------

    def test_post_merge_pr_flag_bumps_metrics_only(self):
        # (a) AC-7 — prs.merged += 1, no ticket state/index/pipeline/archive.
        out = self.run_script("post-merge-pr.py", "--pr", "87")
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["mode"], "exempt-pr")
        self.assertTrue(payload["pr_merged"])
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            metrics = json.load(fh)
        self.assertEqual(metrics["prs"]["merged"], 1)
        self.assertEqual(metrics["prs"].get("created", 0), 0)
        self.assertEqual(metrics.get("totals", {}).get("runs", 0), 0)
        # no ticket index entry was written
        self.assertFalse(os.path.isfile(lib.index_path(self.ws, "acme-shop")))
        self._ws_untouched()

    def test_post_merge_pr_flag_increments_each_call(self):
        self.run_script("post-merge-pr.py", "--pr", "87")
        self.run_script("post-merge-pr.py", "--pr", "88")
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            self.assertEqual(json.load(fh)["prs"]["merged"], 2)

    # ---- spec 03: skill-start --pr exempt-pr mode (gh STUBBED) ----------

    def test_skill_start_pr_exempt_mode_prints_context(self):
        # (b) AC-5 — OPEN exempt PR → mode exempt-pr JSON, no state written.
        env = self._gh_env("echo '%s'" % self._pr_json())
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        ctx = json.loads(out.stdout)
        self.assertEqual(ctx["mode"], "exempt-pr")
        self.assertNotIn("ticket_id", ctx)
        self.assertNotIn("partition", ctx)
        self.assertNotIn("pipeline", ctx)
        self.assertEqual(ctx["pr"]["number"], 87)
        self.assertEqual(ctx["pr"]["url"], "https://github.com/acme/shop/pull/87")
        self.assertEqual(ctx["pr"]["branch"], "chore/cleanup")
        self.assertEqual(ctx["pr"]["base"], "main")
        self.assertIn("acs-exempt", ctx["pr"]["labels"])
        self._ws_untouched()

    def test_skill_start_pr_accepts_exempt_branch_without_label(self):
        # exempt by branch glob (release/*) even with no exempt label.
        body = self._pr_json(headRefName="release/1.2", labels=[])
        env = self._gh_env("echo '%s'" % body)
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["mode"], "exempt-pr")

    def test_skill_start_pr_rejected_for_non_merge_pr_skill(self):
        # (c) --pr only valid with --skill merge-pr.
        env = self._gh_env("echo '%s'" % self._pr_json())
        out = self.run_script("skill-start.py", "--skill", "code",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertTrue(out.stderr.strip())
        self.assertNotIn("Traceback", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_missing_gh_clean_exit(self):
        # (d-i) gh absent → clean exit 2, no traceback.
        env = self._gh_env(None)
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("gh", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_non_open_rejected(self):
        # (d-ii) non-OPEN PR → clean exit 2 naming the state.
        env = self._gh_env("echo '%s'" % self._pr_json(state="MERGED"))
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("MERGED", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_draft_rejected(self):
        env = self._gh_env("echo '%s'" % self._pr_json(isDraft=True))
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)

    def test_skill_start_pr_ticket_backed_label_redirects(self):
        # (d-iii) PR carrying the require_label (ACS) → refuse + redirect.
        body = self._pr_json(labels=[{"name": "ACS"}])
        env = self._gh_env("echo '%s'" % body)
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("/acs:merge-pr", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_ticket_backed_branch_redirects(self):
        # (d-iii) PR whose branch embeds a ticket id → refuse + redirect with id.
        body = self._pr_json(headRefName="story/SHOP-42-x", labels=[])
        env = self._gh_env("echo '%s'" % body)
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("SHOP-42", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_non_exempt_non_ticket_rejected(self):
        # an OPEN PR that is neither exempt-labelled nor exempt-branch nor
        # ticket-backed → refuse + redirect to the ticket path.
        body = self._pr_json(headRefName="feature/whatever", labels=[])
        env = self._gh_env("echo '%s'" % body)
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("/acs:merge-pr", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_not_found_clean_exit(self):
        # gh exits non-zero (PR not found / API error) → clean exit 2.
        env = self._gh_env("echo 'no pull requests found' 1>&2; exit 1")
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "999", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_non_json_output_clean_exit(self):
        # gh exits 0 but emits non-JSON → clean exit 2 (no traceback).
        env = self._gh_env("echo 'not json at all'")
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "87", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self._ws_untouched()

    def test_skill_start_pr_unparseable_ref_clean_exit(self):
        # --pr with a value that is not a PR reference → clean exit 2; gh never run.
        env = self._gh_env("echo '%s'" % self._pr_json())
        out = self.run_script("skill-start.py", "--skill", "merge-pr",
                              "--pr", "not-a-pr", env=env)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("PR reference", out.stderr)
        self._ws_untouched()

    def test_post_merge_pr_flag_outside_acs_repo_clean_exit(self):
        # build_context fails (no .acs settings) → clean exit 1, no traceback.
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        subprocess.run(["git", "init", "-q", plain], check=True)
        out = self.run_script("post-merge-pr.py", "--pr", "1", cwd=plain)
        self.assertEqual(out.returncode, 1)
        self.assertNotIn("Traceback", out.stderr)



class TestDistinctPRCount(AcsWorkspaceCase):
    """AC-1, AC-2, AC-3: distinct-PR counting via created_pr_numbers."""

    def _make_ticket_with_pr(self, pr_number=7):
        """Run the full pipeline up through create-pr with the given PR number,
        returning the child ticket id. The workspace is pre-seeded via setUp."""
        out = self.run_script("skill-start.py", "--skill", "create-ticket",
                              "--allocate", "--type", "epic", "--title", "E")
        self.assertEqual(out.returncode, 0, out.stderr)
        epic = json.loads(out.stdout)["ticket_id"]
        self.post("create-ticket", epic, {"status": "completed"})

        child = self.new_ticket("C", "story", "--parent", epic, "--needs-design", "false")

        with open(os.path.join(self.tdir(epic), "design.md"), "w") as fh:
            fh.write("# design")
        self.start("create-design", epic)
        self.post("create-design", epic, {"status": "completed"})

        # AC-4: gate_code needs no create-spec step or specs/ dir -- go straight to code.
        self.start("code", child)
        # MAR-523: verifier_passed is DERIVED from the verifier's verdict, so
        # the fixture seeds the verdict instead of asserting the conclusion.
        self.seed_verdict(child)
        self.post("code", child, {"status": "completed"})

        self.start("create-pr", child)
        self.post("create-pr", child, {
            "status": "completed",
            "states": {"pr": {"number": pr_number, "url": "https://github.com/acme/shop/pull/%d" % pr_number}},
        })
        return child

    def _read_metrics(self):
        with open(lib.metrics_path(self.ws, "acme-shop")) as fh:
            return json.load(fh)

    # AC-1 + AC-3: pr_number flows from states.pr.number into created_pr_numbers
    def test_ac1_created_pr_numbers_recorded_end_to_end(self):
        """After create-pr post with states.pr.number=7, prs.created_pr_numbers==[7]
        and prs.created==1.  Confirms the caller (run_post) extracts and passes
        the number (AC-3)."""
        self._make_ticket_with_pr(pr_number=7)
        metrics = self._read_metrics()
        self.assertEqual(metrics["prs"]["created"], 1)
        self.assertEqual(metrics["prs"]["created_pr_numbers"], [7])

    # AC-2: same number twice → no increment
    def test_ac2_same_number_twice_no_increment(self):
        """Calling update_metrics with the same pr_number twice must NOT double-count."""
        # Use update_metrics directly to control the pr_number precisely
        ws = self.ws
        repo_id = "acme-shop"
        # seed the workspace (the repo dir must exist for metrics_path)
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        # write a minimal tickets-index.json so index rebuild does not crash
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})

        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 1)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7])

    # AC-2: new number after same number → +1
    def test_ac2_new_number_increments(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})

        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=8)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 2)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7, 8])

    # AC-2: pr_number=None with pr_created=True → no-op
    def test_ac2_none_pr_number_noop(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})

        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=None)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 1)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7])

    # AC-2: non-positive pr_number with pr_created=True → no-op
    def test_ac2_nonpositive_pr_number_noop(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})

        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=0)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=-1)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 1)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7])

    # AC-2: pr_created=False with a valid number → no-op
    def test_ac2_pr_created_false_noop(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})

        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        lib.update_metrics(ws, repo_id, pr_created=False, pr_number=99)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"]["created"], 1)
        self.assertEqual(m["prs"]["created_pr_numbers"], [7])

    # AC-2: default prs block includes created_pr_numbers
    def test_ac1_default_prs_includes_created_pr_numbers(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})
        lib.update_metrics(ws, repo_id)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertIn("created_pr_numbers", m["prs"])
        self.assertEqual(m["prs"]["created_pr_numbers"], [])

    # AC-3: exempt-pr path still leaves created==0
    def test_ac3_exempt_pr_created_stays_zero(self):
        """Confirm the exempt --pr path (run_post_exempt_pr) does NOT set pr_created."""
        # This mirrors the existing test at ~:596-597 but calls lib directly
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})
        lib.update_metrics(ws, repo_id, pr_merged=True)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        self.assertEqual(m["prs"].get("created", 0), 0)
        self.assertEqual(m["prs"]["created_pr_numbers"], [])

    # AC-6: created_pr_numbers round-trips as a plain JSON list of ints
    def test_ac6_created_pr_numbers_round_trips_as_json_list(self):
        ws = self.ws
        repo_id = "acme-shop"
        os.makedirs(os.path.join(ws, repo_id), exist_ok=True)
        lib.write_json(lib.index_path(ws, repo_id), {"tickets": {}})
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=42)
        lib.update_metrics(ws, repo_id, pr_created=True, pr_number=7)
        m = lib.read_json(lib.metrics_path(ws, repo_id))
        nums = m["prs"]["created_pr_numbers"]
        self.assertIsInstance(nums, list)
        self.assertEqual(nums, [7, 42])  # sorted
        for n in nums:
            self.assertIsInstance(n, int)


class TestBackfillDistinctPRCount(AcsWorkspaceCase):
    """AC-4: idempotent backfill of inflated prs.created."""

    def _write_create_pr_state(self, ws, repo_id, ticket_id, pr_number, archived=False):
        """Seed a create-pr-state.json for a ticket partition."""
        if archived:
            tdir = os.path.join(ws, repo_id, "archive", ticket_id)
        else:
            tdir = os.path.join(ws, repo_id, ticket_id)
        os.makedirs(tdir, exist_ok=True)
        state = {"runs": [], "states": {"pr": {"number": pr_number, "url": "https://example.com/pull/%d" % pr_number}}}
        lib.write_json(lib.state_path(tdir, "create-pr"), state)
        return tdir

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
