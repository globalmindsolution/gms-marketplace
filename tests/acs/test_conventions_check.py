"""Unit tests for the convention checker that /acs:setup ships into consumer repos.

The checker (plugins/acs/templates/ci/check-conventions.py) runs in the
consumer's CI with ZERO acs dependencies — only the Python stdlib — so these
tests load it straight from the template path and drive its pure `evaluate()`
core. It checks one thing: that the PR description names its ticket.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join(REPO_ROOT, "plugins", "acs", "templates", "ci", "check-conventions.py")

_spec = importlib.util.spec_from_file_location("acs_check_conventions", CHECKER)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)


def settings(**overrides):
    base = {"ticket_prefix": "MAR"}
    base.update(overrides)
    return base


def ctx(branch="task/MAR-12-add-foo", title="[MAR-12] Add foo",
        body=None, labels=None, commits=None):
    if body is None:
        body = "## Summary\nx\n## Ticket\nMAR-12\n## Changes\nx\n## Test plan\nx\n"
    return {
        "branch": branch,
        "title": title,
        "body": body,
        "labels": ["ACS"] if labels is None else labels,
        "commit_subjects": ["MAR-12 add foo"] if commits is None else commits,
    }


def headings(*names):
    return "".join("## %s\n\nbody\n\n" % n for n in names)


class EvaluatePrTests(unittest.TestCase):
    """CI checks one thing (ADR-0106): the PR description names its ticket."""

    def assertPasses(self, res):
        self.assertEqual(res.errors, [], "unexpected errors: %s" % res.errors)
        self.assertIsNone(res.exempt)

    def assertFails(self, res, heading):
        self.assertIn(heading, [h for h, _ in res.errors],
                      "expected a %r error, got %s" % (heading, res.errors))

    def test_a_description_naming_the_ticket_passes(self):
        self.assertPasses(cc.evaluate(settings(), ctx(), "pr"))

    def test_an_issue_reference_or_link_names_a_ticket_too(self):
        for body in ("Closes #161", "See https://github.com/acme/shop/issues/161"):
            with self.subTest(body=body):
                self.assertPasses(cc.evaluate(settings(), ctx(body=body), "pr"))

    def test_a_description_naming_no_ticket_fails(self):
        for body in ("", "## Summary\nAdd foo\n", "Fixes the thing, step #one"):
            with self.subTest(body=body):
                self.assertFails(cc.evaluate(settings(), ctx(body=body), "pr"), "ticket_link")

    def test_look_alikes_do_not_count(self):
        """Another repo's prefix, an HTML entity and a URL fragment are not a
        ticket reference."""
        for body in ("SHOP-12", "caf&#233;", "docs/page#3"):
            with self.subTest(body=body):
                self.assertFails(cc.evaluate(settings(), ctx(body=body), "pr"), "ticket_link")

    def test_branch_title_label_and_commits_are_not_checked(self):
        """A PR opened from any branch, with any title, no label and any commit
        subjects passes as long as its description names the ticket."""
        res = cc.evaluate(settings(), ctx(branch="claude/whatever", title="wip", labels=[],
                                          commits=["wip"], body="Work for MAR-12"), "pr")
        self.assertPasses(res)
        self.assertEqual(res.skipped, [])

    def test_the_only_check_is_the_ticket_link(self):
        self.assertEqual(cc.MODE_CHECKS, {"pr": ["ticket_link"]})


class ExemptionTests(unittest.TestCase):
    def test_exempt_label_skips_everything(self):
        res = cc.evaluate(settings(), ctx(branch="whatever", title="nope",
                                          labels=["acs-exempt"], body=""), "pr")
        self.assertIsNotNone(res.exempt)
        self.assertEqual(res.errors, [])

    def test_exempt_branch_globs_skip(self):
        for branch in ("release/v1.2.0", "dependabot/npm/x", "renovate/y"):
            with self.subTest(branch=branch):
                res = cc.evaluate(settings(), ctx(branch=branch, labels=[], body=""), "pr")
                self.assertIsNotNone(res.exempt)
                self.assertEqual(res.errors, [])

    def test_the_exemptions_are_fixed_not_configurable(self):
        s = settings(enforcement={"exempt_branches": ["hotfix/*"], "exempt_label": "skip-acs"})
        self.assertIsNone(cc.evaluate(s, ctx(branch="hotfix/x", labels=[], body=""), "pr").exempt)
        self.assertIsNone(cc.evaluate(s, ctx(branch="b", labels=["skip-acs"], body=""), "pr").exempt)
        self.assertIsNotNone(cc.evaluate(s, ctx(branch="release/x", labels=[], body=""), "pr").exempt)


class DefaultsAndMalformedSettingsTests(unittest.TestCase):
    """ADR-0105: an absent prefix takes the plugin's default; a malformed one fails."""

    def test_no_settings_checks_against_the_default_prefix(self):
        self.assertEqual(cc.evaluate({}, ctx(body="ACS-12"), "pr").errors, [])

    def test_the_default_prefix_is_enforced(self):
        res = cc.evaluate({}, ctx(body="MAR-12"), "pr")
        self.assertIn("ticket_link", [h for h, _ in res.errors])

    def test_malformed_prefix_fails_closed(self):
        res = cc.evaluate({"ticket_prefix": "mar"}, ctx(), "pr")
        self.assertIn("settings", [h for h, _ in res.errors])


class MainTests(unittest.TestCase):
    def test_only_the_pr_mode_exists(self):
        with mock.patch.object(sys, "stderr"):
            self.assertEqual(cc.main(["--mode", "pre-push"]), 2)
            self.assertEqual(cc.main(["--mode", "commit-msg"]), 2)


class MirrorsThePluginTest(unittest.TestCase):
    """The checker runs without the plugin, so it carries its own copy of the
    few constants it needs. This keeps them level with acs_lib.conventions."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
        import acs_lib
        cls.lib = acs_lib

    def test_the_ticket_prefix_default_matches(self):
        self.assertEqual(cc.DEFAULT_TICKET_PREFIX, self.lib.DEFAULT_TICKET_PREFIX)

    def test_the_exemptions_match(self):
        self.assertEqual(tuple(cc.EXEMPT_BRANCHES), tuple(self.lib.conventions.EXEMPT_BRANCHES))
        self.assertEqual(cc.EXEMPT_LABEL, self.lib.conventions.EXEMPT_LABEL)

    def test_the_schema_documents_the_prefix_default(self):
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "schemas",
                               "settings.schema.json"), encoding="utf-8") as fh:
            props = json.load(fh)["properties"]
        self.assertEqual(props["ticket_prefix"]["default"], self.lib.DEFAULT_TICKET_PREFIX)

    def test_this_repos_installed_copy_is_the_template(self):
        installed = os.path.join(REPO_ROOT, ".acs", "ci", "check-conventions.py")
        with open(CHECKER, "rb") as a, open(installed, "rb") as b:
            self.assertEqual(a.read(), b.read(),
                             ".acs/ci/check-conventions.py is a copy of the template; "
                             "re-copy it rather than editing it")


if __name__ == "__main__":
    unittest.main()
