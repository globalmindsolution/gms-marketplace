"""MAR-114 spec 03 — regression-key derivation + new-ticket.py call-shape (AC-9/AC-10).

Covers the regression-key contract the /acs:test SKILL.md failure-path
prose states (tests/acs/test_test_skill_closed_loop.py pins the prose
itself): a stable key of the form <suite>:<normalized-failing-test-id>, with
a C-1 fallback to the coarse suite-level key <suite>:__suite__ when no
per-test id can be parsed out of the suite's failure output. This module
exercises a reference derivation function encoding that exact contract (the
key-shape contract, not a parser for every test runner's output format — the
spec explicitly scopes parsing individual runner formats out).

Also asserts the new-ticket.py CLI call-shape this spec's mint/link logic
must use: --title (str), --type task (a lib.TICKET_TYPES member),
--description (str) — no other required flag, no shell=True anywhere in the
factory.

Run:  python3 -m unittest tests.acs.test_mar114_regression_key -v
"""

import ast
import os
import re
import sys
import unittest

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import acs_lib  # noqa: E402

NEW_TICKET_PATH = os.path.join(_SCRIPTS_DIR, "new-ticket.py")

_ID_RE = re.compile(r"[A-Za-z0-9_.:/\-]+")


def derive_regression_key(suite, failure_output, exit_code=None):
    """Reference implementation of the SKILL.md failure-path regression-key
    contract (spec 03 Approach step 3): <suite>:<normalized-failing-test-id>,
    or <suite>:__suite__ when no individual failing-test id can be parsed.

    Parsing rule (deliberately minimal — the key SHAPE is the contract, not
    a parser for every runner's output format, per spec 03:74-76): looks for
    a line matching "FAIL <id>" or "FAILED <id>" (case-insensitive); the
    first match's <id> token is normalized (lowercased, whitespace-collapsed)
    and used. No match (bare non-zero exit, compile error, or any other
    suite-level failure with no per-test identifier) -> the coarse
    suite-level fallback key.
    """
    if failure_output:
        match = re.search(r"(?im)^\s*FAILED?\s*:?\s*(\S.*\S|\S)\s*$", failure_output)
        if match:
            raw_id = match.group(1)
            normalized = " ".join(raw_id.lower().split())
            if normalized:
                return "%s:%s" % (suite, normalized)
    return "%s:__suite__" % suite


def build_mint_argv(title, description, ttype="task"):
    """Reference call-shape for the 'not found' / 'found-closed' mint branches
    (spec 03 Approach items 1 and 3): new-ticket.py --title <str> --type task
    --description <str>. No shell=True, no other required flag."""
    return ["new-ticket.py", "--title", title, "--type", ttype, "--description", description]


class RegressionKeyDerivationCase(unittest.TestCase):
    def test_parseable_single_failing_test_id(self):
        key = derive_regression_key(
            "unit", "some noise\nFAILED test_import_endpoint\nmore noise", exit_code=1
        )
        self.assertEqual(key, "unit:test_import_endpoint")

    def test_normalization_lowercase_and_whitespace_collapsed(self):
        key = derive_regression_key(
            "unit", "FAILED   Test_Import_Endpoint   With Spaces  ", exit_code=1
        )
        self.assertEqual(key, "unit:test_import_endpoint with spaces")

    def test_unparseable_bare_nonzero_exit_falls_back_to_suite_level(self):
        key = derive_regression_key("e2e", "", exit_code=1)
        self.assertEqual(key, "e2e:__suite__")

    def test_unparseable_compile_error_falls_back_to_suite_level(self):
        key = derive_regression_key(
            "unit", "SyntaxError: invalid syntax (line 4)\nBuild failed.", exit_code=2
        )
        self.assertEqual(key, "unit:__suite__")

    def test_two_distinct_failures_in_same_suite_produce_two_keys(self):
        key_a = derive_regression_key("unit", "FAILED test_alpha", exit_code=1)
        key_b = derive_regression_key("unit", "FAILED test_beta", exit_code=1)
        self.assertNotEqual(key_a, key_b)
        self.assertEqual(key_a, "unit:test_alpha")
        self.assertEqual(key_b, "unit:test_beta")

    def test_fallback_key_is_a_fixed_marker_not_a_hash(self):
        """Two distinct unparseable failure blobs in the same suite collapse to the SAME
        coarse key (C-1: fixed marker, not a content fingerprint)."""
        key_a = derive_regression_key("flaky", "random noise A", exit_code=1)
        key_b = derive_regression_key("flaky", "totally different noise B", exit_code=3)
        self.assertEqual(key_a, key_b)
        self.assertEqual(key_a, "flaky:__suite__")


class NewTicketCallShapeCase(unittest.TestCase):
    """Asserts the mint-call argv shape matches new-ticket.py's actual CLI contract."""

    def test_mint_argv_shape_matches_new_ticket_cli_contract(self):
        argv = build_mint_argv("unit: test_import_endpoint regression", "acs-regression-key: unit:test_import_endpoint\n\nsummary text")
        self.assertIn("--title", argv)
        self.assertIn("--type", argv)
        type_idx = argv.index("--type")
        self.assertEqual(argv[type_idx + 1], "task")
        self.assertIn("task", acs_lib.TICKET_TYPES)
        self.assertIn("--description", argv)
        title_idx = argv.index("--title")
        self.assertIsInstance(argv[title_idx + 1], str)
        desc_idx = argv.index("--description")
        self.assertIsInstance(argv[desc_idx + 1], str)

    def test_new_ticket_py_requires_only_title_and_type(self):
        """new-ticket.py's own argparse contract: --title and --type are the only required
        flags (dest="ttype", choices=lib.TICKET_TYPES); --description defaults to ""."""
        with open(NEW_TICKET_PATH, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('parser.add_argument("--title", required=True)', src)
        self.assertIn('dest="ttype", required=True, choices=lib.TICKET_TYPES', src)
        self.assertIn('parser.add_argument("--description", default="")', src)

    def test_new_ticket_py_never_uses_shell_true(self):
        """R1 adjacency: new-ticket.py itself never shells out with shell=True."""
        with open(NEW_TICKET_PATH, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("shell=True", src)

    def test_new_ticket_py_is_valid_python_unedited_contract_surface(self):
        """Sanity: new-ticket.py still parses as valid Python (this spec reuses it unmodified)."""
        with open(NEW_TICKET_PATH, encoding="utf-8") as fh:
            src = fh.read()
        ast.parse(src)  # raises SyntaxError if the file were ever mutated into invalid Python


if __name__ == "__main__":
    unittest.main()
