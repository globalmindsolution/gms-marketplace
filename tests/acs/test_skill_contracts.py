"""Contract tests for the prose layer: SKILL.md and agent definitions.

Skills and agents are product code written in markdown — a stale path, a
missing section, or a contradiction with the deterministic layer breaks the
pipeline even when every Python test passes. This module pins the structural
invariants that INTERNALS.md / AUTHORING.md declare, so drift fails CI
instead of surfacing mid-pipeline. (Behavioral quality — does the model
follow the prose — is the agentic-e2e tier, not unit-testable.)
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

HOOKED_SKILLS = ["create-prd", "create-architecture", "create-project",
                 "create-quality", "create-operations", "create-principles",
                 "create-standards", "create-ticket", "create-design",
                 "create-spec", "code", "create-pr", "merge-pr"]
ALL_SKILLS = HOOKED_SKILLS + ["init", "ship", "handoff", "update", "install-hooks", "metrics", "usage", "test"]
ROLES = ["planner", "executor", "verifier"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


class TestSkillContracts(unittest.TestCase):
    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def test_all_skills_exist_no_strays(self):
        found = sorted(os.path.basename(os.path.dirname(p))
                       for p in glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))
        self.assertEqual(found, sorted(ALL_SKILLS))

    def test_frontmatter_and_name_matches_directory(self):
        for name in ALL_SKILLS:
            text = read(self.skill_path(name))
            fm, _body = frontmatter(text, name)
            self.assertRegex(fm, r"(?m)^name: %s$" % re.escape(name))
            self.assertRegex(fm, r"(?m)^description: \S")

    def test_hooked_skills_call_their_lifecycle_scripts(self):
        for name in HOOKED_SKILLS:
            body = read(self.skill_path(name))
            self.assertIn("skill-start.py", body, name)
            self.assertRegex(body, r"--skill %s\b" % re.escape(name), name)
            self.assertIn("post-%s.py" % name, body, name)
            self.assertIn("validate_xml.py", body, name)

    def test_every_skill_has_completion_report(self):
        for name in ALL_SKILLS:
            self.assertIn("## Completion report (normative)",
                          read(self.skill_path(name)), name)

    def test_hooked_skills_have_clarification_ledger_rule(self):
        for name in HOOKED_SKILLS:
            body = read(self.skill_path(name))
            self.assertIn("Clarification ledger first.", body, name)
            self.assertIn("clarify.py", body, name)

    def test_coordinator_tool_restrictions(self):
        for name in HOOKED_SKILLS + ["ship"]:
            fm, _ = frontmatter(read(self.skill_path(name)), name)
            self.assertRegex(fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$", name)
        for name in ("init", "handoff", "update", "install-hooks"):
            fm, _ = frontmatter(read(self.skill_path(name)), name)
            self.assertNotIn("disallowed-tools", fm, name)

    def test_ship_no_per_step_subagent_spawn(self):
        # /acs:ship drives the pipeline by invoking each step skill DIRECTLY via
        # the Skill tool — not by spawning a general-purpose subagent per step
        # (a subagent cannot spawn the step skill's planner/executor/verifier).
        # Guard the antipattern, not exact positive wording, so the test stays
        # stable across legitimate future edits to the direct-invocation prose.
        body = read(self.skill_path("ship"))
        self.assertNotIn('subagent_type: "general-purpose"', body)
        self.assertNotIn("one subagent per step", body)
        self.assertIsNone(re.search(r"spawn a fresh subagent", body, re.IGNORECASE))

    def test_user_action_only_skills(self):
        # update + install-hooks change the environment; merge-pr is now
        # agent/model-invocable (MAR-42), so it is NOT in this set.
        user_action = ("update", "install-hooks")
        for name in user_action:
            fm, _ = frontmatter(read(self.skill_path(name)), name)
            self.assertRegex(fm, r"(?m)^disable-model-invocation: true$", name)
        for name in ALL_SKILLS:
            if name in user_action:
                continue
            fm, _ = frontmatter(read(self.skill_path(name)), name)
            self.assertNotIn("disable-model-invocation: true", fm, name)

    def test_merge_pr_is_agent_invocable(self):
        # MAR-42: /acs:merge-pr is agent/model-invocable; the readiness gate +
        # branch protection are the merge brakes, and merges require an APPROVED
        # review (m6). The old user-action-only invariant must be gone.
        text = read(self.skill_path("merge-pr"))
        fm, body = frontmatter(text, "merge-pr")
        self.assertNotIn("disable-model-invocation", fm,
                         "merge-pr must not set disable-model-invocation (MAR-42)")
        self.assertNotIn("User action only", body,
                         "merge-pr must drop the 'User action only' section (MAR-42)")
        self.assertNotIn("user-invoked only", body,
                         "merge-pr must drop the 'user-invoked only' framing (MAR-42)")
        self.assertIn("Invocation and safety model", body,
                      "merge-pr must carry the new invocation/safety section (MAR-42)")
        self.assertRegex(body, r"(?i)reviewDecision`? is `?APPROVED",
                         "merge-pr approvals dimension must require APPROVED (m6)")

    def test_no_forked_context_in_frontmatter(self):
        # context: fork would break clarifying questions (AUTHORING.md)
        for name in ALL_SKILLS:
            fm, _ = frontmatter(read(self.skill_path(name)), name)
            self.assertNotRegex(fm, r"(?m)^context:", name)
            self.assertNotRegex(fm, r"(?m)^model:", name)


class TestAgentContracts(unittest.TestCase):
    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def test_all_27_agents_exist_no_strays(self):
        expected = sorted("%s-%s.md" % (s, r) for s in HOOKED_SKILLS for r in ROLES)
        found = sorted(os.path.basename(p)
                       for p in glob.glob(os.path.join(PLUGIN, "agents", "*.md")))
        self.assertEqual(found, expected)

    def test_frontmatter_name_description(self):
        for skill in HOOKED_SKILLS:
            for role in ROLES:
                fm, _ = frontmatter(read(self.agent_path(skill, role)), skill + role)
                self.assertRegex(fm, r"(?m)^name: %s-%s$" % (re.escape(skill), role))
                self.assertIn("not for direct invocation", fm)
                self.assertNotRegex(fm, r"(?m)^model:")    # settings.json owns models
                self.assertNotRegex(fm, r"(?m)^effort:")

    def test_role_tool_restrictions(self):
        for skill in HOOKED_SKILLS:
            for role in ("planner", "verifier"):
                fm, _ = frontmatter(read(self.agent_path(skill, role)), skill)
                self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$",
                                 "%s-%s" % (skill, role))
            fm, _ = frontmatter(read(self.agent_path(skill, "executor")), skill)
            self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$", skill)
            self.assertNotRegex(fm, r"(?m)^tools:", skill)  # executors keep broad access

    def test_grounding_section_everywhere(self):
        for skill in HOOKED_SKILLS:
            for role in ROLES:
                body = read(self.agent_path(skill, role))
                self.assertIn("## Grounding (anti-hallucination)", body,
                              "%s-%s" % (skill, role))
                if role == "verifier":
                    self.assertIn("police grounding", body, skill)

    def test_phase_artifact_mandated(self):
        artifact = {"planner": "plan", "executor": "execute", "verifier": "verify"}
        for skill in HOOKED_SKILLS:
            for role, kind in artifact.items():
                body = read(self.agent_path(skill, role))
                self.assertRegex(body, r"iter-<n(?:>|\b)[^\n]*%s" % kind,
                                 "%s-%s missing iter-<n>-%s artifact" % (skill, role, kind))

    def test_no_stale_heredoc_claims(self):
        # the drift this session actually found — keep it dead
        for path in glob.glob(os.path.join(PLUGIN, "agents", "*.md")):
            body = read(path)
            self.assertNotIn("no Write tool", body, path)
            self.assertNotIn("heredoc", body, path)

    def test_result_is_final_message(self):
        for skill in HOOKED_SKILLS:
            for role in ROLES:
                body = read(self.agent_path(skill, role))
                self.assertIn("<result", body, "%s-%s" % (skill, role))
                self.assertIn("FINAL message", body, "%s-%s" % (skill, role))


class TestCrossReferences(unittest.TestCase):
    """Every path the prose tells the model to use must exist on disk."""

    def collect_bodies(self):
        for pattern in ("skills/*/SKILL.md", "agents/*.md"):
            for path in glob.glob(os.path.join(PLUGIN, pattern)):
                yield path, read(path)

    def test_referenced_helper_scripts_exist(self):
        for path, body in self.collect_bodies():
            for script in set(re.findall(r"hooks/scripts/([a-zA-Z0-9_\-]+\.py)", body)):
                target = os.path.join(PLUGIN, "hooks", "scripts", script)
                self.assertTrue(os.path.isfile(target),
                                "%s references missing script %s" % (path, script))

    def test_referenced_schemas_exist(self):
        for path, body in self.collect_bodies():
            for schema in set(re.findall(r"schemas/([a-zA-Z0-9_\-\.]+\.(?:xsd|json))", body)):
                target = os.path.join(PLUGIN, "schemas", schema)
                self.assertTrue(os.path.isfile(target),
                                "%s references missing schema %s" % (path, schema))

    def test_skills_reference_existing_agents(self):
        for path, body in self.collect_bodies():
            for skill, role in set(re.findall(
                    r"acs:(%s)-(planner|executor|verifier)" % "|".join(HOOKED_SKILLS), body)):
                target = os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))
                self.assertTrue(os.path.isfile(target),
                                "%s references missing agent %s-%s" % (path, skill, role))

    def test_referenced_templates_exist(self):
        for path, body in self.collect_bodies():
            for name in set(re.findall(r"\b(pr|epic|story|task)-default\b", body)):
                target = os.path.join(PLUGIN, "templates", "%s-default.md" % name)
                self.assertTrue(os.path.isfile(target), "%s -> %s-default" % (path, name))


class TestExemptPrDocs(unittest.TestCase):
    """MAR-9 (spec 04): the exempt --pr merge path and the /acs:init CLAUDE.md
    managed block must stay surfaced in the merge-pr skill prose and the docs.
    Additive existence/section assertions only — they pin the new prose so a
    later edit that drops it fails CI. No existing assertion is modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def doc_path(self, *parts):
        return os.path.join(PLUGIN, *parts)

    def test_merge_pr_argument_hint_includes_pr_form(self):
        fm, _ = frontmatter(read(self.skill_path("merge-pr")), "merge-pr")
        self.assertRegex(
            fm, r'(?m)^argument-hint: "\[ticket-id\] \| --pr PRNUMBER"$')

    def test_merge_pr_has_exempt_mode_section(self):
        body = read(self.skill_path("merge-pr"))
        self.assertIn("Exempt non-ticket PR mode", body)

    def test_init_documents_claude_md_managed_block(self):
        body = read(self.skill_path("init"))
        self.assertIn("CLAUDE.acs.md", body)
        self.assertIn("upsert_managed_block", body)

    def test_internals_mentions_exempt_pr_merge(self):
        body = read(self.doc_path("docs", "INTERNALS.md"))
        self.assertIn("--pr", body)
        self.assertIn("CLAUDE.acs.md", body)

    def test_readme_mentions_exempt_pr_merge(self):
        body = read(self.doc_path("README.md"))
        self.assertIn("--pr", body)
        self.assertIn("CLAUDE.md", body)

    def test_changelog_mentions_exempt_pr_merge(self):
        body = read(self.doc_path("CHANGELOG.md"))
        self.assertIn("(MAR-9)", body)
        self.assertIn("--pr", body)


