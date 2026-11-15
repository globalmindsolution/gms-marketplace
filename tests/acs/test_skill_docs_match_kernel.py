"""Skill and agent prose must name only what the kernel admits.

Each case here pins a drift that once sent a coordinator to write something the
post-hook refuses, or to read something the kernel never writes:

  * `needs_input` and `handed_off` as a result STATUS. `acs_lib.run.STEP_STATUSES`
    is `in_progress | completed | failed | interrupted`; `needs_input` is one of
    `STOP_REASONS`, and `handed_off` is neither (a handoff is `interrupted` +
    `stop_reason: context_pressure`, written by handoff.py).
  * `handoff_summary` as a result-document field -- result.schema.json is
    `additionalProperties: false`; the summary lives on the invocation.
  * `prior_run_status` -- the Start context key is `prior_status`.
  * `workflow.record_delivery_path` -- no such function; the path is the
    plan's `## Contract` `delivery_path:` line.
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib as lib  # noqa: E402


def prose_files():
    paths = glob.glob(os.path.join(PLUGIN, "skills", "**", "*.md"), recursive=True)
    paths += glob.glob(os.path.join(PLUGIN, "agents", "*.md"))
    return sorted(paths)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class ResultStatusVocabularyTest(unittest.TestCase):

    #: `"status": "<x>"` / `status: "<x>"` / status `"<x>"` in prose.
    STATUS_RE = re.compile(r'(?:"status"\s*:\s*|\bstatus:\s*|\bstatus\s+)`?"(needs_input|handed_off)"')

    def test_the_kernel_vocabulary_is_what_this_test_assumes(self):
        self.assertNotIn("needs_input", lib.STEP_STATUSES)
        self.assertNotIn("handed_off", lib.STEP_STATUSES)
        self.assertIn("needs_input", lib.STOP_REASONS)

    def test_no_doc_writes_needs_input_or_handed_off_as_a_status(self):
        offenders = []
        for path in prose_files():
            for n, line in enumerate(read(path).splitlines(), 1):
                if self.STATUS_RE.search(line):
                    offenders.append("%s:%d: %s" % (os.path.relpath(path, PLUGIN), n, line.strip()))
        self.assertEqual(offenders, [], "a result status the post-hook refuses:\n" + "\n".join(offenders))

    def test_no_doc_lists_handed_off_as_an_admissible_status(self):
        offenders = [os.path.relpath(p, PLUGIN) for p in prose_files()
                     if re.search(r"completed \| failed \| interrupted \| handed_off", read(p))]
        self.assertEqual(offenders, [])

    def test_the_stop_reason_is_never_free_text(self):
        offenders = [os.path.relpath(p, PLUGIN) for p in prose_files()
                     if re.search(r'`stop_reason`\s+"needs\s+user\s+input"', read(p))]
        self.assertEqual(offenders, [])


class StartContextKeysTest(unittest.TestCase):

    def test_prior_status_is_the_key_the_start_context_emits(self):
        src = read(os.path.join(PLUGIN, "hooks", "scripts", "acs_state_commands.py"))
        self.assertIn('"prior_status": prior_status', src)
        offenders = [os.path.relpath(p, PLUGIN) for p in prose_files()
                     if "prior_run_status" in read(p)]
        self.assertEqual(offenders, [])

    def test_code_protocol_does_not_promise_a_verdict_context_key(self):
        body = read(os.path.join(PLUGIN, "skills", "code", "references", "protocol.md"))
        self.assertNotRegex(body, r"`iteration` — the review loop's current iteration, and `verdict`")
        self.assertIn("steps/review-code/iter-<n-1>/verdict.json", body)


class DeliveryPathRecordingTest(unittest.TestCase):

    def test_classify_names_no_recording_function_the_kernel_lacks(self):
        body = read(os.path.join(PLUGIN, "skills", "code", "references", "classify.md"))
        self.assertFalse(hasattr(lib.workflow, "record_delivery_path"))
        self.assertNotIn("record_delivery_path", body)
        self.assertIn("delivery_path:", body)
        self.assertIn("## Contract", body)


class DocsSyncBindingDesignTest(unittest.TestCase):

    def test_the_binding_design_is_not_placed_under_the_run_partition(self):
        for rel in ("skills/docs-sync/SKILL.md", "agents/docs-sync-doc-updater.md"):
            body = read(os.path.join(PLUGIN, rel))
            with self.subTest(file=rel):
                self.assertNotIn("`<partition>/design.md`", body)
                self.assertIn("docs/tickets/<", body)

    def test_the_no_doc_impact_path_is_documented(self):
        body = read(os.path.join(PLUGIN, "skills", "docs-sync", "SKILL.md"))
        self.assertNotIn("step 1 below", body)
        self.assertIn('"states": {"files": [], "review"', body)
        self.assertIn("acs.py changes diff", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
