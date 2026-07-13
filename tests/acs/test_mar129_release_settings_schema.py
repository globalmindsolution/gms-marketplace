"""MAR-129 — settings.schema.json `release` sub-schema (Decision 5, ADR 0054).

Structure-contract unit test over `plugins/acs/schemas/settings.schema.json`'s
new `properties.release` sub-schema (Option A): shape presence, the
`required` key list, a recursive no-secret-field walk (Security NFR (i)),
and a hand-rolled structural conformance check of this repo's own committed
`.acs/settings.json` `release` profile #1 block (Spec 01's deliverable, read
here, not authored here) against the schema shape — plus a negative sanity
check that an obviously-malformed candidate block fails the same walk.

Stdlib-only (json, os, unittest) — no `jsonschema` import, mirroring this
repo's existing settings-schema tests (`test_mar114_suites_schema.py` and
`test_acs_plugin.py`'s `TestDueDateSchema`/`TestHighStakesPathsSettings`/
`TestOperationsPathSettings`).

Run:  python3 -m unittest tests.acs.test_mar129_release_settings_schema -v
"""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")
SETTINGS_PATH = os.path.join(REPO_ROOT, ".acs", "settings.json")

REQUIRED_KEYS = ["version_locations", "changelog_path", "tag_format", "base_branch", "release_branch_format"]

