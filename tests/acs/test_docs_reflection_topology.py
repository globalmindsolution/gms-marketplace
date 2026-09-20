"""MAR-123 — reflection-topology count refresh across the acs docs.

Several acs docs still described the reflection topology from before the
producer-skill additions (create-quality, create-operations,
create-principles, create-standards, standardize-project). This module
DERIVES the live topology counts (skills on disk, agent files on disk,
`acs_lib.HOOKED_SKILLS`, the executor + verifier pairs the registry declares,
and the live `s04_skill_triggers.py` CASES count) and positively pins the
five affected docs to those derived figures, so the counts cannot silently
drift again.

ADR-0092 retired the planner role from every skill, so the "triad" the
original pins counted no longer exists: the unit is now the executor +
verifier PAIR, and the count of skills that own one is read from the
registry (`skills/<name>/acs.yaml`), never hardcoded.

Stdlib-only (ast, glob, importlib, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_docs_reflection_topology -v
"""

import ast
import glob
import importlib.util
import os
import sys
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")

#: Skills whose only agent is an executor: the work is DOING something to the
#: world (a ticket, a PR, a merge, a changeset) rather than authoring a
#: document a verifier could re-derive. `/acs:code` joined them when the review
#: left for `/acs:review-code` (§3.5).
EXECUTOR_ONLY = {"create-ticket", "create-pr", "merge-pr", "code"}
#: Pair-running skills the docs count SEPARATELY from the authoring ones:
#: `/acs:create-docs` was the first class-D skill (ADR-0094).
NON_AUTHORING_PAIRS = {"create-docs"}
#: The review's own roles. It is not a pair and never was: five lenses raise
#: candidates and one adjudicator per finding tries to refute them (§3.6).
REVIEW_ROLES = {"review-code": ["lens", "adjudicator"]}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def _load_acs_lib():
    """Load the REPO's acs_lib by file path (never the cached plugin install),
    so HOOKED_SKILLS reflects this worktree's live source.

    acs_lib is a package since MAR-522: the spec needs the package's search
    location and the module must be registered before exec, or its own relative
    imports cannot resolve."""
    pkg = os.path.join(PLUGIN, "hooks", "scripts", "acs_lib")
    spec = importlib.util.spec_from_file_location(
        "acs_lib_mar123", os.path.join(pkg, "__init__.py"),
        submodule_search_locations=[pkg])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        # Pop the SUBMODULES too: leaving "<name>.state" cached means a second
        # load re-execs only __init__.py, whose relative imports then resolve
        # from the first build -- certifying a build it never loaded.
        for cached in [n for n in sys.modules
                       if n == spec.name or n.startswith(spec.name + ".")]:
            sys.modules.pop(cached, None)
    return mod


