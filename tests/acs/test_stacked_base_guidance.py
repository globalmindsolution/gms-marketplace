"""Guidance tests for the stacked-base pre-flight: the /acs:create-pr wiring and
the author-facing documentation of the replay remedy.

Originating ticket: MAR-590 (child A of epic MAR-589). stacked-base.py detects
a branch stacked on a squash-merged base; a detector nobody runs and a remedy
nobody can find are worth nothing, so these assertions cover the delivery half:
the check runs BEFORE the push on both create-pr surfaces, and the replay is
documented in the managed-block template, this repo's rendered copy, and the
create-pr skill's own reference.

Two properties are load-bearing and easy to break silently:

  * The prose must match the MODULE. Flags, verdict names, exit codes and the
    stderr prefix quoted in the docs are checked against stacked-base.py's own
    source rather than against a copy of the plan, so documentation that drifts
    away from the code it describes fails here.
  * The managed-block template must carry no placeholder beyond
    {ticket_prefix} and {exempt_label}: render_managed_block
    (acs_lib/setup_helpers.py) is a two-token str.replace, so any other brace
    token would ship unrendered into every consumer repo.

Assertions are whitespace-normalized substring/regex checks over file bodies,
never line-number matches -- prose is revised, line numbers drift.

Run:  python3 -m unittest tests.acs.test_stacked_base_guidance -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
if HOOKS_SCRIPTS not in sys.path:
    sys.path.insert(0, HOOKS_SCRIPTS)

import acs_lib  # noqa: E402

CREATE_PR_SKILL = os.path.join(PLUGIN, "skills", "create-pr", "SKILL.md")
CREATE_PR_EXECUTOR = os.path.join(PLUGIN, "agents", "create-pr-executor.md")
CI_REFERENCE = os.path.join(PLUGIN, "skills", "create-pr", "references",
                            "ci-convention-check.md")
BLOCK_TEMPLATE = os.path.join(PLUGIN, "templates", "CLAUDE.acs.md")
REPO_CLAUDE_MD = os.path.join(REPO_ROOT, "CLAUDE.md")
DETECTOR = os.path.join(HOOKS_SCRIPTS, "stacked-base.py")
REPO_SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")

# Every file this ticket's documentation half ships into.
SHIPPED_DOCS = {
    "create-pr/SKILL.md": CREATE_PR_SKILL,
    "create-pr-executor.md": CREATE_PR_EXECUTOR,
    "ci-convention-check.md": CI_REFERENCE,
    "CLAUDE.acs.md": BLOCK_TEMPLATE,
    "CLAUDE.md": REPO_CLAUDE_MD,
}

# The two surfaces that must run the check before pushing: SKILL.md may delegate
# its whole numbered flow to the executor agent, so a pre-flight on one only is
# a pre-flight that half the runs skip.
PUSH_SURFACES = {
    "create-pr/SKILL.md": CREATE_PR_SKILL,
    "create-pr-executor.md": CREATE_PR_EXECUTOR,
}

CHECK_CALL = 'stacked-base.py" check'
PUSH_CALL = "git push -u origin"
BASE_DETECT = "gh repo view --json defaultBranchRef"

# AC-3 names this exact generic form; the detector's own message substitutes
# real values into it.
REPLAY_FORM = "git rebase --onto origin/<base> <old-base>"


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Whitespace-collapsed body, so a re-wrapped paragraph still matches."""
    return re.sub(r"\s+", " ", text)


def module_docstring_and_code(path):
    """(leading module docstring, everything after it) for a .py file."""
    src = read(path)
    _, _, after_open = src.partition('"""')
    docstring, _, code = after_open.partition('"""')
    return docstring, code


def block_containing(text, token):
    """The one markdown bullet/paragraph holding *token*, bounded by the next
    bullet or blank line."""
    where = text.index(token)
    start = text.rindex("\n- ", 0, where) + 1
    ends = [e for e in (text.find("\n- ", where), text.find("\n\n", where)) if e != -1]
    return text[start:min(ends)] if ends else text[start:]


