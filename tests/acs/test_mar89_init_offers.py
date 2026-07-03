"""MAR-89 — /acs:init offers version-pinned per-role model, per-role effort, and explicit e2e (G21).

Prose-contract unit test for `plugins/acs/skills/init/SKILL.md`. A fresh
`/acs:init` must actively OFFER every user-configurable setting, so no
capability is reachable only by hand-editing `.acs/settings.json`. This module
pins the three previously-gapped offers:

  Gap 1 (AC-1) — the `### models` offer names the version-pinned ids
    claude-opus-4-8 / claude-sonnet-5 for all four roles (aligned with
    .acs/settings.json and MAR-81), not only coarse tiers.
  Gap 2 (AC-2) — per-role reasoning effort is a first-class choice (not merely
    the {model, effort} shape note), with the coordinator-scope caveat, and the
    presented enum stays consistent with settings.schema.json $defs.roleModel.
  Gap 3 (AC-3) — e2e is an explicit, always-asked, candidate-detected offer;
    the Step 4 batch carve-out names e2e alongside `### models` so e2e is no
    longer silently defaultable.
  AC-4 maps to the union of the three above (the full walkthrough of every
    schema key is a verifier-inspection property, not unit-testable).
  AC-5 (scope guard) — no fail-closed model-id/effort validation was added; the
    "Any non-empty model string is accepted" sentence survives.

Stdlib-only (os, re, unittest, json), mirroring
tests/acs/test_skill_contracts.py (REPO_ROOT/PLUGIN + read helper + bounded-
window co-occurrence assertions) and tests/acs/test_mar81_settings_models_pinned.py
(reads the schema's $defs.roleModel effort enum so prose and schema can't
silently diverge). Assertions are bounded-window / co-occurrence anchored on the
`### models` heading and the Step 4 carve-out — never bare file-wide assertIn —
so a too-loose match cannot pass vacuously.

Run:  python3 -m unittest tests.acs.test_mar89_init_offers -v
"""

import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "init", "SKILL.md")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")