class TestMergePrBehindAutoUpdate(unittest.TestCase):
    """MAR-47 (spec 03): pin the BEHIND→update-branch prose contract across all
    three behavior surfaces (SKILL.md, planner, executor) and the exempt --pr
    path. Additive existence/co-occurrence assertions only — they enforce AC-6
    (and AC-1, AC-2, AC-4 across surfaces) so a future edit that drops or
    reverts the carve-out fails CI. No existing assertion is modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def test_skill_behind_routes_to_update_branch(self):
        body = read(self.skill_path("merge-pr"))
        # Basic existence: update-branch is present in the skill prose.
        self.assertIn("update-branch", body,
                      "SKILL.md must mention update-branch (MAR-47 AC-1)")
        # Co-occurrence: BEHIND and update-branch must appear in proximity,
        # proving the routing (not unconditionally report-only).
        self.assertIsNotNone(
            re.search(r"BEHIND.*update-branch|update-branch.*BEHIND", body, re.DOTALL),
            "SKILL.md must co-locate BEHIND and update-branch (MAR-47 AC-1)")

    def test_planner_behind_routes_to_update_branch(self):
        body = read(self.agent_path("merge-pr", "planner"))
        # Basic existence: update-branch is present in the planner prose.
        self.assertIn("update-branch", body,
                      "merge-pr-planner.md must mention update-branch (MAR-47 AC-2)")
        # Co-occurrence: BEHIND and update-branch appear together.
        self.assertIsNotNone(
            re.search(r"BEHIND.*update-branch|update-branch.*BEHIND", body, re.DOTALL),
            "merge-pr-planner.md must co-locate BEHIND and update-branch (MAR-47 AC-2)")
        # C-7 verdict tokens: pin the verdict shape without requiring the exact
        # full sentence — robust to minor rewording of surrounding context.
        self.assertIn("was BEHIND", body,
                      "merge-pr-planner.md must carry 'was BEHIND' verdict token (MAR-47 C-7)")
        self.assertIn("auto-updated", body,
                      "merge-pr-planner.md must carry 'auto-updated' verdict token (MAR-47 C-7)")

    def test_executor_behind_routes_to_update_branch(self):
        body = read(self.agent_path("merge-pr", "executor"))
        # Basic existence: update-branch is present in the executor prose.
        self.assertIn("update-branch", body,
                      "merge-pr-executor.md must mention update-branch (MAR-47 AC-2)")
        # BEHIND-only guard: the executor must scope the update-branch step
        # strictly to when mergeStateStatus == BEHIND (AC-2 — SKIP otherwise).
        self.assertIsNotNone(
            re.search(
                r"(?i)(only when.*BEHIND|BEHIND.*only|skip.*if.*BEHIND"
                r"|mergeStateStatus != BEHIND)",
                body),
            "merge-pr-executor.md must carry the BEHIND-only guard for update-branch "
            "(MAR-47 AC-2 — 'SKIP if mergeStateStatus != BEHIND')")

    def test_conflict_and_timeout_fallbacks_in_skill(self):
        body = read(self.skill_path("merge-pr"))
        # Verbatim load-bearing fallback tokens (design.md lines 238-239).
        # A future edit that drops either fallback will be caught here.
        self.assertIn("update-branch conflict", body,
                      "SKILL.md must carry 'update-branch conflict' fallback stop_reason "
                      "(MAR-47 AC-4)")
        self.assertIn("branch updated but required CI still running", body,
                      "SKILL.md must carry CI-timeout fallback stop_reason (MAR-47 AC-4)")

    def test_conflict_and_timeout_fallbacks_in_executor(self):
        body = read(self.agent_path("merge-pr", "executor"))
        # Same two verbatim fallback tokens must appear in the executor prose
        # independently — asserting both surfaces catches a partial edit that
        # updates only skill or only executor.
        self.assertIn("update-branch conflict", body,
                      "merge-pr-executor.md must carry 'update-branch conflict' fallback "
                      "stop_reason (MAR-47 AC-4)")
        self.assertIn("branch updated but required CI still running", body,
                      "merge-pr-executor.md must carry CI-timeout fallback stop_reason "
                      "(MAR-47 AC-4)")

    def test_exempt_pr_path_behind_routes_to_update_branch(self):
        # C-10 extension: the BEHIND carve-out applies to the exempt --pr path
        # as well as the ticket path (clarifications.json:104-113).
        body = read(self.skill_path("merge-pr"))
        # Exempt section heading must be present (also asserted by TestExemptPrDocs).
        self.assertIn("Exempt non-ticket PR mode", body,
                      "SKILL.md must carry the 'Exempt non-ticket PR mode' section")
        # update-branch must appear within 3000 chars after the exempt heading,
        # proving the exempt section itself was amended — not just the ticket path.
        self.assertIsNotNone(
            re.search(r"(?s)Exempt non-ticket PR mode.{0,3000}update-branch", body),
            "SKILL.md exempt section must mention update-branch within 3000 chars "
            "of its heading (MAR-47 C-10)")
        # BEHIND must also appear within that window.
        self.assertIsNotNone(
            re.search(r"(?s)Exempt non-ticket PR mode.{0,3000}BEHIND", body),
            "SKILL.md exempt section must mention BEHIND within 3000 chars "
            "of its heading (MAR-47 C-10)")


class TestApplyTierInline(unittest.TestCase):
    """MAR-60 (spec 05): pin the apply-tier inline contract across create-pr,
    merge-pr, and create-ticket. Assertions enforce MAR-55 invariant (b) —
    'Apply-work (create-pr, merge-pr, create-ticket) is always
    deterministic-inline (coordinator + at most one executor), never a triad'
    — and the AC-1 through AC-7 acceptance criteria from the ticket.
    These tests are written first (TDD RED) and turn green after specs 01-04
    apply the SKILL.md and doc rewrites. No existing assertion is modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def doc_path(self, *parts):
        return os.path.join(REPO_ROOT, *parts)

    # ------------------------------------------------------------------ Group 1
    # AC-1, AC-2: no planner / no verifier spawn in each apply-work SKILL.md.

    def test_create_pr_no_planner_verifier_spawn(self):
        """AC-1/AC-2 [create-pr]: SKILL.md must not spawn -planner or -verifier."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNone(
            re.search(r"acs:create-pr-planner", body),
            "AC-1 [create-pr]: SKILL.md must not spawn acs:create-pr-planner subagent")
        self.assertIsNone(
            re.search(r"acs:create-pr-verifier", body),
            "AC-1 [create-pr]: SKILL.md must not spawn acs:create-pr-verifier subagent")
        self.assertIsNone(
            re.search(r"\bcreate-pr-planner\b", body),
            "AC-2 [create-pr]: SKILL.md must carry no bare create-pr-planner token")
        self.assertIsNone(
            re.search(r"\bcreate-pr-verifier\b", body),
            "AC-2 [create-pr]: SKILL.md must carry no bare create-pr-verifier token")

    def test_merge_pr_no_planner_verifier_spawn(self):
        """AC-1/AC-2 [merge-pr]: SKILL.md must not spawn -planner or -verifier."""
        body = read(self.skill_path("merge-pr"))
        self.assertIsNone(
            re.search(r"acs:merge-pr-planner", body),
            "AC-1 [merge-pr]: SKILL.md must not spawn acs:merge-pr-planner subagent")
        self.assertIsNone(
            re.search(r"acs:merge-pr-verifier", body),
            "AC-1 [merge-pr]: SKILL.md must not spawn acs:merge-pr-verifier subagent")
        self.assertIsNone(
            re.search(r"\bmerge-pr-planner\b", body),
            "AC-2 [merge-pr]: SKILL.md must carry no bare merge-pr-planner token")
        self.assertIsNone(
            re.search(r"\bmerge-pr-verifier\b", body),
            "AC-2 [merge-pr]: SKILL.md must carry no bare merge-pr-verifier token")

    def test_create_ticket_no_planner_verifier_spawn(self):
        """AC-1/AC-2 [create-ticket]: SKILL.md must not spawn -planner or -verifier."""
        body = read(self.skill_path("create-ticket"))
        self.assertIsNone(
            re.search(r"acs:create-ticket-planner", body),
            "AC-1 [create-ticket]: SKILL.md must not spawn acs:create-ticket-planner subagent")
        self.assertIsNone(
            re.search(r"acs:create-ticket-verifier", body),
            "AC-1 [create-ticket]: SKILL.md must not spawn acs:create-ticket-verifier subagent")
        self.assertIsNone(
            re.search(r"\bcreate-ticket-planner\b", body),
            "AC-2 [create-ticket]: SKILL.md must carry no bare create-ticket-planner token")
        self.assertIsNone(
            re.search(r"\bcreate-ticket-verifier\b", body),
            "AC-2 [create-ticket]: SKILL.md must carry no bare create-ticket-verifier token")

    # ------------------------------------------------------------------ Group 2
    # AC-2: no plan->execute->verify triad instruction in any apply-work SKILL.md.

    def test_apply_skills_no_triad_instruction(self):
        """AC-2: no ASCII-arrow, Unicode-arrow, or prose triad instruction."""
        for skill in ("create-pr", "merge-pr", "create-ticket"):
            body = read(self.skill_path(skill))
            self.assertIsNone(
                re.search(r"plan\s*->\s*execute\s*->\s*verify", body, re.IGNORECASE),
                "AC-2 [%s]: SKILL.md must not contain 'plan -> execute -> verify'" % skill)
            self.assertIsNone(
                re.search(r"plan\s*→\s*execute\s*→\s*verify", body, re.IGNORECASE),
                "AC-2 [%s]: SKILL.md must not contain 'plan → execute → verify'" % skill)
            self.assertIsNone(
                re.search(r"plan to execute to verify", body, re.IGNORECASE),
                "AC-2 [%s]: SKILL.md must not contain 'plan to execute to verify'" % skill)

    # ------------------------------------------------------------------ Group 3
    # AC-1 positive shape: planner and verifier token count must be zero.

    def test_apply_skills_executor_token_allowed(self):
        """AC-1: planner and verifier counts are zero; executor is unconstrained."""
        for skill in ("create-pr", "merge-pr", "create-ticket"):
            body = read(self.skill_path(skill))
            self.assertEqual(
                len(re.findall(r"\b%s-planner\b" % skill, body)), 0,
                "AC-1 [%s]: SKILL.md must have 0 occurrences of %s-planner" % (skill, skill))
            self.assertEqual(
                len(re.findall(r"\b%s-verifier\b" % skill, body)), 0,
                "AC-1 [%s]: SKILL.md must have 0 occurrences of %s-verifier" % (skill, skill))

    # ------------------------------------------------------------------ Group 4
    # AC-3: no lane keyword co-occurs with a planner/verifier spawn in any apply
    # SKILL.md — no lane must conditionally re-introduce the triad.

    def test_apply_skills_no_lane_conditional_triad(self):
        """AC-3: no lane keyword co-occurs within 500 chars of a planner/verifier spawn."""
        for skill in ("create-pr", "merge-pr", "create-ticket"):
            body = read(self.skill_path(skill))
            for lane in ("TRIVIAL", "SMALL", "STANDARD", "COMPLEX"):
                self.assertIsNone(
                    re.search(
                        r"(?s)" + lane + r".{0,500}acs:" + skill + r"-(planner|verifier)"
                        + r"|acs:" + skill + r"-(planner|verifier).{0,500}" + lane,
                        body),
                    "AC-3 [%s]: lane '%s' must not co-occur with planner/verifier spawn"
                    % (skill, lane))

    # ------------------------------------------------------------------ Group 5
    # AC-4: load-bearing step tokens and post-hook references survive the inline
    # rewrite in each apply-work SKILL.md.

    def test_apply_skills_preserved_load_bearing_steps(self):
        """AC-4: canonical states keys and post-hook references must survive."""
        # create-pr: states.pr nested object plus post-hook
        create_pr_body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r'"states"\s*:\s*\{\s*"pr"\s*:', create_pr_body),
            "AC-4 [create-pr]: Finish must declare the canonical states.pr object")
        self.assertIn('"number"', create_pr_body,
                      "AC-4 [create-pr]: states.pr.number field must survive")
        self.assertIn('"url"', create_pr_body,
                      "AC-4 [create-pr]: states.pr.url field must survive")
        self.assertIn('"branch"', create_pr_body,
                      "AC-4 [create-pr]: states.pr.branch field must survive")
        self.assertIn('"base"', create_pr_body,
                      "AC-4 [create-pr]: states.pr.base field must survive")
        self.assertIn("post-create-pr.py", create_pr_body,
                      "AC-4 [create-pr]: post-hook reference must survive inline rewrite")

        # merge-pr: canonical key set plus post-hook
        merge_pr_body = read(self.skill_path("merge-pr"))
        self.assertIn("merged", merge_pr_body,
                      "AC-4 [merge-pr]: Finish must name states.merged key")
        self.assertIn("merge_strategy", merge_pr_body,
                      "AC-4 [merge-pr]: Finish must name states.merge_strategy key")
        self.assertIn("readiness", merge_pr_body,
                      "AC-4 [merge-pr]: Finish must name states.readiness key")
        self.assertIn("post-merge-pr.py", merge_pr_body,
                      "AC-4 [merge-pr]: post-hook reference must survive")

        # create-ticket: canonical key set plus confirmation-gate tokens and post-hook
        create_ticket_body = read(self.skill_path("create-ticket"))
        self.assertIn("ticket_id", create_ticket_body,
                      "AC-4 [create-ticket]: Finish must name states.ticket_id key")
        self.assertIn("type", create_ticket_body,
                      "AC-4 [create-ticket]: Finish must name states.type key")
        self.assertIn("needs_design", create_ticket_body,
                      "AC-4 [create-ticket]: Finish must name states.needs_design key "
                      "(also a confirmation-gate token)")
        self.assertIn("children", create_ticket_body,
                      "AC-4 [create-ticket]: Finish must name states.children key")
        self.assertIn("prd_trace", create_ticket_body,
                      "AC-4 [create-ticket]: Finish must name states.prd_trace key")
        self.assertIn("post-create-ticket.py", create_ticket_body,
                      "AC-4 [create-ticket]: post-hook reference must survive")
        self.assertIn("size", create_ticket_body,
                      "AC-4 [create-ticket]: user-confirmation gate token size must survive")
        self.assertIn("stakes", create_ticket_body,
                      "AC-4 [create-ticket]: user-confirmation gate token stakes must survive")
        self.assertIn("lane", create_ticket_body,
                      "AC-4 [create-ticket]: user-confirmation gate token lane must survive")

    # ------------------------------------------------------------------ Group 6
    # AC-6: the six triad-keeping skills still reference planner and verifier.

    def test_triad_skills_still_reference_planner_and_verifier(self):
        """AC-6: workflow/product skills must still reference their planner+verifier."""
        for skill in ("create-spec", "code", "create-prd",
                      "create-design", "create-architecture", "create-project"):
            body = read(self.skill_path(skill))
            self.assertIsNotNone(
                re.search(r"acs:" + skill + r"-planner", body),
                "AC-6 [%s]: must still reference acs:%s-planner" % (skill, skill))
            self.assertIsNotNone(
                re.search(r"acs:" + skill + r"-verifier", body),
                "AC-6 [%s]: must still reference acs:%s-verifier" % (skill, skill))

    # ------------------------------------------------------------------ Group 7
    # AC-7: requirements docs updated to reflect inline shape.

    def test_skills_md_apply_skills_no_triad_in_subagents(self):
        """AC-7: skills.md must not list planner for apply skills and must carry
        an inline/apply-work carve-out token."""
        body = read(self.doc_path("docs", "requirements", "skills.md"))
        self.assertIsNone(
            re.search(
                r"(?s)(create-pr|merge-pr|create-ticket).{0,500}Subagents.{0,300}planner",
                body),
            "AC-7: skills.md per-skill Subagents must not list planner for apply skills")
        self.assertIsNotNone(
            re.search(r"(?i)(inline|deterministic.inline|apply.work)", body),
            "AC-7: skills.md must carry an inline/apply-work carve-out token")

    def test_reflection_md_no_all_skills_triad_claim(self):
        """AC-7: reflection.md must not describe apply skills as running their own
        planner+verifier triad, and must carry a carve-out or drop the
        unconditional all-skills triad claim."""
        body = read(self.doc_path("docs", "requirements", "reflection.md"))
        self.assertIsNone(
            re.search(
                r"(?s)(create-pr|merge-pr|create-ticket).{0,300}planner.{0,300}verifier",
                body),
            "AC-7: reflection.md must not describe apply skills as running "
            "planner+verifier")
        unconditional = re.search(
            r"Every workflow skill MUST apply the Reflection pattern", body)
        carve_out = re.search(
            r"(?i)(apply.work|create-pr.*inline|inline.*create-pr)", body)
        self.assertTrue(
            unconditional is None or carve_out is not None,
            "AC-7: reflection.md must either drop the all-skills triad claim or "
            "carry an apply-work carve-out")


class TestCreatePrConventionWiring(unittest.TestCase):
    """MAR-72 spec 02: pin the deterministic-render + pre-open self-check
    wiring in plugins/acs/skills/create-pr/SKILL.md. Additive only — no
    existing assertion in this file is modified. Written TDD-first (RED
    before Spec 02's SKILL.md edit lands)."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def test_helper_referenced_by_name(self):
        """AC-1/AC-2: create-pr/SKILL.md references pr-conventions.py by name."""
        body = read(self.skill_path("create-pr"))
        self.assertIn("pr-conventions.py", body,
                      "create-pr/SKILL.md must reference pr-conventions.py")

    def test_title_rendered_via_helper_not_prose(self):
        """AC-1: render-title co-occurs with pr_title within a bounded window,
        and the result is passed verbatim to gh pr create/edit --title."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?s)render-title.{0,400}pr_title|pr_title.{0,400}render-title", body),
            "AC-1 [create-pr]: render-title must co-occur with pr_title within a bounded window")
        self.assertIn("verbatim", body,
                      "AC-1 [create-pr]: rendered title must be stated as passed verbatim to gh pr")

    def test_pre_open_self_check_present_and_blocks_or_retries(self):
        """AC-2: the check subcommand is present, and a mismatch blocks/retries."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r'pr-conventions\.py"?\s+check\b', body),
            "AC-2 [create-pr]: pre-open self-check (check subcommand) must be present")
        self.assertIsNotNone(
            re.search(r"(?s)check\b.{0,600}(blocks|retries)|(blocks|retries).{0,600}check\b", body,
                      re.IGNORECASE),
            "AC-2 [create-pr]: a check mismatch must block or retry, within a bounded window")

    def test_self_check_is_deterministic_cli_not_subagent(self):
        """No-regression belt-and-suspenders: the new self-check step introduces
        no subagent-spawn phrasing (duplicates, locally, the invariant
        test_create_pr_no_planner_verifier_spawn already pins file-wide)."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNone(re.search(r"acs:create-pr-planner", body))
        self.assertIsNone(re.search(r"acs:create-pr-verifier", body))
        self.assertIsNone(re.search(r"\bcreate-pr-planner\b", body))
        self.assertIsNone(re.search(r"\bcreate-pr-verifier\b", body))

    def test_no_regression_guards(self):
        """AC-5: ACS label, base-branch detection, states.pr record,
        post-create-pr.py, and tracker-sync invocations all survive."""
        body = read(self.skill_path("create-pr"))
        self.assertIn("gh label create ACS", body,
                      "AC-5 [create-pr]: ACS label creation must survive")
        self.assertIn("defaultBranchRef", body,
                      "AC-5 [create-pr]: base-branch detection must survive")
        self.assertIsNotNone(
            re.search(r'"states"\s*:\s*\{\s*"pr"\s*:', body),
            "AC-5 [create-pr]: states.pr object must survive")
        self.assertIn('"number"', body)
        self.assertIn('"url"', body)
        self.assertIn('"branch"', body)
        self.assertIn('"base"', body)
        self.assertIn("post-create-pr.py", body,
                      "AC-5 [create-pr]: post-create-pr.py reference must survive")
        self.assertIn("gh issue comment", body,
                      "AC-5 [create-pr]: github tracker-sync invocation must survive")
        self.assertIn("acli jira workitem comment", body,
                      "AC-5 [create-pr]: jira tracker-sync invocation must survive")

    def test_render_title_call_includes_provider(self):
        """MAR-80 spec 03 AC-1/AC-2/AC-3: the render-title call site passes
        --provider so build_title's compute_ticket_ref (spec 01) can compute
        the tracker-native reference. Bounded-window co-occurrence pattern,
        mirroring test_title_rendered_via_helper_not_prose."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?s)render-title.{0,400}--provider|--provider.{0,400}render-title", body),
            "MAR-80 [create-pr]: render-title must co-occur with --provider within a bounded window")

    def test_pre_open_check_and_render_share_same_pr_title_format(self):
        """MAR-80 spec 03: step 4's --pr-title-format and step 2's --template
        must be documented as resolving the SAME committed
        settings.formats.pr_title value -- no per-provider template
        branching, no independently-hardcoded literal."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?s)--pr-title-format.{0,600}(SAME|same).{0,200}settings\.formats\.pr_title", body),
            "MAR-80 [create-pr]: step 4 narrative must state --pr-title-format "
            "resolves the SAME settings.formats.pr_title value step 2's --template uses")

    def test_r4_closes_linkage_fence_untouched(self):
        """MAR-80 R4 fence: the Closes #{external_key} body-fill mechanism
        (MAR-75) is a separate mechanism from title rendering and must not be
        touched by spec 03's wiring."""
        body = read(self.skill_path("create-pr"))
        self.assertIn("Closes #{external_key}", body,
                      "R4 fence: Closes #{external_key} bullet must survive untouched")
        self.assertIn("GitHub-native issue link", body,
                      "R4 fence: GitHub-native issue link mechanism must survive untouched")


class TestProductSkillConventionWiring(unittest.TestCase):
    """MAR-72 spec 03: pin the identical deterministic-render + pre-open
    self-check wiring across create-prd, create-architecture, and
    create-project. Structurally parallel to TestCreatePrConventionWiring
    (spec 02) so the two read as a matched pair. Additive only. Written
    TDD-first (RED before Spec 03's SKILL.md edits land)."""

    SKILLS = ("create-prd", "create-architecture", "create-project", "create-quality", "create-operations")

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def test_references_helper_by_name(self):
        """References the Spec-01 helper by name, per skill."""
        for skill in self.SKILLS:
            body = read(self.skill_path(skill))
            self.assertIn("pr-conventions.py", body,
                          "%s: SKILL.md must reference pr-conventions.py" % skill)

    def test_renders_title_via_helper_not_prose(self):
        """render-title co-occurs with pr_title within a bounded window, per skill."""
        for skill in self.SKILLS:
            body = read(self.skill_path(skill))
            self.assertIsNotNone(
                re.search(r"(?s)render-title.{0,400}pr_title|pr_title.{0,400}render-title", body),
                "%s: render-title must co-occur with pr_title within a bounded window" % skill)

    def test_self_checks_before_gh_pr_create(self):
        """The check subcommand token appears BEFORE the actual gh pr create
        invocation in file order, and a mismatch blocks/retries within a
        bounded window."""
        for skill in self.SKILLS:
            body = read(self.skill_path(skill))
            check_match = re.search(r'pr-conventions\.py"?\s+check\b', body)
            self.assertIsNotNone(check_match,
                                 "%s: pre-open self-check (check subcommand) must be present" % skill)
            # The actual invocation (as opposed to prose mentioning the
            # phrase) always appears as the LAST occurrence in the Delivery
            # section, inside a code fence.
            create_idx = body.rindex("gh pr create")
            self.assertLess(check_match.start(), create_idx,
                            "%s: check must appear before gh pr create in file order" % skill)
            self.assertIsNotNone(
                re.search(r"(?s)check\b.{0,600}(blocks|retries)|(blocks|retries).{0,600}check\b", body,
                          re.IGNORECASE),
                "%s: a check mismatch must block or retry, within a bounded window" % skill)

    def test_no_regression_create_prd(self):
        body = read(self.skill_path("create-prd"))
        self.assertIn("gh label create ACS", body)
        self.assertIn("--label ACS", body)
        self.assertIn("Record the PR number, URL, and branch", body)

    def test_no_regression_create_architecture(self):
        body = read(self.skill_path("create-architecture"))
        self.assertIn("git checkout -b", body)
        self.assertIn("git diff --cached --name-only", body)
        self.assertIn("gh label create ACS", body)
        self.assertIn("{number, url, branch}", body)
        self.assertIn("in_review", body)

    def test_no_regression_create_project(self):
        body = read(self.skill_path("create-project"))
        self.assertIn("push -u origin", body)
        self.assertIn("gh label create ACS", body)
        self.assertIn("states.pr", body)
        self.assertIn("gh pr checks", body)
        self.assertIn("--watch", body)

    def test_render_title_call_includes_provider(self):
        """MAR-80 spec 03 AC-1/AC-2/AC-3: each product skill's render-title
        call site passes --provider so build_title's compute_ticket_ref
        (spec 01) can compute the tracker-native reference -- the same
        uniform mechanism as create-pr, no per-skill carve-out."""
        for skill in self.SKILLS:
            body = read(self.skill_path(skill))
            self.assertIsNotNone(
                re.search(r"(?s)render-title.{0,400}--provider|--provider.{0,400}render-title", body),
                "%s: render-title must co-occur with --provider within a bounded window" % skill)