class WiringTest(unittest.TestCase):
    """AC-1 delivery: the check runs, and it runs before anything is pushed."""

    def test_both_create_pr_surfaces_invoke_the_check_subcommand(self):
        for name, path in PUSH_SURFACES.items():
            self.assertIn(CHECK_CALL, norm(read(path)),
                          "%s: never invokes `stacked-base.py check`" % name)

    def test_the_check_runs_before_the_push_on_both_surfaces(self):
        for name, path in PUSH_SURFACES.items():
            body = read(path)
            self.assertLess(
                body.index(CHECK_CALL), body.index(PUSH_CALL),
                "%s: the stacked-base check is documented AFTER `%s` — by then the "
                "doomed branch is already on origin" % (name, PUSH_CALL))

    def test_the_base_is_detected_before_the_push(self):
        # D6: the detector needs the base ref, so the critical base detect moves
        # out of step 2 (which runs after the push) into step 1.
        body = read(CREATE_PR_SKILL)
        self.assertLess(
            body.index(BASE_DETECT), body.index(PUSH_CALL),
            "create-pr/SKILL.md: the base detect still sits after the push")
        self.assertLess(
            body.index(BASE_DETECT), body.index(CHECK_CALL),
            "create-pr/SKILL.md: the check cannot precede the base it needs")

    def test_the_base_is_refreshed_before_the_check(self):
        # The module is network-free by design, so the fetch belongs to the
        # caller: without it the comparison runs against a stale base.
        body = read(CREATE_PR_SKILL)
        self.assertLess(
            body.index("git fetch origin"), body.index(CHECK_CALL),
            "create-pr/SKILL.md: no `git fetch origin <base>` before the check")

    def test_the_skill_documents_every_exit_code_the_module_returns(self):
        body = read(CREATE_PR_SKILL)
        region = norm(body[body.index(CHECK_CALL):]).lower()
        region = region[:region.index("2. **body")]
        for code in ("exit 0", "exit 1", "exit 2"):
            self.assertIn(code, region,
                          "create-pr/SKILL.md: %s is undocumented at the call site" % code)
        # Exit 1 stops the run before it can open a doomed PR (D5) ...
        self.assertIn("do not push", region)
        self.assertIn("gh pr create", region)
        self.assertIn("verbatim", region,
                      "the detector's message is the deliverable — it is surfaced, not paraphrased")
        # ... exit 2 is advisory and never becomes a new way to fail a good PR.
        self.assertRegex(region, r"exit 2[^.]*(unevaluable|cannot)")
        self.assertRegex(region, r"info[^.]*finding|finding[^.]*info")