ROLES = ("planner", "executor", "verifier", "coordinator")
# Version-pinned ids the offer must name (aligned with .acs/settings.json:18-23
# and tests/acs/test_mar81_settings_models_pinned.py:27-32).
PINNED_IDS = ("claude-opus-4-8", "claude-sonnet-5")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (a real heading, matched at line-start — NOT an inline mention of
    the same token elsewhere in prose) up to the next same-or-higher-level
    heading (or end of file). Anchors bounded-window assertions to a single
    section instead of the whole file."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    # Next heading at the same or higher level (fewer/equal '#'), at line start.
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar89InitOffersCase(unittest.TestCase):
    """Fixture: read the init SKILL.md and the settings schema once."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            cls.schema = json.load(f)
        # The `### models` section: from its real heading to the next `### `/`## ` heading.
        cls.models_section = section(cls.body, "### models")
        # Step 4: from its heading to the next `## ` heading (covers the batch
        # framing plus the e2e bullet, which precede the `### tracker`/`### models`
        # subsections inside Step 4).
        cls.step4 = section(cls.body, "## Step 4")

    # --- A (Gap 1 / AC-1): version-pinned per-role models in the offer ---

    def test_A_models_offer_names_pinned_ids(self):
        """The `### models` offer names the version-pinned ids for the roles —
        each within a bounded window after the `### models` heading, so a stray
        mention elsewhere in the file cannot satisfy it."""
        for pinned in PINNED_IDS:
            self.assertIn(
                pinned, self.models_section,
                msg=f"`### models` offer must name the version-pinned id {pinned!r} "
                    f"(AC-1); found only outside the models section",
            )

    def test_A_models_offer_covers_all_four_roles(self):
        """All four role names still appear in the `### models` offer, so the
        version-pin covers every role (planner/executor/verifier/coordinator)."""
        for role in ROLES:
            self.assertIn(
                role, self.models_section,
                msg=f"`### models` offer must still name role {role!r} (AC-1)",
            )

    def test_A_recommended_default_offer_is_pinned(self):
        """The 'Recommended (default)' choice — the one a user picks 'if unsure'
        — itself names the pinned ids, so the default offer (not just a footnote)
        is version-pinned. Bounded window after 'Recommended (default)'."""
        self.assertIn("Recommended (default)", self.models_section)
        window = re.search(r"(?s)Recommended \(default\).{0,600}", self.models_section).group(0)
        for pinned in PINNED_IDS:
            self.assertIn(
                pinned, window,
                msg=f"the 'Recommended (default)' models offer must name {pinned!r} "
                    f"within its choice text (AC-1), not only the coarse tier alias",
            )

    # --- B (Gap 2 / AC-2): per-role reasoning effort as a first-class choice ---

    def test_B_effort_is_first_class_choice(self):
        """Per-role reasoning effort is surfaced as an explicit choice line
        (marker 'Reasoning effort per role'), distinct from the {model, effort}
        object-shape note."""
        self.assertIn(
            "Reasoning effort per role", self.models_section,
            msg="`### models` must present per-role reasoning effort as a first-class "
                "choice (marker 'Reasoning effort per role'), not only the shape note (AC-2)",
        )

    def test_B_effort_enum_matches_schema(self):
        """Every effort enum value from the schema's $defs.roleModel appears in
        the `### models` offer, so a future schema change and the prose can't
        silently diverge (mirrors test_mar81_settings_models_pinned.py:63-68)."""
        role_model_def = self.schema["$defs"]["roleModel"]
        object_branch = next(
            branch for branch in role_model_def["oneOf"]
            if branch.get("type") == "object"
        )
        effort_enum = object_branch["properties"]["effort"]["enum"]
        # The presented choice line names the full enum next to the effort marker.
        effort_window = re.search(
            r"(?s)Reasoning effort per role.{0,400}", self.models_section
        ).group(0)
        for level in effort_enum:
            self.assertIn(
                level, effort_window,
                msg=f"effort level {level!r} (from settings.schema.json $defs.roleModel) "
                    f"must appear in the presented per-role effort choice (AC-2)",
            )

    def test_B_coordinator_scope_caveat_present(self):
        """The coordinator-scope caveat co-occurs in the models section:
        `coordinator` near `/acs:ship` within a bounded window (the existing
        caveat at SKILL.md:279-283 is retained)."""
        self.assertIsNotNone(
            re.search(r"(?s)coordinator.{0,400}/acs:ship", self.models_section),
            "`### models` must keep the coordinator-scope caveat (coordinator effort "
            "governs the /acs:ship coordinator's own run) (AC-2)",
        )

    # --- C (Gap 3 / AC-3): explicit, candidate-detected e2e offer ---

    def e2e_bullet(self):
        """The e2e list item itself (anchored on the `- `e2e`` list marker at
        line-start), NOT the earlier carve-out mention of e2e — up to the next
        top-level list item or `### ` subheading."""
        m = re.search(r"(?m)^- `e2e`", self.step4)
        self.assertIsNotNone(m, "Step 4 must retain the `- `e2e`` bullet")
        rest = self.step4[m.start() + 1:]
        nxt = re.search(r"(?m)^(- |### )", rest)
        end = m.start() + 1 + (nxt.start() if nxt else len(rest))
        return self.step4[m.start():end]

    def test_C_e2e_is_explicit_always_asked(self):
        """e2e is presented as an explicit always-asked offer (marker
        'always ask' in the e2e bullet), not left silently defaultable."""
        self.assertIn(
            "always ask", self.e2e_bullet(),
            msg="Step 4 must frame the e2e bullet as an explicit always-asked offer "
                "(marker 'always ask' in the e2e bullet) (AC-3)",
        )

    def test_C_batch_carveout_names_both_models_and_e2e(self):
        """The Step 4 batch framing carve-out (SKILL.md:160-164) now names BOTH
        `### models` AND e2e as the always-explicit exceptions — proving the batch
        framing (not just the bullet) was updated. Bounded window: e2e appears
        within the carve-out sentence that also names `### models`."""
        carveout = re.search(
            r"(?s)present these as a batch.{0,900}", self.step4, re.IGNORECASE
        )
        self.assertIsNotNone(
            carveout, "Step 4 must retain the 'present these as a batch' framing"
        )
        window = carveout.group(0)
        self.assertIn(
            "`### models`", window,
            msg="Step 4 batch carve-out must still name `### models` as always-explicit (AC-3)",
        )
        self.assertIn(
            "e2e", window,
            msg="Step 4 batch carve-out must now name e2e alongside `### models` as "
                "always-explicit — e2e is no longer silently defaultable (AC-3)",
        )

    def test_C_e2e_candidate_detection_survives(self):
        """The candidate-detection list survives the edit: playwright, cypress,
        and Makefile tokens still appear in the e2e bullet itself."""
        window = self.e2e_bullet()
        for token in ("playwright", "cypress", "Makefile"):
            self.assertIn(
                token, window,
                msg=f"e2e candidate-detection token {token!r} must survive the edit (AC-3)",
            )

    # --- E (AC-5): scope-guard negative contract ---

    def test_E_no_validation_added_any_string_accepted(self):
        """The 'Any non-empty model string is accepted' sentence survives, so no
        fail-closed model-id validation was introduced (AC-5). Whitespace is
        normalized first so a line-wrap between words does not break the check."""
        flat = re.sub(r"\s+", " ", self.models_section)
        self.assertIn(
            "Any non-empty model string is accepted", flat,
            msg="scope guard: the 'Any non-empty model string is accepted' sentence "
                "must survive — no model-id validation added (AC-5)",
        )

    def test_E_no_model_validation_gate_phrasing(self):
        """No fail-closed 'reject'/'invalid model' validation gate phrasing was
        introduced into the `### models` offer (AC-5)."""
        lowered = self.models_section.lower()
        for gate in ("reject", "invalid model", "fail-closed", "not accepted"):
            self.assertNotIn(
                gate, lowered,
                msg=f"scope guard: `### models` must not introduce validation-gate "
                    f"phrasing {gate!r} (AC-5)",
            )


if __name__ == "__main__":
    unittest.main()