class TestCodeSkillEscalation(unittest.TestCase):
    """MAR-57 Spec 02 (AC-1, AC-2, AC-6): pin the in-loop escalation contract in
    plugins/acs/skills/code/SKILL.md. Doc-assertion tests that read the prose
    and assert the presence of normative tokens. The tests are RED before the
    escalation subsection is added; GREEN after.
    """

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def _body(self):
        return read(self.skill_path("code"))

    # --- AC-6: exactly three triggers enumerated ---

    def test_trigger_a_verifier_finding(self):
        """AC-6: code/SKILL.md must name trigger (a) — verifier finding signaling higher
        stakes/size."""
        body = self._body()
        # Accept either 'verifier finding' or 'finding' near 'stakes' or 'size'
        self.assertIsNotNone(
            re.search(r"(?i)verifier finding|finding.*higher.{0,60}(stakes|size)", body),
            "code/SKILL.md must enumerate trigger (a): verifier finding signaling "
            "higher stakes/size (MAR-57 AC-6)")

    def test_trigger_b_high_stakes_paths_glob(self):
        """AC-6: code/SKILL.md must name trigger (b) using high_stakes_paths (the glob
        mechanism, not a re-implementation)."""
        body = self._body()
        self.assertIn("high_stakes_paths", body,
                      "code/SKILL.md must reference high_stakes_paths for trigger (b) "
                      "(MAR-57 AC-6 — reuse glob mechanism, not a re-implementation)")

    def test_trigger_c_explicit_user_agent_request(self):
        """AC-6: code/SKILL.md must name trigger (c) — explicit user/agent escalation
        request."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)explicit.{0,40}(user|agent)|user.{0,40}agent.{0,40}(escalat|request)",
                      body),
            "code/SKILL.md must enumerate trigger (c): explicit user/agent escalation "
            "request (MAR-57 AC-6)")

    def test_escalate_lane_named(self):
        """AC-4/AC-6: code/SKILL.md must name escalate_lane (the Spec-01 helper) so the
        coordinator recomputes via the canonical derive_lane path (not hand-set)."""
        body = self._body()
        self.assertIn("escalate_lane", body,
                      "code/SKILL.md must reference escalate_lane (MAR-57 AC-4/AC-6)")

    # --- AC-2: first-signal / immediate evaluation ---

    def test_first_signal_evaluated_immediately(self):
        """AC-2: code/SKILL.md must state that escalation is evaluated on the FIRST
        signal (not after N findings or cap exhaustion)."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)(first.{0,30}signal|immediately|on.{0,30}first)", body),
            "code/SKILL.md must state escalation is evaluated on the first signal / "
            "immediately (MAR-57 AC-2)")

    # --- AC-1: no-restart / continue-from-current-point ---

    def test_no_restart_property(self):
        """AC-1: code/SKILL.md must state the no-restart / continue-from-current-point
        property: completed work is not discarded when escalation fires."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(no.restart|without restart|without discard|continue.{0,60}"
                r"(current|completed)|completed work)",
                body),
            "code/SKILL.md must state the no-restart / continue-from-current-point "
            "property on escalation (MAR-57 AC-1)")

    # --- AC-1/AC-7: upward-only, ceiling never lowered ---

    def test_upward_only_stated(self):
        """AC-1/AC-7: code/SKILL.md must state the lane is only ever raised, never
        lowered (upward-only monotone escalation)."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)(upward.only|only.{0,30}rais|never.{0,30}lower|monoton)", body),
            "code/SKILL.md must state upward-only / never-lower escalation "
            "(MAR-57 AC-1/AC-7)")

    # --- AC-4: re-persist to all three state files ---

    def test_repersist_ticket_json(self):
        """AC-4: code/SKILL.md must state that the escalated lane is persisted to
        ticket.json via save_ticket (or by name)."""
        body = self._body()
        self.assertTrue(
            "ticket.json" in body or "save_ticket" in body,
            "code/SKILL.md must mention ticket.json or save_ticket for re-persist "
            "(MAR-57 AC-4)")

    def test_repersist_pipeline_state(self):
        """AC-4: code/SKILL.md must state that pipeline-state.json is updated on
        escalation via update_pipeline."""
        body = self._body()
        self.assertTrue(
            "pipeline-state.json" in body or "update_pipeline" in body,
            "code/SKILL.md must mention pipeline-state.json or update_pipeline for "
            "re-persist (MAR-57 AC-4)")

    def test_repersist_tickets_index(self):
        """AC-4: code/SKILL.md must state that tickets-index.json is updated on
        escalation via update_index."""
        body = self._body()
        self.assertTrue(
            "tickets-index.json" in body or "update_index" in body,
            "code/SKILL.md must mention tickets-index.json or update_index for "
            "re-persist (MAR-57 AC-4)")

    # --- MAR-106 AC-4: step (f) names the helper ---

    def test_step_f_names_record_escalation_event(self):
        """AC-4: code/SKILL.md step (f) must call record_escalation_event
        (replacing the prior free-text coordinator-note phrasing)."""
        body = self._body()
        self.assertIn("record_escalation_event", body,
                      "code/SKILL.md must name record_escalation_event in the "
                      "escalation section (MAR-106 AC-4)")

    # --- MAR-106 AC-4: persist-then-record ordering ---

    def test_record_escalation_event_follows_persistence_steps(self):
        """AC-4: record_escalation_event must be called AFTER the
        save_ticket/update_pipeline/update_index persistence steps (b-d) and
        the ceiling raise (e) — never before/interleaved."""
        body = self._body()
        save_pos = body.find("save_ticket")
        update_pipeline_pos = body.find("update_pipeline")
        update_index_pos = body.find("update_index")
        record_pos = body.find("record_escalation_event")
        self.assertGreater(save_pos, -1)
        self.assertGreater(update_pipeline_pos, -1)
        self.assertGreater(update_index_pos, -1)
        self.assertGreater(record_pos, -1)
        self.assertGreater(record_pos, save_pos,
                           "record_escalation_event must appear after save_ticket (AC-4)")
        self.assertGreater(record_pos, update_pipeline_pos,
                           "record_escalation_event must appear after update_pipeline (AC-4)")
        self.assertGreater(record_pos, update_index_pos,
                           "record_escalation_event must appear after update_index (AC-4)")

    # --- MAR-106 AC-6: idempotency-on-resume statement ---

    def test_idempotency_on_resume_stated(self):
        """AC-6: code/SKILL.md must state the no-duplicate-on-resume argument:
        a resumed run re-reads the already-escalated axes, so the recompute is
        a no-op and no duplicate event is appended."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?is)resum.{0,300}(no-op|no duplicate)", body),
            "code/SKILL.md must state the resume idempotency argument "
            "(MAR-106 AC-6)")

    # --- MAR-106 AC-5/D2: frozen three-trigger statement ---

    def test_signal_set_frozen_at_three_triggers(self):
        """AC-5/D2: code/SKILL.md must state the signal set is frozen/complete
        at exactly three triggers, with (b) named sole deterministic and
        (a)/(c) named judgment."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)(frozen|exactly three).{0,200}trigger|trigger.{0,200}(frozen|exactly three)", body),
            "code/SKILL.md must state the signal set is frozen at exactly "
            "three triggers (MAR-106 AC-5/D2)")
        self.assertIsNotNone(
            re.search(r"(?i)sole deterministic", body),
            "code/SKILL.md must name trigger (b) as the sole deterministic "
            "signal (MAR-106 AC-5/D2)")
        self.assertIsNotNone(
            re.search(r"(?i)judgment", body),
            "code/SKILL.md must name triggers (a)/(c) as judgment "
            "(MAR-106 AC-5/D2)")

    # --- MAR-106 AC-5/D2: no new deterministic helper/tunable (negative) ---

    def test_no_new_deterministic_scope_helper_in_prose(self):
        """AC-5/D2 negative: code/SKILL.md's escalation section must not
        introduce a new settings key or scope/size helper name (e.g. no
        recommend_size-style mechanism)."""
        body = self._body()
        self.assertNotIn("recommend_size", body,
                         "code/SKILL.md must not introduce a recommend_size-style "
                         "deterministic scope helper (MAR-106 AC-5/D2, frozen set)")

    # --- MAR-107 D4 AC-1: named iteration-start escalation detection point ---

    def test_d4_named_detection_point(self):
        """MAR-107 AC-1: code/SKILL.md must contain an explicit label for the
        iteration-start escalation detection point."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)detection point", body),
            "code/SKILL.md must name the iteration-start escalation "
            "'detection point' as a normative contract (MAR-107 AC-1)")

    # --- MAR-107 D4 AC-1: before-the-verifier ordering ---

    def test_d4_before_the_verifier_ordering(self):
        """MAR-107 AC-1: code/SKILL.md must state that re-selection happens
        after the prior verifier and before the current execute, guaranteeing
        escalation lands before the NEXT verifier pass. Distinct from
        test_first_signal_evaluated_immediately (:820), which only pins
        'first signal', not the before/after verifier ordering framing."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)before the (next )?verifier", body),
            "code/SKILL.md must state escalation lands before the next "
            "verifier pass (MAR-107 AC-1)")

    # --- MAR-107 D4 AC-3: no-restart guarantee, D4-framed (anchored near the detection point) ---

    def test_d4_no_restart_guarantee_anchored_near_detection_point(self):
        """MAR-107 AC-3: code/SKILL.md must state the no-restart /
        completed-work-preserved guarantee co-located with the named
        detection-point label (within 400 chars), not merely anywhere in the
        document. Distinct from test_no_restart_property (:831), which pins
        the general MAR-57 no-restart statement anywhere in the body; this
        test requires the guarantee to be near the D4 detection-point anchor
        specifically."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)detection point.{0,400}(no.restart|without restart|"
                r"without discard|completed work)|"
                r"(no.restart|without restart|without discard|completed work)"
                r".{0,400}detection point",
                body, re.DOTALL),
            "code/SKILL.md must state the no-restart guarantee co-located "
            "with the named detection point (MAR-107 AC-3)")


class TestStageReintroduction(unittest.TestCase):
    """MAR-57 Spec 03 (AC-5, AC-8): pin the stage re-introduction contract in
    create-spec/SKILL.md and the cross-reference in code/SKILL.md.

    These doc-assertion tests are RED before the 'Escalation pickup' subsection
    is added to create-spec/SKILL.md and the cross-reference is added to
    code/SKILL.md; GREEN after.

    Per plan Q1 resolution: since MAR-59 fold prose is not yet on disk, the
    MAR-59-unchanged assertion targets the NEW pickup subsection's own statement
    that fold behavior is unchanged for non-escalating tickets — not absent
    pre-existing fold prose.
    """

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def _create_spec_body(self):
        return read(self.skill_path("create-spec"))

    def _code_body(self):
        return read(self.skill_path("code"))

    # --- AC-5: create-spec/SKILL.md has an 'Escalation pickup' subsection ---

    def test_skill_md_documents_escalation_pickup(self):
        """AC-5: create-spec/SKILL.md must contain an 'Escalation pickup' heading
        (or equivalent) describing the mid-/code invocation path."""
        body = self._create_spec_body()
        self.assertIsNotNone(
            re.search(r"(?i)escalation pickup|escalation pick.?up", body),
            "create-spec/SKILL.md must have an 'Escalation pickup' subsection "
            "(MAR-57 AC-5)")

    # --- AC-5: pickup subsection states create-spec rigor is invoked, not skipped ---

    def test_skill_md_pickup_does_not_skip_spec_stage(self):
        """AC-5: the pickup subsection must state that create-spec rigor is invoked
        (not skipped) when a ticket escalates from a fast lane into STANDARD/COMPLEX."""
        body = self._create_spec_body()
        # Must state the escalation pickup runs full create-spec rigor.
        # Patterns: 'create-spec' near 'rigor' near 'invok/run/not skipped', OR
        # 'rigor' near 'not skip/invok', OR 'spec.rigor' directly adjacent.
        self.assertIsNotNone(
            re.search(
                r"(?i)"
                r"create.spec.{0,30}rigor.{0,300}(invok|not skip|pick.?up)|"
                r"(invok|not skip|pick.?up).{0,300}create.spec.{0,30}rigor|"
                r"(rigor).{0,200}(not skip|invok)",
                body, re.DOTALL),
            "create-spec/SKILL.md pickup subsection must state create-spec rigor "
            "is invoked (not skipped) on fast-lane escalation (MAR-57 AC-5)")

    # --- AC-5: pickup subsection references higher verify ceiling ---

    def test_skill_md_pickup_adopts_higher_ceiling(self):
        """AC-5: the pickup subsection must reference adoption of the higher verify
        ceiling after escalation."""
        body = self._create_spec_body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(higher.{0,30}(ceiling|verify)|verify.{0,30}ceiling.{0,30}(higher|raise|adopt)|"
                r"ceiling.{0,30}(raise|adopt|higher))",
                body),
            "create-spec/SKILL.md pickup subsection must reference the higher verify "
            "ceiling adopted on escalation (MAR-57 AC-5)")

    # --- AC-8 sibling-no-regression: pickup subsection states fold is unchanged for
    #     non-escalating tickets (per Q1: assert the NEW subsection's own statement,
    #     NOT pre-existing fold prose from MAR-59 which is not yet on disk) ---

    def test_mar59_fold_behavior_stated_unchanged_for_noescalation(self):
        """AC-8: the pickup subsection must state that for non-escalating TRIVIAL/SMALL
        tickets the fast-lane fold behavior is unchanged — the new subsection is a
        NEW branch only, not a change to the normal fast-lane flow."""
        body = self._create_spec_body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(non.escalat|not escalat).{0,300}(unchanged|unaffected|fold|fast.lane|normal|intact)|"
                r"(fast.lane|fold).{0,300}(unchanged|unaffected|unmodified|intact|not.{0,20}changed).{0,100}"
                r"(non.escalat|not escalat|without escalat)",
                body, re.DOTALL),
            "create-spec/SKILL.md pickup subsection must state fast-lane fold is "
            "unchanged for non-escalating tickets (MAR-57 AC-8 / Q1 resolution)")

    # --- AC-5: code/SKILL.md cross-references the create-spec pickup subsection ---

    def test_code_skill_md_cross_references_create_spec_pickup(self):
        """AC-5: code/SKILL.md must contain a cross-reference to the
        create-spec/SKILL.md 'Escalation pickup' subsection."""
        body = self._code_body()
        # Must mention create-spec in the context of escalation pickup or stage reintroduction
        self.assertIsNotNone(
            re.search(
                r"(?i)create.spec.{0,300}(escalation pickup|pickup|stage.reintroduc|"
                r"fold.boundar|fast.lane.{0,40}escalat)|"
                r"(escalation pickup|stage.reintroduc).{0,300}create.spec",
                body, re.DOTALL),
            "code/SKILL.md must cross-reference the create-spec 'Escalation pickup' "
            "subsection (MAR-57 AC-5)")

    # --- guard_axes must be referenced in code/SKILL.md escalation sequence ---

    def test_code_skill_md_references_guard_axes(self):
        """AC-3/Spec 03: code/SKILL.md must reference guard_axes in the escalation
        sequence (the axis-guard step added by Spec 03)."""
        body = self._code_body()
        self.assertIn("guard_axes", body,
                      "code/SKILL.md must reference guard_axes in the escalation "
                      "sequence (MAR-57 AC-3/Spec 03)")

    # --- AC-3: no automatic-downgrade code path exists in either SKILL ---

    def test_no_automatic_downgrade_path_in_code_skill(self):
        """AC-3: code/SKILL.md must NOT describe an automatic de-escalation or
        downgrade path (outside of the out-of-scope / negative-guarantee note).
        Assertive phrases (e.g. 'will automatically lower the lane') must be absent;
        negating phrases (e.g. 'never lowered', 'no automatic path lowers') are
        the negative-guarantee language and are acceptable."""
        body = self._code_body()
        # Detect assertive automatic-downgrade phrases: patterns where the automatic
        # downgrade is affirmed, not denied.  We exclude lines containing 'never',
        # 'not', 'no automatic' etc. that express the negative guarantee itself.
        # Strategy: search for matches, then verify none is assertive (not negated).
        matches = list(re.finditer(
            r"(?i)(automatic(ally)?.{0,50}(lower.{0,20}lane|de.escalat|downgrad)|"
            r"(lower.{0,20}lane|de.escalat|downgrad).{0,50}automatic)",
            body))
        for m in matches:
            # Allow matches that are explicitly negated (part of the safety contract)
            surrounding = body[max(0, m.start()-30):m.end()+10]
            if re.search(r"(?i)(never|not|no |cannot|must not|does not)", surrounding):
                continue  # this is a negating / negative-guarantee statement
            self.fail(
                "code/SKILL.md describes an automatic downgrade path outside of a "
                "negating context (AC-3 negative guarantee). Found: %r" % m.group(0))

    def test_no_automatic_downgrade_path_in_create_spec_skill(self):
        """AC-3: create-spec/SKILL.md must NOT describe an automatic de-escalation or
        downgrade path. Negating / negative-guarantee statements ('does not introduce
        an automatic...', 'never') are acceptable."""
        body = self._create_spec_body()
        matches = list(re.finditer(
            r"(?i)(automatic(ally)?.{0,50}(lower.{0,20}lane|de.escalat|downgrad)|"
            r"(lower.{0,20}lane|de.escalat|downgrad).{0,50}automatic)",
            body))
        for m in matches:
            surrounding = body[max(0, m.start()-30):m.end()+10]
            if re.search(r"(?i)(never|not|no |cannot|must not|does not)", surrounding):
                continue  # negating / negative-guarantee statement: allowed
            self.fail(
                "create-spec/SKILL.md describes an automatic downgrade path outside of "
                "a negating context (AC-3 negative guarantee). Found: %r" % m.group(0))

    # --- MAR-107 D4 AC-4: fold-boundary condition pinned code-side (step g) ---

    def test_d4_step_g_states_fold_condition_and_pickup_invocation(self):
        """MAR-107 AC-4: code/SKILL.md step (g) must state the fold condition
        (origin lane TRIVIAL or SMALL, and new lane STANDARD or COMPLEX) and
        name the create-spec triad invocation in Escalation-pickup mode. This
        is the first test targeting code/SKILL.md step (g) specifically
        (distinct from the create-spec-side tests in this class, which pin
        create-spec/SKILL.md, not code/SKILL.md)."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)(TRIVIAL|fast lane).{0,120}(SMALL).{0,200}"
                      r"(STANDARD|full lane).{0,60}(COMPLEX)|"
                      r"fast lane.{0,80}(TRIVIAL or SMALL).{0,300}"
                      r"full lane.{0,80}(STANDARD or COMPLEX)",
                      body, re.DOTALL),
            "code/SKILL.md step (g) must state the fold condition: origin "
            "lane TRIVIAL or SMALL and new lane STANDARD or COMPLEX "
            "(MAR-107 AC-4)")
        self.assertIsNotNone(
            re.search(r"(?i)create.spec.{0,200}(triad|escalation.pickup)|"
                      r"(triad|escalation.pickup).{0,200}create.spec",
                      body, re.DOTALL),
            "code/SKILL.md step (g) must name the create-spec triad "
            "invocation in Escalation-pickup mode (MAR-107 AC-4)")

    # --- MAR-107 D4 AC-4: resume-only-after-zero-findings pinned code-side (step g) ---

    def test_d4_step_g_states_resume_only_after_zero_findings(self):
        """MAR-107 AC-4: code/SKILL.md step (g) must state that /code resumes
        implementation only once create-spec has passed at zero verifier
        findings."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)only once.{0,10}create.spec.{0,120}(passed|pass).{0,120}"
                      r"zero.{0,20}(verifier )?findings.{0,60}resume",
                      body, re.DOTALL),
            "code/SKILL.md step (g) must state /code resumes only once "
            "create-spec passes at zero verifier findings (MAR-107 AC-4)")


