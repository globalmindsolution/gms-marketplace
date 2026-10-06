"""MAR-4 — other shipped skill surfaces + product docs describe the in-repo
default state root (AC3, AC4, AC5, AC6).

Prose-contract unit test covering every shipped surface outside
`setup/SKILL.md` (Task 1's file) that still referenced the retired
"workspace_path lives outside the repo, machine-local, always set" model:

  AC3 — handoff/SKILL.md carries no workspace derivation of its own since
    ADR-0131 made it the team-handoff skill: `acs.py handoff` resolves the
    in-repo default (`<main-checkout>/.acs/state-machine`) like every hook,
    the skill never names the retired `workspace_path` or its unreachable
    "workspace_path is not configured" hint, and its scope is cross-machine
    through the hidden ref `refs/acs/handoff/<ID>`.
  AC4 — update/SKILL.md's Step 6 item 3 "Workspace reachable" check resolves
    the same way item 1 already does (settings load + validate/derive),
    instead of assuming a bare workspace_path key is always set;
    release/SKILL.md carries no outside-repo claim (verification-only,
    grounded finding from the plan — pinned here as a regression guard).
  AC5 — plugin.json's description is ASCII-only and describes the in-repo
    default; .claude-plugin/marketplace.json stays byte-identical (out of
    MAR-4 scope, byte-pinned). plugins/acs/CHANGELOG.md is append-only
    instead of byte-identical: MAR-5 (`/acs:docs-sync`) is the ticket
    responsible for landing the epic's missing changelog entries, so this
    guard only checks that the diff against `main` never removes or
    rewords an existing line.
  AC6 — both README.md files (plugin + repo-root) describe the in-repo
    default; plugins/acs/README.md gains a "Migrating an existing external
    workspace" section naming the exact migrate_workspace.py CLI shape.

Stdlib-only (json, os, re, unittest), mirroring
the retired tests/acs/test_setup_offers.py (REPO_ROOT/PLUGIN + read helper +
bounded-window section-scoped assertions) so a too-loose match cannot pass
vacuously.

Run:  python3 -m unittest tests.acs.test_state_root_skill_surfaces -v
"""

import json
import os
import sys
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


class HandoffLeavesTheWorkspaceToTheCliCase(unittest.TestCase):
    """AC3, as ADR-0131 rewrote the skill: /acs:handoff no longer derives the
    workspace by hand. Every byte a team handoff moves is moved by `acs.py
    handoff`, which resolves the in-repo state root the way every hook does
    (`acs_lib.default_state_root()`), so the skill carries no derivation of its
    own to drift -- and, a fortiori, no retired `workspace_path` model."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(HANDOFF_SKILL)

    def test_no_hand_derivation_of_the_workspace(self):
        self.assertNotRegex(self.body, r"(?m)^#+ Locating the workspace")
        self.assertNotIn("checkout-id", self.body)

    def test_every_move_is_the_cli(self):
        for mode in ("send", "receive", "list"):
            self.assertRegex(self.body, r'acs\.py" handoff %s\b' % mode, mode)

    def test_no_retired_workspace_path_model(self):
        self.assertNotIn("workspace_path", self.body)

    def test_no_unreachable_workspace_path_is_not_configured_hint(self):
        """`workspace_path is not configured` is not a message acs_lib/ or
        handoff.py ever emits -- the skill must not document it either."""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from acs_case import acs_lib_paths
        for path in acs_lib_paths() + [
            os.path.join(PLUGIN, "hooks", "scripts", "handoff.py"),
        ]:
            self.assertNotIn(
                "workspace_path is not configured", read(path),
                msg="grounding check: this message must not exist in %s "
                    "for this test's premise to hold" % path,
            )
        self.assertNotIn("workspace_path is not configured", self.body)


class HandoffScopeClaimCase(unittest.TestCase):
    """AC3's Scope claim, superseded by ADR-0131: the state machine is still
    local to each machine, and a handoff now crosses machines through the
    shared remote's hidden ref rather than declaring that out of scope."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(HANDOFF_SKILL)
        cls.norm = re.sub(r"\s+", " ", cls.body)

    def test_cross_machine_is_no_longer_out_of_scope(self):
        self.assertNotIn("cross-machine handoff is out of scope", self.norm)
        self.assertNotIn("same machine and checkout", self.norm)

    def test_names_the_hidden_ref(self):
        self.assertIn("refs/acs/handoff/<ID>", self.body)
        self.assertRegex(self.norm, r"(?i)never a branch or a PR")