class DegradedStateReachesTheAuthorTest(unittest.TestCase):
    """A run whose throwaway index failed exits 0 with a `notes` entry and a
    `message` saying so -- so prose reading exit 0 as "these subjects are this
    branch's own" makes the one claim the module refuses to make, and the
    author never sees the note. All three surfaces must read `notes`: the two
    that instruct an agent, and the reference an author opens when the
    conventions gate is already red."""

    #: One distinctive topic per KNOWN LIMITATIONS bullet in stacked-base.py.
    LIMITATION_TOPICS = {
        "the region the base re-edited after the squash": r"edited again|not recognised",
        "the zero-net-content false positive": r"no net content|entire net content",
        "the degraded run": r"degraded run|fork-point index",
    }

    def exit_zero_region(self, path):
        """The exit-0 handling only: from `Exit 0` up to `Exit 1`."""
        body = norm(read(path))
        start = body.index("Exit 0")
        return body[start:body.index("Exit 1", start)]

    def test_both_surfaces_condition_the_ownership_conclusion_on_notes(self):
        for name, path in PUSH_SURFACES.items():
            region = self.exit_zero_region(path)
            self.assertIn("notes", region,
                          "%s: exit 0 never looks at `notes`, so a degraded run reads "
                          "as a healthy branch" % name)
            self.assertRegex(
                region.lower(),
                r"notes[^.]*(empty|non-empty)|(empty|non-empty)[^.]*notes",
                "%s: the subjects-are-your-own conclusion is stated "
                "unconditionally" % name)

    def reference_region(self, start, end):
        """One paragraph span of the reference, anchored on its own lead-ins."""
        body = norm(read(CI_REFERENCE))
        begin = body.index(start)
        return body[begin:body.index(end, begin)]

    def test_the_reference_conditions_the_ownership_conclusion_on_notes_too(self):
        # The third surface. The other two instruct an agent; this one describes
        # what the author sees, so it is held to the CONCLUSION rather than to
        # the info-finding shape -- but to the same conclusion, because a red
        # commit_message gate is exactly when a reader opens this file to decide
        # whether the failing subjects are his own.
        region = self.reference_region("What the pre-flight reports.",
                                       "The remedy is a replay")
        self.assertIn("notes", region,
                      "ci-convention-check.md: exit 0 never looks at `notes`, so a "
                      "degraded run reads as a healthy branch")
        self.assertRegex(
            region.lower(),
            r"notes[^.]*(empty|non-empty)|(empty|non-empty)[^.]*notes",
            "ci-convention-check.md: the subjects-are-your-own conclusion is "
            "stated unconditionally")
        self.assertNotRegex(
            region.lower(), r"any non-conforming subject[^.]*this branch's own",
            "ci-convention-check.md: still states the unconditional ownership "
            "claim the other two surfaces retracted")

    def test_the_reference_lists_every_limitation_the_module_accepts(self):
        # Not a word-count of the prose: the module's KNOWN LIMITATIONS section
        # is the source of truth, and each bullet there has to be recognisable
        # in the paragraph that promises to say what the check will not tell
        # you. A fourth bullet in the module turns this red rather than letting
        # the reference quietly fall one short again.
        docstring, _ = module_docstring_and_code(DETECTOR)
        section = docstring[docstring.index("KNOWN LIMITATIONS"):docstring.index("Usage:")]
        self.assertEqual(len(re.findall(r"^\s+\* ", section, re.M)),
                         len(self.LIMITATION_TOPICS),
                         "stacked-base.py accepts a different number of limitations "
                         "than this test knows how to look for")
        paragraph = self.reference_region("What it will and will not tell you.",
                                          "Do not reach for")
        for topic, pattern in self.LIMITATION_TOPICS.items():
            self.assertRegex(paragraph.lower(), pattern,
                             "ci-convention-check.md: the paragraph promising what "
                             "the check will not tell you omits %s" % topic)

    def test_a_degraded_exit_zero_surfaces_the_message_as_an_info_finding(self):
        for name, path in PUSH_SURFACES.items():
            region = self.exit_zero_region(path)
            self.assertIn("message", region,
                          "%s: the degraded run's `message` reaches nobody" % name)
            self.assertRegex(region.lower(), r"info[^.]*finding|finding[^.]*info",
                             "%s: a degraded exit-0 run produces no finding" % name)

    def test_the_degraded_exit_zero_still_never_fails_a_good_pr(self):
        # The exit-2 shape being mirrored is advisory; exit 0 must stay so too.
        for name, path in PUSH_SURFACES.items():
            region = self.exit_zero_region(path).lower()
            self.assertRegex(region, r"continue|carry on",
                             "%s: exit 0 no longer continues" % name)
            self.assertNotRegex(region, r"do not push|needs_input|stop the run",
                                "%s: exit 0 became a way to fail a good PR" % name)


