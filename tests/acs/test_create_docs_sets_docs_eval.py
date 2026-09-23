"""Docs / eval / CHANGELOG sweep for the four product doc sets behind
`/acs:create-docs` (ADR-0094).

Replaces the MAR-117 (`/acs:create-principles`) and MAR-118
(`/acs:create-standards`) sweep tests, whose premise — one skill per doc
set — the fold retired. What survives the fold is pinned here for every
set at once: the `configuration.md` default-location row (the `<set>_path`
keys it replaced are gone, ADR-0102), the `skills.md` `/acs:create-docs`
section, the C4/architecture files naming the fold and not the retired legs
as live skills, the routing probe, and the two tickets' durable CHANGELOG
entries.

Stdlib-only (ast, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_create_docs_sets_docs_eval -v
"""

import ast
import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_cases  # noqa: E402  (the case files are the probe set)

import acs_lib  # noqa: E402

SETS = ("quality", "operations", "principles", "standards")
RETIRED = tuple("create-%s" % s for s in SETS)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """The text of a markdown section: from the line starting with
    `heading` up to the next same-or-higher-level heading."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[m.start():end]


class DocSetsTableIsTheContractTest(unittest.TestCase):
    """The docs below are pinned against `acs_lib.DOC_SETS`, not against a
    second hand-typed list, so a fifth set shows up here as a doc gap."""

    def test_the_four_sets_are_the_declared_ones(self):
        self.assertEqual(tuple(acs_lib.DOC_SETS), SETS)

    def test_every_set_declares_its_default_dir_and_sentinel(self):
        for name in SETS:
            row = acs_lib.DOC_SETS[name]
            self.assertEqual(row["default_dir"], "docs/%s" % name)
            self.assertNotIn("settings_key", row, "no setting locates a doc set (ADR-0102)")
            self.assertTrue(row["files"], name)


class SkillsMdTest(unittest.TestCase):
    """skills.md carries one `/acs:create-docs` section that names every
    set and its default location (no settings key: ADR-0102), and no section
    for a retired leg."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))

    def test_intro_lists_create_docs_among_the_design_skills(self):
        intro = self._skills_req()[:800]
        self.assertIn("create-docs", intro)
        for retired in RETIRED:
            self.assertNotIn("`/%s`" % retired, intro,
                             "%s is a doc set, not a skill" % retired)

    def test_create_docs_section_names_every_set(self):
        body = self._skills_req()
        m = re.search(r"(?m)^## .*/acs:create-docs.*$", body)
        self.assertIsNotNone(m, "skills.md must have a '## /acs:create-docs' section")
        window = section(body, m.group(0))
        flat = " ".join(window.split())
        for name in SETS:
            self.assertIn("`docs/%s/`" % name, window)
            self.assertIn("`%s`" % name, window)
            self.assertNotIn("%s_path" % name, window)
        self.assertIn("DOC_SETS", window)
        self.assertRegex(flat, r"the skill checks for the architecture doc set \(its "
                               r"`hld/tech-stack\.md`, not merely a directory\) at Start",
                         "the shared precondition is the skill's Start check (ADR-0102)")
        self.assertIn("principles set **when the repo has one**", flat,
                      "the standards set's soft upstream read must be stated")

    def test_no_section_survives_for_a_retired_leg(self):
        body = self._skills_req()
        for retired in RETIRED:
            self.assertIsNone(
                re.search(r"(?m)^## .*/acs:%s\b" % retired, body),
                "skills.md must not keep a '## /acs:%s' section" % retired)


class ConfigurationMdRowsTest(unittest.TestCase):
    """Each set's default location sits in the "Document and workspace
    locations" table and points at the fold; the `<set>_path` key rows are
    gone with the keys (ADR-0102)."""

    def _configuration(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "configuration.md"))

    def test_every_set_has_a_row_pointing_at_create_docs(self):
        table = section(self._configuration(), "### Document and workspace locations")
        for name in SETS:
            with self.subTest(set=name):
                rows = [l for l in table.splitlines()
                        if l.startswith("|") and "`docs/%s/`" % name in l]
                self.assertEqual(len(rows), 1,
                                 "configuration.md needs one row stating `docs/%s/`" % name)
                row = rows[0]
                self.assertIn("`/acs:create-docs <set>`", row)
                self.assertNotIn("/acs:create-%s" % name, row)

    def test_no_set_path_key_row_survives(self):
        body = self._configuration()
        for name in SETS:
            with self.subTest(set=name):
                self.assertIsNone(re.search(r"(?m)^\|\s*`%s_path`\s*\|" % name, body))


