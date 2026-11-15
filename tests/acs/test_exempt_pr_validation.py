"""validate_exempt_pr — which PRs `/acs:merge-pr --pr <n>` may land.

The exempt path is for PRs no ticket backs. A PR is ticket-backed when its head
branch embeds a ticket id (every ticket PR's branch is `<type>/<ticket_id>-<slug>`),
or when it carries the `ACS` pipeline label with no exemption. The label alone is
not proof: `/acs:create-pr` labels a ticketless PR both `ACS` and `acs-exempt`,
and `/acs:release` labels its `release/*` PR `ACS`. Both must land here.

Run:  python3 -m unittest tests.acs.test_exempt_pr_validation -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import SCRIPTS  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib as lib  # noqa: E402

SETTINGS = {"ticket_prefix": "ACS"}


def pr(branch, labels=(), state="OPEN", draft=False, number=42):
    return {"number": number, "headRefName": branch, "state": state, "isDraft": draft,
            "labels": [{"name": name} for name in labels]}


class ExemptGrantTest(unittest.TestCase):
    def test_ticketless_create_pr_pr_carrying_both_labels_is_granted(self):
        ok, reason = lib.validate_exempt_pr(pr("docs/baseline-prd", ["ACS", "acs-exempt"]), SETTINGS)
        self.assertTrue(ok, reason)
        self.assertIn("acs-exempt", reason)

    def test_release_pr_carrying_the_pipeline_label_is_granted_by_branch(self):
        ok, reason = lib.validate_exempt_pr(pr("release/v0.8.0", ["ACS"]), SETTINGS)
        self.assertTrue(ok, reason)
        self.assertIn("release/*", reason)

    def test_exempt_label_alone_is_granted(self):
        ok, _ = lib.validate_exempt_pr(pr("hotfix/health-casing", ["acs-exempt"]), SETTINGS)
        self.assertTrue(ok)

    def test_each_exempt_branch_pattern_is_granted(self):
        for branch in ("release/v1.2.3", "dependabot/pip/requests-2.32", "renovate/node-22"):
            with self.subTest(branch=branch):
                ok, _ = lib.validate_exempt_pr(pr(branch), SETTINGS)
                self.assertTrue(ok)

    def test_labels_given_as_plain_strings_are_read(self):
        ok, _ = lib.validate_exempt_pr(
            {"number": 7, "headRefName": "chore/x", "state": "OPEN", "labels": ["acs-exempt"]}, SETTINGS)
        self.assertTrue(ok)


class TicketBackedRefusalTest(unittest.TestCase):
    def test_ticket_id_in_branch_is_refused_with_its_id(self):
        ok, message = lib.validate_exempt_pr(pr("task/ACS-12-wishlist", ["ACS"]), SETTINGS)
        self.assertFalse(ok)
        self.assertIn("ticket-backed", message)
        self.assertIn("/acs:merge-pr ACS-12", message)

    def test_ticket_id_in_branch_wins_over_the_exempt_label(self):
        ok, message = lib.validate_exempt_pr(pr("task/ACS-12-wishlist", ["ACS", "acs-exempt"]), SETTINGS)
        self.assertFalse(ok)
        self.assertIn("/acs:merge-pr ACS-12", message)

    def test_ticket_id_in_an_exempt_looking_branch_is_still_refused(self):
        ok, _ = lib.validate_exempt_pr(pr("release/ACS-31-notes"), SETTINGS)
        self.assertFalse(ok)

    def test_pipeline_label_without_an_exemption_is_refused(self):
        ok, message = lib.validate_exempt_pr(pr("feature/search", ["ACS"]), SETTINGS)
        self.assertFalse(ok)
        self.assertIn("carries the 'ACS' label", message)
        self.assertIn("/acs:merge-pr <TICKET-ID>", message)

    def test_custom_prefix_is_used_to_find_the_ticket(self):
        ok, message = lib.validate_exempt_pr(pr("bug/SHOP-9-rounding", ["acs-exempt"]), {"ticket_prefix": "SHOP"})
        self.assertFalse(ok)
        self.assertIn("SHOP-9", message)


class OtherRefusalTest(unittest.TestCase):
    def test_unlabelled_pr_on_an_ordinary_branch_is_not_sanctioned(self):
        ok, message = lib.validate_exempt_pr(pr("chore/tidy"), SETTINGS)
        self.assertFalse(ok)
        self.assertIn("not a sanctioned exempt PR", message)

    def test_closed_pr_is_refused_before_anything_else(self):
        ok, message = lib.validate_exempt_pr(pr("release/v1.0.0", ["acs-exempt"], state="MERGED"), SETTINGS)
        self.assertFalse(ok)
        self.assertIn("not OPEN", message)

    def test_draft_pr_is_refused(self):
        ok, message = lib.validate_exempt_pr(pr("release/v1.0.0", ["acs-exempt"], draft=True), SETTINGS)
        self.assertFalse(ok)
        self.assertIn("draft", message)


if __name__ == "__main__":
    unittest.main()
