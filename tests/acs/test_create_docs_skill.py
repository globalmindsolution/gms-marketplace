"""/acs:create-docs -- the product skill that bootstraps the four doc sets.

Prose-contract tests over `create-docs/SKILL.md` and the doc-set table it
reads. Every assertion is a whitespace-normalized substring/regex check over
the prose, never a line-number assertion. Behavioral quality -- does the
model actually spawn the subagents this prose describes -- is the
agentic-e2e tier, not unit-testable here.

History: the umbrella used to fan out four internal leg skills (ADR-0085,
ADR-0091); ADR-0094 folded the legs into it, so the umbrella IS the skill --
hooked, one delivery ticket per set, executor + verifier, no planner.

Run:  python3 -m unittest tests.acs.test_create_docs_skill -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
SKILL_PATH = os.path.join(SKILLS_DIR, "create-docs", "SKILL.md")
TEMPLATES = os.path.join(PLUGIN, "templates")

sys.path.insert(0, HOOKS_DIR)
import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


def _body():
    """The skill's contract: SKILL.md plus the references it points at.

    Two branches moved into `references/` under progressive disclosure -- the
    multi-set fan-out machinery and the resume/handoff seam -- because each is
    read by exactly one kind of run. These assertions pin what the skill SAYS,
    never which of its files says it, so reading the concatenation keeps the
    pin honest while the layout stays free to change, and a rule that
    genuinely vanishes still fails.
    """
    parts = [read(SKILL_PATH)]
    refs = os.path.join(SKILLS_DIR, "create-docs", "references", "*.md")
    parts.extend(read(q) for q in sorted(glob.glob(refs)))
    return "\n".join(parts)


def _frontmatter():
    # Frontmatter is a property of SKILL.md itself, never of a reference.
    m = re.match(r"^---\n(.*?)\n---\n", read(SKILL_PATH), re.DOTALL)
    assert m, "create-docs/SKILL.md must open with a front-matter block"
    return m.group(1)


def section(body, heading):
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    assert m is not None, "heading %r not found" % heading
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[m.start():end]


class TheFoldTest(unittest.TestCase):
    """One skill, four sets: the legs are gone and the umbrella is hooked."""

    LEGS = ("create-quality", "create-operations", "create-principles", "create-standards")

    def test_no_leg_skill_directory_survives(self):
        for leg in self.LEGS:
            with self.subTest(leg=leg):
                self.assertFalse(os.path.isdir(os.path.join(SKILLS_DIR, leg)))

    def test_no_leg_hook_script_survives_and_the_umbrella_has_its_own(self):
        for leg in self.LEGS:
            for kind in ("pre", "post"):
                self.assertFalse(os.path.exists(os.path.join(HOOKS_DIR, "%s-%s.py" % (kind, leg))))
        for kind in ("pre", "post"):
            body = read(os.path.join(HOOKS_DIR, "%s-create-docs.py" % kind))
            self.assertIn('run_%s("create-docs")' % kind, body)

    def test_create_docs_is_a_hooked_product_skill(self):
        self.assertIn("create-docs", acs_lib.PRODUCT_SKILLS)
        self.assertIn("create-docs", acs_lib.HOOKED_SKILLS)
        self.assertIn("create-docs", acs_lib.DELIVERY_TICKET_SKILLS)
        self.assertNotIn("create-docs", acs_lib.UNHOOKED_SKILLS)
        self.assertIn("create-docs", acs_lib.GATES)
        for leg in self.LEGS:
            self.assertNotIn(leg, acs_lib.HOOKED_SKILLS)
            self.assertNotIn(leg, acs_lib.GATES)

    def test_the_registry_lists_it_as_a_skill_not_an_entry_point(self):
        self.assertIn("create-docs", acs_lib.registered_skills())
        self.assertEqual([leg for leg, entry in acs_lib.skill_legs().items()
                          if entry == "create-docs"], [])

    def test_the_prose_never_dispatches_a_leg(self):
        body = _body()
        for leg in self.LEGS:
            self.assertNotIn("Skill(acs:%s)" % leg, body)
            self.assertNotIn("acs:%s-" % leg, body)


class DocSetTableTest(unittest.TestCase):
    """acs_lib.DOC_SETS is the one declaration; the prose table mirrors it."""

    def test_four_sets_with_their_settings_keys(self):
        self.assertEqual(list(acs_lib.DOC_SETS), ["quality", "operations", "principles", "standards"])
        for name, row in acs_lib.DOC_SETS.items():
            with self.subTest(set=name):
                self.assertEqual(row["settings_key"], name + "_path")
                self.assertEqual(row["title"], "Product %s doc set" % name)
                self.assertEqual(row["template_dir"], name)

    def test_every_file_has_a_template_carrying_its_required_sections(self):
        for name, row in acs_lib.DOC_SETS.items():
            for fname, sections in row["files"].items():
                with self.subTest(set=name, file=fname):
                    template = read(os.path.join(TEMPLATES, row["template_dir"], fname))
                    for heading in sections:
                        self.assertIn("## " + heading, template,
                                      "the template must carry every section the verifier lints for")

    def test_no_template_file_is_undeclared(self):
        for name, row in acs_lib.DOC_SETS.items():
            with self.subTest(set=name):
                on_disk = sorted(os.listdir(os.path.join(TEMPLATES, row["template_dir"])))
                self.assertEqual(on_disk, sorted(row["files"]))

    def test_the_sentinel_is_the_first_file(self):
        self.assertEqual(acs_lib.DOC_BOOTSTRAP_SENTINEL,
                         {name: next(iter(row["files"])) for name, row in acs_lib.DOC_SETS.items()})

    def test_the_prose_table_mirrors_the_declaration(self):
        table = section(_body(), "## The doc sets")
        for name, row in acs_lib.DOC_SETS.items():
            with self.subTest(set=name):
                line = next(l for l in table.splitlines() if l.startswith("| `%s` |" % name))
                self.assertIn("`%s`" % row["settings_key"], line)
                for fname in row["files"]:
                    self.assertIn("`%s`" % fname, line)
                self.assertIn(row["audience"], line)

    def test_required_sections_are_read_from_the_table_not_restated(self):
        body = norm(_body())
        self.assertIn("doc_sets[<set>].files[<file>]", body)
        self.assertRegex(body, r"(?i)you never restate them from memory")

    def test_upstream_inputs_per_set(self):
        d = acs_lib.DOC_SETS
        self.assertEqual(d["quality"]["upstream"]["prd"], "Non-functional requirements")
        self.assertEqual(d["operations"]["upstream"]["prd"], "Non-functional requirements")
        self.assertEqual(d["principles"]["upstream"]["prd"], "whole")
        self.assertTrue(all(row["upstream"]["architecture"] for row in d.values()))
        self.assertEqual([n for n, row in d.items() if row["upstream"]["principles"]], ["standards"])

    def test_standards_soft_depends_on_principles_and_nothing_is_hard(self):
        self.assertEqual(acs_lib.DOC_BOOTSTRAP_DEPENDENCIES["standards"]["soft"], ["principles"])
        self.assertTrue(all(not row["hard"] for row in acs_lib.DOC_SETS.values()))


class ArgumentContractTest(unittest.TestCase):

    def test_argument_hint_names_sets_all_and_a_ticket_id(self):
        fm = _frontmatter()
        self.assertRegex(fm, r"argument-hint:.*all \| <set>\[,<set>\.\.\.\] \| <delivery-ticket-id to resume>")

    def test_description_names_the_four_sets_and_the_precondition(self):
        fm = _frontmatter()
        for word in ("quality", "operations", "principles", "standards"):
            self.assertIn(word, fm)
        self.assertIn("/acs:create-architecture", fm)
        self.assertNotIn("disable-model-invocation", fm)
        self.assertIn("disallowed-tools: Edit, NotebookEdit", fm)

    def test_parsing_lives_in_acs_lib(self):
        body = norm(_body())
        self.assertIn("lib.parse_doc_set_arg(args_text)", body)
        self.assertRegex(body, r"(?i)You never parse this yourself")

    def test_a_ticket_id_resumes_one_set(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)`resume` set.{0,40}skip eligibility entirely")
        self.assertIn("--skill create-docs --ticket <delivery-ticket-id>", body)

    def test_rejection_refuses_the_whole_run(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)refuses the WHOLE run \(exit 2")
        self.assertRegex(body, r"(?i)never silently dropped")

    def test_legacy_for_flag_one_release(self):
        body = norm(_body())
        self.assertRegex(body, r"`--for <set>\[,<set>\.\.\.\]` stays accepted for \*\*one release\*\*")


class StartContractTest(unittest.TestCase):

    def test_per_set_start_allocates_with_the_doc_set(self):
        body = _body()
        self.assertIn('skill-start.py" --skill create-docs --doc-set <set> --allocate', body)

    def test_starts_are_sequential_from_the_session_checkout(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)run its Start \*\*sequentially\*\* — never concurrently")
        self.assertRegex(body, r"(?i)runs from the \*\*session checkout\*\*")

    def test_eligibility_is_the_declared_predicate(self):
        body = norm(_body())
        self.assertIn("lib.fanout_batches(settings, tickets_index, root, candidates=request.candidates)", body)
        self.assertRegex(body, r"(?i)\*\*declared, not inferred\*\* eligibility predicate")
        self.assertRegex(body, r"(?i)a `null` path is the consumer'?s opt-out")

    def test_a_null_principles_path_never_stops_standards(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)A `null` `principles_path` never stops a `standards` run")
        self.assertRegex(body, r"(?i)Graceful degradation \(mandatory\)")

    def test_the_gate_ran_once_for_every_set(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)`pre-create-docs.py` gates the Skill call on the architecture doc set, once")
        self.assertRegex(body, r"(?i)checked by the pre-hook before any set started")

    def test_the_start_snippet_prints_the_table_and_paths(self):
        body = _body()
        self.assertIn('"doc_sets": lib.DOC_SETS', body)
        self.assertIn('"resume": request.resume', body)

    def test_hook_bypass_language_absent(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)You never bypass, simulate, or duplicate a hook")


class ConcurrencyAndWorktreeTest(unittest.TestCase):

    def test_cap_is_max_parallel(self):
        body = norm(_body())
        self.assertRegex(body, r"run \*\*at most 2\*\* sets concurrently")
        self.assertIn("DEFAULT_MAX_PARALLEL", body)

    def test_worktree_per_set_detached(self):
        body = _body()
        self.assertIn("git worktree add --detach <path> <default-branch>", body)
        self.assertRegex(norm(body), r"(?i)never ticket-id-named")

    def test_executors_then_verifiers_in_one_message_each(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)executors \(`acs:create-docs-executor`, one per set, at most `max_parallel`\) in ONE message")
        self.assertRegex(body, r"(?i)verifiers \(`acs:create-docs-verifier`, one per set\) in one message")

    def test_cites_the_code_skill_parallel_mechanism(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)the mechanism `/acs:code`'?s coordinator already uses")


class DeliveryTest(unittest.TestCase):

    def test_one_independent_pr_per_set(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)one independent delivery ticket and one independent docs-only PR \*\*per set\*\*")
        self.assertRegex(body, r"(?i)never one shared branch, never a combined PR")

    def test_stages_only_the_set_path_and_asserts_docs_only(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)stage ONLY `<path>/` and verify the diff is docs-only")

    def test_delivery_pattern_sentence_matches_the_sibling_product_skills(self):
        self.assertIn("/acs:create-design and /acs:code are not involved):", _body())


class FailureAndResumeTest(unittest.TestCase):

    def test_failure_is_isolated_per_set(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)Every failure is isolated to its own set")
        self.assertRegex(body, r"(?i)every OTHER set'?s run, PR and ledger are never touched")

    def test_no_fan_out_ledger_of_its_own(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)There is no fan-out ledger of its own")
        self.assertRegex(body, r"(?i)step key `create-docs`")

    def test_ship_product_flow_refusal_is_restated_not_reversed(self):
        body = norm(_body())
        self.assertRegex(body, r"(?i)`/acs:ship` never drives these")


class FinishTest(unittest.TestCase):

    def test_result_document_states_keys(self):
        body = _body()
        self.assertIn('"doc_set": {', body)
        self.assertIn('"set": "quality"', body)
        self.assertIn('post-create-docs.py" --ticket <id> --result-file <partition>/steps/create-docs/result.json', body)

    def test_completion_report_present(self):
        body = _body()
        self.assertIn("## /acs:create-docs · <status>", body)
        self.assertIn("- **<set>**: <ticket-id> — <status> — <PR url, or reason>", body)


if __name__ == "__main__":
    unittest.main()
