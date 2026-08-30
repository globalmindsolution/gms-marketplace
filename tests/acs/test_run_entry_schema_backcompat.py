"""Backward-compatibility guard for skill-state.schema.json's run-entry
`model_usage` property (D4 Option A: additive, optional, forward-only).

Originating ticket: MAR-3.

Stdlib-only where possible; the full-schema validation tests guard a bare
`import jsonschema` behind `skipUnless` so the CI "Tests & validation" job
(which does not install jsonschema) stays green -- see
tests/acs/test_principles_doc_set.py for the same pattern.
"""

import json
import os
import unittest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "skill-state.schema.json")

_LEGACY_ENTRY = {
    "started_at": "2026-01-01T00:00:00Z",
    "ended_at": "2026-01-01T00:05:00Z",
    "status": "completed",
    "tokens": {"input": 10, "output": 20},
    "cost_usd": 0.0,
}

_LEGACY_STATE = {
    "skill": "code",
    "ticket_id": "SHOP-1",
    "states": {},
    "findings": [],
    "errors": [],
    "runs": [_LEGACY_ENTRY],
}


def _run_entry_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    return schema, schema["properties"]["runs"]["items"]


class TestRunEntrySchemaModelUsageProperty(unittest.TestCase):
    """Structural checks on the schema file itself, no jsonschema needed."""

    def test_model_usage_property_declared_on_run_entry(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertIn("model_usage", run_entry_schema["properties"])
        prop = run_entry_schema["properties"]["model_usage"]
        self.assertEqual(prop["type"], "array")

    def test_model_usage_not_added_to_required(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertNotIn("model_usage", run_entry_schema.get("required", []))

    def test_tokens_object_additional_properties_still_false(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertEqual(run_entry_schema["properties"]["tokens"]["additionalProperties"], False)
        self.assertNotIn("model_usage", run_entry_schema["properties"]["tokens"]["properties"])


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
class TestRunEntrySchemaBackcompatValidation(unittest.TestCase):
    """AC-6 of the epic: a MAR-1-era run entry without model_usage still
    validates against the amended schema (the "renders as no data" half is
    Spec 04 test 5)."""

    def test_legacy_run_entry_without_model_usage_still_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(_LEGACY_STATE, schema)

    def test_run_entry_with_model_usage_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["model_usage"] = [
            {"model": "claude-opus", "input": 10, "output": 20, "cache_creation": 0,
             "cache_read": 0, "cost_usd": 0.05, "cost_basis": "apportioned"},
        ]
        jsonschema.validate(state, schema)

    def test_tokens_object_still_rejects_an_unknown_key(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["tokens"]["model_usage"] = []
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(state, schema)

    def test_model_usage_item_without_model_key_is_rejected(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["model_usage"] = [
            {"input": 10, "output": 20, "cache_creation": 0, "cache_read": 0},
        ]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(state, schema)


class TestRunEntrySchemaRoleDurationProperty(unittest.TestCase):
    """MAR-5: `role_duration` is additive/optional/forward-only, parallel to
    and independent of role_usage's own (untouched) shape (ADR 0084)."""

    def test_role_duration_property_declared_on_run_entry(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertIn("role_duration", run_entry_schema["properties"])
        prop = run_entry_schema["properties"]["role_duration"]
        self.assertEqual(prop["type"], "array")

    def test_role_duration_is_not_added_to_required(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertNotIn("role_duration", run_entry_schema.get("required", []))


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
class TestRunEntrySchemaRoleDurationValidation(unittest.TestCase):
    def test_legacy_run_entry_without_role_duration_still_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(_LEGACY_STATE, schema)

    def test_run_entry_with_role_duration_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["role_duration"] = [
            {"role": "coordinator", "api_duration_ms": 1500, "duration_basis": "derived"},
            {"role": "executor", "api_duration_ms": None, "duration_basis": "unavailable"},
        ]
        jsonschema.validate(state, schema)

    def test_role_usage_object_still_accepts_its_documented_shape(self):
        """Regression guard: role_duration's addition must not touch
        role_usage's sibling schema block."""
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["role_usage"] = [
            {"role": "coordinator", "input": 10, "output": 20, "cache_creation": 0,
             "cache_read": 0, "cost_usd": 0.05, "cost_basis": "apportioned"},
        ]
        jsonschema.validate(state, schema)


if __name__ == "__main__":
    unittest.main()