class ProseMatchesModuleTest(unittest.TestCase):
    """The documented CLI is the CLI the module actually implements."""

    def test_every_documented_flag_exists_in_the_parser(self):
        body = read(CREATE_PR_SKILL)
        call = body[body.index(CHECK_CALL):]
        call = call[:call.index("```")]
        flags = sorted(set(re.findall(r"--[a-z][a-z-]+", call)))
        self.assertIn("--base", flags, "the invocation lost its required --base")
        source = read(DETECTOR)
        for flag in flags:
            self.assertIn('"%s"' % flag, source,
                          "create-pr/SKILL.md documents %s, which stacked-base.py "
                          "does not accept" % flag)

    def test_the_documented_verdicts_and_stderr_prefix_are_the_modules_own(self):
        source = read(DETECTOR)
        docs = norm(read(CREATE_PR_SKILL) + read(CI_REFERENCE))
        for verdict in ("stacked_base", "own_violations", "clean"):
            self.assertIn('"%s"' % verdict, source)
            self.assertIn(verdict, docs,
                          "the docs never name the %r verdict they must explain" % verdict)
        self.assertIn("acs stacked-base: ", source)
        self.assertIn("acs stacked-base:", docs,
                      "the exit-2 stderr prefix an author will see is undocumented")


class ReplayDocumentedTest(unittest.TestCase):
    """AC-3: the remedy is written where an author actually meets it."""

    SURFACES = ("CLAUDE.acs.md", "CLAUDE.md", "ci-convention-check.md")

    def test_every_author_surface_carries_the_replay_command(self):
        for name in self.SURFACES:
            self.assertIn(REPLAY_FORM, norm(read(SHIPPED_DOCS[name])),
                          "%s: missing the `%s` form AC-3 requires" % (name, REPLAY_FORM))

    def test_every_author_surface_warns_that_the_shas_change(self):
        for name in self.SURFACES:
            body = norm(read(SHIPPED_DOCS[name]))
            self.assertRegex(body.lower(), r"every commit sha[^.]*changes",
                             "%s: no every-SHA-changes warning" % name)
            self.assertIn("stale", body.lower(),
                          "%s: never says recorded SHAs go stale after the replay" % name)

    def test_the_reference_explains_the_replay_target_without_hedging(self):
        body = norm(read(CI_REFERENCE))
        # replay_onto is only ever the PROVEN R (find_replay_point), so the
        # lossless claim is stated as fact — the withdrawn tree-identity rule was
        # the variant that needed a hedge.
        self.assertIn("replay_onto", body)
        self.assertRegex(body.lower(), r"loses nothing|lose nothing|cannot lose")

    def test_the_skill_points_at_the_reference_for_the_remedy(self):
        body = norm(read(CREATE_PR_SKILL))
        table = body[body.index("| Open | When |"):]
        table = table[:table.index("## Inline apply flow")]
        self.assertIn("references/ci-convention-check.md", table)
        self.assertRegex(table.lower(), r"stacked[- ]base",
                         "the references table never routes a stacked-base report anywhere")


class ManagedBlockTest(unittest.TestCase):
    """The template is rendered by a two-token str.replace — nothing else survives."""

    def test_the_template_carries_no_placeholder_beyond_the_two_supported_ones(self):
        tokens = set(re.findall(r"\{[^}\n]*\}", read(BLOCK_TEMPLATE)))
        self.assertEqual(tokens, {"{ticket_prefix}", "{exempt_label}"},
                         "a new brace token would ship unrendered into every consumer repo")

    def test_the_rendered_block_has_no_brace_left_in_it(self):
        rendered = acs_lib.render_managed_block(read(BLOCK_TEMPLATE), "MAR", "acs-exempt")
        self.assertNotIn("{", rendered)
        self.assertIn("MAR-N", rendered)
        self.assertIn("acs-exempt", rendered)

    def test_the_replay_bullet_uses_angle_brackets_for_its_two_values(self):
        bullet = norm(block_containing(read(BLOCK_TEMPLATE), REPLAY_FORM))
        self.assertIn("<base>", bullet)
        self.assertIn("<old-base>", bullet)
        self.assertNotRegex(bullet, r"\{[^}]*\}")

    def test_the_repo_copy_carries_the_identical_bullet(self):
        template_bullet = norm(block_containing(read(BLOCK_TEMPLATE), REPLAY_FORM))
        rendered = acs_lib.render_managed_block(template_bullet, "MAR", "acs-exempt")
        self.assertEqual(rendered, norm(block_containing(read(REPO_CLAUDE_MD), REPLAY_FORM)),
                         "this repo's managed block and its template disagree on the "
                         "replay bullet — the rendered copy is the one /acs:setup overwrites")

    def test_the_existing_pipeline_guidance_is_undisturbed(self):
        template = read(BLOCK_TEMPLATE)
        self.assertIn("/acs:ship", template)
        self.assertIn("/acs:merge-pr --pr", template)


