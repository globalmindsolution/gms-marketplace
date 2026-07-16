"""MAR-113 — /acs:init Step 4 documents and defaults operations_path (AC-3).

Prose-contract unit test for `plugins/acs/skills/init/SKILL.md`.
`operations_path` must be defaulted like `architecture_path`/`quality_path` in
the Step 4 optional-settings batch, and must NOT be added to the "always ask
explicitly" carve-out (which names only `### models` and `e2e`).

Stdlib-only (os, re, unittest), mirroring
tests/acs/test_init_quality_path.py's `section()` bounded-window
technique so a stray mention elsewhere in the file cannot satisfy either
assertion.

Run:  python3 -m unittest tests.acs.test_mar113_operations_path_init -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "init", "SKILL.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


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


class Mar113OperationsPathInitCase(unittest.TestCase):
    """Fixture: read the init SKILL.md once and isolate its Step 4 section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.step4 = section(cls.body, "## Step 4")

    def test_step4_batch_documents_operations_path_default(self):
        """The Step 4 batch-default bullet list names operations_path with its
        default 'docs/operations' in a bounded window after the marker,
        proving the default is documented (not merely present in the
        schema)."""
        m = re.search(r"`operations_path`", self.step4)
        self.assertIsNotNone(
            m, "Step 4 must document an `operations_path` bullet (AC-3)"
        )
        window = self.step4[m.start():m.start() + 300]
        self.assertIn(
            "docs/operations", window,
            msg="the `operations_path` bullet must state its default "
                "'docs/operations' within a bounded window of the marker (AC-3)",
        )

    def test_step4_names_create_operations_as_consumer(self):
        """The operations_path bullet names /acs:create-operations as the
        consuming skill, mirroring how the quality_path bullet names
        /acs:create-quality."""
        m = re.search(r"`operations_path`", self.step4)
        self.assertIsNotNone(m)
        window = self.step4[m.start():m.start() + 300]
        self.assertIn(
            "create-operations", window,
            msg="the `operations_path` bullet must name /acs:create-operations "
                "as the consumer (AC-3)",
        )

    def test_carveout_does_not_name_operations_path(self):
        """The 'always ask explicitly' carve-out sentence (naming `### models`
        and e2e) must NOT gain operations_path — proving operations_path is a
        silently-defaultable batch entry, not an always-ask exception."""
        carveout = re.search(
            r"(?s)present these as a batch.{0,900}", self.step4, re.IGNORECASE
        )
        self.assertIsNotNone(
            carveout, "Step 4 must retain the 'present these as a batch' framing"
        )
        window = carveout.group(0)
        self.assertNotIn(
            "operations_path", window,
            msg="operations_path must NOT appear in the always-ask carve-out "
                "window — it is defaulted like architecture_path, not an "
                "always-ask exception (AC-3)",
        )


if __name__ == "__main__":
    unittest.main()