def _s04_cases():
    path = os.path.join(REPO_ROOT, "src", "acs-evals", "behavioural", "acs", "scenarios", "s04_skill_triggers.py")
    tree = ast.parse(read(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CASES" for t in node.targets
        ):
            return len(ast.literal_eval(node.value))
    raise AssertionError("CASES list not found in s04_skill_triggers.py")


def derive():
    skills_dir = os.path.join(PLUGIN, "skills")
    n_skills = len([
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
    ])
    agent_files = glob.glob(os.path.join(PLUGIN, "agents", "*.md"))
    n_agents = len(agent_files)
    acs_lib = _load_acs_lib()
    hooked = list(acs_lib.HOOKED_SKILLS)
    n_hooked = len(hooked)
    # Reachable = every role some skill DECLARES it owns. Read from the
    # registry (ADR-0092) rather than recomputed from hardcoded sets, which
    # were a third copy of the same fact and the reason the doc and the disk
    # could disagree.
    declared_roles = acs_lib.skill_agents()
    reachable = sum(len(roles) for roles in declared_roles.values())
    orphaned = n_agents - reachable
    pairs = sorted(s for s, roles in declared_roles.items()
                   if sorted(roles) == ["executor", "verifier"])
    authoring = [s for s in pairs if s not in NON_AUTHORING_PAIRS]
    return {
        "n_skills": n_skills,
        "agent_files": agent_files,
        "n_agents": n_agents,
        "hooked": hooked,
        "n_hooked": n_hooked,
        "pairs": pairs,
        "n_pairs": len(pairs),
        "authoring": authoring,
        "n_authoring": len(authoring),
        "reachable": reachable,
        "declared_roles": declared_roles,
        "orphaned": orphaned,
        "s04_cases": _s04_cases(),
    }


D = derive()

#: Every role an agent file may carry, longest-suffix-safe.
ROLE_SUFFIXES = ("executor", "verifier", "planner", "adjudicator", "lens")

NEW_TRIAD_SUFFIXES = (
    "standardize-project", "create-requirements", "analyze-requirements",
    "create-impl-plan", "create-api-contract", "create-test-docs",
    "create-e2e-tests",
)


class TopologyDerivationTest(unittest.TestCase):
    """Self-consistency checks — no doc read. Pins the structural identities
    the doc assertions below are built on."""

    def test_every_agent_file_belongs_to_a_hooked_skill(self):
        """Every agent file is `<skill>-<role>.md` for a skill that is hooked.
        The converse does not hold and should not: `/acs:run-e2e-tests` runs
        commands and reads their output, which is what a coordinator is for."""
        prefixes = set()
        for path in D["agent_files"]:
            base = os.path.splitext(os.path.basename(path))[0]
            for role in ROLE_SUFFIXES:
                if base.endswith("-" + role):
                    prefixes.add(base[: -len(role) - 1])
                    break
            else:
                self.fail("%s does not end in a known role" % path)
        self.assertTrue(prefixes <= set(D["hooked"]),
                        sorted(prefixes - set(D["hooked"])))
        self.assertEqual(set(D["hooked"]) - prefixes, {"run-e2e-tests"})

    def test_no_planner_file_and_no_planner_declaration(self):
        """ADR-0092: the planner role is gone from the registry and the disk."""
        for path in D["agent_files"]:
            self.assertFalse(os.path.basename(path).endswith("-planner.md"), path)
        for skill, roles in D["declared_roles"].items():
            self.assertNotIn("planner", roles, skill)

    def test_agent_count_matches_the_role_inventory(self):
        """The files on disk are exactly the roles the registry declares.

        Each skill declares its own shape (ADR-0092), so there is no formula
        to apply and no per-skill exception to carve out: the inventory IS the
        declaration.
        """
        self.assertEqual(D["n_agents"], D["reachable"])

    def test_every_agent_on_disk_is_declared(self):
        declared = {"%s-%s" % (skill, role)
                    for skill, roles in D["declared_roles"].items()
                    for role in roles}
        on_disk = {os.path.splitext(os.path.basename(p))[0]
                   for p in D["agent_files"]}
        self.assertEqual(on_disk, declared)

    def test_no_agent_is_orphaned(self):
        """Was `test_orphaned_is_six`, and six was the point.

        create-pr, create-ticket and merge-pr each forbade spawning a planner
        or verifier in their own prose and shipped both files anyway. That the
        orphan count was a PINNED CONSTANT — an expected, documented six —
        rather than a failure is how it survived. ADR-0092 deleted them; the
        assertion is now that the number is zero and stays there.
        """
        self.assertEqual(D["orphaned"], 0)

    def test_pairs_are_the_authoring_skills_plus_create_docs(self):
        self.assertEqual(set(D["pairs"]) - set(D["authoring"]), NON_AUTHORING_PAIRS)
        self.assertEqual(D["n_authoring"], 12)
        for suffix in NEW_TRIAD_SUFFIXES:
            self.assertIn(suffix, D["authoring"])
        executors_only = [s for s, roles in D["declared_roles"].items()
                          if roles == ["executor"]]
        self.assertEqual(set(executors_only), EXECUTOR_ONLY)

    def test_the_review_owns_lenses_and_adjudicators_not_a_pair(self):
        """`/acs:review-code` is the one skill whose roles are neither a pair
        nor a lone executor, and the registry is where that is declared."""
        for skill, roles in REVIEW_ROLES.items():
            self.assertEqual(D["declared_roles"].get(skill), roles)
        self.assertNotIn("review-code", D["pairs"])


class InternalsTopologyTest(unittest.TestCase):
    def _body(self):
        return read(os.path.join(PLUGIN, "docs", "INTERNALS.md"))

    def test_skills_row_count(self):
        body = self._body()
        m = re.search(r"(?m)^\| Skills \|.*\|\s*(\d+)\s*\|\s*$", body)
        self.assertIsNotNone(m, "INTERNALS.md Skills row not found")
        self.assertEqual(int(m.group(1)), D["n_skills"])

    def test_hook_pre_post_counts(self):
        body = self._body()
        m = re.search(r"dispatcher \+ (\d+) pre \+ (\d+) post", body)
        self.assertIsNotNone(m, "INTERNALS.md dispatcher/pre/post count not found")
        self.assertEqual(int(m.group(1)), D["n_hooked"])
        self.assertEqual(int(m.group(2)), D["n_hooked"])

    def test_subagent_counts_present(self):
        body = self._body()
        self.assertIn("%d files" % D["n_agents"], body)
        self.assertIn("%d reachable" % D["reachable"], body)
        self.assertIn("%d executor + verifier pairs" % D["n_pairs"], body)
        self.assertIn("%d agent files named" % D["n_agents"], body)

    def test_stale_forms_absent(self):
        body = self._body()
        for stale in ("nine hooked skills", "six triad-keeping skills",
                      "twelve triad-keeping skills", "triad-keeping",
                      "9 pre + 9 post", "21 reachable", "27 agent files",
                      "27 files", "43 agent files", "43 files"):
            self.assertNotIn(stale, body, "stale form %r still in INTERNALS.md" % stale)


class OverviewTopologyTest(unittest.TestCase):
    """MAR-145: the Packaging-requirements + subagent-count window moved
    wholesale from the old flat overview.md into
    non-functional/packaging-distribution.md during the functional/
    non-functional reorg; repointed here, content unchanged."""

    def _body(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements",
                                  "non-functional", "packaging-distribution.md"))

    def test_subagent_counts_present(self):
        body = self._body()
        self.assertIn("%d agent files exist on disk" % D["n_agents"], body)
        self.assertIn("%d are reachable" % D["reachable"], body)
        self.assertIn("%d for the twelve" % (D["n_authoring"] * 2), body)

    def test_pair_enumeration_names_new_skills(self):
        body = self._body()
        window = section(body, "## Packaging requirements")
        for suffix in NEW_TRIAD_SUFFIXES:
            self.assertIn(suffix, window,
                          "packaging-distribution.md Packaging requirements must name -%s" % suffix)

    def test_stale_triad_forms_absent(self):
        body = self._body()
        self.assertNotIn("six **triad-keeping skills**", body)
        self.assertNotIn("triad-keeping", body)
        self.assertNotIn("27 agent files", body)
        self.assertNotIn("21 are reachable", body)
        self.assertNotIn("43 agent files", body)