class TestBoundaryOnlyDeescalationContract(unittest.TestCase):
    """MAR-108 (AC-4, AC-5 prose half): pin the boundary-only user-confirmed
    de-escalation subsection in code/SKILL.md (design D3).

    Doc-assertion tests reading code/SKILL.md. RED before the new
    'Boundary-only user-confirmed de-escalation (D3)' subsection is added;
    GREEN after."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def _code_body(self):
        return read(self.skill_path("code"))

    def test_boundary_only_timing_gate(self):
        """AC-4: the subsection must state de-escalation fires only at an
        iteration/run boundary and never mid-iteration."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(iteration|run).{0,60}boundary.{0,300}never.{0,30}"
                r"mid.iteration|"
                r"never.{0,30}mid.iteration.{0,300}(iteration|run).{0,60}boundary",
                body, re.DOTALL),
            "code/SKILL.md must state the boundary-only timing gate: fires "
            "only at an iteration/run boundary, never mid-iteration (MAR-108 AC-4)")

    def test_names_confirm_deescalation(self):
        """AC-4: code/SKILL.md must name confirm_deescalation literally."""
        body = self._code_body()
        self.assertIn(
            "confirm_deescalation", body,
            "code/SKILL.md must reference confirm_deescalation by name (MAR-108 AC-4)")

    def test_askuserquestion_and_clarify_precede_writer_call(self):
        """AC-4: the subsection must require AskUserQuestion + clarify.py
        confirmation BEFORE the confirm_deescalation call (ordering)."""
        body = self._code_body()
        self.assertIn("AskUserQuestion", body,
                      "code/SKILL.md must mention AskUserQuestion in the "
                      "de-escalation confirmation sequence (MAR-108 AC-4)")
        self.assertIn("clarify", body,
                      "code/SKILL.md must mention clarify.py recording in the "
                      "de-escalation confirmation sequence (MAR-108 AC-4)")
        ask_idx = body.find("AskUserQuestion")
        clarify_idx = body.find("clarify")
        writer_idx = body.find("confirm_deescalation")
        self.assertGreater(writer_idx, -1,
                            "confirm_deescalation must appear in code/SKILL.md")
        self.assertLess(ask_idx, writer_idx,
                         "AskUserQuestion must precede the confirm_deescalation "
                         "call in code/SKILL.md (MAR-108 AC-4)")
        self.assertLess(clarify_idx, writer_idx,
                         "clarify.py recording must precede the confirm_deescalation "
                         "call in code/SKILL.md (MAR-108 AC-4)")

    def test_sole_lane_lowering_path_single_call_site_never_inloop_or_subagent(self):
        """AC-4/AC-5 prose: confirm_deescalation must be stated as the ONLY
        sanctioned lane-lowering path, called from exactly one location, and
        never from the in-loop trigger path or any subagent."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(
                r"(?i)confirm_deescalation.{0,200}(only|sole).{0,60}"
                r"(sanctioned )?lane.lowering.{0,60}path|"
                r"(only|sole).{0,60}(sanctioned )?lane.lowering.{0,60}path.{0,200}"
                r"confirm_deescalation",
                body, re.DOTALL),
            "code/SKILL.md must state confirm_deescalation is the only "
            "sanctioned lane-lowering path (MAR-108 AC-4)")
        self.assertIsNotNone(
            re.search(r"(?i)never.{0,60}in.loop.{0,60}trigger", body, re.DOTALL),
            "code/SKILL.md must state confirm_deescalation is never called "
            "from the in-loop trigger-evaluation path (MAR-108 AC-4)")
        self.assertIsNotNone(
            re.search(r"(?i)never.{0,60}(from )?(any )?subagent", body, re.DOTALL),
            "code/SKILL.md must state confirm_deescalation is never called "
            "from any subagent (MAR-108 AC-4)")


class TestAdr0042D3Section(unittest.TestCase):
    """MAR-108 (AC-6): pin the additive D3 section appended to
    docs/adr/0042-dynamic-mid-flight-lane-correctness.md. The ADR's own text
    defers D3 (:21-23); this class asserts the deferred section now exists."""

    def _adr_path(self):
        return os.path.join(REPO_ROOT, "docs", "adr",
                            "0042-dynamic-mid-flight-lane-correctness.md")

    def _adr_body(self):
        return read(self._adr_path())

    def test_adr_0042_has_d3_heading_naming_writer_and_decision(self):
        """AC-6: docs/adr/0042 must contain a '### D3' heading naming
        confirm_deescalation and the boundary-only/user-confirmed decision."""
        body = self._adr_body()
        self.assertIsNotNone(
            re.search(r"(?i)### D3.{0,400}confirm_deescalation.{0,300}"
                      r"(boundary.only|user.confirmed)|"
                      r"### D3.{0,400}(boundary.only|user.confirmed).{0,300}"
                      r"confirm_deescalation",
                      body, re.DOTALL),
            "docs/adr/0042 must contain a '### D3' heading naming "
            "confirm_deescalation and the boundary-only/user-confirmed "
            "decision (MAR-108 AC-6)")

    def test_adr_0042_d3_records_unreachable_without_resolved_clarify_ref(self):
        """AC-6: the D3 section must state the writer is unreachable without
        a resolved clarify_ref (the negative-guarantee statement)."""
        body = self._adr_body()
        d3_start = body.find("### D3")
        self.assertGreater(d3_start, -1, "### D3 heading must exist")
        d3_section = body[d3_start:]
        self.assertIsNotNone(
            re.search(r"(?i)unreachable.{0,60}(without|resolved).{0,60}"
                      r"clarify_ref|"
                      r"clarify_ref.{0,120}unreachable",
                      d3_section, re.DOTALL),
            "docs/adr/0042 D3 section must state confirm_deescalation is "
            "unreachable without a resolved clarify_ref (MAR-108 AC-6)")


class TestLaneStatementUserConfirmedExceptionDocs(unittest.TestCase):
    """MAR-108 (AC-6): overview.md / c4-component.md / reflection.md must
    each carry the 'never *automatically* downward' + user-confirmed
    de-escalation exception wording (design D3 architecture conformance)."""

    def _overview_body(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld",
                                  "overview.md"))

    def _c4_component_body(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld",
                                  "c4-component.md"))

    def _reflection_body(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements",
                                  "reflection.md"))

    def _assert_never_automatically_downward_with_exception(self, body, path):
        self.assertIsNotNone(
            re.search(r"(?i)never.{0,20}automatically.{0,20}downward",
                      body, re.DOTALL),
            "%s must state the precise invariant 'never *automatically* "
            "downward' (MAR-108 AC-6)" % path)
        self.assertIsNotNone(
            re.search(r"(?i)user.confirmed.{0,60}de.escalat|"
                      r"de.escalat.{0,60}user.confirmed",
                      body, re.DOTALL),
            "%s must mention the user-confirmed de-escalation exception "
            "(MAR-108 AC-6)" % path)

    def test_overview_md_never_automatically_downward_exception(self):
        self._assert_never_automatically_downward_with_exception(
            self._overview_body(), "docs/architecture/hld/overview.md")

    def test_c4_component_md_never_automatically_downward_exception(self):
        self._assert_never_automatically_downward_with_exception(
            self._c4_component_body(), "docs/architecture/hld/c4-component.md")

    def test_reflection_md_never_automatically_downward_exception(self):
        self._assert_never_automatically_downward_with_exception(
            self._reflection_body(), "docs/requirements/reflection.md")


class TestMidFlightEscalationContract(unittest.TestCase):
    """MAR-57 Spec 04 (AC-3, AC-6, AC-7, AC-8): pin the mid-flight escalation
    contract in docs/requirements/skills.md.

    Doc-assertion tests reading skills.md and verifying the standing contract
    is present. RED before the 'Mid-flight lane escalation' subsection is added;
    GREEN after.
    """

    def _skills_md_path(self):
        return os.path.join(REPO_ROOT, "docs", "requirements", "skills.md")

    def _body(self):
        return read(self._skills_md_path())

    # --- AC-6: exactly three triggers, each enumerated ---

    def test_skills_md_contains_escalation_trigger_a(self):
        """AC-6: skills.md must enumerate trigger (a) — verifier finding signaling
        higher stakes/size."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(verifier finding.{0,100}(higher|stakes|size)|"
                r"finding.{0,60}(higher.{0,30}(stakes|size)|stakes|size))",
                body),
            "skills.md must enumerate trigger (a): verifier finding signaling "
            "higher stakes/size (MAR-57 AC-6)")

    def test_skills_md_contains_escalation_trigger_b(self):
        """AC-6: skills.md must enumerate trigger (b) — high_stakes_paths glob match."""
        body = self._body()
        self.assertIn(
            "high_stakes_paths", body,
            "skills.md must enumerate trigger (b): high_stakes_paths glob match "
            "(MAR-57 AC-6)")

    def test_skills_md_contains_escalation_trigger_c(self):
        """AC-6: skills.md must enumerate trigger (c) — explicit user/agent escalation
        request."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(explicit.{0,60}(user|agent).{0,60}(escalat|request)|"
                r"user.{0,40}agent.{0,60}escalat)",
                body),
            "skills.md must enumerate trigger (c): explicit user/agent escalation "
            "request (MAR-57 AC-6)")

    def test_skills_md_trigger_set_is_exactly_three(self):
        """AC-6: skills.md must enumerate exactly triggers (a), (b), (c) in the
        escalation section — no fourth trigger listed."""
        body = self._body()
        # Find the escalation subsection
        section_match = re.search(
            r"(?i)mid.?flight.{0,20}(lane.{0,20}escalation|escalation)", body)
        self.assertIsNotNone(
            section_match,
            "skills.md must have a mid-flight escalation section (MAR-57 AC-6)")
        section_start = section_match.start()
        # Take up to 3000 chars after the section heading
        section = body[section_start:section_start + 3000]
        # Exactly three labeled triggers (a), (b), (c) in the trigger list
        trigger_labels = re.findall(r"\(([abc])\)", section)
        for label in ("a", "b", "c"):
            self.assertIn(
                label, trigger_labels,
                "skills.md escalation section must label trigger (%s) (MAR-57 AC-6)" % label)
        # Must not list a (d) trigger
        self.assertNotIn(
            "d", trigger_labels,
            "skills.md escalation section must NOT list a fourth trigger (d) "
            "(MAR-57 AC-6 — bounded trigger set)")

    # --- AC-3/AC-8: upward-only automatic escalation ---

    def test_skills_md_upward_only_contract(self):
        """AC-3/AC-8: skills.md must state the upward-only automatic escalation contract."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(upward.only|upward only|only.{0,30}rais|automatically escalat|"
                r"automatic.{0,30}escalat)",
                body),
            "skills.md must state upward-only automatic escalation contract "
            "(MAR-57 AC-3/AC-8)")

    # --- AC-3: negative guarantee (no automatic downgrade) ---

    def test_skills_md_negative_guarantee(self):
        """AC-3: skills.md must state that no automatic/unattended code path lowers
        the lane or authoritative axes below a user-confirmed value."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(never automatic|no automatic.{0,60}(lower|lowers|de.escalat)|"
                r"automatic.{0,30}(never|not|never).{0,60}(lower|lowers)|"
                r"negative guarantee|automatic.{0,50}silent)",
                body),
            "skills.md must state the negative guarantee: no automatic/unattended "
            "path lowers the lane or axes below a user-confirmed value (MAR-57 AC-3)")

    # --- AC-3/AC-8: user-confirmed-only de-escalation + interactive downgrade deferred ---

    def test_skills_md_user_confirmed_only_de_escalation(self):
        """AC-3/AC-8: skills.md must state that de-escalation requires explicit user
        confirmation and that interactive downgrade is deferred."""
        body = self._body()
        # Must state user confirmation required for de-escalation
        self.assertIsNotNone(
            re.search(
                r"(?i)(de.escalat.{0,100}(user.confirm|explicit.confirm|explicit.user)|"
                r"(user.confirm|explicit).{0,100}de.escalat|"
                r"lower.{0,60}user.confirm)",
                body),
            "skills.md must state de-escalation requires explicit user confirmation "
            "(MAR-57 AC-3/AC-8)")
        # Must state the interactive downgrade command is deferred
        self.assertIsNotNone(
            re.search(
                r"(defer|deferred|out.of.scope).{0,200}(downgrade|de.escalat|interactiv)|"
                r"(downgrade|de.escalat|interactiv).{0,200}(defer|deferred|out.of.scope)",
                body, re.IGNORECASE | re.DOTALL),
            "skills.md must state the interactive downgrade command is deferred "
            "(MAR-57 AC-3/AC-8)")

    # --- AC-5/AC-8: stage re-introduction mentioned ---

    def test_skills_md_stage_reintroduction_mentioned(self):
        """AC-5/AC-8: skills.md must mention stage re-introduction (picking up
        create-spec rigor on fast-lane escalation)."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(stage re.?introduc|re.?introduc.{0,60}(stage|create.spec)|"
                r"create.spec.{0,100}(rigor|skip|pick.?up)|"
                r"fast.lane.{0,200}escalat.{0,200}create.spec)",
                body, re.DOTALL),
            "skills.md must mention stage re-introduction (picking up create-spec "
            "rigor on fast-lane escalation) (MAR-57 AC-5/AC-8)")

    # --- AC-8: sibling behaviors MAR-59 / MAR-60 stated unchanged ---

    def test_skills_md_mar59_fold_unchanged(self):
        """AC-8: skills.md must state that the fast-lane fold (MAR-59) is unchanged
        for non-escalating tickets."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(MAR.59|fast.lane fold|fast.?lane.{0,60}fold)"
                r".{0,300}(unchanged|unaffected|not changed|intact)|"
                r"(unchanged|unaffected|not changed).{0,300}(MAR.59|fast.lane fold)",
                body, re.DOTALL),
            "skills.md must state the fast-lane fold (MAR-59) is unchanged for "
            "non-escalating tickets (MAR-57 AC-8)")

    def test_skills_md_mar60_apply_tier_unchanged(self):
        """AC-8: skills.md must state that apply-tier inlining (MAR-60) is unchanged."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(MAR.60|apply.tier).{0,300}(unchanged|unaffected|not changed|intact)|"
                r"(unchanged|unaffected|not changed).{0,300}(MAR.60|apply.tier)",
                body, re.DOTALL),
            "skills.md must state apply-tier inlining (MAR-60) is unchanged "
            "(MAR-57 AC-8)")

    # --- AC-6: routing always via derive_lane ---

    def test_skills_md_derive_lane_as_single_authority(self):
        """AC-6: skills.md must state routing always via derive_lane (no caller
        re-implements routing)."""
        body = self._body()
        self.assertIn(
            "derive_lane", body,
            "skills.md must reference derive_lane as the single routing authority "
            "(MAR-57 AC-6)")


class TestAdr0042D4Section(unittest.TestCase):
    """MAR-107 (AC-5): pin the additive D4 section appended to
    docs/adr/0042-dynamic-mid-flight-lane-correctness.md. The ADR's own text
    defers D4 (:22-23); this class asserts the deferred section now exists."""

    def _adr_path(self):
        return os.path.join(REPO_ROOT, "docs", "adr",
                            "0042-dynamic-mid-flight-lane-correctness.md")

    def _adr_body(self):
        return read(self._adr_path())

    def test_adr_0042_has_d4_heading_naming_reselection_and_stage_reentry(self):
        """AC-5: docs/adr/0042 must contain a '### D4' heading naming
        verify_depth re-selection and stage re-entry."""
        body = self._adr_body()
        self.assertIsNotNone(
            re.search(r"(?i)### D4.{0,120}(verify_depth|re.selection).{0,120}"
                      r"(stage.re.entry|re.introduc)",
                      body, re.DOTALL),
            "docs/adr/0042 must contain a '### D4' heading naming "
            "verify_depth re-selection and stage re-entry (MAR-107 AC-5)")

    def test_adr_0042_d4_records_option_a_chosen(self):
        """AC-5: the D4 section must state Option A was chosen (formalize the
        shipped detection point unchanged)."""
        body = self._adr_body()
        d4_start = body.find("### D4")
        self.assertGreater(d4_start, -1, "### D4 heading must exist")
        d4_section = body[d4_start:]
        self.assertIsNotNone(
            re.search(r"(?i)option a.{0,300}(unchanged|formaliz)|"
                      r"(unchanged|formaliz).{0,300}option a",
                      d4_section, re.DOTALL),
            "docs/adr/0042 D4 section must record Option A chosen "
            "(formalize the shipped detection point unchanged) (MAR-107 AC-5)")


class TestReflectionMdEscalationCeiling(unittest.TestCase):
    """MAR-57 Spec 04 (AC-1, AC-7, AC-8): pin the in-loop ceiling-raise contract
    in docs/requirements/reflection.md.

    Doc-assertion tests reading reflection.md and verifying the escalation
    ceiling-raise prose is present and invariants are retained. RED before the
    ADD-only ceiling-raise paragraph is added; GREEN after.
    """

    def _reflection_md_path(self):
        return os.path.join(REPO_ROOT, "docs", "requirements", "reflection.md")

    def _body(self):
        return read(self._reflection_md_path())

    def test_reflection_md_exists_at_expected_path(self):
        """AC-8: docs/requirements/reflection.md must exist at the expected path."""
        self.assertTrue(
            os.path.isfile(self._reflection_md_path()),
            "docs/requirements/reflection.md must exist (MAR-57 AC-8)")

    def test_reflection_md_in_loop_ceiling_raise(self):
        """AC-8/AC-1: reflection.md must describe the in-loop ceiling raise on
        escalation (e.g. 'escalation', 'mid-run', 'ceiling' adjustment, or monotone raise)."""
        body = self._body()
        self.assertIsNotNone(
            re.search(
                r"(?i)(escalat.{0,200}(ceiling|ceiling raise|mid.run|in.loop|raise)|"
                r"ceiling.{0,200}(raise|escalat|mid.run)|"
                r"mid.run.{0,100}ceiling|in.loop.{0,100}ceiling)",
                body, re.DOTALL),
            "reflection.md must describe the in-loop ceiling raise on escalation "
            "(MAR-57 AC-8/AC-1)")

    def test_reflection_md_invariants_preserved(self):
        """AC-7: reflection.md must retain language about absolute invariants
        (verifier always runs; TDD/coverage gate immutable) — the existing
        invariant text is not removed or weakened by this spec's edit."""
        body = self._body()
        # Check both invariants are still stated
        self.assertIn(
            "Absolute invariants", body,
            "reflection.md must retain the 'Absolute invariants' block "
            "(MAR-57 AC-7 — ADD-only, must not remove)")
        self.assertIsNotNone(
            re.search(r"(?i)(verifier.{0,60}(always runs|every lane)|every lane.{0,60}verifier)",
                      body),
            "reflection.md must retain 'verifier always runs in every lane' invariant "
            "(MAR-57 AC-7)")
        self.assertIsNotNone(
            re.search(r"(?i)(TDD.{0,60}coverage.{0,60}(gate|immutable|never trimmed)|"
                      r"coverage.{0,60}gate.{0,60}(immutable|never trimmed|full))",
                      body),
            "reflection.md must retain 'TDD/coverage gate immutable' invariant "
            "(MAR-57 AC-7)")

    # --- MAR-107 D4 AC-6: names the detection point + fold-boundary re-entry ---

    def test_reflection_md_names_d4_detection_point_and_fold_boundary_reentry(self):
        """MAR-107 AC-6: the mid-flight ceiling-raise paragraph must name the
        iteration-start detection point and the fold-boundary stage re-entry
        in D4 terms. Does not edit test_reflection_md_in_loop_ceiling_raise or
        test_reflection_md_invariants_preserved (both remain unchanged)."""
        body = self._body()
        self.assertIsNotNone(
            re.search(r"(?i)detection point", body),
            "reflection.md must name the iteration-start 'detection point' "
            "(MAR-107 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?i)fold.boundary.{0,200}(re.entry|re.introduc)|"
                      r"(re.entry|re.introduc).{0,200}fold.boundary",
                      body, re.DOTALL),
            "reflection.md must name the fold-boundary stage re-entry "
            "(MAR-107 AC-6)")


