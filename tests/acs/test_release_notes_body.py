"""The release body fits GitHub's limit, and v0.5.0's real section is the proof.

release.yml created the v0.5.0 tag, then `gh release create` failed with
HTTP 422 "body is too long (maximum is 125000 characters)": the section was
142,000 characters. .github/scripts/release_notes_body.py now cuts a section
over the limit at an entry boundary and links the full one.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, ".github", "scripts"))
import release_notes_body as rnb  # noqa: E402

GITHUB_LIMIT = 125000
REPO = "https://github.com/globalmindsolution/gms-marketplace"


def changelog():
    with open(os.path.join(REPO_ROOT, rnb.CHANGELOG), encoding="utf-8") as fh:
        return fh.read()


class ReleaseBodyTest(unittest.TestCase):

    def test_the_v0_5_0_section_fits_and_links_the_full_section(self):
        text = changelog()
        self.assertGreater(len(rnb.section(text, "0.5.0")), GITHUB_LIMIT,
                           "the case this guards: the section alone is over the limit")
        body = rnb.body(text, "0.5.0", REPO)
        self.assertLessEqual(len(body), GITHUB_LIMIT)
        self.assertIn(REPO + "/blob/v0.5.0/plugins/acs/CHANGELOG.md#050---2026-09-30", body)

    def test_a_short_section_is_the_section_unchanged(self):
        text = changelog()
        self.assertEqual(rnb.body(text, "0.4.9", REPO), rnb.section(text, "0.4.9"))

    def test_link_reference_definitions_are_dropped(self):
        text = "## [1.0.0] - 2026-01-01\n- a thing\n[1.0.0]: https://example.com\n"
        self.assertEqual(rnb.section(text, "1.0.0"), "- a thing\n")

    def test_a_missing_section_is_none(self):
        self.assertIsNone(rnb.body("## [1.0.0]\n- x\n", "2.0.0", REPO))

    def test_the_cut_never_splits_an_entry(self):
        entry = "- an entry\n  that continues on a second line\n"
        notes = "### Added\n" + entry * 50
        cut = rnb.truncate(notes, "URL", limit=400)
        self.assertLessEqual(len(cut), 400)
        kept = cut.split("\n\n---\n\n")[0]
        self.assertTrue(kept.endswith("that continues on a second line"), kept[-80:])
        self.assertIn("URL", cut)


if __name__ == "__main__":
    unittest.main()
