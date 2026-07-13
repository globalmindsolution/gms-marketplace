"""MAR-129 — /acs:release registry wiring + SAFETY prose (AC-1, AC-5).

`"release"` must land in `UNHOOKED_SKILLS` only — never `HOOKED_SKILLS`,
`PRODUCT_SKILLS`, `WORKFLOW_SKILLS`, or `GATES` — proving `dispatch.py`'s
existing `skill not in acs_lib.HOOKED_SKILLS` passthrough exempts
`/acs:release` with zero dispatch code change (mirrors
`test_mar114_test_skill_registry.py` for `/acs:test`). Also pins the
on-disk negatives (no pre-/post-release.py, no release-*.md agent file,
agent count unchanged) and the SAFETY-invariant prose `release/SKILL.md`
must carry (AC-5): never tags/publishes itself, never force-pushes or
pushes to main, and the PR-open step is labeled/branched correctly.

Also pins the settings-driven delta (MAR-129 re-spec, Decision 5/C-20):
every release_notes.py status/draft/bump call passes --release-config, no
marketplace-specific literal is hardcoded in a bash fence, and the body
states the release-block fail-fast + non-secret invariants.

Run:  python3 -m unittest tests.acs.test_mar129_release_skill_registry -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
AGENTS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "agents")
SKILL_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "release", "SKILL.md")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


def _read_skill_body():
    with open(SKILL_PATH, encoding="utf-8") as fh:
        return fh.read()


def _bash_fences(body):
    return re.findall(r"```bash\n(.*?)```", body, re.DOTALL)


class Mar129ReleaseSkillRegistryCase(unittest.TestCase):
    def test_release_in_unhooked_skills(self):
        self.assertIn(
            "release", acs_lib.UNHOOKED_SKILLS,
            msg="'release' must be registered in UNHOOKED_SKILLS (AC-1)",
        )

    def test_release_not_in_hooked_skills(self):
        self.assertNotIn(
            "release", acs_lib.HOOKED_SKILLS,
            msg="'release' must NOT be in HOOKED_SKILLS — it is not a "
                "hooked pipeline skill (AC-1)",
        )

    def test_release_not_in_product_or_workflow_skills(self):
        self.assertNotIn(
            "release", acs_lib.PRODUCT_SKILLS,
            msg="'release' must NOT be miscategorized into PRODUCT_SKILLS",
        )
        self.assertNotIn(
            "release", acs_lib.WORKFLOW_SKILLS,
            msg="'release' must NOT be miscategorized into WORKFLOW_SKILLS",
        )

    def test_release_not_in_gates(self):
        self.assertNotIn(
            "release", acs_lib.GATES,
            msg="'release' must NOT have a GATES entry — no synthetic "
                "predecessor gate for an unhooked utility skill (AC-1)",
        )

    def test_unhooked_skills_count_is_nine(self):
        self.assertEqual(len(acs_lib.UNHOOKED_SKILLS), 9)

    def test_hooked_skills_count_unchanged_fourteen(self):
        self.assertEqual(len(acs_lib.HOOKED_SKILLS), 14)

    def test_gates_count_unchanged_fourteen(self):
        self.assertEqual(len(acs_lib.GATES), 14)

    def test_no_pre_or_post_release_script_on_disk(self):
        self.assertFalse(
            os.path.isfile(os.path.join(HOOKS_DIR, "pre-release.py")),
            msg="pre-release.py must not exist — release is unhooked (AC-1, AC-5)",
        )
        self.assertFalse(
            os.path.isfile(os.path.join(HOOKS_DIR, "post-release.py")),
            msg="post-release.py must not exist — release is unhooked (AC-1, AC-5)",
        )

    def test_no_release_agent_files_on_disk(self):
        self.assertEqual(
            glob.glob(os.path.join(AGENTS_DIR, "release-*.md")), [],
            "no plugins/acs/agents/release-*.md file may exist (AC-1)",
        )

    def test_agent_count_unchanged_forty_two(self):
        self.assertEqual(len(glob.glob(os.path.join(AGENTS_DIR, "*.md"))), 42)

    def test_release_config_flag_passed_to_every_subcommand(self):
        for fence in _bash_fences(_read_skill_body()):
            for line in fence.splitlines():
                if re.search(r"release_notes\.py\"?\s+(status|draft|bump)\b", line):
                    self.assertIn(
                        "--release-config", line,
                        msg="every release_notes.py status/draft/bump call must "
                            "pass --release-config (settings-driven, AC-2/AC-6): %r" % line,
                    )

    def test_no_hardcoded_marketplace_literals_in_bash_fences(self):
        forbidden = [
            ".claude-plugin/marketplace.json",
            "plugins/acs/.claude-plugin/plugin.json",
            "plugins/acs/CHANGELOG.md",
            "release/v",
            "--base main",
        ]
        for fence in _bash_fences(_read_skill_body()):
            for literal in forbidden:
                self.assertNotIn(
                    literal, fence,
                    msg="release/SKILL.md bash fences must not hardcode the "
                        "marketplace-specific literal %r — use the "
                        "block-rendered placeholder instead" % literal,
                )

    def test_release_block_absence_fails_fast_stated(self):
        self.assertRegex(
            _read_skill_body(),
            r"(?i)release.{0,40}block.{0,60}(fail fast|no .{0,20}release.{0,20}configured)",
            msg="release/SKILL.md must state that an absent/missing release "
                "settings block causes the skill to fail fast before any "
                "release_notes.py invocation",
        )


class Mar129ReleaseSafetyProseCase(unittest.TestCase):
    """AC-5 (SAFETY): the invariants must be explicit, load-bearing prose."""

    def setUp(self):
        self.body = _read_skill_body()

    def _bash_fences(self):
        return _bash_fences(self.body)

    def test_never_git_tag_or_gh_release_create_prohibition_stated(self):
        forward = re.search(
            r"(?i)never.{0,60}(git tag|gh release create)", self.body,
        )
        backward = re.search(
            r"(?i)(git tag|gh release create).{0,60}never", self.body,
        )
        self.assertTrue(
            forward or backward,
            "release/SKILL.md must explicitly state it never runs "
            "'git tag' or 'gh release create' (AC-5)",
        )
        # Both literal strings must each be paired with "never" somewhere,
        # not just one of the two.
        self.assertRegex(self.body, r"(?i)never[^\n]{0,60}git tag|git tag[^\n]{0,60}never")
        self.assertRegex(
            self.body,
            r"(?i)never[^\n]{0,60}gh release create|gh release create[^\n]{0,60}never",
        )

    def test_no_bash_fence_actually_invokes_forbidden_commands(self):
        for fence in self._bash_fences():
            for line in fence.splitlines():
                self.assertNotRegex(
                    line, r"^\s*(git tag|gh release create)\b",
                    "a ```bash fence must never invoke 'git tag' or "
                    "'gh release create' as a command (AC-5): %r" % line,
                )

    def test_release_workflow_stated_reused_unchanged(self):
        self.assertTrue(
            re.search(
                r"(?i)(publish[ _]driver|release\.yml)[^\n]{0,80}"
                r"(reused unchanged|not modified)",
                self.body,
            )
            or re.search(
                r"(?i)(reused unchanged|not modified)[^\n]{0,80}"
                r"(publish[ _]driver|release\.yml)",
                self.body,
            ),
            "release/SKILL.md must state the publish_driver (release.yml) is "
            "reused unchanged / not modified (AC-5)",
        )

    def test_pr_open_step_labeled_and_branched(self):
        fences = self._bash_fences()
        pr_create_fences = [f for f in fences if "gh pr create" in f]
        self.assertTrue(pr_create_fences, "no ```bash fence contains 'gh pr create'")
        for fence in pr_create_fences:
            self.assertIn("--label ACS", fence)
            self.assertRegex(
                fence, r"(?i)release[_-]?branch",
                msg="the gh pr create fence must reference the "
                    "<release_branch> placeholder (block-rendered branch name)",
            )

    def test_no_force_push_or_push_to_main(self):
        self.assertNotIn("--force", self.body)
        self.assertNotIn("push origin main", self.body)
        for fence in self._bash_fences():
            if "gh pr create" in fence:
                self.assertNotRegex(
                    fence, r"--base main\b",
                    msg="main must never be hardcoded as the PR base — only "
                        "reachable via the <base_branch> placeholder",
                )

    def test_release_block_stated_non_secret(self):
        self.assertRegex(
            self.body,
            r"(?i)release.{0,80}no secret|no secret.{0,80}release",
            msg="release/SKILL.md must state the release settings block "
                "holds no secret (paths/pointers/format strings only, AC-5)",
        )


if __name__ == "__main__":
    unittest.main()