class RoadmapTopologyTest(unittest.TestCase):
    def _body(self):
        return read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))

    def test_ls_skills_and_agents_counts(self):
        body = self._body()
        m1 = re.search(r"`ls src/acs/skills` = (\d+)", body)
        m2 = re.search(r"`ls src/acs/agents` = (\d+)", body)
        self.assertIsNotNone(m1, "roadmap.md ls-skills count not found")
        self.assertIsNotNone(m2, "roadmap.md ls-agents count not found")
        self.assertEqual(int(m1.group(1)), D["n_skills"])
        self.assertEqual(int(m2.group(1)), D["n_agents"])

    def test_skills_plus_agents_summary_present(self):
        body = self._body()
        self.assertIn("%d skills + %d agent files" % (D["n_skills"], D["n_agents"]), body)

    def test_g8_mapping_today_reachable_present(self):
        body = self._body()
        self.assertIn("today %d vs %d reachable" % (D["n_agents"], D["reachable"]), body)

    def test_e12_routing_coverage_matches_live_s04(self):
        body = self._body()
        self.assertIn("all %d green" % D["s04_cases"], body)
        self.assertIn("%d-skill routing coverage" % D["s04_cases"], body)

    def test_stale_forms_absent(self):
        body = self._body()
        for stale in ("16 skills + 27 agent files", "= 16,", "= 27);",
                      "six triad-keeping skills", "twelve triad-keeping skills",
                      "today 27 vs 21 reachable", "today 43 vs 43 reachable"):
            self.assertNotIn(stale, body, "stale form %r still in roadmap.md" % stale)


class ReflectionTopologyTest(unittest.TestCase):
    def _body(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "reflection.md"))

    def test_agent_count_in_total_present(self):
        body = self._body()
        self.assertIn("%d agent files exist on disk in total" % D["n_agents"], body)

    def test_the_role_shapes_are_counted_and_add_up(self):
        """Three shapes, and the doc names each with its count: pairs that
        author, executor-only skills that DO something to the world, and the
        review, which is neither."""
        body = self._body()
        self.assertIn("**Thirteen** skills run the execute\u2192verify cycle", body)
        self.assertIn("**twelve** authoring", body)
        self.assertIn("**Four** prefixes are executor-only", body)
        self.assertIn("**One** prefix is neither", body)
        self.assertNotIn("triad", body)
        # ...and the words match the registry, not just each other.
        self.assertEqual(D["n_pairs"], 13)
        self.assertEqual(D["n_authoring"], 12)
        self.assertEqual(
            len([s for s, roles in D["declared_roles"].items() if roles == ["executor"]]), 4)

    def test_pattern_heading_is_execute_verify_and_names_new_skills(self):
        body = self._body()
        self.assertNotIn("## Reflection pattern: plan", body)
        window = section(body, "## Reflection pattern: execute")
        for suffix in NEW_TRIAD_SUFFIXES:
            self.assertIn(suffix, window,
                          "reflection.md pattern heading must name -%s" % suffix)


