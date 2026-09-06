"""MAR-81 — Pin acs subagent models to explicit ids and effort levels.

Asserts the repo-committed .acs/settings.json `models` block holds explicit,
version-stable model ids plus an explicit reasoning-effort level per role
(object form, mirroring the sibling `hirex` repo's configuration), instead of
the generic runtime aliases ("opus" / "sonnet") with no effort, and that the
file remains valid against plugins/acs/schemas/settings.schema.json.

The ids themselves are NOT written here: they are read from
acs_lib.RECOMMENDED_MODELS, so this module keeps asserting the property when
the recommendation moves to a newer model generation.

A role this repo deliberately runs OFF that recommendation is declared once, in
REPO_OVERRIDES below -- the only place a literal id belongs, because a
repo-local choice is not the plugin's recommendation and must not be pushed
into RECOMMENDED_MODELS (that constant is what a fresh /acs:setup offers every
other consumer repo). Every role absent from REPO_OVERRIDES still has to mirror
the recommendation exactly, so the constant remains the single source for those.

For an OVERRIDDEN role the picture is different, and saying so is the point: the
guard below also requires the pinned id to still be one RECOMMENDED_MODELS uses,
so moving the recommendation to a new generation makes this file fail until the
override moves with it. That is deliberate -- an override left on a retired id
is the failure this file exists to catch, and there is no model-id validation at
spawn time to catch it later -- but it means a generation bump IS a change here
as well as to the constant, for as long as an override exists.

Uses the same stdlib-only approach as TestHighStakesPathsSettings /
TestDueDateSchema in test_acs_plugin.py (no jsonschema import) -- the CI
"Tests & validation" job does not install jsonschema (only a separate,
dedicated settings-schema-validation CI step does; see .github/workflows/ci.yml
around line 170).

MAR-154 dropped the `coordinator` role from the `models` settings contract
entirely (schema, committed settings.json, and acs_lib.py's validate_models
role loop) and moved the planner/verifier default to the then-current opus
generation.

Run:  python3 -m unittest tests.acs.test_settings_models_pinned -v
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(REPO_ROOT, ".acs", "settings.json")
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

# Roles this repo runs off the shipped recommendation, on purpose. A literal id
# is correct here and nowhere else: it states THIS repo's choice, not what acs
# recommends to anyone else. Each entry needs a reason, and must actually differ
# from RECOMMENDED_MODELS -- test_overrides_are_live_divergences fails a stale
# entry the recommendation has since caught up with, so the list cannot rot into
# a silent copy of the mirror it is exempting. That test enforces a SECOND
# property too: the pinned id must still be one the recommendation uses
# somewhere, so an override left behind by a model generation fails here rather
# than silently pinning a retired id.
#
#   executor: the executor is the only role that WRITES the code planner and
#   verifier merely reason about, and this repo would rather pay for one strong
#   pass than iterate a cheaper one. The shipped recommendation keeps sonnet
#   there, where the cost/benefit is a consumer repo's call to make.
REPO_OVERRIDES = {
    "executor": {"model": "claude-opus-5", "effort": "high"},
}

# Not a literal pin for the roles that mirror: their ids live in
# acs_lib.RECOMMENDED_MODELS. What is asserted is the shape (object form with a
# non-empty id and a schema-valid effort) and that the committed settings agree
# with that single source wherever REPO_OVERRIDES does not deliberately depart
# from it, so a new model generation changes the constant and the settings it is
# mirrored into -- never this file.
EXPECTED = dict(lib.RECOMMENDED_MODELS, **REPO_OVERRIDES)


class SettingsModelsPinnedCase(unittest.TestCase):
    """Fixture: load the committed settings.json + schema once."""

    @classmethod
    def setUpClass(cls):
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            cls.settings = json.load(f)
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            cls.schema = json.load(f)

    def test_planner_pinned(self):
        self.assertEqual(self.settings["models"]["planner"], EXPECTED["planner"])

    def test_verifier_pinned(self):
        self.assertEqual(self.settings["models"]["verifier"], EXPECTED["verifier"])

    def test_executor_pinned(self):
        self.assertEqual(self.settings["models"]["executor"], EXPECTED["executor"])

    def test_recommended_models_are_well_shaped(self):
        """The recommendation is an object form with a real id and a valid effort
        for every role — the property that must hold whatever the ids become.

        Asserted against RECOMMENDED_MODELS itself, not the merged EXPECTED:
        merging REPO_OVERRIDES over it removed the only shape check on the
        SHIPPED recommendation for any overridden role. Verified by mutation —
        with EXPECTED, setting the recommendation's executor to
        `{"model": "", "effort": "bogus"}` left this module green, and
        test_setup_offers could not catch it either (PINNED_IDS would hold ""
        and `assertIn("", section)` is vacuously true)."""
        for role in lib.MODEL_ROLES:
            for label, table in (("recommendation", lib.RECOMMENDED_MODELS),
                                 ("this repo's pin", EXPECTED)):
                entry = table[role]
                with self.subTest(role=role, table=label):
                    self.assertIsInstance(entry, dict,
                                          msg="%s %s must use the {model, effort} form"
                                              % (label, role))
                    self.assertTrue(entry.get("model", "").strip(),
                                    msg="%s %s needs a model id" % (label, role))
                    self.assertIn(entry.get("effort"), lib.MODEL_EFFORTS,
                                  msg="%s %s effort must be one of %s"
                                      % (label, role, ", ".join(lib.MODEL_EFFORTS)))

    def test_committed_settings_validate(self):
        """The committed models block passes the runtime validator, not just the schema."""
        lib.validate_models(self.settings["models"])

    def test_no_coordinator_key(self):
        self.assertNotIn(
            "coordinator", self.settings["models"],
            msg="models.coordinator must be removed from .acs/settings.json (AC-2)",
        )

    def test_settings_schema_valid(self):
        """Stdlib-only structural check (no jsonschema dependency): the schema's
        $defs.roleModel accepts an object {model, effort} for each models.*
        role (settings.schema.json's roleModel oneOf second branch), effort is
        one of the enumerated levels, and the three committed values satisfy
        that shape."""
        role_model_def = self.schema["$defs"]["roleModel"]
        object_branch = next(
            branch for branch in role_model_def["oneOf"]
            if branch.get("type") == "object"
        )
        effort_enum = object_branch["properties"]["effort"]["enum"]

        models = self.settings["models"]
        self.assertIsInstance(models, dict)
        for role in ("planner", "executor", "verifier"):
            self.assertIn(role, self.schema["properties"]["models"]["properties"])
            value = models[role]
            self.assertIsInstance(value, dict)
            self.assertEqual(set(value.keys()), {"model", "effort"})
            self.assertIsInstance(value["model"], str)
            self.assertGreaterEqual(len(value["model"]), 1)
            self.assertIn(value["effort"], effort_enum)

    def test_no_alias_literals_remain(self):
        models = self.settings["models"]
        for role in ("planner", "executor", "verifier"):
            self.assertNotIn(
                models[role]["model"],
                ("opus", "sonnet"),
                msg=f"models.{role}.model still holds a generic alias literal: {models[role]['model']!r}",
            )

    def test_overrides_are_live_divergences(self):
        """Every REPO_OVERRIDES entry names a real role, is shaped like one, and
        satisfies TWO properties -- both enforced below, so both are stated here:

        1. It still DIFFERS from the recommendation. An override the
           recommendation has caught up with is dead weight that would silently
           exempt a role from the mirror, so it fails until it is deleted.
        2. Its pinned id is still one RECOMMENDED_MODELS uses for some role. An
           override the recommendation has moved PAST is a pin on a retired
           model, and nothing validates model ids at spawn time.

        The two point in opposite directions on purpose: (1) catches an override
        that has become redundant, (2) catches one left behind."""
        for role, entry in REPO_OVERRIDES.items():
            self.assertIn(role, lib.MODEL_ROLES, msg="%s is not a model role" % role)
            self.assertIsInstance(entry, dict, msg="%s must use the {model, effort} form" % role)
            self.assertTrue(entry.get("model", "").strip(), msg="%s needs a model id" % role)
            self.assertIn(entry.get("effort"), lib.MODEL_EFFORTS,
                          msg="%s effort must be one of %s" % (role, ", ".join(lib.MODEL_EFFORTS)))
            self.assertNotEqual(
                entry, lib.RECOMMENDED_MODELS[role],
                msg="REPO_OVERRIDES[%r] now equals the recommendation -- delete the "
                    "override and let the role mirror RECOMMENDED_MODELS again" % role,
            )
            # The direction that actually happens. The override encodes a
            # literal id, but its INTENT is "the same strong model the planner
            # and verifier get". Without this, moving RECOMMENDED_MODELS to a
            # new generation leaves the executor pinned to the retired id with
            # nothing failing — and no model-id validation at spawn time to
            # catch it later.
            # The set is every id the recommendation currently uses for ANY
            # role -- deliberately weaker than "the same id the planner and
            # verifier get". A partial generation bump (planner moves, verifier
            # does not) therefore stays silent, and a pin AHEAD of the
            # recommendation reports as "left behind". Both are acceptable: the
            # remedy for either is a repo-local edit to REPO_OVERRIDES, and
            # nothing here can reach RECOMMENDED_MODELS, which is what the
            # decoupling requires.
            in_use = {rec["model"] for rec in lib.RECOMMENDED_MODELS.values()}
            self.assertIn(
                entry["model"], in_use,
                msg="REPO_OVERRIDES[%r] pins %r, which the recommendation uses "
                    "for no role (%s). Either the override was left behind by a "
                    "model generation, or it is pinned ahead of one acs does not "
                    "recommend yet -- update REPO_OVERRIDES either way"
                    % (role, entry["model"],
                                                      ", ".join(sorted(in_use))),
            )

    def test_coordinator_no_longer_shape_checked(self):
        """AC-3: acs_lib.validate_models's role loop no longer resolves/shape-
        checks a `coordinator` role. A models.coordinator value shaped wrong
        for check_role (a list, neither str nor dict) would raise GateError
        while `coordinator` was still in the role tuple; once dropped, the
        same input must pass through untouched (validate_models never checks
        for unrecognized top-level keys, only shape-validates known roles)."""
        self.assertIsNone(
            lib.validate_models({"coordinator": ["not", "a", "valid", "shape"]}),
            msg="models.coordinator must no longer be shape-checked by validate_models (AC-3)",
        )


if __name__ == "__main__":
    unittest.main()