SECRET_NAME_MARKERS = ("secret", "token", "credential", "password", "api_key")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _walk_property_names(node):
    """Yield every property-name string anywhere in a JSON-Schema fragment's `properties` maps."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for prop_name, prop_schema in value.items():
                    yield prop_name
                    yield from _walk_property_names(prop_schema)
            else:
                yield from _walk_property_names(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_property_names(item)


def is_structurally_valid_release_block(block):
    """Hand-rolled structural walk mirroring the schema shape (NOT a JSON-Schema validator).

    Checks required keys, array-item shapes, and leaf string types — enough
    to prove a real conformance check (item 4 below), not a rubber stamp.
    """
    if not isinstance(block, dict):
        return False
    for key in REQUIRED_KEYS:
        if key not in block:
            return False

    locations = block.get("version_locations")
    if not isinstance(locations, list) or not locations:
        return False
    for entry in locations:
        if not isinstance(entry, dict):
            return False
        if not isinstance(entry.get("file"), str) or not entry.get("file"):
            return False
        if not isinstance(entry.get("pointer"), str) or not entry.get("pointer"):
            return False

    extra_refs = block.get("extra_refs", [])
    if not isinstance(extra_refs, list):
        return False
    for entry in extra_refs:
        if not isinstance(entry, dict):
            return False
        if not isinstance(entry.get("file"), str) or not entry.get("file"):
            return False
        selector = entry.get("selector")
        if not isinstance(selector, dict):
            return False
        if not isinstance(selector.get("pointer"), str) or not selector.get("pointer"):
            return False
        if not isinstance(selector.get("match"), dict) or not selector.get("match"):
            return False
        if not isinstance(selector.get("set"), str) or not selector.get("set"):
            return False
        if not isinstance(entry.get("value_format"), str) or not entry.get("value_format"):
            return False

    for key in ("changelog_path", "tag_format", "base_branch", "release_branch_format"):
        if not isinstance(block.get(key), str) or not block.get(key):
            return False

    publish_driver = block.get("publish_driver")
    if publish_driver is not None and not isinstance(publish_driver, dict):
        return False

    return True


class Mar129ReleaseSettingsSchemaShapeCase(unittest.TestCase):
    """Shape presence and structure (schema-authoring conformance)."""

    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMA_PATH)
        cls.release = cls.schema["properties"]["release"]
        one_of = cls.release["oneOf"]
        cls.object_branch = next(b for b in one_of if b.get("type") == "object")
        cls.null_branch = next(b for b in one_of if b.get("type") == "null")

    def test_release_property_exists(self):
        self.assertIn("release", self.schema["properties"], "settings.schema.json must gain a top-level `release` property (ADR 0054)")

    def test_release_is_one_of_object_or_null(self):
        one_of = self.release["oneOf"]
        self.assertEqual(len(one_of), 2, "`release` must be a oneOf with exactly two branches")
        types = sorted(b.get("type") for b in one_of)
        self.assertEqual(types, ["null", "object"])

    def test_object_branch_required_keys(self):
        self.assertEqual(
            self.object_branch.get("required"), REQUIRED_KEYS,
            "extra_refs/publish_driver must NOT be required (§10's flagged assumption)",
        )

    def test_version_locations_items_shape(self):
        items = self.object_branch["properties"]["version_locations"]["items"]
        self.assertEqual(items.get("required"), ["file", "pointer"])
        kind = items["properties"]["kind"]
        self.assertEqual(kind.get("default"), "json-pointer")
        self.assertEqual(kind.get("enum"), ["json-pointer"])

    def test_extra_refs_items_shape(self):
        items = self.object_branch["properties"]["extra_refs"]["items"]
        self.assertEqual(items.get("required"), ["file", "selector", "value_format"])
        selector = items["properties"]["selector"]
        self.assertEqual(selector.get("required"), ["pointer", "match", "set"])

    def test_simple_string_fields_shape(self):
        for key in ("changelog_path", "tag_format", "base_branch", "release_branch_format"):
            field = self.object_branch["properties"][key]
            self.assertEqual(field.get("type"), "string")
            self.assertEqual(field.get("minLength"), 1)

    def test_publish_driver_shape(self):
        pd = self.object_branch["properties"]["publish_driver"]
        self.assertEqual(pd.get("type"), "object")
        self.assertEqual(pd["properties"]["workflow"]["type"], "string")
        self.assertEqual(pd["properties"]["trigger_paths"]["type"], "array")
        self.assertEqual(pd["properties"]["trigger_paths"]["items"]["type"], "string")
        self.assertTrue(pd.get("additionalProperties"))

    def test_additional_properties_true_everywhere_in_the_tree(self):
        object_branch = self.object_branch
        self.assertTrue(object_branch.get("additionalProperties"))
        self.assertTrue(object_branch["properties"]["version_locations"]["items"].get("additionalProperties"))
        self.assertTrue(object_branch["properties"]["extra_refs"]["items"].get("additionalProperties"))
        self.assertTrue(object_branch["properties"]["extra_refs"]["items"]["properties"]["selector"].get("additionalProperties"))
        self.assertTrue(object_branch["properties"]["publish_driver"].get("additionalProperties"))


class Mar129ReleaseSettingsSchemaNoSecretCase(unittest.TestCase):
    """No secret/credential field anywhere in the `release` sub-schema tree (Security NFR (i))."""

    def test_no_secret_shaped_property_name(self):
        schema = load_json(SCHEMA_PATH)
        release = schema["properties"]["release"]
        offenders = [
            name for name in _walk_property_names(release)
            if any(marker in name.lower() for marker in SECRET_NAME_MARKERS)
        ]
        self.assertEqual(
            offenders, [],
            "release sub-schema must carry no secret/credential/token/password/api_key-shaped property: %r" % offenders,
        )


class Mar129ReleaseSettingsProfileOneConformanceCase(unittest.TestCase):
    """This repo's own committed `.acs/settings.json` `release` block (Spec 01) validates against the schema shape."""

    def test_profile_one_block_present(self):
        settings = load_json(SETTINGS_PATH)
        self.assertIn(
            "release", settings,
            "this repo's own .acs/settings.json must carry a committed `release` profile #1 block (Spec 01)",
        )

    def test_profile_one_structurally_conforms(self):
        settings = load_json(SETTINGS_PATH)
        block = settings.get("release")
        self.assertTrue(
            is_structurally_valid_release_block(block),
            "the committed .acs/settings.json release block must structurally conform to the `release` sub-schema shape: %r" % (block,),
        )

    def test_profile_one_version_locations_are_marketplace_and_plugin_manifest(self):
        settings = load_json(SETTINGS_PATH)
        files = {entry["file"] for entry in settings["release"]["version_locations"]}
        self.assertEqual(
            files,
            {".claude-plugin/marketplace.json", "plugins/acs/.claude-plugin/plugin.json"},
        )


class Mar129ReleaseSettingsSchemaMalformedRejectionCase(unittest.TestCase):
    """A malformed candidate block fails the same structural walk (proves it's a real check)."""

    def test_non_array_version_locations_rejected(self):
        self.assertFalse(is_structurally_valid_release_block({
            "version_locations": "not-an-array",
            "changelog_path": "CHANGELOG.md",
            "tag_format": "v{version}",
            "base_branch": "main",
            "release_branch_format": "release/v{version}",
        }))

    def test_missing_changelog_path_rejected(self):
        self.assertFalse(is_structurally_valid_release_block({
            "version_locations": [{"file": "package.json", "pointer": "/version"}],
            "tag_format": "v{version}",
            "base_branch": "main",
            "release_branch_format": "release/v{version}",
        }))

    def test_non_dict_block_rejected(self):
        self.assertFalse(is_structurally_valid_release_block("not-a-dict"))
        self.assertFalse(is_structurally_valid_release_block(None))

    def test_empty_object_rejected(self):
        self.assertFalse(is_structurally_valid_release_block({}))


if __name__ == "__main__":
    unittest.main()
