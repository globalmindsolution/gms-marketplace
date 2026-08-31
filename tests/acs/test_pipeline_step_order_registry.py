"""Schema-mirror guard for acs_lib.PIPELINE_STEP_ORDER.

Originating ticket: MAR-6. The constant is genuinely unused within this
ticket (no call site anywhere yet) -- Seam B2 (a sibling ticket) is its first
consumer. The sole obligation here is that the mirrored list never drifts
from the schema enum it mirrors.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

PIPELINE_STATE_SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "pipeline-state.schema.json")


class TestPipelineStepOrderRegistry(unittest.TestCase):
    def test_pipeline_step_order_equals_schema_enum(self):
        with open(PIPELINE_STATE_SCHEMA_PATH, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertEqual(lib.PIPELINE_STEP_ORDER, schema["properties"]["steps"]["propertyNames"]["enum"])


if __name__ == "__main__":
    unittest.main()