class TestClarifyBatchingContract(unittest.TestCase):
    """MAR-61 (spec 03): pin the grouped-ask clarify-batching contract across
    all 9 hooked coordinator skill bodies and the cross-cutting requirements.
    Additive existence/co-occurrence assertions only — they enforce AC-7
    so a future edit that drops the grouped-ask prose fails CI."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def test_grouped_ask_present_in_all_hooked_skills(self):
        for name in HOOKED_SKILLS:
            body = read(self.skill_path(name))
            # Co-occurrence: "ONE grouped" near "interaction" (may span a line
            # break). re.DOTALL so "." crosses newlines — same discipline as
            # the MAR-47 co-occurrence tests (test_skill_contracts.py:289-292).
            self.assertIsNotNone(
                re.search(
                    r"(?i)(ONE grouped[\s\S]{0,50}interaction"
                    r"|grouped[\s\S]{0,50}interaction"
                    r"|single[\s\S]{0,80}interaction[\s\S]{0,80}question)",
                    body),
                "%s: SKILL.md must document presenting >=2 open clarifications in "
                "ONE grouped interaction (MAR-61 AC-7)" % name)

    def test_per_question_ledger_entry_documented_in_all_hooked_skills(self):
        for name in HOOKED_SKILLS:
            body = read(self.skill_path(name))
            # Co-occurrence: "each answer" near "clarify.py" or "per question"
            # near "clarify.py", or "one C-<n>" phrasing.
            self.assertIsNotNone(
                re.search(
                    r"(?i)(each answer.*clarify\.py|per question.*clarify\.py"
                    r"|clarify\.py.*per question|one `C-"
                    r"|each.*own.*clarify\.py|clarify\.py add.*per question"
                    r"|Record each answer)",
                    body, re.DOTALL),
                "%s: SKILL.md must document recording each answer as its own "
                "clarify.py ledger entry (MAR-61 AC-7)" % name)

    def test_no_auto_answer_documented_in_all_hooked_skills(self):
        for name in HOOKED_SKILLS:
            body = read(self.skill_path(name))
            # The prose must mention that questions are not skipped/merged/
            # auto-answered outside the assumption rule.
            self.assertIsNotNone(
                re.search(
                    r"(?i)(never skip|never.*merge|never.*auto.?answer"
                    r"|not.*skip.*question|outside.*assumption)",
                    body),
                "%s: SKILL.md must document not skipping/merging/auto-answering "
                "questions outside the assumption rule (MAR-61 AC-7)" % name)

    def test_skills_requirements_doc_carries_grouped_ask_rule(self):
        path = os.path.join(REPO_ROOT, "docs", "requirements", "skills.md")
        body = read(path)
        self.assertIsNotNone(
            re.search(
                r"(?i)(grouped interaction|ONE grouped|one.*interaction.*question"
                r"|grouped.*clarif)",
                body),
            "docs/requirements/skills.md must document the grouped-ask rule "
            "(MAR-61 AC-7)")




class TestDocSyncAuthoringContract(unittest.TestCase):
    """MAR-65 Spec 01 (AC-1, AC-2, AC-4, AC-7): pin the doc-sync authoring contract
    that extends Execute step 4 to reconcile FACTUAL claims in prd.md/roadmap.md
    and flag (never rewrite) intent divergence. Additive assertions only —
    no existing assertion modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def _code_body(self):
        return read(self.skill_path("code"))

    def _executor_body(self):
        return read(self.agent_path("code", "executor"))

    def _planner_body(self):
        return read(self.agent_path("code", "planner"))

    # --- AC-1: prd.md and roadmap.md named in SKILL.md step 4 ---

    def test_skill_step4_names_prd_md(self):
        """AC-1: code/SKILL.md must name prd.md within 2000 chars of the step-4 'part of
        the change' clause (the doc-update step heading)."""
        body = self._code_body()
        # Find the step-4 occurrence: 'Update the docs' is the unique step-4 heading.
        anchor = body.find("**Update the docs")
        self.assertGreater(anchor, 0,
                           "code/SKILL.md must contain '**Update the docs' step-4 heading")
        window = body[anchor:anchor + 2000]
        self.assertIn("prd.md", window,
                      "code/SKILL.md must name prd.md within 2000 chars of step-4 heading "
                      "(MAR-65 AC-1)")

    def test_skill_step4_names_roadmap_md(self):
        """AC-1: code/SKILL.md must name roadmap.md within 2000 chars of the step-4
        'Update the docs' heading."""
        body = self._code_body()
        anchor = body.find("**Update the docs")
        self.assertGreater(anchor, 0,
                           "code/SKILL.md must contain '**Update the docs' step-4 heading")
        window = body[anchor:anchor + 2000]
        self.assertIn("roadmap.md", window,
                      "code/SKILL.md must name roadmap.md within 2000 chars of step-4 heading "
                      "(MAR-65 AC-1)")

    def test_executor_step4_names_prd_md(self):
        """AC-1: code-executor.md must name prd.md in the step 4 block."""
        body = self._executor_body()
        self.assertIn("prd.md", body,
                      "code-executor.md must name prd.md in step 4 (MAR-65 AC-1)")

    def test_executor_step4_names_roadmap_md(self):
        """AC-1: code-executor.md must name roadmap.md in the step 4 block."""
        body = self._executor_body()
        self.assertIn("roadmap.md", body,
                      "code-executor.md must name roadmap.md in step 4 (MAR-65 AC-1)")

    def test_planner_docmap_names_prd_md(self):
        """AC-1: code-planner.md doc-map section must name prd.md."""
        body = self._planner_body()
        self.assertIn("prd.md", body,
                      "code-planner.md must name prd.md in the doc-map section (MAR-65 AC-1)")

    def test_planner_docmap_names_roadmap_md(self):
        """AC-1: code-planner.md doc-map section must name roadmap.md."""
        body = self._planner_body()
        self.assertIn("roadmap.md", body,
                      "code-planner.md must name roadmap.md in the doc-map section (MAR-65 AC-1)")

    # --- AC-2: intent-flag-never-rewrite rule ---

    def test_skill_flag_intent_co_occurrence(self):
        """AC-2: code/SKILL.md must have 'flag'/'FLAGS' co-occurring with 'intent'
        within 500 chars."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)(flag|FLAGS).{0,500}intent|intent.{0,500}(flag|FLAGS)", body, re.DOTALL),
            "code/SKILL.md must co-locate flag/FLAGS and intent within 500 chars (MAR-65 AC-2)")

    def test_skill_never_rewrite_intent(self):
        """AC-2: code/SKILL.md must carry 'never'/'NEVER' near 'rewrite' near 'intent'."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)(never|NEVER).{0,200}rewrite.{0,200}intent|"
                      r"intent.{0,200}(never|NEVER).{0,200}rewrite|"
                      r"(never|NEVER).{0,200}rewrite", body, re.DOTALL),
            "code/SKILL.md must carry never/NEVER near rewrite (MAR-65 AC-2)")

    def test_skill_intent_flag_names_result_document(self):
        """AC-2: code/SKILL.md must name 'result document' as the flag destination."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)result.{0,20}document", body),
            "code/SKILL.md must name 'result document' as intent-flag destination "
            "(MAR-65 AC-2)")

    def test_skill_intent_flag_names_pr_body(self):
        """AC-2: code/SKILL.md must name 'PR body' as the flag destination."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)PR.{0,10}body|pull.request.{0,10}body", body),
            "code/SKILL.md must name 'PR body' as intent-flag destination (MAR-65 AC-2)")

    def test_executor_never_rewrite_intent(self):
        """AC-2: code-executor.md must carry never/rewrite/intent co-occurrence."""
        body = self._executor_body()
        self.assertIsNotNone(
            re.search(r"(?i)(never|NEVER).{0,200}rewrite|rewrite.{0,200}(never|NEVER)",
                      body, re.DOTALL),
            "code-executor.md must carry never/NEVER near rewrite (MAR-65 AC-2)")

    # --- AC-4: factual/intent boundary with concrete examples ---

    def test_skill_factual_term_agent_counts(self):
        """AC-4: code/SKILL.md must name agent/subagent counts as a factual item."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)(agent.subagent.counts|agent counts|subagent counts)", body),
            "code/SKILL.md must name 'agent/subagent counts' as a factual item (MAR-65 AC-4)")

    def test_skill_factual_term_shipped_vs_planned(self):
        """AC-4: code/SKILL.md must name shipped-vs-planned status as a factual item."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)(shipped.vs.planned|shipped vs planned)", body),
            "code/SKILL.md must name 'shipped-vs-planned' as a factual item (MAR-65 AC-4)")

    def test_skill_factual_term_topology(self):
        """AC-4: code/SKILL.md must name topology as a factual item."""
        body = self._code_body()
        self.assertIn("topology", body,
                      "code/SKILL.md must name 'topology' as a factual item (MAR-65 AC-4)")

    def test_skill_factual_term_version(self):
        """AC-4: code/SKILL.md must name version numbers as a factual item."""
        body = self._code_body()
        self.assertIn("version", body,
                      "code/SKILL.md must name 'version' as a factual item (MAR-65 AC-4)")

    def test_skill_intent_term_goals(self):
        """AC-4: code/SKILL.md must name goals as an intent item."""
        body = self._code_body()
        self.assertIn("goals", body,
                      "code/SKILL.md must name 'goals' as an intent item (MAR-65 AC-4)")

    def test_skill_intent_term_nfr(self):
        """AC-4: code/SKILL.md must name NFR/non-functional as an intent item."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)(NFR|non-functional)", body),
            "code/SKILL.md must name 'NFR'/'non-functional' as an intent item (MAR-65 AC-4)")

    def test_skill_intent_term_scope(self):
        """AC-4: code/SKILL.md must name scope as an intent item."""
        body = self._code_body()
        self.assertIn("scope", body,
                      "code/SKILL.md must name 'scope' as an intent item (MAR-65 AC-4)")

    def test_skill_intent_term_vision(self):
        """AC-4: code/SKILL.md must name vision as an intent item."""
        body = self._code_body()
        self.assertIn("vision", body,
                      "code/SKILL.md must name 'vision' as an intent item (MAR-65 AC-4)")

    def test_executor_factual_term_agent_counts(self):
        """AC-4: code-executor.md must name agent/subagent counts as a factual item."""
        body = self._executor_body()
        self.assertIsNotNone(
            re.search(r"(?i)(agent.subagent.counts|agent counts|subagent counts)", body),
            "code-executor.md must name 'agent/subagent counts' as a factual item "
            "(MAR-65 AC-4)")

    def test_executor_factual_term_shipped_vs_planned(self):
        """AC-4: code-executor.md must name shipped-vs-planned status as a factual item."""
        body = self._executor_body()
        self.assertIsNotNone(
            re.search(r"(?i)(shipped.vs.planned|shipped vs planned)", body),
            "code-executor.md must name 'shipped-vs-planned' as a factual item (MAR-65 AC-4)")

    def test_executor_factual_term_topology(self):
        """AC-4: code-executor.md must name topology as a factual item."""
        body = self._executor_body()
        self.assertIn("topology", body,
                      "code-executor.md must name 'topology' as a factual item (MAR-65 AC-4)")

    def test_executor_intent_term_goals(self):
        """AC-4: code-executor.md must name goals as an intent item."""
        body = self._executor_body()
        self.assertIn("goals", body,
                      "code-executor.md must name 'goals' as an intent item (MAR-65 AC-4)")

    def test_executor_intent_term_nfr(self):
        """AC-4: code-executor.md must name NFR/non-functional as an intent item."""
        body = self._executor_body()
        self.assertIsNotNone(
            re.search(r"(?i)(NFR|non-functional)", body),
            "code-executor.md must name 'NFR'/'non-functional' as an intent item "
            "(MAR-65 AC-4)")

    def test_executor_intent_term_vision(self):
        """AC-4: code-executor.md must name vision as an intent item."""
        body = self._executor_body()
        self.assertIn("vision", body,
                      "code-executor.md must name 'vision' as an intent item (MAR-65 AC-4)")

    # --- AC-7: regression guard (existing path tokens still present) ---

    def test_skill_step4_still_has_requirements_path(self):
        """AC-7: code/SKILL.md step-4 block must still reference requirements_path."""
        body = self._code_body()
        self.assertIn("requirements_path", body,
                      "code/SKILL.md must still reference requirements_path in step 4 "
                      "(MAR-65 AC-7 regression guard)")

    def test_skill_step4_still_has_architecture_path(self):
        """AC-7: code/SKILL.md step-4 block must still reference architecture_path."""
        body = self._code_body()
        self.assertIn("architecture_path", body,
                      "code/SKILL.md must still reference architecture_path in step 4 "
                      "(MAR-65 AC-7 regression guard)")

    def test_skill_step4_still_has_adr_path(self):
        """AC-7: code/SKILL.md step-4 block must still reference adr_path."""
        body = self._code_body()
        self.assertIn("adr_path", body,
                      "code/SKILL.md must still reference adr_path in step 4 "
                      "(MAR-65 AC-7 regression guard)")

    def test_executor_still_has_requirements_path(self):
        """AC-7: code-executor.md must still reference requirements_path."""
        body = self._executor_body()
        self.assertIn("requirements_path", body,
                      "code-executor.md must still reference requirements_path "
                      "(MAR-65 AC-7 regression guard)")

    def test_executor_still_has_architecture_path(self):
        """AC-7: code-executor.md must still reference architecture_path."""
        body = self._executor_body()
        self.assertIn("architecture_path", body,
                      "code-executor.md must still reference architecture_path "
                      "(MAR-65 AC-7 regression guard)")

    def test_executor_still_has_adr_path(self):
        """AC-7: code-executor.md must still reference adr_path."""
        body = self._executor_body()
        self.assertIn("adr_path", body,
                      "code-executor.md must still reference adr_path "
                      "(MAR-65 AC-7 regression guard)")


class TestVerifierProductDocConsistency(unittest.TestCase):
    """MAR-65 Spec 02 (AC-3, AC-6): pin the product-doc-consistency check in the
    Documentation dimension of SKILL.md (Verify section) and code-verifier.md.
    Additive assertions only — no existing assertion modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def _code_body(self):
        return read(self.skill_path("code"))

    def _verifier_body(self):
        return read(self.agent_path("code", "verifier"))

    # --- AC-3: product-doc-consistency check in SKILL.md Verify / Documentation dimension ---

    def test_skill_verify_documentation_names_prd_md(self):
        """AC-3: prd.md must appear in SKILL.md within 2000 chars of the Verify
        'Documentation' dimension heading."""
        body = self._code_body()
        anchor = body.find("**Documentation**")
        self.assertGreater(anchor, 0,
                           "code/SKILL.md must contain '**Documentation**' in Verify section")
        window = body[anchor:anchor + 2000]
        self.assertIn("prd.md", window,
                      "code/SKILL.md Verify/Documentation dimension must name prd.md "
                      "(MAR-65 AC-3)")

    def test_skill_verify_documentation_names_roadmap_md(self):
        """AC-3: roadmap.md must appear in SKILL.md within 2000 chars of the Verify
        'Documentation' dimension heading."""
        body = self._code_body()
        anchor = body.find("**Documentation**")
        self.assertGreater(anchor, 0,
                           "code/SKILL.md must contain '**Documentation**' in Verify section")
        window = body[anchor:anchor + 2000]
        self.assertIn("roadmap.md", window,
                      "code/SKILL.md Verify/Documentation dimension must name roadmap.md "
                      "(MAR-65 AC-3)")

    def test_skill_blocking_factual_co_occurrence(self):
        """AC-3: code/SKILL.md must co-locate 'blocking' and 'factual'/'stale'
        within 500 chars."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)blocking.{0,500}(factual|stale)|(factual|stale).{0,500}blocking",
                      body, re.DOTALL),
            "code/SKILL.md must co-locate 'blocking' and 'factual'/'stale' within 500 chars "
            "(MAR-65 AC-3 — stale factual claim produces blocking finding)")

    def test_skill_flagged_intent_co_occurrence(self):
        """AC-3: code/SKILL.md must co-locate 'flagged' and 'intent' within 500 chars."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(r"(?i)flagged.{0,500}intent|intent.{0,500}flagged", body, re.DOTALL),
            "code/SKILL.md must co-locate 'flagged' and 'intent' within 500 chars "
            "(MAR-65 AC-3 — intent contradiction produces flagged divergence, not a block)")

    def test_verifier_documentation_names_prd_md(self):
        """AC-3: code-verifier.md must name prd.md in the Documentation dimension."""
        body = self._verifier_body()
        self.assertIn("prd.md", body,
                      "code-verifier.md must name prd.md in Documentation dimension "
                      "(MAR-65 AC-3)")

    def test_verifier_documentation_names_roadmap_md(self):
        """AC-3: code-verifier.md must name roadmap.md in the Documentation dimension."""
        body = self._verifier_body()
        self.assertIn("roadmap.md", body,
                      "code-verifier.md must name roadmap.md in Documentation dimension "
                      "(MAR-65 AC-3)")

    def test_verifier_blocking_factual_co_occurrence(self):
        """AC-3: code-verifier.md must co-locate 'blocking' and 'factual'/'stale'
        within 500 chars."""
        body = self._verifier_body()
        self.assertIsNotNone(
            re.search(r"(?i)blocking.{0,500}(factual|stale)|(factual|stale).{0,500}blocking",
                      body, re.DOTALL),
            "code-verifier.md must co-locate 'blocking' and 'factual'/'stale' within 500 chars "
            "(MAR-65 AC-3)")

    def test_verifier_flagged_intent_co_occurrence(self):
        """AC-3: code-verifier.md must co-locate 'flagged'/'flagging' and 'intent' within 500
        chars."""
        body = self._verifier_body()
        self.assertIsNotNone(
            re.search(r"(?i)(flagged|flagging).{0,500}intent|intent.{0,500}(flagged|flagging)",
                      body, re.DOTALL),
            "code-verifier.md must co-locate 'flagged'/'flagging' and 'intent' within 500 chars "
            "(MAR-65 AC-3 — intent contradiction is flagged, not blocking)")

    # --- AC-6: docs_only relaxation prose intact (regression guard) ---

    def test_skill_docs_only_present(self):
        """AC-6: 'docs_only' must appear in code/SKILL.md (the relaxation block)."""
        body = self._code_body()
        self.assertIn("docs_only", body,
                      "code/SKILL.md must contain 'docs_only' (docs_only relaxation block) "
                      "(MAR-65 AC-6 regression guard)")

    def test_skill_every_other_dimension_documentation_consistency(self):
        """AC-6: 'every other dimension' must co-occur with 'Documentation consistency'
        within 300 chars in code/SKILL.md."""
        body = self._code_body()
        self.assertIsNotNone(
            re.search(
                r"(?i)every other dimension.{0,300}Documentation consistency|"
                r"Documentation consistency.{0,300}every other dimension",
                body, re.DOTALL),
            "code/SKILL.md must co-locate 'every other dimension' and "
            "'Documentation consistency' within 300 chars (MAR-65 AC-6 regression guard)")


class TestAdr0007Amendment(unittest.TestCase):
    """MAR-65 Spec 03 (AC-5): pin the ADR-0007 amendment that extends the
    induction loop to factual prd/roadmap content. Additive assertions only."""

    def _adr_path(self):
        return os.path.join(REPO_ROOT, "docs", "adr", "0007-living-docs-by-induction.md")

    def _adr_index_path(self):
        return os.path.join(REPO_ROOT, "docs", "adr", "README.md")

    def _adr_body(self):
        return read(self._adr_path())

    def _index_body(self):
        return read(self._adr_index_path())

    # --- AC-5: ADR-0007 names factual prd/roadmap content ---

    def test_adr_names_prd_md(self):
        """AC-5: docs/adr/0007 must contain 'prd.md'."""
        body = self._adr_body()
        self.assertIn("prd.md", body,
                      "docs/adr/0007-living-docs-by-induction.md must contain 'prd.md' "
                      "(MAR-65 AC-5 — extended scope)")

    def test_adr_names_roadmap_md(self):
        """AC-5: docs/adr/0007 must contain 'roadmap.md'."""
        body = self._adr_body()
        self.assertIn("roadmap.md", body,
                      "docs/adr/0007-living-docs-by-induction.md must contain 'roadmap.md' "
                      "(MAR-65 AC-5 — extended scope)")

    def test_adr_factual_prd_co_occurrence(self):
        """AC-5: 'factual' must co-occur with 'prd' within 500 chars in ADR-0007."""
        body = self._adr_body()
        self.assertIsNotNone(
            re.search(r"(?i)factual.{0,500}prd|prd.{0,500}factual", body, re.DOTALL),
            "docs/adr/0007 must co-locate 'factual' and 'prd' within 500 chars "
            "(MAR-65 AC-5 — factual scope extension recorded)")

    def test_adr_intent_flag_co_occurrence(self):
        """AC-5: 'intent' must co-occur with 'flag'/'FLAGS' within 500 chars in ADR-0007."""
        body = self._adr_body()
        self.assertIsNotNone(
            re.search(r"(?i)intent.{0,500}(flag|FLAGS)|(flag|FLAGS).{0,500}intent",
                      body, re.DOTALL),
            "docs/adr/0007 must co-locate 'intent' and 'flag'/'FLAGS' within 500 chars "
            "(MAR-65 AC-5 — intent-flag rule recorded)")

    def test_adr_status_still_accepted(self):
        """AC-5: ADR-0007 status must remain 'Accepted'."""
        body = self._adr_body()
        self.assertIn("Accepted", body,
                      "docs/adr/0007 status must remain 'Accepted' (MAR-65 AC-5)")

    # --- AC-5: ADR index consistent ---

    def test_adr_index_has_0007_entry(self):
        """AC-5: docs/adr/README.md must contain '0007'."""
        body = self._index_body()
        self.assertIn("0007", body,
                      "docs/adr/README.md must contain '0007' entry (MAR-65 AC-5)")

    def test_adr_index_0007_mentions_product_or_prd(self):
        """AC-5: 'prd' or 'product' must appear within 200 chars of '0007' in
        docs/adr/README.md."""
        body = self._index_body()
        self.assertIsNotNone(
            re.search(r"(?i)0007.{0,200}(prd|product)|(prd|product).{0,200}0007",
                      body, re.DOTALL),
            "docs/adr/README.md must mention 'prd'/'product' within 200 chars of '0007' "
            "(MAR-65 AC-5 — index summary updated)")


class TestSimplicityScopeRestraintLayer(unittest.TestCase):
    """Pin the Simplicity First + Surgical Changes restraint layer across all
    three code agents, SKILL.md, the shared docs, and the CHANGELOG (MAR-2)."""

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def _executor(self):
        return read(self.agent_path("code", "executor"))

    def _planner(self):
        return read(self.agent_path("code", "planner"))

    def _verifier(self):
        return read(self.agent_path("code", "verifier"))

    def _skill(self):
        return read(self.skill_path("code"))

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def _reflection_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "reflection.md"))

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    # --- AC-1: executor carries Simplicity First ---

    def test_executor_simplicity_first_present(self):
        """AC-1: code-executor.md must contain 'Simplicity First'."""
        self.assertIn("Simplicity First", self._executor(),
                      "code-executor.md must contain 'Simplicity First' (MAR-2 AC-1)")

    def test_executor_simplicity_first_200_50(self):
        """AC-1: '200' and '50' must co-occur within 200 chars (the 200->50 rewrite heuristic)."""
        body = self._executor()
        self.assertIsNotNone(
            re.search(r"200.{0,200}50|50.{0,200}200", body, re.DOTALL),
            "code-executor.md must co-locate '200' and '50' within 200 chars (MAR-2 AC-1)")

    def test_executor_simplicity_first_senior_check(self):
        """AC-1: 'senior' or 'overcomplicated' must appear within 300 chars of
        'Simplicity First' (the senior-engineer check)."""
        body = self._executor()
        self.assertIsNotNone(
            re.search(
                r"(?i)Simplicity First.{0,300}(senior|overcomplicated)|"
                r"(senior|overcomplicated).{0,300}Simplicity First",
                body, re.DOTALL),
            "code-executor.md must co-locate 'senior'/'overcomplicated' within 300 chars "
            "of 'Simplicity First' (MAR-2 AC-1)")

    # --- AC-2: executor carries Surgical Changes ---

    def test_executor_surgical_changes_present(self):
        """AC-2: code-executor.md must contain 'Surgical Changes'."""
        self.assertIn("Surgical Changes", self._executor(),
                      "code-executor.md must contain 'Surgical Changes' (MAR-2 AC-2)")

    def test_executor_surgical_traces_to_spec(self):
        """AC-2: 'traces' or 'trace' must appear within 300 chars of 'Surgical'."""
        body = self._executor()
        self.assertIsNotNone(
            re.search(r"(?i)Surgical.{0,300}trac(e|es)|trac(e|es).{0,300}Surgical",
                      body, re.DOTALL),
            "code-executor.md must co-locate 'trace'/'traces' within 300 chars "
            "of 'Surgical' (MAR-2 AC-2)")

    def test_executor_surgical_no_adjacent_refactor(self):
        """AC-2: 'refactor' or 'reformat' must appear within 500 chars of
        'Surgical Changes'."""
        body = self._executor()
        self.assertIsNotNone(
            re.search(
                r"(?i)Surgical Changes.{0,500}(refactor|reformat)|"
                r"(refactor|reformat).{0,500}Surgical Changes",
                body, re.DOTALL),
            "code-executor.md must co-locate 'refactor'/'reformat' within 500 chars "
            "of 'Surgical Changes' (MAR-2 AC-2)")

    def test_executor_surgical_own_orphan(self):
        """AC-2: 'orphan' must appear within 500 chars of 'Surgical Changes'."""
        body = self._executor()
        self.assertIsNotNone(
            re.search(r"(?i)Surgical Changes.{0,500}orphan|orphan.{0,500}Surgical Changes",
                      body, re.DOTALL),
            "code-executor.md must co-locate 'orphan' within 500 chars "
            "of 'Surgical Changes' (MAR-2 AC-2)")

    # --- AC-3: planner carries minimal-surface / no-speculative-scope ---

    def test_planner_minimal_surface_present(self):
        """AC-3: code-planner.md must co-locate 'minimal' with 'surface' or a
        change-surface pattern."""
        body = self._planner()
        self.assertIsNotNone(
            re.search(r"(?i)minimal.{0,80}(surface|change surface)|"
                      r"(surface|change surface).{0,80}minimal",
                      body, re.DOTALL),
            "code-planner.md must co-locate 'minimal' and 'surface'/'change surface' "
            "(MAR-2 AC-3)")

    def test_planner_no_speculative_scope(self):
        """AC-3: 'speculative' must appear within 400 chars of 'minimal' in
        code-planner.md."""
        body = self._planner()
        self.assertIsNotNone(
            re.search(r"(?i)minimal.{0,400}speculative|speculative.{0,400}minimal",
                      body, re.DOTALL),
            "code-planner.md must co-locate 'speculative' within 400 chars "
            "of 'minimal' (MAR-2 AC-3)")

    # --- AC-4: verifier carries Simplicity & scope dimension, blocking ---

    def test_verifier_simplicity_scope_dimension_present(self):
        """AC-4: 'Simplicity' and 'scope' must co-occur within 50 chars in
        code-verifier.md (the dimension name)."""
        body = self._verifier()
        self.assertIsNotNone(
            re.search(r"(?i)Simplicity.{0,50}scope|scope.{0,50}Simplicity",
                      body, re.DOTALL),
            "code-verifier.md must co-locate 'Simplicity' and 'scope' within 50 chars "
            "(MAR-2 AC-4 — dimension name)")

    def test_verifier_simplicity_scope_overcomplication(self):
        """AC-4: 'overcompl' must appear within 500 chars of 'Simplicity' in
        code-verifier.md."""
        body = self._verifier()
        self.assertIsNotNone(
            re.search(r"(?i)Simplicity.{0,500}overcompl|overcompl.{0,500}Simplicity",
                      body, re.DOTALL),
            "code-verifier.md must co-locate 'overcompl' within 500 chars "
            "of 'Simplicity' (MAR-2 AC-4)")

    def test_verifier_simplicity_scope_out_of_scope(self):
        """AC-4: 'out-of-scope' or 'out of scope' must appear within 500 chars
        of 'Simplicity' in code-verifier.md."""
        body = self._verifier()
        self.assertIsNotNone(
            re.search(r"(?i)Simplicity.{0,500}out.of.scope|out.of.scope.{0,500}Simplicity",
                      body, re.DOTALL),
            "code-verifier.md must co-locate 'out-of-scope'/'out of scope' within 500 chars "
            "of 'Simplicity' (MAR-2 AC-4)")

    def test_verifier_simplicity_scope_blocking(self):
        """AC-4: 'blocking' must appear within 500 chars of 'Simplicity' in
        code-verifier.md."""
        body = self._verifier()
        self.assertIsNotNone(
            re.search(r"(?i)Simplicity.{0,500}blocking|blocking.{0,500}Simplicity",
                      body, re.DOTALL),
            "code-verifier.md must co-locate 'blocking' within 500 chars "
            "of 'Simplicity' (MAR-2 AC-4)")

    # --- AC-5: shared docs carry restraint-layer token ---

    def test_skills_md_simplicity_scope_present(self):
        """AC-5: docs/requirements/skills.md must co-locate 'Simplicity' and
        'scope' within 100 chars."""
        body = self._skills_req()
        self.assertIsNotNone(
            re.search(r"(?i)Simplicity.{0,100}scope|scope.{0,100}Simplicity",
                      body, re.DOTALL),
            "docs/requirements/skills.md must co-locate 'Simplicity' and 'scope' "
            "within 100 chars (MAR-2 AC-5)")

    def test_reflection_md_simplicity_scope_present(self):
        """AC-5: docs/requirements/reflection.md must co-locate 'Simplicity'
        and 'scope' within 100 chars."""
        body = self._reflection_req()
        self.assertIsNotNone(
            re.search(r"(?i)Simplicity.{0,100}scope|scope.{0,100}Simplicity",
                      body, re.DOTALL),
            "docs/requirements/reflection.md must co-locate 'Simplicity' and 'scope' "
            "within 100 chars (MAR-2 AC-5)")

    # --- AC-6: cross-agent — all three agents carry both rule names ---

    def test_all_three_agents_carry_simplicity_first(self):
        """AC-6: each of code-executor, code-planner, code-verifier must contain
        'Simplicity First'."""
        for role in ("executor", "planner", "verifier"):
            body = read(self.agent_path("code", role))
            self.assertIn("Simplicity First", body,
                          "code-%s.md must contain 'Simplicity First' (MAR-2 AC-6)" % role)

    def test_all_three_agents_carry_surgical_changes(self):
        """AC-6: each of code-executor, code-planner, code-verifier must contain
        'Surgical Changes'."""
        for role in ("executor", "planner", "verifier"):
            body = read(self.agent_path("code", role))
            self.assertIn("Surgical Changes", body,
                          "code-%s.md must contain 'Surgical Changes' (MAR-2 AC-6)" % role)

    # --- AC-7: MAR-2 has a CHANGELOG entry (in [Unreleased] before release,
    #     or a released [X.Y.Z] section once cut — anchored on the entry itself
    #     so a release that moves it out of [Unreleased] stays green) ---

    def test_changelog_unreleased_mar2_entry(self):
        """AC-7: a '(MAR-2)' entry must be documented in CHANGELOG.md."""
        body = self._changelog()
        self.assertIn(
            "(MAR-2)", body,
            "CHANGELOG.md must contain a '(MAR-2)' entry (MAR-2 AC-7)")

    def test_changelog_unreleased_restraint_layer_token(self):
        """AC-7: 'restraint' or 'Simplicity' must appear within 500 chars of the
        '(MAR-2)' CHANGELOG entry."""
        body = self._changelog()
        self.assertIsNotNone(
            re.search(
                r"(?i)\(MAR-2\).{0,500}(restraint|Simplicity)|"
                r"(restraint|Simplicity).{0,500}\(MAR-2\)",
                body, re.DOTALL),
            "CHANGELOG.md must contain 'restraint'/'Simplicity' within 500 chars "
            "of the '(MAR-2)' entry (MAR-2 AC-7)")


