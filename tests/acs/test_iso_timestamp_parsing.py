"""parse_iso: which ISO-8601 forms acs accepts, and which it deliberately does not.

MAR-520. Claude Code transcript records carry fractional seconds and explicit
offsets, and the old strict `%Y-%m-%dT%H:%M:%SZ` parse dropped every one of
them silently. Widening that is bounded by two invariants, both asserted here:

* a bare date stays unparseable (ADR 0020 -- the panel-7 lead/cycle callers
  read None as "no data"; a date parsed as midnight would render a
  real-looking number instead);
* acceptance does not vary by interpreter. `datetime.fromisoformat` gained
  most of this leniency in CPython 3.11, so a fromisoformat-backed
  implementation accepts records on 3.12 that it drops on 3.9 -- this repo's
  support floor per .github/workflows/ci.yml, and the exact silent-drop this
  ticket exists to remove.

Run:  python3 -m unittest tests.acs.test_iso_timestamp_parsing -v
"""

import os
import sys
import unittest
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))

import acs_lib as lib  # noqa: E402


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class AcceptedFormsTest(unittest.TestCase):
    """Every form acs or Claude Code actually writes."""

    def test_the_strict_form_acs_writes(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00Z"), utc(2026, 6, 20, 9, 0, 0))

    def test_z_and_explicit_zero_offset_are_the_same_instant(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00Z"),
                         lib.parse_iso("2026-06-20T09:00:00+00:00"))

    def test_three_digit_fraction(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00.123Z"),
                         utc(2026, 6, 20, 9, 0, 0, 123000))

    def test_six_digit_fraction(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00.123456Z"),
                         utc(2026, 6, 20, 9, 0, 0, 123456))

    def test_short_fraction_is_padded_not_rejected(self):
        """A 1- or 2-digit fraction is `.12` == 120ms, not 12 microseconds."""
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00.12Z"),
                         utc(2026, 6, 20, 9, 0, 0, 120000))
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00.1Z"),
                         utc(2026, 6, 20, 9, 0, 0, 100000))

    def test_sub_microsecond_precision_is_truncated_not_rejected(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00.1234567Z"),
                         utc(2026, 6, 20, 9, 0, 0, 123456))

    def test_positive_offset_normalises_to_utc(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00+02:00"), utc(2026, 6, 20, 7, 0, 0))

    def test_negative_offset_normalises_to_utc(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00-05:30"), utc(2026, 6, 20, 14, 30, 0))

    def test_colonless_offset_is_accepted(self):
        """`+0200` is the form CPython < 3.11's fromisoformat rejects."""
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00+0200"),
                         lib.parse_iso("2026-06-20T09:00:00+02:00"))

    def test_a_naive_timestamp_is_read_as_utc(self):
        self.assertEqual(lib.parse_iso("2026-06-20T09:00:00"), utc(2026, 6, 20, 9, 0, 0))

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(lib.parse_iso("  2026-06-20T09:00:00Z\n"), utc(2026, 6, 20, 9, 0, 0))

    def test_every_accepted_form_is_timezone_aware_utc(self):
        for text in ("2026-06-20T09:00:00Z", "2026-06-20T09:00:00",
                     "2026-06-20T09:00:00+0200", "2026-06-20T09:00:00.5Z"):
            parsed = lib.parse_iso(text)
            self.assertEqual(parsed.tzinfo, timezone.utc, msg=text)


class BareDateStaysUnparseableTest(unittest.TestCase):
    """ADR 0020: the panel-7 lead/cycle callers depend on None for a bare date.

    Widening parse_iso to accept one would turn "no data" into a
    midnight-anchored number that looks measured. The directive is restated in
    code at metrics_aggregate.py.
    """

    def test_a_bare_date_returns_none(self):
        self.assertIsNone(lib.parse_iso("2026-06-20"))

    def test_elapsed_seconds_between_bare_dates_stays_none(self):
        self.assertIsNone(lib.elapsed_seconds("2026-01-01", "2026-01-02"))

    def test_lock_is_stale_does_not_break_a_lock_on_a_bare_date(self):
        self.assertFalse(lib.lock_is_stale(
            {"created_at": "2020-01-01", "host": "some-other-host", "pid": None}))


class RejectedFormsTest(unittest.TestCase):
    """Tolerance is bounded: these are not instants acs or Claude Code writes."""

    def test_space_separator_is_rejected(self):
        self.assertIsNone(lib.parse_iso("2026-06-20 09:00:00Z"))

    def test_basic_format_is_rejected(self):
        self.assertIsNone(lib.parse_iso("20260620T090000Z"))

    def test_an_impossible_date_is_rejected(self):
        self.assertIsNone(lib.parse_iso("2026-02-30T09:00:00Z"))

    def test_an_impossible_time_is_rejected(self):
        self.assertIsNone(lib.parse_iso("2026-06-20T25:00:00Z"))

    def test_time_without_seconds_is_rejected(self):
        self.assertIsNone(lib.parse_iso("2026-06-20T09:00Z"))

    def test_trailing_text_is_rejected(self):
        self.assertIsNone(lib.parse_iso("2026-06-20T09:00:00Z and then some"))

    def test_empty_and_blank_are_rejected(self):
        self.assertIsNone(lib.parse_iso(""))
        self.assertIsNone(lib.parse_iso("   "))

    def test_non_strings_are_rejected(self):
        for value in (None, 5, 1750000000.0, [], {}, object()):
            self.assertIsNone(lib.parse_iso(value), msg=repr(value))


class InterpreterIndependenceTest(unittest.TestCase):
    """The acceptance set must not be inherited from fromisoformat's version.

    Each form below is one CPython 3.11 taught fromisoformat and 3.9/3.10
    reject, so an implementation delegating to it would give a different answer
    per interpreter. Asserting them pins acceptance to acs's own parser.
    """

    VERSION_SENSITIVE = (
        "2026-06-20T09:00:00Z",           # bare Z suffix
        "2026-06-20T09:00:00.12Z",        # fraction that is not 3 or 6 digits
        "2026-06-20T09:00:00.1234567Z",   # sub-microsecond precision
        "2026-06-20T09:00:00+0200",       # colon-less offset
    )

    def test_forms_that_differ_across_cpython_versions_are_all_accepted(self):
        for text in self.VERSION_SENSITIVE:
            self.assertIsNotNone(lib.parse_iso(text), msg=text)

    def test_parse_iso_does_not_delegate_to_fromisoformat(self):
        """A structural guard on the mechanism, not just the outcome: if this
        function ever routes through fromisoformat again, its acceptance set
        silently becomes interpreter-dependent and the assertions above stop
        meaning what they say on the 3.9 leg of the CI matrix."""
        import ast
        import inspect
        import textwrap
        func = ast.parse(textwrap.dedent(inspect.getsource(lib.parse_iso))).body[0]
        if ast.get_docstring(func):
            func.body = func.body[1:]  # the docstring names it to explain why
        self.assertNotIn("fromisoformat", ast.dump(func))


if __name__ == "__main__":
    unittest.main()