class UpdateWorkspaceReachableCase(unittest.TestCase):
    """AC4 — update/SKILL.md Step 6 item 4 'Workspace reachable'."""

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
        """Item 4 no longer reads 'workspace_path exists and is writable' as
        if the key is always set — that assumption is gone."""
        item3 = self.item(4, "Workspace reachable")
        self.assertNotIn(
            "`workspace_path` exists and is writable", item3,
            msg="item 4 must no longer assume workspace_path is always a set key (AC4)",
        )

    def test_workspace_reachable_resolves_like_item_one(self):
        """Item 4 resolves the workspace the same way item 2 already does
        (acs_lib.load_settings + acs_lib.validate_settings), rather than
        reading a possibly-absent workspace_path key directly."""
        item1 = self.item(2, "Settings still valid")
        item3 = self.item(4, "Workspace reachable")
        self.assertIn("acs_lib.load_settings", item1)
        self.assertIn("acs_lib.validate_settings", item1)
        for marker in ("acs_lib.load_settings", "acs_lib.validate_settings"):
            self.assertIn(
                marker, item3,
                msg="item 4 must resolve the workspace via %r, the same "
                    "resolution approach item 2 already uses (AC4)" % marker,
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


def git_diff_against_merge_base(rel_path):
    """Unified diff of `rel_path` between the commit where this branch
    diverged from `main` and the current working tree."""
    base_ref = _base_ref()
    base = subprocess.check_output(
        ["git", "merge-base", base_ref, "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    return subprocess.check_output(
        ["git", "diff", base, "--", rel_path], cwd=REPO_ROOT, text=True
    )


class OutOfScopeUntouchedCase(unittest.TestCase):
    """AC5 regression guard on the CHANGELOG's append-only invariant.

    This class also byte-pinned `.claude-plugin/marketplace.json` to `main`,
    a per-PR scope guard for MAR-4 that outlived its PR. A release MUST edit
    that file -- the version and the acs `source.ref` are steps 1 and 2 of
    the documented release process -- so the guard made cutting any release
    impossible. Removed in 0.4.9, the same class of cleanup as #488.

    `plugins/acs/CHANGELOG.md` is different: any ticket adding its own
    dated entry under `[Unreleased]` is expected and must not be blocked by
    this guard (see `plugins/acs/skills/code/SKILL.md`'s docs-sync
    hand-off, and `docs-sync/SKILL.md`), so a byte-identical guard would
    directly contradict that required deliverable. The invariant this
    file's own header actually promises — CHANGELOG.md is append-only — is
    checked instead: the diff against the merge-base may only ADD lines,
    never remove or reword an existing one."""

    def setUp(self):
        if _base_ref() is None:
            self.skipTest("no base ref (origin/main or main) to diff against")

    def test_changelog_append_only(self):
        diff = git_diff_against_merge_base("plugins/acs/CHANGELOG.md")
        removed = [
            line for line in diff.splitlines()
            if line.startswith("-") and not line.startswith("---")
        ]
        self.assertEqual(
            removed, [],
            msg="`plugins/acs/CHANGELOG.md` must only gain new lines "
                "relative to `main` (append-only) — no pre-existing line may "
                "be edited or removed: %r" % (removed[:5],),
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

    def test_configuration_names_the_in_repo_workspace_and_no_key_for_it(self):
        """ADR-0102: the workspace_path row is gone with the key; the section
        still names where the workspace is."""
        config = section(self.body, "## Configuration")
        self.assertNotIn("workspace_path", config)
        self.assertNotIn("outside the repo", config)
        self.assertIn(
            ".acs/state-machine", config,
            msg="the Configuration section must name the in-repo workspace (AC6)",
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
            msg="the migration section must name the retired workspace_path key "
                "left in settings.local.json as ignored (AC6, ADR-0102)",
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
