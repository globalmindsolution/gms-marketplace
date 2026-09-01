"""MAR-4 — other shipped skill surfaces + product docs describe the in-repo
default state root (AC3, AC4, AC5, AC6).

Prose-contract unit test covering every shipped surface outside
`setup/SKILL.md` (Task 1's file) that still referenced the retired
"workspace_path lives outside the repo, machine-local, always set" model:

  AC3 — handoff/SKILL.md derives the same default
    (`<main-checkout>/.acs/state-machine`) before falling back to an
    explicit override, and no longer frames "workspace_path is not
    configured" as reachable prose (that message does not exist in
    acs_lib.py/handoff.py); Step 5's "Scope" bullet no longer claims
    workspace_path is unconditionally machine-local.
  AC4 — update/SKILL.md's Step 6 item 3 "Workspace reachable" check resolves
    the same way item 1 already does (settings load + validate/derive),
    instead of assuming a bare workspace_path key is always set;
    release/SKILL.md carries no outside-repo claim (verification-only,
    grounded finding from the plan — pinned here as a regression guard).
  AC5 — plugin.json's description is ASCII-only and describes the in-repo
    default; .claude-plugin/marketplace.json and plugins/acs/CHANGELOG.md
    stay byte-identical (out of scope, byte-pinned/append-only).
  AC6 — both README.md files (plugin + repo-root) describe the in-repo
    default; plugins/acs/README.md gains a "Migrating an existing external
    workspace" section naming the exact migrate_workspace.py CLI shape.

Stdlib-only (json, os, re, unittest), mirroring
tests/acs/test_setup_offers.py (REPO_ROOT/PLUGIN + read helper +
bounded-window section-scoped assertions) so a too-loose match cannot pass
vacuously.

Run:  python3 -m unittest tests.acs.test_state_root_skill_surfaces -v
"""

import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

