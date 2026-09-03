"""MAR-403 (parent MAR-401) — the canonical gh-failure diagnostic in acs_lib.py.

Unit tests for GH_ACCESS_DENIED_MARKER, GH_ACCESS_HINT, GH_GENERIC_HINT, and
the pure gh_failure_hint(stderr_text) predicate (Option F / decision D3).
These are the only tests exercising T1's new, measured statements in
plugins/acs/hooks/scripts/acs_lib.py; T2's and T3's outputs are prose,
covered by their own doc/anti-drift test modules rather than by line
coverage.

Run:  python3 -m unittest tests.acs.test_gh_call_criticality -v
"""

import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

from acs_lib import (  # noqa: E402
    GH_ACCESS_DENIED_MARKER,
    GH_ACCESS_HINT,
    GH_GENERIC_HINT,
    gh_failure_hint,
)

# The 403 body measured in this session (design.md:31), quoted verbatim.
MEASURED_403_BODY = (
    '{"message":"GitHub access is not enabled for this session. An org admin '
    'must connect the Claude GitHub App for this organization.",'
    '"documentation_url":"https://docs.anthropic.com/en/docs/claude-code/github-actions"}'
)


class GhFailureHintTest(unittest.TestCase):
    """gh_failure_hint(stderr_text) -> str: pure, never raises, both branches covered."""

    def test_marker_is_the_measured_403_substring(self):
        self.assertEqual(
            GH_ACCESS_DENIED_MARKER, "GitHub access is not enabled for this session"
        )
        self.assertIn(GH_ACCESS_DENIED_MARKER, MEASURED_403_BODY)

    def test_access_denied_stderr_selects_the_canonical_hint(self):
        stderr = "some preamble\n%s\ngh: (HTTP 403)" % MEASURED_403_BODY
        self.assertEqual(gh_failure_hint(stderr), GH_ACCESS_HINT)

    def test_unrelated_stderr_selects_the_generic_hint(self):
        stderr = "gh: could not resolve host: github.com"
        self.assertEqual(gh_failure_hint(stderr), GH_GENERIC_HINT)

    def test_empty_and_none_stderr_return_the_generic_hint_without_raising(self):
        self.assertEqual(gh_failure_hint(""), GH_GENERIC_HINT)
        self.assertEqual(gh_failure_hint(None), GH_GENERIC_HINT)

    def test_non_string_input_never_raises(self):
        for value in (b"not a str", 42, ["list"], {"a": 1}):
            result = gh_failure_hint(value)
            self.assertIsInstance(result, str)
            self.assertTrue(result)

    def test_hint_is_never_empty_for_any_input(self):
        for value in (
            MEASURED_403_BODY,
            "unrelated stderr",
            "",
            None,
            b"bytes",
            0,
            [],
        ):
            self.assertTrue(gh_failure_hint(value))

    def test_gh_failure_hint_is_pure_no_subprocess(self):
        import acs_lib

        with mock.patch.object(acs_lib.subprocess, "run", side_effect=AssertionError(
            "gh_failure_hint must never invoke subprocess"
        )):
            self.assertEqual(
                gh_failure_hint(MEASURED_403_BODY), GH_ACCESS_HINT
            )
            self.assertEqual(
                gh_failure_hint("could not resolve host"), GH_GENERIC_HINT
            )

    def test_canonical_hint_names_the_actual_remedy(self):
        self.assertIn("Claude GitHub App", GH_ACCESS_HINT)
        self.assertIn("org admin", GH_ACCESS_HINT)


if __name__ == "__main__":
    unittest.main()