class TestSpecSimplicityGate(unittest.TestCase):
    """Pin the spec-time simplicity gate added to /acs:create-spec (MAR-88):
    the create-spec-planner evaluates each decomposition for a materially-
    simpler alternative meeting the same acceptance criteria and surfaces
    (never blocks) a finding to the user/spec owner for a decision. Mirrors
    the TestSimplicityScopeRestraintLayer (MAR-2) pattern, deconflicted from
    code-verifier dimension 12 (spec-time vs code-time simplicity, AC-7)."""

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def _planner(self):
        return read(self.agent_path("create-spec", "planner"))

    def _skill(self):
        return read(self.skill_path("create-spec"))

    def _verifier(self):
        return read(self.agent_path("create-spec", "verifier"))

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def _reflection_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "reflection.md"))

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    # --- AC-1 / AC-3: planner gate wording + spec-time placement ---

    def test_planner_gate_wording_present(self):
        """AC-1/AC-3: create-spec-planner.md must co-locate 'materially'
        (simpler) and 'same acceptance criteria' within a bounded window —
        passing only if the clause lives in the planner charter (spec-time
        placement, before any spec file is written)."""
        body = self._planner()
        self.assertIsNotNone(
            re.search(
                r"(?i)materially.{0,400}same acceptance criteria|"
                r"same acceptance criteria.{0,400}materially",
                body, re.DOTALL),
            "create-spec-planner.md must co-locate 'materially' and 'same "
            "acceptance criteria' within 400 chars (MAR-88 AC-1/AC-3)")

    # --- AC-3: SKILL.md documents the new question type ---

    def test_skill_documents_surface_question(self):
        """AC-3: create-spec SKILL.md Plan-phase section must co-locate
        'materially' and 'surface' (the planner may surface this question
        type through the existing User-interaction path)."""
        body = self._skill()
        self.assertIsNotNone(
            re.search(r"(?i)materially.{0,400}surface|surface.{0,400}materially",
                      body, re.DOTALL),
            "create-spec SKILL.md must co-locate 'materially' and 'surface' "
            "within 400 chars (MAR-88 AC-3)")

    # --- AC-4: requirements SoT coverage ---

    def test_skills_req_carries_gate(self):
        """AC-4: docs/requirements/skills.md's /create-spec block must
        co-locate 'materially' and 'surface'."""
        body = self._skills_req()
        self.assertIsNotNone(
            re.search(r"(?i)materially.{0,400}surface|surface.{0,400}materially",
                      body, re.DOTALL),
            "docs/requirements/skills.md must co-locate 'materially' and "
            "'surface' within 400 chars (MAR-88 AC-4)")

    def test_reflection_req_carries_deconfliction(self):
        """AC-4/AC-7: docs/requirements/reflection.md must co-locate
        'surface' and 'decision' (the spec-time-vs-code-time deconfliction
        clause)."""
        body = self._reflection_req()
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,400}decision|decision.{0,400}surface",
                      body, re.DOTALL),
            "docs/requirements/reflection.md must co-locate 'surface' and "
            "'decision' within 400 chars (MAR-88 AC-4/AC-7)")

    # --- AC-5: CHANGELOG entry ---

    def test_changelog_unreleased_mar88_entry(self):
        """AC-5: '(MAR-88)' must appear somewhere in CHANGELOG.md at/after
        '[Unreleased]' — uses the same section-slice technique as
        test_changelog_unreleased_mar101_entry rather than a fixed-width
        DOTALL bleed-through window: a raw '.{0,500}' budget is consumed by
        whatever [Unreleased] entries accumulate ahead of (MAR-88) as later
        tickets land (MAR-103 pushed the distance past 500 chars; not a
        weakening of intent, only of the fragile distance mechanism, same
        discovery as MAR-102's CHANGELOG test fix)."""
        body = self._changelog()
        unreleased_idx = body.find("[Unreleased]")
        self.assertNotEqual(unreleased_idx, -1, "CHANGELOG.md must carry an [Unreleased] heading")
        self.assertIn("(MAR-88)", body[unreleased_idx:],
                      "CHANGELOG.md must contain '(MAR-88)' at or after "
                      "'[Unreleased]' (MAR-88 AC-5)")

    # --- AC-2: SURFACE not BLOCK, scoped to the gate's own text window ---

    def test_gate_surface_decision_present(self):
        """AC-2: 'surface' and 'decision' framing must be present in the
        gate window in BOTH create-spec-planner.md and SKILL.md."""
        planner = self._planner()
        skill = self._skill()
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,400}decision|decision.{0,400}surface",
                      planner, re.DOTALL),
            "create-spec-planner.md must co-locate 'surface' and 'decision' "
            "within 400 chars (MAR-88 AC-2)")
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,400}decision|decision.{0,400}surface",
                      skill, re.DOTALL),
            "create-spec SKILL.md must co-locate 'surface' and 'decision' "
            "within 400 chars (MAR-88 AC-2)")

    # BLOCK-as-disposition framing: bare 'block'/'loopback'/'auto-reject', but
    # NOT the correct negated SURFACE-not-BLOCK phrasing ("never/not/nor
    # blocks") the gate's own description is expected to use to state its
    # disposition explicitly.
    _BLOCK_DISPOSITION_RE = re.compile(
        r"(?i)(?<!never )(?<!never-)(?<!not )(?<!nor )"
        r"\bblock(s|ed|ing)?\b|\bloopback\b|\bauto-reject\b")

    def test_gate_no_block_wording_in_window(self):
        """AC-2: 'block'/'loopback'/'auto-reject' framing (as the gate's own
        disposition, not the negated 'never blocks' SURFACE statement) must
        be ABSENT from the gate's own co-location window in
        create-spec-planner.md and in SKILL.md's Plan-phase section —
        window-scoped, NEVER whole-file, since both files legitimately use
        'block' elsewhere for unrelated concerns (verifier findings,
        escalation, handoff)."""
        planner = self._planner()
        match = re.search(
            r"(?i)materially.{0,400}same acceptance criteria|"
            r"same acceptance criteria.{0,400}materially",
            planner, re.DOTALL)
        self.assertIsNotNone(match, "planner gate window must exist to scope this check")
        window = planner[max(0, match.start() - 200):match.end() + 200]
        self.assertNotRegex(
            window, self._BLOCK_DISPOSITION_RE,
            "create-spec-planner.md gate window must not use 'block'/"
            "'loopback'/'auto-reject' as its own disposition (MAR-88 AC-2)")

        skill = self._skill()
        plan_phase = skill[skill.index("### Plan (per iteration)"):skill.index("### Execute (per iteration)")]
        skill_match = re.search(r"(?i)materially.{0,400}surface|surface.{0,400}materially",
                                 plan_phase, re.DOTALL)
        self.assertIsNotNone(skill_match, "SKILL.md Plan-phase gate window must exist to scope this check")
        skill_window = plan_phase[max(0, skill_match.start() - 200):skill_match.end() + 200]
        self.assertNotRegex(
            skill_window, self._BLOCK_DISPOSITION_RE,
            "create-spec SKILL.md Plan-phase gate window must not use 'block'/"
            "'loopback'/'auto-reject' as its own disposition (MAR-88 AC-2)")

    # --- AC-7: verifier dimension count unchanged (regression guard) ---

    def test_create_spec_verifier_still_four_dimensions(self):
        """AC-7/C-4: create-spec-verifier.md must still declare exactly four
        numbered dimensions, and no fifth/'spec-simplicity' dimension may be
        added — regression guard, green from the start."""
        body = self._verifier()
        dimensions = re.findall(r"^[0-9]+\.\s+\*\*", body, re.M)
        self.assertEqual(
            len(dimensions), 4,
            "create-spec-verifier.md must declare exactly 4 numbered "
            "dimensions (MAR-88 AC-7/C-4); found %d" % len(dimensions))
        self.assertNotIn(
            "spec-simplicity", body.lower(),
            "create-spec-verifier.md must not add a 'spec-simplicity' "
            "dimension (MAR-88 C-4 — planner-only scope)")


class TestReconcileTicketIssueLinkage(unittest.TestCase):
    """MAR-75 spec 02: pin the reconciliation prose contract (acs ticket id <->
    GitHub issue/PR) that spec 01 introduces across create-ticket, create-pr,
    merge-pr, and init, plus the three description templates and pr-default.md.
    Written TDD-first (RED before spec 01's SKILL.md/template edits land);
    turns GREEN once spec 01 is implemented. Additive only — no existing
    assertion in this file is modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def template_path(self, name):
        return os.path.join(PLUGIN, "templates", "%s.md" % name)

    def test_create_ticket_step5_embeds_acs_id_on_issue(self):
        """AC-1, AC-6 (prose proof): create-ticket/SKILL.md Step 5's github
        branch carries the acs-ticket-id-on-issue-body instruction co-occurring
        with `gh issue create`, and the three type description templates each
        contain the acs-id line rendered identically (`acs-ticket: {ticket_id}`)."""
        body = read(self.skill_path("create-ticket"))
        self.assertIsNotNone(
            re.search(r"(?s)gh issue create.{0,1200}acs-ticket:|acs-ticket:.{0,1200}gh issue create", body),
            "create-ticket/SKILL.md Step 5 must co-locate 'acs-ticket:' with "
            "'gh issue create' within a bounded window (MAR-75 AC-1)")
        for name in ("task-default", "story-default", "epic-default"):
            tmpl = read(self.template_path(name))
            self.assertIn("acs-ticket: {ticket_id}", tmpl,
                          "%s must carry the byte-identical 'acs-ticket: {ticket_id}' "
                          "line (MAR-75 AC-1, AC-6, R-3)" % name)

    def test_create_ticket_step5_fills_labels_assignee_milestone_fields(self):
        """AC-6 (prose proof): Step 5's github branch enumerates label
        (ACS + type, create-if-absent), assignee-when-known, milestone-when-
        defined, and Project field-fill, plus surfacing a schema-undefined
        field rather than silently skipping it."""
        body = read(self.skill_path("create-ticket"))
        self.assertIn("ACS", body,
                      "create-ticket/SKILL.md must reference the ACS label (MAR-75 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?i)type.label", body),
            "create-ticket/SKILL.md must reference the type label (MAR-75 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?i)assignee", body),
            "create-ticket/SKILL.md must reference assignee fill (MAR-75 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?i)milestone", body),
            "create-ticket/SKILL.md must reference milestone fill (MAR-75 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?i)(surfaced|surfac\w*).{0,200}(not silently|never silently)|"
                      r"(not silently|never silently).{0,200}(surfaced|surfac\w*)", body),
            "create-ticket/SKILL.md must state a schema-undefined Project field is "
            "surfaced, not silently skipped (MAR-75 AC-6)")

    def test_create_pr_body_carries_closes_reference(self):
        """AC-2, AC-7 (prose proof): create-pr/SKILL.md Step 2 references a
        GitHub-native `Closes #` linking instruction co-occurring with
        pr-default.md/the Ticket section, conditional on a synced github
        ticket; pr-default.md itself carries the new conditional bullet."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?s)Closes #.{0,400}(pr-default|Ticket)|(pr-default|Ticket).{0,400}Closes #", body),
            "create-pr/SKILL.md Step 2 must co-locate 'Closes #' with "
            "'pr-default'/'Ticket' within a bounded window (MAR-75 AC-2, AC-7)")
        self.assertIsNotNone(
            re.search(r"(?i)provider.{0,60}github|github.{0,60}provider", body),
            "create-pr/SKILL.md must state the Closes # link is conditional on "
            "provider == github (MAR-75 AC-4)")
        pr_default = read(self.template_path("pr-default"))
        self.assertIn("Closes #{external_key}", pr_default,
                      "pr-default.md must carry the new conditional "
                      "'Closes #{external_key}' bullet (MAR-75 AC-2, R-2)")

    def test_merge_pr_close_comment_carries_acs_id_and_pr_ref(self):
        """AC-3, AC-5 (prose proof): merge-pr/SKILL.md Step 2's gh issue close
        comment instruction co-occurs with both an acs-ticket-id token and a
        PR back-reference within a bounded window."""
        body = read(self.skill_path("merge-pr"))
        self.assertIsNotNone(
            re.search(
                r"(?s)gh issue close.{0,300}\{ticket_id\}.{0,300}(PR #|\{pr\.url\}|\{pr\.number\})|"
                r"gh issue close.{0,300}(PR #|\{pr\.url\}|\{pr\.number\}).{0,300}\{ticket_id\}",
                body),
            "merge-pr/SKILL.md Step 2 gh issue close comment must co-occur with "
            "both {ticket_id} and a PR back-reference (MAR-75 AC-3, AC-5)")

    def test_unsynced_nonregression_clause_present(self):
        """AC-4 (prose proof): create-ticket/SKILL.md and create-pr/SKILL.md
        each state the local/unsynced non-regression clause — no Closes #
        line is emitted when the ticket is unsynced."""
        create_ticket_body = read(self.skill_path("create-ticket"))
        create_pr_body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?i)local.{0,200}(unsynced|skip)|unsynced.{0,200}local", create_ticket_body),
            "create-ticket/SKILL.md must state the local/unsynced non-regression "
            "clause (MAR-75 AC-4)")
        self.assertIsNotNone(
            re.search(r"(?i)(local|unsynced).{0,300}(omit|bullet is omitted)|"
                      r"(omit|bullet is omitted).{0,300}(local|unsynced)", create_pr_body),
            "create-pr/SKILL.md must state the local/unsynced non-regression "
            "clause — the Closes # bullet is omitted for unsynced tickets "
            "(MAR-75 AC-4)")

    def test_init_documents_reconciliation_convention(self):
        """AC-5 (prose proof + R-1 guard): init/SKILL.md's formats section
        notes the reconciliation convention. Since MAR-80 (which makes
        pr_title provider-aware), the block must instead state that pr_title
        renders the tracker's native reference when synced and the local id
        when unsynced, while branch_name/commit_message stay id-based and
        unconditional."""
        body = read(self.skill_path("init"))
        self.assertIsNotNone(
            re.search(r"(?s)acs-ticket:.{0,800}Closes #|Closes #.{0,800}acs-ticket:", body),
            "init/SKILL.md must document both the acs-ticket: issue-body "
            "convention and the Closes # PR-body convention within a bounded "
            "window (MAR-75 AC-5)")
        self.assertIsNotNone(
            re.search(r"(?is)pr_title.{0,200}(tracker|synced)|"
                      r"(tracker|synced).{0,200}pr_title", body),
            "init/SKILL.md must explicitly state that pr_title renders the "
            "tracker's native reference when synced (MAR-80 AC-1/AC-2/AC-3, "
            "AC-6)")
        self.assertIsNotNone(
            re.search(r"(?is)branch_name.{0,200}commit_message.{0,120}"
                      r"(id-based|unconditional)|"
                      r"(id-based|unconditional).{0,200}branch_name.{0,120}"
                      r"commit_message", body),
            "init/SKILL.md must explicitly state that branch_name and "
            "commit_message remain id-based and unconditional in every case "
            "(MAR-80 AC-4 scope-fence)")