HANDOFF_SKILL = os.path.join(PLUGIN, "skills", "handoff", "SKILL.md")
UPDATE_SKILL = os.path.join(PLUGIN, "skills", "update", "SKILL.md")
RELEASE_SKILL = os.path.join(PLUGIN, "skills", "release", "SKILL.md")
PLUGIN_JSON = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
PLUGIN_README = os.path.join(PLUGIN, "README.md")
ROOT_README = os.path.join(REPO_ROOT, "README.md")
MARKETPLACE_JSON = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
CHANGELOG = os.path.join(PLUGIN, "CHANGELOG.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (a real heading, matched at line-start) up to the next
    same-or-higher-level heading (or end of file). Mirrors
    test_setup_offers.py's `section()` so bounded-window assertions
    are anchored to a single section instead of the whole file."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class HandoffLocatingWorkspaceCase(unittest.TestCase):
    """AC3 — handoff/SKILL.md's `### Locating the workspace` section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(HANDOFF_SKILL)
        cls.locating = section(cls.body, "### Locating the workspace")

    def test_locating_the_workspace_derives_the_default(self):
        """The section names the in-repo default derivation (state-machine
        under the main checkout) before it describes falling back to an
        explicit workspace_path override."""
        self.assertIn(
            ".acs/state-machine", self.locating,
            msg="`### Locating the workspace` must derive the in-repo default "
                "(.acs/state-machine) before falling back to an override (AC3)",
        )
        default_pos = self.locating.find(".acs/state-machine")
        override_pos = self.locating.lower().find("override")
        self.assertNotEqual(-1, override_pos, "an explicit override fallback must still be named (AC3)")
        self.assertLess(
            default_pos, override_pos,
            msg="the derived default must be described BEFORE the override fallback (AC3)",
        )

    def test_locating_the_workspace_no_longer_says_absence_means_uninitialized(self):
        """The stale claim that absence of workspace_path anywhere means acs
        is not initialized is gone — absence now derives the default."""
        self.assertNotIn(
            "No `workspace_path` anywhere means acs is not initialized", self.locating,
            msg="the now-false 'no workspace_path anywhere = not initialized' claim "
                "must be corrected (AC3)",
        )

    def test_no_unreachable_workspace_path_is_not_configured_hint(self):
        """`workspace_path is not configured` is not a message acs_lib.py or
        handoff.py ever emits (grep confirms it does not exist in either
        source file) — the error-hint list must not reference it."""
        for path in (
            os.path.join(PLUGIN, "hooks", "scripts", "acs_lib.py"),
            os.path.join(PLUGIN, "hooks", "scripts", "handoff.py"),
        ):
            self.assertNotIn(
                "workspace_path is not configured", read(path),
                msg="grounding check: this message must not exist in %s "
                    "for this test's premise to hold" % path,
            )
        self.assertNotIn(
            "workspace_path is not configured", self.body,
            msg="handoff/SKILL.md must not document an error hint "
                "(`workspace_path is not configured`) that acs_lib/handoff.py "
                "never actually raises (AC3)",
        )


class HandoffScopeClaimCase(unittest.TestCase):
    """AC3 — handoff/SKILL.md Step 5 item 4 'Scope'."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(HANDOFF_SKILL)
        cls.step5 = section(cls.body, "## Step 5")

    def scope_bullet(self):
        m = re.search(r"(?m)^\d+\. \*\*Scope\*\*", self.step5)
        self.assertIsNotNone(m, "Step 5 must retain a numbered 'Scope' bullet")
        rest = self.step5[m.start() + 1:]
        nxt = re.search(r"(?m)^\d+\. \*\*", rest)
        end = m.start() + 1 + (nxt.start() if nxt else len(rest))
        return self.step5[m.start():end]

    def test_scope_no_longer_says_machine_local_only(self):
        """The mirrored 'same machine and workspace (workspace_path is
        machine-local)' claim is gone from the Scope bullet."""
        bullet = self.scope_bullet()
        self.assertNotIn(
            "same machine and workspace", bullet,
            msg="Scope bullet must no longer claim 'same machine and workspace' "
                "as workspace_path being unconditionally machine-local (AC3)",
        )
        self.assertNotIn(
            "workspace_path is machine-local", bullet,
            msg="Scope bullet must drop the unconditional machine-local claim (AC3)",
        )

    def test_scope_names_the_in_repo_default(self):
        """The corrected Scope bullet names the in-repo, main-checkout-anchored
        default, with the override as the named exception."""
        bullet = self.scope_bullet()
        self.assertIn(".acs/state-machine", bullet)
        self.assertIn("override", bullet.lower())


class UpdateWorkspaceReachableCase(unittest.TestCase):
    """AC4 — update/SKILL.md Step 6 item 3 'Workspace reachable'."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(UPDATE_SKILL)
        cls.step6 = section(cls.body, "## Step 6")

    def item(self, number, label):
        m = re.search(r"(?m)^%d\. \*\*%s" % (number, re.escape(label)), self.step6)
        self.assertIsNotNone(m, "Step 6 item %d (%s) must exist" % (number, label))
        rest = self.step6[m.start() + 1:]
        nxt = re.search(r"(?m)^\d+\. \*\*", rest)
        end = m.start() + 1 + (nxt.start() if nxt else len(rest))
        return self.step6[m.start():end]

    def test_workspace_reachable_no_longer_assumes_a_bare_key(self):
        """Item 3 no longer reads 'workspace_path exists and is writable' as
        if the key is always set — that assumption is gone."""
        item3 = self.item(3, "Workspace reachable")
        self.assertNotIn(
            "`workspace_path` exists and is writable", item3,
            msg="item 3 must no longer assume workspace_path is always a set key (AC4)",
        )

    def test_workspace_reachable_resolves_like_item_one(self):
        """Item 3 resolves the workspace the same way item 1 already does
        (acs_lib.load_settings + acs_lib.validate_settings), rather than
        reading a possibly-absent workspace_path key directly."""
        item1 = self.item(1, "Settings still valid")
        item3 = self.item(3, "Workspace reachable")
        self.assertIn("acs_lib.load_settings", item1)
        self.assertIn("acs_lib.validate_settings", item1)
        for marker in ("acs_lib.load_settings", "acs_lib.validate_settings"):
            self.assertIn(
                marker, item3,
                msg="item 3 must resolve the workspace via %r, the same "
                    "resolution approach item 1 already uses (AC4)" % marker,
            )


class ReleaseSkillNoOutsideRepoClaimCase(unittest.TestCase):
    """AC4 (second half) — release/SKILL.md regression guard. Grounded finding
    (this ticket's plan): no outside-repo claim exists today; pinned so a
    future edit cannot reintroduce it."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(RELEASE_SKILL)

    def test_release_skill_has_no_outside_repo_claim(self):
        lowered = self.body.lower()
        for claim in ("outside the", "must be outside", "machine-local"):
            self.assertNotIn(
                claim, lowered,
                msg="release/SKILL.md must not claim workspace_path is "
                    "outside-the-repo/machine-local (AC4)",
            )


class PluginJsonDescriptionCase(unittest.TestCase):
    """AC5 — plugin.json's description; marketplace.json/CHANGELOG.md untouched."""

    @classmethod
    def setUpClass(cls):
        with open(PLUGIN_JSON, encoding="utf-8") as fh:
            cls.data = json.load(fh)
        cls.description = cls.data["description"]

    def test_description_is_ascii(self):
        self.assertTrue(
            self.description.isascii(),
            msg="plugin.json description must stay ASCII-only (AC5)",
        )

    def test_description_no_longer_claims_outside_the_consumer_repo(self):
        self.assertNotIn(
            "workspace outside the consumer repo", self.description,
            msg="plugin.json description must drop the outside-the-repo claim (AC5)",
        )

    def test_description_describes_the_in_repo_default(self):
        self.assertIn(
            ".acs/state-machine", self.description,
            msg="plugin.json description must name the in-repo .acs/state-machine "
                "default (AC5)",
        )


def _base_ref():
    """`origin/main` is preferred over a local `main`: a CI checkout has no
    local `main` branch at all (only `origin/main`), and a long-lived
    worktree's local `main` can go stale, folding already-merged sibling
    changes into the range and producing a false positive here."""
    for ref in ("origin/main", "main"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return ref
    return None


def git_blob_at_merge_base(rel_path):
    """Content of `rel_path` at the commit where this branch diverged from
    `main` — a fixed historical snapshot (unlike re-reading the working tree
    twice in one process, which would trivially always match itself)."""
    base_ref = _base_ref()
    base = subprocess.check_output(
        ["git", "merge-base", base_ref, "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    return subprocess.check_output(
        ["git", "show", "%s:%s" % (base, rel_path)], cwd=REPO_ROOT, text=True
    )


class OutOfScopeUntouchedCase(unittest.TestCase):
    """AC5 regression guard — .claude-plugin/marketplace.json (byte-pinned)
    and plugins/acs/CHANGELOG.md (append-only: no existing line may be
    deleted/rewritten, though a later ticket may add its own dated entry)
    relative to their content at the commit this branch diverged from
    `main` — this task's own file map excludes both paths."""

    def setUp(self):
        if _base_ref() is None:
            self.skipTest("no base ref (origin/main or main) to diff against")

    def test_marketplace_json_untouched(self):
        self.assertEqual(
            git_blob_at_merge_base(".claude-plugin/marketplace.json"), read(MARKETPLACE_JSON),
            msg="`.claude-plugin/marketplace.json` must stay byte-identical "
                "to its content on `main` (out of MAR-4 scope, byte-pinned)",
        )

    def test_changelog_untouched(self):
        # append-only, not byte-identical: a later ticket (e.g. MAR-1) may
        # legitimately add its own dated entry under [Unreleased] in the
        # same append-only style this file already uses -- what this guard
        # actually protects is that no EXISTING line is rewritten/deleted.
        result = subprocess.run(
            ["git", "diff", "--numstat", "%s...HEAD" % _base_ref(), "--", CHANGELOG],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout.strip()
        if output == "":
            return
        _added, deleted, _path = output.split("\t", 2)
        self.assertEqual(
            deleted, "0",
            msg="`plugins/acs/CHANGELOG.md` must never delete/rewrite an "
                "existing line relative to `main` (out of MAR-4 scope, "
                "append-only), got: %s" % output,
        )


class PluginReadmeCase(unittest.TestCase):
    """AC6 — plugins/acs/README.md describes the in-repo default and gains
    a migration section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PLUGIN_README)

    def test_no_outside_your_repo_claim(self):
        self.assertNotIn(
            "outside your repo", self.body,
            msg="plugins/acs/README.md must drop the 'outside your repo' claim (AC6)",
        )

    def test_quick_start_no_longer_requires_outside_repo_workspace_path(self):
        quick_start = section(self.body, "## Quick start")
        self.assertNotIn(
            "must be outside the repo", quick_start,
            msg="Quick start must no longer say workspace_path must be outside "
                "the repo (AC6)",
        )
        self.assertIn(
            ".acs/state-machine", quick_start,
            msg="Quick start must name the in-repo .acs/state-machine default (AC6)",
        )

    def test_configuration_table_workspace_path_row_describes_in_repo_default(self):
        config = section(self.body, "## Configuration")
        self.assertIn("workspace_path", config)
        self.assertNotIn(
            "outside the repo", config,
            msg="the workspace_path settings-table row must no longer say "
                "'outside the repo' (AC6)",
        )
        self.assertIn(
            ".acs/state-machine", config,
            msg="the workspace_path settings-table row must name the in-repo "
                "default (AC6)",
        )

    def test_has_a_migration_section(self):
        self.assertIn(
            "## Migrating an existing external workspace", self.body,
            msg="plugins/acs/README.md must gain a 'Migrating an existing "
                "external workspace' section (AC6)",
        )
        migration = section(self.body, "## Migrating an existing external workspace")
        for token in ("migrate_workspace.py", "--from", "--to", "--repo-root"):
            self.assertIn(
                token, migration,
                msg="the migration section must name the exact "
                    "migrate_workspace.py CLI shape (%r missing) (AC6)" % token,
            )
        self.assertIn(
            "workspace_path", migration,
            msg="the migration section must mention removing the "
                "workspace_path key from settings.local.json as the follow-up (AC6)",
        )


class RootReadmeCase(unittest.TestCase):
    """AC6 — repo-root README.md's acs-plugin bullet."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ROOT_README)

    def test_acs_bullet_no_longer_claims_outside_the_consumer_repo(self):
        m = re.search(r"(?ms)^- \*\*`acs`.{0,1200}", self.body)
        self.assertIsNotNone(m, "repo-root README.md must retain the acs plugin bullet")
        bullet = m.group(0)
        self.assertNotIn(
            "outside the consumer repo", bullet,
            msg="repo-root README.md's acs bullet must drop the outside-the-consumer-repo "
                "claim (AC6)",
        )
        self.assertIn(
            ".acs/state-machine", bullet,
            msg="repo-root README.md's acs bullet must name the in-repo "
                ".acs/state-machine default (AC6)",
        )


if __name__ == "__main__":
    unittest.main()
