"""Shape pins for .github/workflows/acs-evals.yml — the acs-evals tier 1 gate.

The workflow runs a sibling repo's golden dataset against this checkout's
plugin at a pinned commit. Its value is entirely in the parts that are easy to
delete under pressure: the pin, the plugin-root wiring, the artifact upload and
the fact that a non-zero runner exit fails the job. Each of those is pinned
here so the deletion shows up as a red suite rather than as a silently green
gate.

Parsing is textual (re + str), not PyYAML: the CI runner's Python carries no
third-party packages, the same constraint tests/acs/test_ci_shape_conditional.py
works under.

Originating ticket: MAR-576.
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOWS_DIR = os.path.join(REPO_ROOT, ".github", "workflows")
ACS_EVALS_YML = os.path.join(WORKFLOWS_DIR, "acs-evals.yml")

#: This repo's own behavioral eval runner. C-4 (evals/README.md) keeps it out
#: of CI; acs-evals' deterministic tier is a different harness entirely.
LOCAL_EVAL_RUNNER = "run_evals"


def read_workflow():
    with open(ACS_EVALS_YML, encoding="utf-8") as fh:
        return fh.read()


def top_level_block(text, key):
    """Return the top-level `key:` line plus its indented body, or ''."""
    lines = text.splitlines(keepends=True)
    out = []
    for i, line in enumerate(lines):
        if not out:
            if re.match(r"^%s:" % re.escape(key), line):
                out.append(line)
            continue
        if line.strip() and not line.startswith((" ", "\t")):
            break
        out.append(line)
    return "".join(out)


def comment_above(text, key):
    """Return the contiguous comment lines directly above a top-level key."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^%s:" % re.escape(key), line):
            out = []
            j = i - 1
            while j >= 0 and lines[j].lstrip().startswith("#"):
                out.append(lines[j])
                j -= 1
            return "\n".join(reversed(out))
    return ""


def steps(text):
    """Split the job's `steps:` sequence into one text block per step."""
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "steps:":
            start = i + 1
            break
    if start is None:
        return []

    dash = re.compile(r"^(\s*)-\s")
    indent = None
    blocks, current = [], []
    for line in lines[start:]:
        match = dash.match(line)
        if match and (indent is None or len(match.group(1)) == indent):
            indent = len(match.group(1))
            if current:
                blocks.append("".join(current))
            current = [line]
        elif current:
            # A comment sits at the dash's own indent, so only a dedent out of
            # the sequence ends it.
            if line.strip() and len(line) - len(line.lstrip()) < indent:
                break
            current.append(line)
    if current:
        blocks.append("".join(current))
    return blocks


def step_containing(text, needle):
    found = [block for block in steps(text) if needle in block]
    return found[0] if len(found) == 1 else None


