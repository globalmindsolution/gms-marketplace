"""Backward-compatibility guard for skill-state.schema.json's run-entry
`model_usage` property (D4 Option A: additive, optional, forward-only), and
for the `api_duration_*` run-entry/role_usage properties, the
`pipeline-state.schema.json`/`metrics.schema.json` `totals` counters added
alongside them, and the `gate_enforcement` run-entry property.

Originating tickets: MAR-3 (model_usage); MAR-6 (api_duration_*, duration
counters); MAR-583 (gate_enforcement).

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
SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "skill-state.schema.json")
PIPELINE_STATE_SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "pipeline-state.schema.json")
METRICS_SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "acs", "schemas", "metrics.schema.json")

# The exact 5 api_duration_scope strings cost_sampler.allocate_cost can emit
# (Spec 01, this ticket). Hardcoded rather than imported from cost_sampler.py:
# T1 defines these values in the same plan this test was written from, and
# may land in a parallel commit -- the schema's own enum is what this test
# guards, so it is compared against the plan's literal spec, not the sibling
# module's source.
_API_DURATION_SCOPE_VALUES = [
    "session_total",
    "main_session_only",
    "no_unconsumed_sample_in_window",
    "cost_total_reset",
    "duration_unavailable_on_cursor",
]

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


class TestRunEntrySchemaApiDurationProperty(unittest.TestCase):
    """Structural checks on the schema file itself, no jsonschema needed.

    D4 Option A additive declarations for the new API-duration fields
    (Spec 03): api_duration_ms/api_duration_basis mirror cost_usd/cost_basis's
    own shapes; api_duration_scope is a schema property distinct from
    cost_scope, not an extension of cost_scope's own enum."""

    def test_api_duration_ms_property_declared_on_run_entry(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertIn("api_duration_ms", run_entry_schema["properties"])
        prop = run_entry_schema["properties"]["api_duration_ms"]
        self.assertEqual(prop, run_entry_schema["properties"]["cost_usd"])

        role_usage_item = run_entry_schema["properties"]["role_usage"]["items"]
        self.assertIn("api_duration_ms", role_usage_item["properties"])
        self.assertEqual(role_usage_item["properties"]["api_duration_ms"], prop)
        self.assertTrue(role_usage_item.get("additionalProperties") is True)

    def test_api_duration_basis_property_declared(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertIn("api_duration_basis", run_entry_schema["properties"])
        prop = run_entry_schema["properties"]["api_duration_basis"]
        self.assertEqual(prop["enum"], ["measured", "apportioned", "unavailable"])

        role_usage_item = run_entry_schema["properties"]["role_usage"]["items"]
        self.assertIn("api_duration_basis", role_usage_item["properties"])
        self.assertEqual(role_usage_item["properties"]["api_duration_basis"]["enum"],
                          ["measured", "apportioned", "unavailable"])

    def test_api_duration_scope_property_declared_distinct_from_cost_scope(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertIn("api_duration_scope", run_entry_schema["properties"])
        # A property distinct from cost_scope -- not an extension of cost_scope's
        # own enum -- so cost_scope's own 4-value enum stays untouched, and the
        # 5th (cursor-only) value never bleeds into it.
        cost_scope_enum = run_entry_schema["properties"]["cost_scope"]["enum"]
        self.assertEqual(
            sorted(cost_scope_enum),
            sorted(["session_total", "main_session_only",
                    "no_unconsumed_sample_in_window", "cost_total_reset"]),
        )
        self.assertNotIn("duration_unavailable_on_cursor", cost_scope_enum)
        self.assertIsNot(run_entry_schema["properties"]["api_duration_scope"],
                          run_entry_schema["properties"]["cost_scope"])

    def test_api_duration_fields_not_added_to_required(self):
        _, run_entry_schema = _run_entry_schema()
        required = run_entry_schema.get("required", [])
        for field in ("api_duration_ms", "api_duration_basis", "api_duration_scope"):
            self.assertNotIn(field, required)

    def test_api_duration_scope_enum_matches_cost_sampler_emitted_values(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertEqual(
            sorted(run_entry_schema["properties"]["api_duration_scope"]["enum"]),
            sorted(_API_DURATION_SCOPE_VALUES),
        )


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
class TestRunEntrySchemaApiDurationValidation(unittest.TestCase):
    """A MAR-1/MAR-3-era run entry without api_duration_* fields still
    validates against the further-amended schema; a fully populated
    post-MAR-6 entry also validates."""

    def test_legacy_entry_without_api_duration_fields_still_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(_LEGACY_STATE, schema)

    def test_run_entry_with_api_duration_fields_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["api_duration_ms"] = 4200
        state["runs"][0]["api_duration_basis"] = "measured"
        state["runs"][0]["api_duration_scope"] = "session_total"
        state["runs"][0]["role_usage"] = [
            {"role": "main", "input": 10, "output": 20, "cache_creation": 0,
             "cache_read": 0, "cost_usd": 0.05, "cost_basis": "apportioned",
             "api_duration_ms": 4200, "api_duration_basis": "measured"},
        ]
        jsonschema.validate(state, schema)


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
class TestPipelineStateAndMetricsApiDurationCounters(unittest.TestCase):
    """pipeline-state.schema.json and metrics.schema.json totals gain
    api_duration_ms/runs_api_duration_measured/runs_api_duration_unavailable
    (Spec 03); backward compatible in both directions (counters present or
    absent)."""

    def test_pipeline_state_and_metrics_totals_gain_api_duration_counters_still_backward_compatible(self):
        for schema_path in (PIPELINE_STATE_SCHEMA_PATH, METRICS_SCHEMA_PATH):
            with open(schema_path, encoding="utf-8") as fh:
                schema = json.load(fh)
            totals_props = schema["properties"]["totals"]["properties"]
            for field in ("api_duration_ms", "runs_api_duration_measured", "runs_api_duration_unavailable"):
                self.assertIn(field, totals_props, f"{field} missing in {schema_path}")

            minimal_doc = {"ticket_id": "SHOP-1", "flow": "ticket", "steps": {}} \
                if schema_path == PIPELINE_STATE_SCHEMA_PATH else {}
            minimal_doc["totals"] = {"runs": 1, "cost_usd": 0.0}
            jsonschema.validate(minimal_doc, schema)

            full_doc = json.loads(json.dumps(minimal_doc))
            full_doc["totals"]["api_duration_ms"] = 4200
            full_doc["totals"]["runs_api_duration_measured"] = 1
            full_doc["totals"]["runs_api_duration_unavailable"] = 0
            jsonschema.validate(full_doc, schema)


_GATED_VERDICT = {
    "gated": True,
    "reason": "gate_marker_accepted",
    "response": "warn",
    "not_in_force": [],
    "notice": None,
    "checked_at": "2026-01-01T00:00:00Z",
}

_UNGATED_VERDICT = {
    "gated": False,
    "reason": "no_gate_marker",
    "response": "refuse",
    "not_in_force": ["precondition gate", "file-map guard",
                     "phase-artifact validation", "session bookkeeping"],
    "notice": "acs: DEGRADED ENFORCEMENT — ...",
    "checked_at": "2026-01-01T00:00:00Z",
}


class TestRunEntrySchemaGateEnforcementProperty(unittest.TestCase):
    """Structural checks on the schema file itself, no jsonschema needed.

    Same additive/optional/forward-only shape as guard_events (MAR-578): the
    verdict is recorded at run start, and a run started before it shipped
    carries none."""

    def test_gate_enforcement_property_declared_on_run_entry(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertIn("gate_enforcement", run_entry_schema["properties"])
        prop = run_entry_schema["properties"]["gate_enforcement"]
        self.assertEqual(prop["type"], "object")
        self.assertTrue(prop.get("additionalProperties") is True)

    def test_gate_enforcement_not_added_to_required(self):
        _, run_entry_schema = _run_entry_schema()
        self.assertNotIn("gate_enforcement", run_entry_schema.get("required", []))

    def test_response_is_the_settings_key_enum(self):
        _, run_entry_schema = _run_entry_schema()
        prop = run_entry_schema["properties"]["gate_enforcement"]
        self.assertEqual(prop["properties"]["response"]["enum"], ["warn", "refuse"])

    def test_reason_is_an_open_string_not_an_enum(self):
        # The reason vocabulary lives in acs_lib.hostgates and grows as new
        # ways for evidence to fail are found; enumerating it here would make
        # every such addition retroactively invalidate old state files.
        _, run_entry_schema = _run_entry_schema()
        reason = run_entry_schema["properties"]["gate_enforcement"]["properties"]["reason"]
        self.assertEqual(reason["type"], "string")
        self.assertNotIn("enum", reason)


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
class TestRunEntrySchemaGateEnforcementValidation(unittest.TestCase):
    """A run entry written before MAR-583 still validates; both a gated and an
    ungated verdict validate; a verdict missing its core answer does not."""

    def test_legacy_entry_without_gate_enforcement_still_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(_LEGACY_STATE, schema)

    def test_run_entry_with_a_gated_verdict_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["gate_enforcement"] = _GATED_VERDICT
        jsonschema.validate(state, schema)

    def test_run_entry_with_an_ungated_verdict_validates(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        state["runs"][0]["gate_enforcement"] = _UNGATED_VERDICT
        jsonschema.validate(state, schema)

    def test_verdict_without_the_gated_key_is_rejected(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        verdict = json.loads(json.dumps(_GATED_VERDICT))
        del verdict["gated"]
        state["runs"][0]["gate_enforcement"] = verdict
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(state, schema)

    def test_verdict_with_an_unknown_response_is_rejected(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        state = json.loads(json.dumps(_LEGACY_STATE))
        verdict = json.loads(json.dumps(_GATED_VERDICT))
        verdict["response"] = "block"
        state["runs"][0]["gate_enforcement"] = verdict
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(state, schema)


if __name__ == "__main__":
    unittest.main()
