"""update_pipeline's `extra` channel: a writer for step fields it does not own.

MAR-510. /acs:ship keeps a `fix_loops` counter on the `test` step entry and
had no supported way to write it -- the skill's prose claimed update_pipeline
"already writes an arbitrary-shape step dict", which it did not. `extra` merges
caller fields, `extra={"<key>": None}` removes one, and the fields the step
entry itself owns stay unwritable through it.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


class PipelineCase(AcsWorkspaceCase):
    """AcsWorkspaceCase plus the repo id its fixture remote implies."""

    @property
    def repo_id(self):
        return lib.build_context(self.repo)["repo_id"]


class UpdatePipelineExtraTest(PipelineCase):
    """update_pipeline(extra=...) merges caller fields without letting them
    overwrite the fields the step entry owns."""

    def _tdir(self, ticket_id="SHOP-1"):
        tdir = lib.ticket_dir(self.ws, self.repo_id, ticket_id)
        os.makedirs(tdir, exist_ok=True)
        return tdir

    def test_extra_fields_are_merged(self):
        tdir = self._tdir()
        data = lib.update_pipeline(tdir, "SHOP-1", "test", "in_progress", extra={"fix_loops": 2})
        self.assertEqual(data["steps"]["test"]["fix_loops"], 2)

    def test_none_value_removes_the_field(self):
        tdir = self._tdir()
        lib.update_pipeline(tdir, "SHOP-1", "test", "in_progress", extra={"fix_loops": 2})
        data = lib.update_pipeline(tdir, "SHOP-1", "test", "completed", extra={"fix_loops": None})
        self.assertNotIn("fix_loops", data["steps"]["test"])

    def test_reserved_keys_are_not_overridable(self):
        """A caller cannot rewrite the step's own status or timestamps."""
        tdir = self._tdir()
        data = lib.update_pipeline(tdir, "SHOP-1", "test", "failed",
                                   extra={"status": "completed", "ended_at": "whenever",
                                          "summary": "spoofed"})
        self.assertEqual(data["steps"]["test"]["status"], "failed")
        self.assertNotEqual(data["steps"]["test"]["ended_at"], "whenever")
        self.assertNotEqual(data["steps"]["test"].get("summary"), "spoofed")


if __name__ == "__main__":
    unittest.main()