class TestCreatePrTrackerMetadataFill(unittest.TestCase):
    """MAR-101 spec 01: pin the tracker-metadata fill (assignee, type label,
    Project membership + Status) prose contract in create-pr/SKILL.md and
    create-pr-executor.md. Written TDD-first (RED before spec 01's edits
    land); turns GREEN once spec 01 is implemented. Additive only — no
    existing assertion in this file is modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def test_create_pr_fills_assignee_type_label_project_status(self):
        """AC-1/AC-2/AC-3: create-pr/SKILL.md references an assignee fill
        (--add-assignee / @me), a type-label fill distinct from the existing
        ACS label, and a Project item-add co-occurring with a Status-set
        call, all within bounded windows."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?i)--add-assignee|@me", body),
            "create-pr/SKILL.md must reference the --add-assignee/@me fill (MAR-101 AC-1)")
        self.assertIsNotNone(
            re.search(r"(?i)type.label", body),
            "create-pr/SKILL.md must reference a type-label fill distinct from ACS (MAR-101 AC-2)")
        self.assertIsNotNone(
            re.search(r"(?s)item-add.{0,600}(item-edit|field-list)|"
                      r"(item-edit|field-list).{0,600}item-add", body),
            "create-pr/SKILL.md must co-locate 'item-add' with a Status-set "
            "call ('item-edit'/'field-list') within a bounded window (MAR-101 AC-3)")

    def test_create_pr_project_schema_undefined_field_is_info_finding(self):
        """AC-3: a Project-schema-undefined field is surfaced, not silently
        skipped — same phrasing already pinned for create-ticket."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?i)(surfaced|surfac\w*).{0,200}(not silently|never silently)|"
                      r"(not silently|never silently).{0,200}(surfaced|surfac\w*)", body),
            "create-pr/SKILL.md must state a schema-undefined Project field is "
            "surfaced, not silently skipped (MAR-101 AC-3)")

    def test_create_pr_metadata_fill_both_create_and_edit_paths(self):
        """AC-1: the metadata-fill instruction is stated to apply on both the
        create and edit paths, placed after step 6 Record (i.e. after the PR
        number is known) rather than nested only in the create-only branch."""
        body = read(self.skill_path("create-pr"))
        record_idx = body.find("**Record.**")
        self.assertNotEqual(record_idx, -1, "create-pr/SKILL.md must still carry the Record step")
        metadata_idx = None
        for m in re.finditer(r"(?i)--add-assignee|@me", body):
            metadata_idx = m.start()
            break
        self.assertIsNotNone(metadata_idx, "metadata-fill block must exist")
        self.assertGreater(
            metadata_idx, record_idx,
            "AC-1: metadata-fill must be placed after step 6 Record, not inside "
            "the create-only sub-branch of step 5 (MAR-101 AC-1)")
        self.assertIsNotNone(
            re.search(r"(?i)\bboth\b.{0,120}(create and edit|create.{0,10}edit)|"
                      r"(create and edit|create.{0,10}edit).{0,120}\bboth\b", body),
            "create-pr/SKILL.md must explicitly say the metadata-fill applies "
            "on both create and edit paths (MAR-101 AC-1)")

    def test_create_pr_metadata_local_unsynced_noop(self):
        """AC-4: the metadata-fill block itself (not step 7's pre-existing
        tracker-sync guard) states it is skipped for local/unsynced tickets,
        within the bounded span from the assignee-fill marker to the start
        of step 7 Tracker sync."""
        body = read(self.skill_path("create-pr"))
        assignee_idx = None
        for m in re.finditer(r"(?i)--add-assignee|@me", body):
            assignee_idx = m.start()
            break
        self.assertIsNotNone(assignee_idx, "metadata-fill block must exist")
        step7_idx = body.find("**Tracker sync.**")
        self.assertNotEqual(step7_idx, -1, "step 7 Tracker sync must still exist")
        window = body[assignee_idx:step7_idx]
        self.assertIsNotNone(
            re.search(r"(?i)(local|unsynced).{0,300}(no-?op|skip)|"
                      r"(no-?op|skip).{0,300}(local|unsynced)|byte-identical", window),
            "create-pr/SKILL.md's metadata-fill section itself (between the "
            "assignee fill and step 7 Tracker sync) must state the "
            "local/unsynced no-op (MAR-101 AC-4)")

    def test_create_pr_metadata_failure_surfaced_not_aborting(self):
        """AC-5: a failed gh metadata call is captured as a finding and does
        not abort PR creation."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?is)finding.{0,300}(never abort|does not abort|do(es)? not abort)|"
                      r"(never abort|does not abort|do(es)? not abort).{0,300}finding", body),
            "create-pr/SKILL.md must state a failed gh metadata call is "
            "surfaced as a finding and never aborts the PR (MAR-101 AC-5)")

    def test_create_pr_deviates_from_item_add_format_json(self):
        """Guards the named deviation: the actual gh project item-add
        command (inside its own backtick/code span) is NOT paired with
        --format json in the metadata-fill section; item-list instead
        carries --limit 500 with strict=False-equivalent language."""
        body = read(self.skill_path("create-pr"))
        item_add_commands = re.findall(r"`[^`]*item-add[^`]*`", body)
        self.assertTrue(item_add_commands, "create-pr/SKILL.md must reference a gh project item-add command")
        for call in item_add_commands:
            self.assertNotIn(
                "--format json", call,
                "create-pr/SKILL.md's actual item-add command must NOT pair "
                "with --format json — this is a deliberate, permanent "
                "deviation from the create-ticket precedent (MAR-101)")
        self.assertIsNotNone(
            re.search(r"(?is)item-list.{0,200}--limit 500.{0,200}strict=False|"
                      r"item-list.{0,200}strict=False.{0,200}--limit 500", body),
            "create-pr/SKILL.md must resolve the item id via item-list "
            "--limit 500 parsed strict=False (MAR-101)")

    def test_create_pr_executor_charter_has_metadata_fill_step(self):
        """Executor coverage: create-pr-executor.md carries the same
        assignee/type-label/Project-Status fill instruction the SKILL
        carries — the executor enumerates the flow and must not omit it."""
        body = read(self.agent_path("create-pr", "executor"))
        self.assertIsNotNone(
            re.search(r"(?i)--add-assignee|@me", body),
            "create-pr-executor.md must reference the assignee fill (MAR-101)")
        self.assertIsNotNone(
            re.search(r"(?i)type.label", body),
            "create-pr-executor.md must reference the type-label fill (MAR-101)")
        self.assertIsNotNone(
            re.search(r"(?i)item-add", body),
            "create-pr-executor.md must reference the Project item-add call (MAR-101)")

    def test_create_pr_calls_codeowners_resolve_in_step_6a(self):
        """MAR-103 AC-2: create-pr/SKILL.md's Step 6a references a call to
        codeowners.py (or codeowners.py resolve) to derive PR reviewers."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"codeowners\.py(\s+resolve)?", body),
            "create-pr/SKILL.md Step 6a must reference codeowners.py "
            "(MAR-103 AC-2)")

    def test_create_pr_add_reviewer_drops_author(self):
        """MAR-103 AC-2: --add-reviewer co-occurs with an author-drop/@me-
        exclusion phrase within a bounded window (mirrors the item-add/
        item-edit co-occurrence pattern already pinned above)."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?is)--add-reviewer.{0,600}(drop|exclu\w*).{0,120}author|"
                      r"(drop|exclu\w*).{0,120}author.{0,600}--add-reviewer", body),
            "create-pr/SKILL.md must co-locate --add-reviewer with an "
            "author-drop/@me-exclusion phrase within a bounded window "
            "(MAR-103 AC-2)")

    def test_create_pr_reviewer_graceful_skip_info_finding(self):
        """MAR-103 AC-2: the empty-reviewer-set outcome is an info finding
        naming at least one of the three exact reason phrases, never a
        hard failure."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?i)No CODEOWNERS file found|"
                      r"No CODEOWNERS pattern matched the changed files|"
                      r"self-review impossible", body),
            "create-pr/SKILL.md must name at least one of the three exact "
            "graceful-skip reason phrases for the reviewer request "
            "(MAR-103 AC-2)")
        self.assertIsNotNone(
            re.search(r"(?i)\binfo\b.{0,120}finding", body),
            "create-pr/SKILL.md must characterize the reviewer skip as an "
            "info-severity finding, not a hard failure (MAR-103 AC-2)")

    def test_create_pr_groupb_fields_in_project_field_fill_window(self):
        """MAR-103 AC-3: Priority/Story Points/Parent field resolution is
        named within the existing Project field-fill window (extends the
        already-pinned undefined-field-is-info-finding assertion above to
        also require these three field names)."""
        body = read(self.skill_path("create-pr"))
        for name in ("Priority", "Story Points", "Parent"):
            self.assertIn(
                name, body,
                "create-pr/SKILL.md must name the '%s' Project field within "
                "its field-fill window (MAR-103 AC-3)" % name)

    def test_create_pr_executor_mirrors_reviewer_and_groupb(self):
        """Executor coverage: create-pr-executor.md mirrors the reviewer
        codeowners.py call and the Group-B field names (MAR-103)."""
        body = read(self.agent_path("create-pr", "executor"))
        self.assertIsNotNone(
            re.search(r"codeowners\.py(\s+resolve)?", body),
            "create-pr-executor.md must reference codeowners.py (MAR-103 AC-2)")
        self.assertIsNotNone(
            re.search(r"(?i)--add-reviewer", body),
            "create-pr-executor.md must reference --add-reviewer (MAR-103 AC-2)")
        for name in ("Priority", "Story Points", "Parent"):
            self.assertIn(
                name, body,
                "create-pr-executor.md must name the '%s' Project field "
                "(MAR-103 AC-3)" % name)


class TestCreateTicketGroupBFields(unittest.TestCase):
    """MAR-103 spec 03: pin the create-ticket Group-B (Priority, Story
    Points, Parent) creation-time Project-field-fill prose contract in
    create-ticket/SKILL.md and create-ticket-executor.md. Written TDD-first
    (RED before spec 03's edits land); turns GREEN once spec 03 is
    implemented. Additive only — no existing assertion in this file is
    modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def test_create_ticket_groupb_fields_in_step5_item_d_window(self):
        """MAR-103 AC-3: Priority/Story Points/Parent are named within Step
        5 item d's field-fill window."""
        body = read(self.skill_path("create-ticket"))
        item_d_idx = body.find("**Project fields.**")
        self.assertNotEqual(item_d_idx, -1,
                             "create-ticket/SKILL.md must still carry Step 5 "
                             "item d 'Project fields'")
        for name in ("Priority", "Story Points", "Parent"):
            self.assertIn(
                name, body[item_d_idx:],
                "create-ticket/SKILL.md Step 5 item d must name the '%s' "
                "Project field (MAR-103 AC-3)" % name)

    def test_create_ticket_groupb_null_value_silent_skip(self):
        """MAR-103 AC-3/C-4 constraint: a null Group-B ticket value is
        skipped silently (expected data, not missing data) — mirrors the
        existing null-assignee rule already stated for Step 5 item b."""
        body = read(self.skill_path("create-ticket"))
        self.assertIsNotNone(
            re.search(r"(?is)null.{0,200}(expected data|not (a|to) (gap|surface))|"
                      r"(expected data|not (a|to) (gap|surface)).{0,200}null", body),
            "create-ticket/SKILL.md must state the Group-B null-value "
            "silent-skip rule mirroring the null-assignee 'expected data, "
            "not missing data' pattern (MAR-103 AC-3)")

    def test_create_ticket_executor_mirrors_groupb(self):
        """Executor coverage: create-ticket-executor.md names the same three
        Group-B fields and the null-value silent-skip rule (MAR-103)."""
        body = read(self.agent_path("create-ticket", "executor"))
        for name in ("Priority", "Story Points", "Parent"):
            self.assertIn(
                name, body,
                "create-ticket-executor.md must name the '%s' Project "
                "field (MAR-103 AC-3)" % name)
        self.assertIsNotNone(
            re.search(r"(?is)null.{0,200}(expected data|skip)|"
                      r"(expected data|skip).{0,200}null", body),
            "create-ticket-executor.md must mirror the null-value "
            "silent-skip rule (MAR-103 AC-3)")


class TestCreatePrMetadataFillDocs(unittest.TestCase):
    """MAR-101 spec 02: pin the CHANGELOG + living-requirements documentation
    of spec 01's tracker-metadata-fill behavior. Additive only, strictly on
    CHANGELOG.md/skills.md prose — no assertion here touches create-pr's
    SKILL.md apply-flow body (that surface belongs to
    TestCreatePrTrackerMetadataFill / spec 01)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def test_changelog_unreleased_mar101_entry(self):
        """AC-7: '(MAR-101)' and '(MAR-88)' must each be locatable relative
        to '[Unreleased]' in CHANGELOG.md. Uses the same section-slice
        technique as test_changelog_unreleased_mar102_entry (see
        TestCreatePrInReviewStatusDocs) rather than a fixed-width DOTALL
        bleed-through window: a raw '.{0,500}' budget is consumed almost
        entirely by CHANGELOG.md's frozen [0.3.5] preamble and cannot
        tolerate any real [Unreleased] entry (discovered MAR-102; not a
        weakening of intent, only of the fragile distance mechanism)."""
        body = self._changelog()
        unreleased_idx = body.find("## [Unreleased]")
        self.assertNotEqual(unreleased_idx, -1, "CHANGELOG.md must carry an [Unreleased] heading")
        search_from = unreleased_idx + len("## [Unreleased]")
        next_heading = re.search(r"\n## \[[^\]]*\]", body[search_from:])
        self.assertIsNotNone(next_heading, "CHANGELOG.md must still have a dated section after [Unreleased]")
        unreleased_section_end = search_from + next_heading.start()
        # (MAR-101) was swept into [0.3.5] by the v0.3.5 release cut, so it is
        # searched for across the whole remainder of the document, not just
        # inside [Unreleased] — the pre-existing intent (the entry must still
        # exist somewhere in the CHANGELOG) is preserved.
        self.assertIn("(MAR-101)", body[unreleased_idx:],
                      "CHANGELOG.md must contain '(MAR-101)' (MAR-101 AC-7)")
        self.assertIn("(MAR-88)", body[unreleased_idx:],
                      "CHANGELOG.md must still contain '(MAR-88)' "
                      "(regression guard, MAR-88 AC-5)")
        self.assertNotIn("(MAR-101)", body[unreleased_idx:unreleased_section_end],
                          "sanity: (MAR-101) belongs to the dated [0.3.5] "
                          "section, not [Unreleased], post release-cut")

    def test_changelog_no_new_version_section(self):
        """AC-7: the section following [Unreleased] is a well-formed dated
        semver release heading — feature tickets never insert one (only a
        release cut may), and a malformed or undated heading is a defect."""
        body = self._changelog()
        unreleased_idx = body.find("## [Unreleased]")
        search_from = unreleased_idx + len("## [Unreleased]")
        next_heading = re.search(r"\n## \[[^\]]*\]", body[search_from:])
        self.assertIsNotNone(next_heading, "CHANGELOG.md must still have a dated section after [Unreleased]")
        next_heading_text = next_heading.group(0)
        self.assertRegex(next_heading_text, r"\n## \[\d+\.\d+\.\d+\]",
                         "the heading after [Unreleased] must be a dated semver "
                         "release section (MAR-101 AC-7: feature changesets never "
                         "insert version headings; release cuts do)")

    def test_skills_md_create_pr_section_has_mar101_standing_behavior(self):
        """AC-7: docs/requirements/skills.md's '## 5. `/create-pr`' section
        carries a '(standing behavior, MAR-101)' bullet referencing
        assignee/type label/Project/Status. MAR-103 retires the
        '[ASSUMPTION] ... reviewers are left to repo conventions' clause
        (it is no longer true) and replaces it with a Group-A
        CODEOWNERS-derived standing-behavior bullet — this assertion is
        REWRITTEN (not deleted) to assert the retired state, per MAR-103
        Spec 04's required regression-assertion update."""
        body = self._skills_req()
        section_start = body.index("## 5. `/create-pr`")
        section_end = body.index("## 6. `/merge-pr`")
        section = body[section_start:section_end]
        self.assertIn("(standing behavior, MAR-101)", section,
                      "docs/requirements/skills.md '/create-pr' section must carry "
                      "a '(standing behavior, MAR-101)' bullet (MAR-101 AC-7)")
        self.assertIsNotNone(
            re.search(r"(?is)assignee.{0,300}(type label|Project|Status)|"
                      r"(type label|Project|Status).{0,300}assignee", section),
            "the MAR-101 standing-behavior bullet must reference assignee "
            "co-occurring with type label/Project/Status (MAR-101 AC-7)")
        self.assertIsNone(
            re.search(r"(?s)reviewers\s+are left to repo conventions\.", section),
            "the retired reviewers-left-to-repo-conventions ASSUMPTION "
            "clause must be GONE from the '/create-pr' section (MAR-103 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?is)CODEOWNERS.{0,300}(last-match-wins|author)|"
                      r"(last-match-wins|author).{0,300}CODEOWNERS", section),
            "the '/create-pr' section must carry the new Group-A "
            "CODEOWNERS-derived reviewers standing-behavior bullet "
            "(MAR-103 AC-2/AC-6)")


