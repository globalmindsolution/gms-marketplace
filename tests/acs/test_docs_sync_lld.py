"""/acs:docs-sync keeps the feature's LLD current (ADR-0137).

Before ADR-0137 nothing updated the per-feature living LLD that
/acs:create-api-contract, /acs:create-data-design and /acs:create-flows write
(`<architecture_dir>/lld/<feature>/{api,data,flows,components}/`, versioned by
ADR-0122), and nothing ever moved a document to `implemented`. This module pins
the contract that closes both gaps:

* a fifth doc area, `lld`, owning the run's feature folders (the longest-prefix
  rule leaves `architecture` the HLD and the legacy flat `lld/flows/`);
* a `docs-sync-gap-analyst` per feature, in iteration 1, in the same message as
  the doc-updaters, classifying every element matches | unimplemented |
  undocumented | drifted with a per-document `implemented-candidate` verdict;
* the `lld` doc-updater never silently rewrites a contract: a proposed document
  is brought in line and bumped, drift from an approved or implemented one is a
  question in the one grouped ask, never auto-answered;
* the coordinator flips `approved -> implemented` after a passing review and
  records `states.implemented`;
* the drift-reviewer's seventh dimension, `lld-currency`.

Run:  python3 -m unittest tests.acs.test_docs_sync_lld -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_DIR = os.path.join(PLUGIN, "skills", "docs-sync")
AGENTS = os.path.join(PLUGIN, "agents")
GAP_ANALYST = os.path.join(AGENTS, "docs-sync-gap-analyst.md")
DOC_UPDATER = os.path.join(AGENTS, "docs-sync-doc-updater.md")
DRIFT_REVIEWER = os.path.join(AGENTS, "docs-sync-drift-reviewer.md")
LLD_REF = os.path.join(SKILL_DIR, "references", "lld.md")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_text  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


class LldAreaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.skill = read(os.path.join(SKILL_DIR, "SKILL.md"))
        cls.contract = norm(skill_text.skill_contract("docs-sync"))

    def test_the_lld_area_owns_the_run_features_living_folders(self):
        row = re.search(r"(?m)^\| `lld` \| ([^\n]+)\|$", self.skill)
        self.assertIsNotNone(row, "no `lld` row in the Doc areas table")
        self.assertIn("<architecture_dir>/lld/<feature>/{api,data,flows,components}/", row.group(1))

    def test_architecture_keeps_the_hld_and_the_legacy_flat_flows(self):
        row = re.search(r"(?m)^\| `architecture` \| ([^\n]+)\|$", self.skill).group(1)
        self.assertIn("HLD", row)
        self.assertIn("legacy flat `lld/flows/`", row)

    def test_skill_points_at_the_lld_reference_when_the_run_names_a_feature(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/docs-sync/references/lld.md", self.skill)
        self.assertRegex(norm(self.skill), r"(?i)whenever the run names a feature")
        self.assertRegex(self.contract, r"(?i)With no feature the area has no work")

    def test_per_run_record_folders_are_never_edited(self):
        self.assertRegex(self.contract, r"per-run record folders `lld/<feature>/<key>/`[^.]*never edited")
        self.assertIn("per-run `lld/<feature>/<key>/` record", norm(read(DOC_UPDATER)))

    def test_the_join_names_the_lld_notes(self):
        self.assertIn("<partition>/steps/docs-sync/iter-<n>/authoring-lld.md", self.skill)

    def test_the_doc_updater_knows_the_lld_slice(self):
        body = norm(read(DOC_UPDATER))
        self.assertIn("`requirements`, `architecture`, `lld`, `adr` or `general`", body)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/docs-sync/references/lld.md", body)
        self.assertIn("legacy flat `lld/flows/`", body)


class GapAnalystTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = read(GAP_ANALYST)
        cls.body = norm(cls.text)
        cls.skill = read(os.path.join(SKILL_DIR, "SKILL.md"))
        cls.contract = norm(skill_text.skill_contract("docs-sync"))

    def test_it_is_a_read_only_survey(self):
        fm = front_matter(self.text)
        self.assertRegex(fm, r"(?m)^name: docs-sync-gap-analyst$")
        self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash$")
        self.assertIn("not for direct invocation", fm)
        self.assertNotRegex(fm, r"(?m)^(model|effort):")

    def test_it_classifies_every_element_into_the_four_classes(self):
        for cls_name in ("matches", "unimplemented", "undocumented", "drifted"):
            self.assertIn("**%s**" % cls_name, self.text)
        for heading in ("## Documents", "## Unimplemented", "## Undocumented",
                        "## Drifted", "## Matches", "## Unverified"):
            self.assertIn("`%s`" % heading, self.text)

    def test_the_per_document_verdict_needs_every_element_to_match(self):
        self.assertRegex(self.body, r"`implemented-candidate` when every element `matches` — "
                                    r"nothing unimplemented, undocumented or drifted")
        self.assertIn('acs.py" design check <doc>', self.body)

    def test_it_writes_its_notes_through_acs_write(self):
        self.assertIn("steps/docs-sync/iter-<n>/gaps-<feature>.md", self.body)
        self.assertIn("steps/docs-sync/iter-<n>/gap-analyst-<feature>.json", self.body)
        self.assertIn("""acs.py" write <partition>/<path> <<'ACS_EOF'""", self.body)
        self.assertIn("never `acs.py design status` or `design bump`", self.body)

    def test_its_result_is_the_docs_sync_gap_analyst_phase(self):
        self.assertIn('<result skill="docs-sync" phase="gap-analyst" slice="customer-listing"', self.text)

    def test_the_coordinator_spawns_it_beside_the_doc_updaters_then_joins(self):
        self.assertRegex(self.skill, r"(?m)^\| gap-analyst \| `acs:docs-sync-gap-analyst` \| survey \| `context.agents.gap-analyst` \|")
        self.assertRegex(self.contract, r"(?i)in the SAME message as the `requirements`, `architecture`, `adr` and `general` doc-updaters")
        self.assertIn("--out <partition>/steps/docs-sync/iter-1/gaps.md", self.contract)
        self.assertRegex(self.contract, r"(?i)Then spawn the `lld` doc-updater — after the join")


class LldDocUpdaterRulesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ref = norm(read(LLD_REF))
        cls.contract = norm(skill_text.skill_contract("docs-sync"))

    def test_a_proposed_document_is_brought_in_line_and_bumped(self):
        self.assertRegex(self.ref, r"\*\*`proposed`\*\* .{0,80}`undocumented` / `drifted` → update the document to match the code, then `python3 \"\$\{CLAUDE_PLUGIN_ROOT\}/hooks/scripts/acs.py\" design bump")
        self.assertIn("`unimplemented` → leave it (planned, still proposed)", self.ref)

    def test_drift_from_an_approved_document_is_a_question_with_two_answers(self):
        self.assertRegex(self.ref, r"\*\*`approved`\*\* or \*\*`implemented`\*\*: ANY `drifted` or `undocumented` element is a question for docs-sync's ONE grouped ask")
        self.assertIn("(a) Update the document to match the code — it is bumped and set back to `proposed` for re-approval", self.ref)
        self.assertIn("(b) keep the document: the code is wrong, a blocking finding for /acs:code", self.ref)

    def test_a_deprecated_document_is_never_touched(self):
        self.assertIn("**`deprecated`**: never touched", self.ref)

    def test_the_question_is_never_auto_answered(self):
        self.assertIn("These questions are NEVER auto-answered", self.ref)
        self.assertIn('"stop_reason": "needs_input"', self.ref)
        self.assertRegex(self.contract, r"except an approved-drift question .{0,80}which is never assumed")


class FlipTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ref = norm(read(LLD_REF))
        cls.contract = norm(skill_text.skill_contract("docs-sync"))

    def test_the_flip_runs_after_a_passing_review_in_one_atomic_call(self):
        self.assertIn('design status --set implemented --by acs --reason "<run-id>: the code matches"', self.ref)
        self.assertRegex(self.contract, r"(?i)The flip first, and only when the drift review passed")
        self.assertIn("A document with any element still `unimplemented` stays `approved`", self.ref)

    def test_finish_records_states_implemented(self):
        example = skill_text.result_example(skill_text.skill_contract("docs-sync"))
        states = json.loads(example)["states"]
        self.assertEqual(states["implemented"], [])
        with open(os.path.join(SKILL_DIR, "state.schema.json"), encoding="utf-8") as fh:
            declared = json.load(fh)["properties"]["states"]["properties"]
        self.assertEqual(set(states) - set(declared), set())
        self.assertEqual(declared["implemented"]["items"], {"type": "string"})
        self.assertRegex(self.contract, r"`implemented`: the repo-relative paths the flip moved")


class LldCurrencyDimensionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = read(DRIFT_REVIEWER)

    def _block(self, label):
        m = re.search(r"(?ms)^\d+\.\s+`%s`(.*?)(?=^\d+\.\s+`|^#{1,3} )" % re.escape(label), self.text)
        self.assertIsNotNone(m, label)
        return norm(m.group(1))

    def test_dimension_seven_is_lld_currency_in_the_placement_slice(self):
        self.assertRegex(self.text, r"(?m)^7\. `lld-currency`")
        self.assertIn("`placement` (4 mechanics, 5 requirements-routing, 7 lld-currency)", norm(self.text))

    def test_lld_currency_checks_bumps_answers_and_flips(self):
        block = self._block("lld-currency")
        self.assertIn("every document the `lld` area edited was bumped", block)
        self.assertIn("no `approved`/`implemented` document changed without a recorded answer", block)
        self.assertIn("every `implemented-candidate` verdict", block)

    def test_requirements_routing_drops_the_flat_flows_only_wording(self):
        self.assertNotIn("lld/flows/", self._block("requirements-routing"))


if __name__ == "__main__":
    unittest.main()