class RejectedApproachTest(unittest.TestCase):
    """AC-5: the --cherry-pick dead end is recorded with its evidence, in prose
    only, so nobody re-attempts it and no patch-id logic creeps into the code."""

    def test_the_module_docstring_records_the_rejection_with_its_evidence(self):
        docstring, _ = module_docstring_and_code(DETECTOR)
        flat = norm(docstring)
        self.assertIn("--cherry-pick", flat)
        self.assertIn("patch-id", flat)
        self.assertIn("one combined patch", flat)
        self.assertIn("Reconcile the ADR record", flat,
                      "the measured evidence (the real subjects it returned) is missing")

    def test_no_patch_id_logic_is_implemented(self):
        _, code = module_docstring_and_code(DETECTOR)
        self.assertNotIn("cherry-pick", code)
        self.assertNotIn("patch-id", code)

    def test_the_author_facing_reference_repeats_the_rejection(self):
        # An author staring at a red gate reaches for --cherry-pick next; the
        # record belongs where they are looking, not only in the module.
        flat = norm(read(CI_REFERENCE))
        self.assertIn("--cherry-pick", flat)
        self.assertIn("patch-id", flat)
        self.assertIn("one combined patch", flat)


class ScopeHeldTest(unittest.TestCase):
    """AC-6 and the MAR-591 boundary: this ticket reports, it does not legislate."""

    def test_no_shipped_doc_names_the_unimplemented_resync_command(self):
        # Non-vacuous by construction: the same surfaces are asserted BELOW to
        # carry the stale-SHA warning, so the corpus provably discusses the topic
        # the forbidden command belongs to.
        for name, path in SHIPPED_DOCS.items():
            self.assertNotIn("resync-shas", read(path),
                             "%s: names a subcommand that does not exist yet (MAR-591)" % name)
        for name in ("CLAUDE.acs.md", "CLAUDE.md", "ci-convention-check.md"):
            self.assertIn("stale", norm(read(SHIPPED_DOCS[name])).lower(),
                          "%s: the stale-SHA consequence is what stands in for that "
                          "command — it must be stated" % name)

    def test_the_merge_policy_is_unchanged(self):
        with open(REPO_SETTINGS, "r", encoding="utf-8") as fh:
            settings = json.load(fh)
        self.assertNotIn("merge_strategy", settings,
                         "AC-6: this ticket does not enable merge commits")
        self.assertEqual(acs_lib.DEFAULT_SETTINGS["merge_strategy"], "squash")

    def test_stacking_stays_permitted(self):
        for name in ("CLAUDE.acs.md", "CLAUDE.md", "ci-convention-check.md"):
            body = norm(read(SHIPPED_DOCS[name]))
            self.assertIn("stays permitted", body,
                          "%s: must say stacking remains allowed (AC-6, ledger C-1)" % name)
        for name, path in SHIPPED_DOCS.items():
            self.assertNotRegex(
                norm(read(path)).lower(),
                r"(never|do not|don't) stack\b|stop stacking|forbid\w* stacking",
                "%s: discourages stacking, which AC-6 forbids" % name)


if __name__ == "__main__":
    unittest.main()