class PrdTopologyTest(unittest.TestCase):
    def _body(self):
        return read(os.path.join(REPO_ROOT, "docs", "product", "prd.md"))

    def test_g8_skill_count_and_routing_coverage(self):
        body = self._body()
        self.assertIn("**%d** skills" % D["n_skills"], body)
        self.assertIn("%d-skill routing coverage" % D["s04_cases"], body)

    def test_g8_agent_baseline(self):
        body = self._body()
        self.assertIn("%d agent files vs %d reachable" % (D["n_agents"], D["reachable"]), body)

    def test_must_have_reachable_and_authoring_pairs(self):
        body = self._body()
        self.assertIn("only %d are reachable" % D["reachable"], body)
        self.assertIn("%d agents in the twelve authoring skills" % (D["n_authoring"] * 2), body)

    def test_discoverability_bullet_skill_count(self):
        body = self._body()
        self.assertIn("%d acs skills" % D["n_skills"], body)

    def test_g31_today_skill_count(self):
        body = self._body()
        m = re.search(r"today acs \((\d+) skills\)", body)
        self.assertIsNotNone(m, "prd.md G31 'today acs (N skills)' not found")
        self.assertEqual(int(m.group(1)), D["n_skills"])

    def test_stale_forms_absent(self):
        body = self._body()
        for stale in ("the **16** skills", "16-skill routing coverage",
                      "currently 27 agent files vs 21 reachable",
                      "The six triad-keeping skills", "twelve triad-keeping skills",
                      "active triad agents",
                      "27 agent files exist on disk (9 skills"):
            self.assertNotIn(stale, body, "stale form %r still in prd.md" % stale)


class PrdG8IntentPreservedTest(unittest.TestCase):
    def test_intent_strings_survive_verbatim(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "prd.md"))
        self.assertIn("agent-file count == reachable-agent count", body)
        self.assertIn("orphaned per MAR-62", body)


class RoadmapG8MappingTest(unittest.TestCase):
    def test_intent_string_survives_verbatim(self):
        # source wraps the phrase across a line break ("... count on\n  disk
        # equals ..."); tolerate whitespace/newline runs, not a literal word.
        body = read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))
        self.assertRegex(
            body,
            r"agent-file count on\s+disk equals reachable-agent count")


class HistoricalMarkersPreservedTest(unittest.TestCase):
    """AC-2: deliberately-historical / point-in-time markers stay unchanged."""

    def test_prd_v01_snapshot_untouched(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "prd.md"))
        self.assertIn("16 skills:", body)
        self.assertIn("19 skills as of MAR-114", body)

    def test_roadmap_wave1_delta_untouched(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))
        self.assertIn("16 → 19", body)


class SkillsMdUnchangedTest(unittest.TestCase):
    """AC-4 (MAR-123) baseline, bumped by MAR-129: skills.md's count moves
    22 -> 23 for the new /acs:release unhooked skill; then 23 -> 24 by
    MAR-143, which registers the HOOKED create-requirements skill into the
    product enumeration. The 'Unchanged' name is historical (MAR-123 itself
    did not touch skills.md); these pins track the current epic state, not a
    frozen MAR-123 snapshot."""

    def test_skill_count_word_present(self):
        """The count in words, level with the directories on disk. It reached
        32 by adding `/acs:review-code` and dropping the `test` alias, and the
        word is pinned here because prose is where a count goes stale."""
        body = read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))
        self.assertIn("Thirty-two skills", body)
        self.assertEqual(D["n_skills"], 32)
        for stale in ("Twenty-three skills", "Twenty-seven skills"):
            self.assertNotIn(stale, body)
        self.assertNotIn("Twenty-five skills", body)

    def test_twelve_authoring_list_intact(self):
        body = read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))
        self.assertIn("Nine **workflow/product skills**", body)
        self.assertNotIn("Eleven **workflow/product skills**", body)
        self.assertIn("twelve **authoring skills**", body)
        self.assertNotIn("triad", body)
        for suffix in NEW_TRIAD_SUFFIXES:
            self.assertIn(suffix, body)


class S04RoutingCoverageTest(unittest.TestCase):
    """Couples the doc claims to the live s04_skill_triggers.py CASES count."""

    def test_prd_g8_matches_live_s04_cases(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "prd.md"))
        self.assertIn("%d-skill routing coverage" % D["s04_cases"], body)

    def test_roadmap_e12_matches_live_s04_cases(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))
        self.assertIn("%d-skill routing coverage" % D["s04_cases"], body)


class ChangelogMar123EntryTest(unittest.TestCase):
    """AC-6: durable-invariant CHANGELOG entry — never pins the literal
    '[Unreleased]' or a dated version string as a fixed anchor."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar123_entry_in_topmost_section(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-123)" in candidate:
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text,
            "CHANGELOG.md must contain '(MAR-123)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-123)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertTrue(
            re.search(r"reflection|topology|agent", section_text, re.IGNORECASE),
            "the MAR-123 CHANGELOG entry must mention a durable keyword "
            "(reflection/topology/agent)")


if __name__ == "__main__":
    unittest.main()