class ArchitectureDocsTest(unittest.TestCase):
    """The C4 set names the fold's shape and stops naming the legs as live
    skills."""

    HLD = os.path.join(REPO_ROOT, "docs", "architecture", "hld")

    def test_c4_container_counts_agents_as_on_disk(self):
        body = read(os.path.join(self.HLD, "c4-container.md"))
        on_disk = len([f for f in os.listdir(os.path.join(PLUGIN, "agents"))
                       if f.endswith(".md")])
        self.assertIn("%d x agent .md" % on_disk, body)
        self.assertIn("create-docs", body)
        self.assertNotIn("39 reachable", body)

    def test_tech_stack_counts_skills_and_agents_as_on_disk(self):
        body = read(os.path.join(self.HLD, "tech-stack.md"))
        skills = len([d for d in os.listdir(os.path.join(PLUGIN, "skills"))
                      if os.path.isdir(os.path.join(PLUGIN, "skills", d))])
        agents = len([f for f in os.listdir(os.path.join(PLUGIN, "agents"))
                      if f.endswith(".md")])
        self.assertIn("acs Skills (%d)" % skills, body)
        self.assertIn("Subagents (%d files" % agents, body)
        self.assertNotIn("39 reachable", body)

    def test_c4_component_places_create_docs_outside_the_triads(self):
        body = read(os.path.join(self.HLD, "c4-component.md"))
        self.assertIn("every one of the fourteen runs execute→verify with no planner", body)
        self.assertNotIn("triad-keeping", body)
        self.assertNotIn("39 reachable", body)
        self.assertNotIn("remain on disk but are orphaned", body)
        # The fold made create-docs a hooked skill; the doc must not still
        # describe it as an unhooked umbrella.
        self.assertNotIn("`/acs:create-docs` and `/acs:project` are unhooked", body)

    def test_overview_and_flow_name_the_fold_not_the_legs(self):
        overview = read(os.path.join(self.HLD, "overview.md"))
        flow = read(os.path.join(REPO_ROOT, "docs", "architecture", "lld", "flows",
                                 "hook-gated-skill-run.md"))
        for body, name in ((overview, "overview.md"), (flow, "hook-gated-skill-run.md")):
            self.assertIn("create-docs", body, name)
            for retired in RETIRED:
                self.assertNotIn("`/acs:%s`" % retired, body,
                                 "%s names retired leg %s" % (name, retired))


class RoutingProbeCaseTest(unittest.TestCase):
    """One routing probe for the fold, read from the curated dataset (no paid
    call): a description-shaped probe that names two sets and routes to
    create-docs; no probe survives for a retired leg.

    The probe set used to live in s04_skill_triggers.py's CASES list, parsed
    out of its AST. Routing consolidated onto the `claude plugin eval` tree, so
    the probe set is the case files under plugins/acs/evals/, read through
    tests/acs/eval_cases.py."""

    @staticmethod
    def _probes(positive=None):
        probes = eval_cases.probe_dicts()
        if positive is not None:
            probes = [p for p in probes if p["must_route"] is positive]
        return probes

    @staticmethod
    def _skill(probe):
        return probe["skill"].split(":", 1)[1]

    def test_create_docs_case_present_and_internally_consistent(self):
        matches = [p for p in self._probes(positive=True)
                   if self._skill(p) == "create-docs"]
        self.assertEqual(len(matches), 1, "exactly one create-docs probe")
        prompt = matches[0]["prompt"]
        self.assertNotIn("create-docs", prompt,
                         "the probe describes intent without naming the skill")
        named = [x for x in SETS if x in prompt]
        self.assertGreaterEqual(len(named), 2,
                                "the probe should name more than one set, so "
                                "routing must reach the umbrella and not a leg")

    def test_no_case_survives_for_a_retired_leg(self):
        probed = {self._skill(p) for p in self._probes()}
        for retired in RETIRED:
            self.assertNotIn(retired, probed)


class ChangelogEntriesTest(unittest.TestCase):
    """The two tickets that shipped the legs keep their durable CHANGELOG
    entries — the log is append-only — and the fold's own entry names the
    ADR."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def _section_containing(self, needle):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if needle in candidate:
                return candidate
        return None

    def test_mar117_and_mar118_entries_survive(self):
        for ticket in ("(MAR-117)", "(MAR-118)"):
            self.assertIsNotNone(self._section_containing(ticket),
                                 "CHANGELOG.md must keep %s" % ticket)

    def test_the_fold_entry_names_adr_0094(self):
        body = self._changelog()
        self.assertRegex(body, r"folded into `/acs:create-docs`\s+\(ADR-0094\)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