class AcsEvalsWorkflowShapeTest(unittest.TestCase):
    """[AC-1, AC-2, AC-3] the gate's load-bearing shape."""

    def setUp(self):
        self.assertTrue(
            os.path.isfile(ACS_EVALS_YML),
            "%s is missing — the acs-evals tier 1 gate is not wired" % ACS_EVALS_YML,
        )
        self.text = read_workflow()

    def test_workflow_exists_and_triggers_on_pull_request_and_push_to_main(self):
        on_block = top_level_block(self.text, "on")
        self.assertIn("pull_request:", on_block)
        for event_type in ("opened", "reopened", "synchronize"):
            self.assertIn(event_type, on_block)
        self.assertIn("push:", on_block)
        push = on_block[on_block.index("push:"):]
        self.assertIsNotNone(
            re.search(r"branches:\s*\[\s*main\s*\]", push),
            "push trigger does not name main: %r" % push,
        )

    def test_the_pin_is_a_full_commit_sha_declared_once_in_top_level_env(self):
        pins = re.findall(r"^\s*ACS_EVALS_REF:\s*(\S+)\s*$", self.text, re.M)
        self.assertEqual(1, len(pins), "expected exactly one ACS_EVALS_REF: %r" % pins)
        self.assertRegex(pins[0], r"^[0-9a-f]{40}$", "the ref is not a 40-hex commit SHA")
        self.assertIn("ACS_EVALS_REF:", top_level_block(self.text, "env"))

    def test_the_pin_documents_the_bump_protocol(self):
        comment = comment_above(self.text, "env").lower()
        self.assertTrue(comment, "no comment above the pinned ref")
        for token in ("re-record", "make record", "bump", "non-blocking"):
            self.assertIn(token, comment, "bump protocol does not mention %r" % token)

    def test_checks_out_acs_evals_at_the_pinned_ref(self):
        block = step_containing(self.text, "repository: globalmindsolution/acs-evals")
        self.assertIsNotNone(block, "no single step checks out globalmindsolution/acs-evals")
        self.assertIn("actions/checkout@", block)
        self.assertIn("ref: ${{ env.ACS_EVALS_REF }}", block)
        # actions/checkout cannot write outside GITHUB_WORKSPACE, so the
        # dataset lands beside this checkout, not above it.
        self.assertIsNotNone(re.search(r"^\s+path:\s*acs-evals\s*$", block, re.M), block)
        self.assertNotIn("..", block)

    def test_runs_tier_one_against_this_checkouts_plugin(self):
        block = step_containing(self.text, "runner/run_golden.py")
        self.assertIsNotNone(block, "no single step runs the golden runner")
        self.assertIn("working-directory: acs-evals", block)
        self.assertIn("ACS_PLUGIN_ROOT: ${{ github.workspace }}/plugins/acs", block)
        self.assertIsNotNone(
            re.search(r"run:\s*python3 runner/run_golden\.py --json results/latest\.json\s*$",
                      block, re.M),
            block,
        )
        self.assertIn('python-version: "3.12"', self.text)
        self.assertIn("runs-on: ubuntu-latest", self.text)

    def test_uploads_the_results_artifact(self):
        block = step_containing(self.text, "actions/upload-artifact")
        self.assertIsNotNone(block, "no single step uploads the results artifact")
        self.assertIn("if: always()", block)
        self.assertIn("name: acs-evals-results", block)
        self.assertIn("path: acs-evals/results/latest.json", block)

    def test_concurrency_cancels_superseded_runs(self):
        block = top_level_block(self.text, "concurrency")
        self.assertIn("cancel-in-progress: true", block)
        self.assertIn("github.event.pull_request.number", block)
        # `|| github.sha` keeps push runs out of the PR group.
        self.assertIn("github.sha", block)

    def test_the_job_cannot_be_made_non_blocking(self):
        self.assertNotIn("continue-on-error", self.text)
        self.assertNotIn("|| true", self.text)
        self.assertNotIn("exit 0", self.text)
        self.assertIn("permissions:", self.text)
        self.assertIn("contents: read", self.text)

    def test_exactly_one_job(self):
        jobs = top_level_block(self.text, "jobs")
        names = re.findall(r"^  (\w[\w-]*):\s*$", jobs, re.M)
        self.assertEqual(1, len(names), "expected a single job, found %r" % names)


class WorkflowsNeverRunTheLocalEvalHarnessTest(unittest.TestCase):
    """[AC-5, AC-6] C-4 holds: this repo's behavioral evals stay out of CI."""

    def test_no_workflow_invokes_this_repos_eval_runner(self):
        offenders = []
        for path in sorted(glob.glob(os.path.join(WORKFLOWS_DIR, "*.y*ml"))):
            with open(path, encoding="utf-8") as fh:
                if LOCAL_EVAL_RUNNER in fh.read():
                    offenders.append(os.path.basename(path))
        self.assertEqual([], offenders,
                         "%r is invoked by %r" % (LOCAL_EVAL_RUNNER, offenders))


if __name__ == "__main__":
    unittest.main()
