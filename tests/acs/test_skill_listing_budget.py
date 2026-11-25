"""ADR-0151: acs's skills fit inside Claude Code's skill-listing budget.

Claude Code lists every skill to the model with its description, under a
character budget (30,000 characters in the build the v0.7.1 gate ran on). The
CLI fills that list in order, and once it is spent, each remaining skill is
listed by name alone. At about 24,400 characters acs's own entries used most of
it, so in an isolated session `set-doc-status`, `setup`, `ship` and `update`
reached the model with no description. The routing gate measured the result:
setup 15/55, ship 41/50, update 41/50.

The budget is shared with Claude Code's bundled skills and with every other
plugin a consumer installs, so acs keeps its share well under it. This module
measures acs's entries the way the CLI renders them (``- <plugin>:<name>:
<description>``, then `` - <when_to_use>`` when the skill has one), so the
listing cannot outgrow its share again without failing a PR.
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS = os.path.join(REPO_ROOT, "plugins", "acs", "skills")

#: acs's share of the listing, in characters. It is a budget, not a target:
#: about 16,000 is in use, which leaves room for a new skill and for the
#: bundled skills and other plugins that share the 30,000 the CLI allows.
LISTING_BUDGET = 17_000

#: No one description may crowd the others out: the CLI also truncates any
#: single entry past 1,536 characters.
DESCRIPTION_CAP = 900


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return text.split("---", 2)[1]


def field(fm, key):
    match = re.search(r"(?m)^%s: (.*)$" % key, fm)
    return match.group(1) if match else None


def listing_entries():
    for path in sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))):
        fm = frontmatter(path)
        name = field(fm, "name")
        description = field(fm, "description") or ""
        when = field(fm, "when_to_use")
        listed = description + (" - " + when if when else "")
        yield name, "- acs:%s: %s" % (name, listed)


class SkillListingBudgetTest(unittest.TestCase):

    def test_acs_entries_fit_their_share_of_the_listing(self):
        entries = list(listing_entries())
        total = sum(len(line) for _, line in entries) + len(entries) - 1
        self.assertLessEqual(
            total, LISTING_BUDGET,
            "acs's skill listing is %d characters, over its %d budget; shorten "
            "descriptions (the trigger clause stays, mechanics move to the body) "
            "rather than raise the budget -- ADR-0151" % (total, LISTING_BUDGET))

    def test_no_single_description_crowds_out_the_rest(self):
        for name, line in listing_entries():
            with self.subTest(skill=name):
                listed = line.split(": ", 1)[1]
                self.assertLessEqual(len(listed), DESCRIPTION_CAP,
                                     "%s's listing entry is %d characters" % (name, len(listed)))

    def test_every_skill_is_measured(self):
        names = [name for name, _ in listing_entries()]
        self.assertGreaterEqual(len(names), 31)
        self.assertNotIn(None, names)


if __name__ == "__main__":
    unittest.main()
