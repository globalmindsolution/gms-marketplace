"""MAR-114 — /acs:test skill: deterministic run mechanics (spec 02).

Prose-contract unit test for the NEW `plugins/acs/skills/test/SKILL.md`,
covering AC-6 (model-invocability), AC-7 (--suite argument contract +
setup/command/teardown), AC-8 (results-artifact shape), AC-9 all-green half
(no-model-call determinism), AC-11 report half, and the R1 safety note.

Stdlib-only (os, re, unittest), mirroring tests/acs/test_init_quality_path.py's
bounded-window `section()` technique so a stray mention elsewhere in the file
cannot satisfy an assertion.

Run:  python3 -m unittest tests.acs.test_mar114_test_skill_run_mechanics -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "test", "SKILL.md")
METRICS_SKILL_PATH = os.path.join(PLUGIN, "skills", "metrics", "SKILL.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def front_matter(body):
    m = re.match(r"(?s)^---\n(.*?)\n---\n", body)
    if m is None:
        raise AssertionError("SKILL.md must open with a --- front-matter block")
    return m.group(1)


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar114TestSkillFileExistsCase(unittest.TestCase):
    def test_skill_file_exists(self):
        self.assertTrue(
            os.path.isfile(SKILL_PATH),
            msg="plugins/acs/skills/test/SKILL.md must exist (AC-6)",
        )


class Mar114TestSkillRunMechanicsCase(unittest.TestCase):
    """Fixture: read the new test SKILL.md once for all prose assertions."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.fm = front_matter(cls.body)
        cls.opening = cls.body[: cls.body.index("## Step 1")] if "## Step 1" in cls.body else cls.body

    # -- AC-6: model-invocability --------------------------------------

    def test_front_matter_name_is_test(self):
        self.assertRegex(
            self.fm, r"(?m)^name:\s*test\s*$",
            msg="front matter must declare name: test (AC-6)",
        )

    def test_front_matter_has_no_disable_model_invocation(self):
        self.assertNotIn(
            "disable-model-invocation", self.fm,
            msg="front matter must NOT set disable-model-invocation — /acs:test "
                "must remain model-invocable (AC-6)",
        )

    def test_front_matter_has_description(self):
        self.assertRegex(
            self.fm, r"(?m)^description:\s*\S",
            msg="front matter must have a non-empty description for routing",
        )

    # -- Opening framing: NOT hooked, NOT read-only ---------------------

    def test_opening_states_not_hooked_pipeline_skill(self):
        self.assertRegex(
            self.opening,
            r"(?i)not\s+a\s+hooked\s+pipeline\s+skill",
            msg="opening must state this is NOT a hooked pipeline skill",
        )
        for token in ("skill-start", "pre/post hooks", "subagents", "reflection loop"):
            self.assertIn(
                token, self.opening,
                msg="opening must mirror metrics/usage framing: no %s" % token,
            )

    def test_opening_does_not_claim_read_only(self):
        metrics_body = read(METRICS_SKILL_PATH)
        # The exact read-only claim sentence from metrics/SKILL.md must not
        # be copied verbatim into the test skill's opening.
        readonly_sentence = "this skill is **read-only**"
        self.assertIn(
            readonly_sentence, metrics_body,
            msg="fixture check: metrics/SKILL.md's read-only sentence moved or changed",
        )
        self.assertNotIn(
            readonly_sentence, self.opening,
            msg="the test skill must NOT copy the metrics/usage read-only claim "
                "verbatim — it writes a results artifact (spec 02 divergence)",
        )

    def test_opening_states_it_writes_results_artifact(self):
        self.assertRegex(
            self.opening,
            r"(?is)writes?\b.{0,80}\bresults\b.{0,40}\bartifact\b",
            msg="opening must state plainly that this skill writes a results "
                "artifact (accurate write/mutate framing, not read-only)",
        )

    # -- AC-7: --suite argument contract ---------------------------------

    def test_suite_flag_contract_documented(self):
        self.assertIn("--suite", self.body, msg="--suite flag must be documented")
        step1 = section(self.body, "## Step 1")
        self.assertRegex(
            step1, r"(?is)no\s+(?:`)?--suite(?:`)?\s+flag.{0,60}(run|every)",
            msg="Step 1 must document: no --suite flag runs every configured suite",
        )
        self.assertRegex(
            step1, r"(?is)(one or more|subset).{0,120}--suite",
            msg="Step 1 must document: one or more --suite flags run only the named subset",
        )

    # -- AC-7: setup -> command -> teardown, teardown ALWAYS -------------

    def test_teardown_always_runs(self):
        m = re.search(r"(?i)teardown", self.body)
        self.assertIsNotNone(m, "teardown must be documented")
        window = self.body[max(0, m.start() - 200):m.start() + 400]
        self.assertRegex(
            window, r"(?i)always",
            msg="'always' must appear in a bounded window near 'teardown' "
                "(teardown always runs, pass or fail)",
        )

    def test_setup_command_teardown_order_documented(self):
        self.assertRegex(
            self.body, r"(?i)setup.{0,20}(?:→|->|then).{0,20}command.{0,20}(?:→|->|then).{0,20}teardown",
            msg="must document the setup -> command -> teardown execution order",
        )

    # -- AC-8: results artifact path + shape -----------------------------

    def test_results_artifact_path_documented(self):
        self.assertIn(
            "test-runs/", self.body,
            msg="results artifact path fragment 'test-runs/' must be documented",
        )
        self.assertIn(
            "results.json", self.body,
            msg="results artifact filename 'results.json' must be documented",
        )

    def test_results_artifact_field_names_documented(self):
        for field in ("run_id", "started_at", "ended_at", "suites", "regressions"):
            self.assertIn(
                field, self.body,
                msg="results artifact field %r must be documented" % field,
            )

    # -- AC-9 (all-green half): deterministic no-model-call --------------

    def test_all_green_no_model_call_guarantee(self):
        m = re.search(r"(?i)all[- ]green|all suites pass", self.body)
        self.assertIsNotNone(
            m, "must document the all-green / all-suites-pass branch",
        )
        window = self.body[max(0, m.start() - 300):m.start() + 600]
        self.assertRegex(
            window, r"(?i)no\s+(?:paid\s+)?model\s+call",
            msg="must state explicitly that no model call is made on all-green",
        )
        self.assertRegex(
            window, r"(?i)no\s+triage",
            msg="must state explicitly that no triage step runs on all-green",
        )

    # -- AC-11 (report half): summary + artifact left in place -----------

    def test_report_summary_documented(self):
        self.assertRegex(
            self.body, r"(?i)summary",
            msg="must document a run summary is printed",
        )
        self.assertRegex(
            self.body, r"(?i)pass(?:/|\s+and\s+|\s*,\s*)fail",
            msg="must document pass/fail counts in the summary",
        )

    def test_artifact_left_in_place_documented(self):
        self.assertRegex(
            self.body, r"(?i)left in place|persists|not (?:cleaned up|deleted|removed)",
            msg="must state the results artifact is left in place on disk",
        )

    # -- R1 safety note ----------------------------------------------------

    def test_r1_no_interpolation_rule_documented(self):
        self.assertRegex(
            self.body,
            r"(?is)(?:never|no).{0,80}interpolat(?:ed|e|ing).{0,150}(?:shell\s+)?command",
            msg="must document the R1 rule: failure content is never "
                "interpolated back into a shell command",
        )

    # -- Scheduling-surface note -------------------------------------------

    def test_scheduling_note_points_to_template_without_duplicating(self):
        self.assertRegex(
            self.body, r"test-scheduling\.md",
            msg="must reference test-scheduling.md",
        )
        # Must not inline a duplicate cron recipe body (no literal crontab
        # line syntax embedded in this SKILL.md).
        self.assertNotRegex(
            self.body, r"\*\s+\*\s+\*\s+\*\s+\*",
            msg="must NOT inline a duplicate cron recipe (5-star crontab syntax)",
        )

    # -- Completion report block -------------------------------------------

    def test_completion_report_block_present(self):
        m = re.search(r"(?m)^## Completion report\b", self.body)
        self.assertIsNotNone(
            m, "must close with a normative Completion report block",
        )
        completion = self.body[m.start():]
        self.assertIn("**Run**", completion)
        self.assertIn("**Findings**", completion)


if __name__ == "__main__":
    unittest.main()
