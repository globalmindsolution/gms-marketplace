"""MAR-123 — reflection-topology count refresh across the acs docs.

Several acs docs still described the reflection topology from before the
producer-skill additions (create-quality, create-operations,
create-principles, create-standards, standardize-project). This module
DERIVES the live topology counts (skills on disk, agent files on disk,
`acs_lib.HOOKED_SKILLS`, triad-vs-apply-work classification, and the live
`s04_skill_triggers.py` CASES count) and positively pins the five affected
docs to those derived figures, so the counts cannot silently drift again.

Stdlib-only (ast, glob, importlib, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar123_docs_topology -v
"""

import ast
import glob
import importlib.util
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

APPLY_WORK = {"create-ticket", "create-pr", "merge-pr"}  # MAR-55/60 inline set


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
    """Load the REPO's acs_lib.py by file path (never the cached plugin
    install), so HOOKED_SKILLS reflects this worktree's live source."""
    target = os.path.join(PLUGIN, "hooks", "scripts", "acs_lib.py")
    spec = importlib.util.spec_from_file_location("acs_lib_mar123", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _s04_cases():
    path = os.path.join(REPO_ROOT, "evals", "acs", "scenarios", "s04_skill_triggers.py")
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
    triad = [s for s in hooked if s not in APPLY_WORK]
    n_triad = len(triad)
    reachable = n_triad * 3 + len(APPLY_WORK)
    orphaned = n_agents - reachable
    return {
        "n_skills": n_skills,
        "agent_files": agent_files,
        "n_agents": n_agents,
        "hooked": hooked,
        "n_hooked": n_hooked,
        "triad": triad,
        "n_triad": n_triad,
        "reachable": reachable,
        "orphaned": orphaned,
        "s04_cases": _s04_cases(),
    }


D = derive()

NEW_TRIAD_SUFFIXES = (
    "create-quality", "create-operations", "create-principles",
    "create-standards", "standardize-project",
)


class TopologyDerivationTest(unittest.TestCase):
    """Self-consistency checks — no doc read. Pins the structural identities
    the doc assertions below are built on."""

    def test_agent_file_prefixes_equal_hooked_skills(self):
        prefixes = set()
        for path in D["agent_files"]:
            base = os.path.splitext(os.path.basename(path))[0]
            for role in ("-planner", "-executor", "-verifier"):
                if base.endswith(role):
                    prefixes.add(base[: -len(role)])
                    break
        self.assertEqual(prefixes, set(D["hooked"]))

    def test_agent_count_equals_hooked_times_three(self):
        self.assertEqual(D["n_agents"], D["n_hooked"] * 3)

    def test_reachable_equals_triad_times_three_plus_apply_work(self):
        self.assertEqual(D["reachable"], D["n_triad"] * 3 + len(APPLY_WORK))

    def test_orphaned_is_six(self):
        # apply-work executor count (3) and orphaned count (6) are the two
        # UNCHANGED figures per the ticket's ground-truth map.
        self.assertEqual(D["orphaned"], 6)


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
        self.assertIn("%d triad-keeping" % D["n_triad"], body)
        self.assertIn("%d agent files named" % D["n_agents"], body)

    def test_stale_forms_absent(self):
        body = self._body()
        for stale in ("nine hooked skills", "six triad-keeping skills",
                      "9 pre + 9 post", "21 reachable", "27 agent files",
                      "27 files"):
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
        self.assertIn("%d triad" % (D["n_triad"] * 3), body)

    def test_triad_enumeration_names_new_skills(self):
        body = self._body()
        window = section(body, "## Packaging requirements")
        for suffix in NEW_TRIAD_SUFFIXES:
            self.assertIn(suffix, window,
                          "overview.md Packaging requirements must name -%s" % suffix)

    def test_stale_six_triad_absent(self):
        body = self._body()
        self.assertNotIn("six **triad-keeping skills**", body)
        self.assertNotIn("27 agent files", body)
        self.assertNotIn("21 are reachable", body)


class RoadmapTopologyTest(unittest.TestCase):
    def _body(self):
        return read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))

    def test_ls_skills_and_agents_counts(self):
        body = self._body()
        m1 = re.search(r"`ls plugins/acs/skills` = (\d+)", body)
        m2 = re.search(r"`ls plugins/acs/agents` = (\d+)", body)
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
                      "six triad-keeping skills", "today 27 vs 21 reachable"):
            self.assertNotIn(stale, body, "stale form %r still in roadmap.md" % stale)


class ReflectionTopologyTest(unittest.TestCase):
    def _body(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "reflection.md"))

    def test_agent_count_in_total_present(self):
        body = self._body()
        self.assertIn("%d agent files exist on disk in total" % D["n_agents"], body)

    def test_fourteen_skill_prefixes(self):
        body = self._body()
        self.assertNotIn("nine skill prefixes", body)
        self.assertIn("fifteen skill prefixes", body)

    def test_eleven_triad_keeping(self):
        body = self._body()
        self.assertIn("**twelve**", body)
        self.assertNotIn("**six**", body)

    def test_triad_enumeration_names_new_skills(self):
        body = self._body()
        window = section(body, "## Reflection pattern: plan")
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

    def test_must_have_reachable_and_active_triad(self):
        body = self._body()
        self.assertIn("only %d are reachable" % D["reachable"], body)
        self.assertIn("%d active triad agents" % (D["n_triad"] * 3), body)

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
                      "The six triad-keeping skills",
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
    22 -> 23 for the new /acs:release unhooked skill, not stale drift."""

    def test_twenty_three_skills_present(self):
        body = read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))
        self.assertIn("Twenty-three skills", body)

    def test_eleven_triad_list_intact(self):
        body = read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))
        self.assertIn("Eleven **workflow/product skills**", body)
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