class TestFanoutTrackerSyncLoop(unittest.TestCase):
    """MAR-84 spec 01: pin the fan-out tracker-sync loop prose contract across
    create-ticket/SKILL.md and create-ticket-executor.md. Written TDD-first
    (RED before the Step 5 loop/record-external.py edits land); turns GREEN
    once spec 01 is implemented. Additive only — no existing assertion in
    this file (incl. TestReconcileTicketIssueLinkage's MAR-75 tests) is
    modified, per AC-5's regression gate."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def _bodies(self):
        return {
            "create-ticket/SKILL.md": read(self.skill_path("create-ticket")),
            "create-ticket-executor.md": read(self.agent_path("create-ticket", "executor")),
        }

    def test_loop_token_co_occurs_with_gh_issue_create(self):
        """AC-2/AC-6: both files contain a per-ticket iteration token
        ('tickets to sync' / 'for each ticket to sync') co-occurring, within a
        bounded window, with the existing gh-sync sequence token
        ('gh issue create') — proving the loop actually wraps the sync
        sequence rather than sitting disconnected from it."""
        for name, body in self._bodies().items():
            self.assertIsNotNone(
                re.search(r"(?is)(tickets to sync|for each ticket to sync)"
                          r".{0,1500}gh issue create|"
                          r"gh issue create.{0,1500}(tickets to sync|for each ticket to sync)",
                          body),
                "%s must co-locate a per-ticket iteration token with "
                "'gh issue create' within a bounded window (MAR-84 AC-2/AC-6)" % name)

    def test_record_external_co_occurs_with_external(self):
        """AC-2/AC-6: both files reference record-external.py co-occurring
        with 'external' — proving the write step names the new helper, not
        just generic 'write external' prose."""
        for name, body in self._bodies().items():
            self.assertIsNotNone(
                re.search(r"(?is)record-external\.py.{0,200}external|"
                          r"external.{0,200}record-external\.py", body),
                "%s must reference record-external.py co-occurring with "
                "'external' (MAR-84 AC-2/AC-6)" % name)

    def test_per_child_failure_surfaced_never_aborts_batch(self):
        """AC-3: both files state a per-ticket sync failure is
        surfaced/reported and does not abort the batch — a
        'never...silently'/'surfaced' token co-occurring with a
        'continue'/'other children'/'does not abort' token."""
        for name, body in self._bodies().items():
            self.assertIsNotNone(
                re.search(r"(?is)(never.{0,40}silently|surfaced|reported)"
                          r".{0,400}(continue|other (ticket|child)|does not abort|"
                          r"never.{0,20}abort)|"
                          r"(continue|other (ticket|child)|does not abort|"
                          r"never.{0,20}abort).{0,400}"
                          r"(never.{0,40}silently|surfaced|reported)", body),
                "%s must state a per-ticket sync failure is surfaced and does "
                "not abort the batch (MAR-84 AC-3)" % name)

    def test_product_flow_exclusion_stated(self):
        """AC-4: both files explicitly state the sync set excludes
        product-flow delivery tickets."""
        for name, body in self._bodies().items():
            self.assertIsNotNone(
                re.search(r"(?is)product.flow.{0,300}(exclud|never sync|unsynced|"
                          r"not sync)|"
                          r"(exclud|never sync|unsynced|not sync).{0,300}product.flow",
                          body),
                "%s must state the sync set excludes product-flow delivery "
                "tickets (MAR-84 AC-4)" % name)

    def test_mar75_tokens_survive_the_loop_edit(self):
        """AC-5: the existing MAR-75 prose contract this spec's edits sit
        beside stays intact — re-run the exact assertions
        TestReconcileTicketIssueLinkage pins for create-ticket/SKILL.md, as a
        belt-and-suspenders regression guard co-located with this ticket's
        own test class."""
        body = read(self.skill_path("create-ticket"))
        self.assertIsNotNone(
            re.search(r"(?s)gh issue create.{0,1200}acs-ticket:|acs-ticket:.{0,1200}gh issue create", body),
            "create-ticket/SKILL.md Step 5 must still co-locate 'acs-ticket:' "
            "with 'gh issue create' after the loop edit (MAR-84 AC-5 / MAR-75 AC-1)")
        self.assertIn("ACS", body)
        self.assertIsNotNone(re.search(r"(?i)assignee", body))
        self.assertIsNotNone(re.search(r"(?i)milestone", body))


class TestCreatePrInReviewStatus(unittest.TestCase):
    """MAR-102: pin the in-review Project-Status resolution prose contract
    extending MAR-101's tracker-metadata-fill Status-set call, in
    create-pr/SKILL.md and create-pr-executor.md. Written TDD-first (RED
    before MAR-102's edits land); turns GREEN once MAR-102 is implemented.
    Additive only — no existing assertion in this file is modified."""

    def skill_path(self, name):
        return os.path.join(PLUGIN, "skills", name, "SKILL.md")

    def agent_path(self, skill, role):
        return os.path.join(PLUGIN, "agents", "%s-%s.md" % (skill, role))

    def test_create_pr_resolves_in_review_option_case_insensitively(self):
        """AC-1: create-pr/SKILL.md's Status-set call co-locates a
        case-insensitive in-review option-name resolution naming both
        'In Review' and 'Review' within a bounded window of the existing
        item-edit/field-list Status-set call."""
        body = read(self.skill_path("create-pr"))
        self.assertIsNotNone(
            re.search(r"(?is)(In Review.{0,400}\bReview\b|Review.{0,400}In Review)"
                      r".{0,600}(item-edit|field-list|single-select-option-id)|"
                      r"(item-edit|field-list|single-select-option-id)"
                      r".{0,600}(In Review.{0,400}\bReview\b|Review.{0,400}In Review)",
                      body),
            "create-pr/SKILL.md must resolve the in-review option by "
            "case-insensitive name (In Review, then Review) co-located with "
            "the Status-set call (MAR-102 AC-1)")

    def test_create_pr_in_review_status_both_create_and_edit_paths(self):
        """AC-1: the in-review Status resolution is placed after step 6
        Record (i.e. after the PR number is known) and the block still
        states it applies on both create and edit paths."""
        body = read(self.skill_path("create-pr"))
        record_idx = body.find("**Record.**")
        self.assertNotEqual(record_idx, -1, "create-pr/SKILL.md must still carry the Record step")
        review_idx = body.find("In Review")
        self.assertNotEqual(review_idx, -1, "in-review option resolution must exist")
        self.assertGreater(
            review_idx, record_idx,
            "MAR-102: in-review Status resolution must be placed after step 6 "
            "Record, not before the PR number is known")
        self.assertIsNotNone(
            re.search(r"(?i)\bboth\b.{0,120}(create and edit|create.{0,10}edit)|"
                      r"(create and edit|create.{0,10}edit).{0,120}\bboth\b", body),
            "create-pr/SKILL.md must explicitly say the metadata-fill "
            "(incl. Status resolution) applies on both create and edit "
            "paths (MAR-102 AC-1)")

    def test_create_pr_missing_in_review_option_is_info_finding(self):
        """AC-2: when no in-review option is defined, an info finding names
        the missing option and how to add it; Status is left unchanged; the
        PR is unaffected — all within a bounded window of the resolution
        rule."""
        body = read(self.skill_path("create-pr"))
        review_idx = body.find("In Review")
        self.assertNotEqual(review_idx, -1, "in-review option resolution must exist")
        window = body[max(0, review_idx - 200):review_idx + 1200]
        self.assertIsNotNone(
            re.search(r"(?i)info", window),
            "must co-locate an info-severity finding with the in-review "
            "resolution rule (MAR-102 AC-2)")
        self.assertIsNotNone(
            re.search(r"(?is)Status.{0,200}(unchanged|left unchanged)|"
                      r"(unchanged|left unchanged).{0,200}Status", window),
            "must state Status is left unchanged when no in-review option "
            "is defined (MAR-102 AC-2)")
        self.assertIsNotNone(
            re.search(r"(?i)how to add", window),
            "must name how to add the missing in-review option (MAR-102 AC-2)")

    def test_create_pr_in_review_resolution_inside_guarded_block(self):
        """AC-3/AC-4: the new in-review resolution sits inside MAR-101's
        guarded metadata-fill block — the local/unsynced no-op and
        failure-surfaced-never-abort guarantees still cover the span from
        the assignee-fill marker to step 7 Tracker sync."""
        body = read(self.skill_path("create-pr"))
        assignee_idx = None
        for m in re.finditer(r"(?i)--add-assignee|@me", body):
            assignee_idx = m.start()
            break
        self.assertIsNotNone(assignee_idx, "metadata-fill block must exist")
        step7_idx = body.find("**Tracker sync.**")
        self.assertNotEqual(step7_idx, -1, "step 7 Tracker sync must still exist")
        window = body[assignee_idx:step7_idx]
        self.assertIn("In Review", window,
                      "MAR-102: the in-review Status resolution must sit "
                      "inside the guarded metadata-fill block (between the "
                      "assignee fill and step 7 Tracker sync)")
        self.assertIsNotNone(
            re.search(r"(?i)(local|unsynced).{0,300}(no-?op|skip)|"
                      r"(no-?op|skip).{0,300}(local|unsynced)|byte-identical", window),
            "the local/unsynced no-op guarantee must still cover the whole "
            "guarded block, incl. the new in-review resolution (MAR-102 AC-3)")
        self.assertIsNotNone(
            re.search(r"(?is)finding.{0,300}(never abort|does not abort|do(es)? not abort)|"
                      r"(never abort|does not abort|do(es)? not abort).{0,300}finding", window),
            "the failure-surfaced-never-abort guarantee must still cover the "
            "whole guarded block, incl. the new in-review resolution "
            "(MAR-102 AC-4)")

    def test_create_pr_executor_mirrors_in_review_resolution(self):
        """AC-1 (executor surface): create-pr-executor.md carries the
        identical in-review option-name resolution (In Review/Review)
        co-located with its item-edit/field-list sequence."""
        body = read(self.agent_path("create-pr", "executor"))
        self.assertIsNotNone(
            re.search(r"(?is)(In Review.{0,400}\bReview\b|Review.{0,400}In Review)"
                      r".{0,600}(item-edit|field-list|single-select-option-id)|"
                      r"(item-edit|field-list|single-select-option-id)"
                      r".{0,600}(In Review.{0,400}\bReview\b|Review.{0,400}In Review)",
                      body),
            "create-pr-executor.md must mirror the in-review option "
            "resolution (In Review, then Review) co-located with the "
            "Status-set call (MAR-102 AC-1)")


class TestCreatePrInReviewStatusDocs(unittest.TestCase):
    """MAR-102: pin the CHANGELOG + living-requirements documentation of the
    in-review Status resolution. Additive only, strictly on
    CHANGELOG.md/skills.md prose — no assertion here touches create-pr's
    SKILL.md apply-flow body (that surface belongs to
    TestCreatePrInReviewStatus)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def test_changelog_unreleased_mar102_entry(self):
        """AC-7: '(MAR-102)' must appear inside exactly one well-formed
        section span — [Unreleased] before the release cut, or a dated
        semver release section after it (sliced heading-to-heading, never
        matched via a bleed-through DOTALL window). The entry must also
        acknowledge the graceful-degradation wording."""
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-102)" in candidate:
                section = candidate
                break
        self.assertIsNotNone(
            section,
            "CHANGELOG.md must contain '(MAR-102)' inside a section span "
            "(MAR-102 AC-7)")
        heading = section[:section.index("\n")] if "\n" in section else section
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-102)' entry must live under [Unreleased] or a dated "
            "semver release heading (MAR-102 AC-7; release cuts legitimately "
            "graduate the entry)")
        self.assertIsNotNone(
            re.search(r"(?i)In Review|info finding|unchanged", section),
            "the MAR-102 CHANGELOG entry must acknowledge the "
            "graceful-degradation wording (MAR-102 AC-2/AC-7)")

    def test_changelog_no_new_version_section(self):
        """AC-7: the section following [Unreleased] is still a well-formed
        dated semver release heading — this ticket does not bump the
        version."""
        body = self._changelog()
        unreleased_idx = body.find("## [Unreleased]")
        search_from = unreleased_idx + len("## [Unreleased]")
        next_heading = re.search(r"\n## \[[^\]]*\]", body[search_from:])
        self.assertIsNotNone(next_heading, "CHANGELOG.md must still have a dated section after [Unreleased]")
        next_heading_text = next_heading.group(0)
        self.assertRegex(next_heading_text, r"\n## \[\d+\.\d+\.\d+\]",
                         "the heading after [Unreleased] must be a dated semver "
                         "release section (MAR-102 AC-7: feature changesets never "
                         "insert version headings)")

    def test_skills_md_create_pr_section_has_mar102_standing_behavior(self):
        """AC-7: docs/requirements/skills.md's '## 5. `/create-pr`' section
        carries a '(standing behavior, MAR-102)' bullet referencing the
        in-review Status resolution, and the pre-existing MAR-101 bullet
        remains untouched. MAR-103 retires the reviewers-ASSUMPTION clause
        (see the MAR-101 sibling assertion above) — this assertion is
        REWRITTEN (not deleted) to assert that retired state instead of the
        old bullet's persistence, per MAR-103 Spec 04's required
        regression-assertion update."""
        body = self._skills_req()
        section_start = body.index("## 5. `/create-pr`")
        section_end = body.index("## 6. `/merge-pr`")
        section = body[section_start:section_end]
        self.assertIn("(standing behavior, MAR-102)", section,
                      "docs/requirements/skills.md '/create-pr' section must "
                      "carry a '(standing behavior, MAR-102)' bullet (MAR-102 AC-7)")
        self.assertIsNotNone(
            re.search(r"(?i)In Review", section),
            "the MAR-102 standing-behavior bullet must reference the "
            "In Review option (MAR-102 AC-7)")
        self.assertIn("(standing behavior, MAR-101)", section,
                      "the pre-existing MAR-101 standing-behavior bullet must "
                      "remain untouched (MAR-102 out-of-scope guard)")
        self.assertIsNone(
            re.search(r"(?s)reviewers\s+are left to repo conventions\.", section),
            "the retired reviewers-left-to-repo-conventions ASSUMPTION "
            "clause must be GONE from the '/create-pr' section (MAR-103 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?is)CODEOWNERS.{0,300}(last-match-wins|author)|"
                      r"(last-match-wins|author).{0,300}CODEOWNERS", section),
            "the '/create-pr' section must carry the new Group-A "
            "CODEOWNERS-derived reviewers standing-behavior bullet "
            "(MAR-103 AC-2/AC-6)")

    def test_merge_pr_done_transition_unaffected(self):
        """AC-5: merge-pr/SKILL.md Step 2 cleanup still sets Status to Done
        — pins that this changeset leaves the Done transition intact and is
        not itself edited."""
        body = read(os.path.join(PLUGIN, "skills", "merge-pr", "SKILL.md"))
        self.assertIsNotNone(
            re.search(r"(?is)single-select-option-id.{0,200}Done|Done.{0,200}single-select-option-id", body),
            "merge-pr/SKILL.md must still set Project Status to Done via "
            "single-select-option-id in Step 2 cleanup (MAR-102 AC-5)")


class TestContractsMdD4FoldBoundaryReentry(unittest.TestCase):
    """MAR-107 (AC-6): pin the additive sentence in the existing
    'Escalation-event audit trail (MAR-106)' section of
    docs/architecture/lld/contracts.md naming the D4 detection point and
    fold-boundary re-entry — no new section, since the event shape is
    unchanged by D4."""

    def _contracts_body(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md"))

    def test_escalation_audit_trail_section_names_d4_detection_point_and_reentry(self):
        """AC-6: the 'Escalation-event audit trail (MAR-106)' section must
        name the D4 detection point and the fold-boundary re-entry."""
        body = self._contracts_body()
        section_start = body.index("## Escalation-event audit trail (MAR-106)")
        next_heading = re.search(r"\n## ", body[section_start + 1:])
        section_end = section_start + 1 + next_heading.start() if next_heading else len(body)
        section = body[section_start:section_end]
        self.assertIsNotNone(
            re.search(r"(?i)detection point", section),
            "contracts.md's escalation-event audit trail section must name "
            "the D4 detection point (MAR-107 AC-6)")
        self.assertIsNotNone(
            re.search(r"(?i)fold.boundary.{0,200}(re.entry|re.introduc)|"
                      r"(re.entry|re.introduc).{0,200}fold.boundary",
                      section, re.DOTALL),
            "contracts.md's escalation-event audit trail section must name "
            "the fold-boundary re-entry (MAR-107 AC-6)")


class TestChangelogMar107Entry(unittest.TestCase):
    """MAR-107 (AC-6): durable-invariant CHANGELOG entry — never pins the
    literal '[Unreleased]' string as a fixed anchor (the recurring
    release-cut gotcha hit at v0.3.5/v0.3.6; MAR-88/101/102 fixed style)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar107_entry_in_topmost_section(self):
        """AC-6: '(MAR-107)' must appear inside the top-most changelog
        section span, whose heading is either [Unreleased] or a dated semver
        release heading (sliced heading-to-heading, never a literal
        '[Unreleased]' anchor)."""
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-107)" in candidate:
                section = candidate
                break
        self.assertIsNotNone(
            section,
            "CHANGELOG.md must contain '(MAR-107)' inside a section span "
            "(MAR-107 AC-6)")
        heading = section[:section.index("\n")] if "\n" in section else section
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-107)' entry must live under [Unreleased] or a dated "
            "semver release heading (MAR-107 AC-6; release cuts legitimately "
            "graduate the entry)")


class TestCreateQualityDocConformance(unittest.TestCase):
    """MAR-112 spec 04 (AC-7): doc-conformance for the /acs:create-quality
    doc-set closure — skills.md's new product-level section, configuration.md's
    quality_path row, and c4-component.md's own +1 triad/reachable-agent/
    pre-post-pair arithmetic. Structural string/regex assertions only."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def _configuration(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "configuration.md"))

    def _c4_component(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))

    def test_skills_md_has_create_quality_section(self):
        """AC-7: skills.md carries a '/acs:create-quality' (product-level)
        section naming quality_path, create-quality-planner, and
        create-quality-state.json."""
        body = self._skills_req()
        heading = "## `/acs:create-quality` (product-level)"
        self.assertIn(heading, body,
                      "docs/requirements/skills.md must have a "
                      "'/acs:create-quality' (product-level) section (MAR-112 AC-7)")
        section_start = body.index(heading)
        next_heading = re.search(r"\n## ", body[section_start + 1:])
        section_end = section_start + 1 + next_heading.start() if next_heading else len(body)
        section = body[section_start:section_end]
        self.assertIn("quality_path", section,
                      "the create-quality section must name quality_path (MAR-112 AC-7)")
        self.assertIn("create-quality-planner", section,
                      "the create-quality section must name create-quality-planner (MAR-112 AC-7)")
        self.assertIn("create-quality-state.json", section,
                      "the create-quality section must name create-quality-state.json (MAR-112 AC-7)")

    def test_configuration_md_has_quality_path_row(self):
        """AC-7: configuration.md's Keys table has a quality_path row with
        default "docs/quality"."""
        body = self._configuration()
        self.assertIsNotNone(
            re.search(r"\|\s*`quality_path`\s*\|[^\n]*`\"docs/quality\"`", body),
            "docs/requirements/configuration.md must have a quality_path row "
            "with default \"docs/quality\" (MAR-112 AC-7)")

    def test_c4_component_triad_count_advanced(self):
        """AC-7 sub-check 1: the triad-count sentence reflects the current
        epic state. MAR-112/113 landed '8 active triads (24 agents)'; MAR-117
        is a later producer child and lands the superseding arithmetic
        directly ('9 active triads (27 agents in triads)'), per its own spec
        — so this assertion is updated in place to the superseding truth
        rather than asserting stale text."""
        body = self._c4_component()
        self.assertIn("9 active triads (27 agents", body,
                      "c4-component.md must read '9 active triads "
                      "(27 agents in triads)' (MAR-112/113 AC-7, superseded "
                      "by MAR-117)")
        self.assertNotIn("8 active triads (24 agents)", body,
                         "c4-component.md must not retain the stale "
                         "'8 active triads (24 agents)' text (MAR-112/113 AC-7)")

    def test_c4_component_reachable_agents_advanced(self):
        """AC-7 sub-check 2: in a bounded window AFTER the triad-count
        sentence, the reachable-agents figure matches the current epic state
        (see test_c4_component_triad_count_advanced) -- a partial edit (triad
        line bumped, reachable line left stale) must fail loudly."""
        body = self._c4_component()
        triad_idx = body.index("9 active triads (27 agents")
        window = body[triad_idx:triad_idx + 800]
        self.assertIn("30 reachable agents", window,
                      "c4-component.md must read '30 reachable agents' "
                      "in the window after the triad-count sentence "
                      "(MAR-112/113 AC-7, superseded by MAR-117)")
        self.assertNotIn("27 reachable agents", window,
                         "c4-component.md must not retain the stale "
                         "'27 reachable agents' text in that window (MAR-112/113 AC-7)")

    def test_c4_component_dispatch_pair_count_advanced(self):
        """AC-7 sub-check 3: the dispatch.py component description shows
        the current epic pre/post hook pair count (see
        test_c4_component_triad_count_advanced); x9 is gone."""
        body = self._c4_component()
        self.assertIn("x11", body,
                      "c4-component.md's dispatch.py component description "
                      "must read x11 pre/post hook pairs (MAR-112 AC-7, "
                      "superseded by MAR-113)")
        self.assertNotIn("x9", body,
                         "c4-component.md must not retain the stale x9 "
                         "pre/post hook pair count (MAR-112 AC-7)")


class TestCreateQualityChangelogEntry(unittest.TestCase):
    """MAR-112 spec 04 (AC-9): durable-invariant CHANGELOG entry -- never
    pins the literal '[Unreleased]' string as a fixed anchor (the recurring
    release-cut gotcha; constraint changelog_gotcha)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar112_entry_in_topmost_section(self):
        """AC-9: '(MAR-112)' must appear inside exactly one well-formed
        section span, whose heading is either [Unreleased] or a dated semver
        release heading (sliced heading-to-heading, never a literal
        '[Unreleased]' anchor), and the section mentions create-quality or
        quality_path."""
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-112)" in candidate:
                section = candidate
                break
        self.assertIsNotNone(
            section,
            "CHANGELOG.md must contain '(MAR-112)' inside a section span "
            "(MAR-112 AC-9)")
        heading = section[:section.index("\n")] if "\n" in section else section
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-112)' entry must live under [Unreleased] or a dated "
            "semver release heading (MAR-112 AC-9; release cuts legitimately "
            "graduate the entry)")
        self.assertIsNotNone(
            re.search(r"(?i)create-quality|quality_path", section),
            "the MAR-112 CHANGELOG entry must mention create-quality or "
            "quality_path (MAR-112 AC-9)")


class TestCreateOperationsDocConformance(unittest.TestCase):
    """MAR-113 spec 04 (AC-7): doc-conformance for the /acs:create-operations
    doc-set closure — skills.md's new product-level section, configuration.md's
    operations_path row, and c4-component.md's own +1 triad/reachable-agent/
    pre-post-pair arithmetic. Structural string/regex assertions only."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def _configuration(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "configuration.md"))

    def _c4_component(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))

    def test_skills_md_has_create_operations_section(self):
        """AC-7: skills.md carries a '/acs:create-operations' (product-level)
        section naming operations_path, create-operations-planner, and
        create-operations-state.json."""
        body = self._skills_req()
        heading = "## `/acs:create-operations` (product-level)"
        self.assertIn(heading, body,
                      "docs/requirements/skills.md must have a "
                      "'/acs:create-operations' (product-level) section (MAR-113 AC-7)")
        section_start = body.index(heading)
        next_heading = re.search(r"\n## ", body[section_start + 1:])
        section_end = section_start + 1 + next_heading.start() if next_heading else len(body)
        section = body[section_start:section_end]
        self.assertIn("operations_path", section,
                      "the create-operations section must name operations_path (MAR-113 AC-7)")
        self.assertIn("create-operations-planner", section,
                      "the create-operations section must name create-operations-planner (MAR-113 AC-7)")
        self.assertIn("create-operations-state.json", section,
                      "the create-operations section must name create-operations-state.json (MAR-113 AC-7)")

    def test_configuration_md_has_operations_path_row(self):
        """AC-7: configuration.md's Keys table has an operations_path row with
        default "docs/operations"."""
        body = self._configuration()
        self.assertIsNotNone(
            re.search(r"\|\s*`operations_path`\s*\|[^\n]*`\"docs/operations\"`", body),
            "docs/requirements/configuration.md must have an operations_path row "
            "with default \"docs/operations\" (MAR-113 AC-7)")

    def test_c4_component_triad_count_advanced(self):
        """AC-7 sub-check 1: the triad-count sentence reflects the current
        epic state. MAR-113 landed '8 active triads (24 agents)'; MAR-117 is
        a later producer child and lands the superseding arithmetic directly
        ('9 active triads (27 agents in triads)'), per its own spec — so this
        assertion is updated in place to the superseding truth rather than
        asserting stale text."""
        body = self._c4_component()
        self.assertIn("9 active triads (27 agents", body,
                      "c4-component.md must advance to '9 active triads "
                      "(27 agents in triads)' (MAR-113 AC-7, superseded by "
                      "MAR-117)")
        self.assertNotIn("8 active triads (24 agents)", body,
                         "c4-component.md must not retain the stale "
                         "'8 active triads (24 agents)' text (MAR-113 AC-7)")

    def test_c4_component_reachable_agents_advanced(self):
        """AC-7 sub-check 2: in a bounded window AFTER the triad-count
        sentence, the reachable-agents figure matches the current epic state
        -- a partial edit (triad line bumped, reachable line left stale)
        must fail loudly."""
        body = self._c4_component()
        triad_idx = body.index("9 active triads (27 agents")
        window = body[triad_idx:triad_idx + 800]
        self.assertIn("30 reachable agents", window,
                      "c4-component.md must advance to '30 reachable agents' "
                      "in the window after the triad-count sentence "
                      "(MAR-113 AC-7, superseded by MAR-117)")
        self.assertNotIn("27 reachable agents", window,
                         "c4-component.md must not retain the stale "
                         "'27 reachable agents' text in that window (MAR-113 AC-7)")

    def test_c4_component_dispatch_pair_count_advanced(self):
        """AC-7 sub-check 3: the dispatch.py component description shows
        x11 pre/post hook pairs; x10 is gone."""
        body = self._c4_component()
        self.assertIn("x11", body,
                      "c4-component.md's dispatch.py component description "
                      "must advance to x11 pre/post hook pairs (MAR-113 AC-7)")
        self.assertNotIn("x10", body,
                         "c4-component.md must not retain the stale x10 "
                         "pre/post hook pair count (MAR-113 AC-7)")


class TestCreateOperationsChangelogEntry(unittest.TestCase):
    """MAR-113 spec 04 (AC-9): durable-invariant CHANGELOG entry -- never
    pins the literal '[Unreleased]' string as a fixed anchor (the recurring
    release-cut gotcha; constraint changelog_gotcha)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar113_entry_in_topmost_section(self):
        """AC-9: '(MAR-113)' must appear inside exactly one well-formed
        section span, whose heading is either [Unreleased] or a dated semver
        release heading (sliced heading-to-heading, never a literal
        '[Unreleased]' anchor), and the section mentions create-operations or
        operations_path."""
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-113)" in candidate:
                section = candidate
                break
        self.assertIsNotNone(
            section,
            "CHANGELOG.md must contain '(MAR-113)' inside a section span "
            "(MAR-113 AC-9)")
        heading = section[:section.index("\n")] if "\n" in section else section
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-113)' entry must live under [Unreleased] or a dated "
            "semver release heading (MAR-113 AC-9; release cuts legitimately "
            "graduate the entry)")
        self.assertIsNotNone(
            re.search(r"(?i)create-operations|operations_path", section),
            "the MAR-113 CHANGELOG entry must mention create-operations or "
            "operations_path (MAR-113 AC-9)")


if __name__ == "__main__":
    unittest.main()
