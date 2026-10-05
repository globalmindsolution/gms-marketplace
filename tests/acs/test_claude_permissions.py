"""acs_lib.claude_permissions -- the Claude Code permission rules /acs:setup offers.

No skill sets `allowed-tools`, so every acs CLI call and every read-only git
call prompts. Setup offers (opt-in) a fixed set of `permissions.allow` rules for
the team's `.claude/settings.json` or the user's `.claude/settings.local.json`.
These tests pin the rules against the command strings Claude Code actually
sees -- `${CLAUDE_PLUGIN_ROOT}` already expanded -- with a matcher that follows
Claude Code's documented wildcard rule, and drive detect/apply in real repos.

Run:  python3 -m unittest tests.acs.test_claude_permissions -v
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import lib  # noqa: E402

CP = lib.claude_permissions


def claude_code_matches(rule, command):
    """Claude Code's documented Bash wildcard rule: `*` matches any run of
    characters, spaces included, anywhere in the pattern; a pattern ending in
    ` *` also matches the bare command without arguments."""
    pattern = re.fullmatch(r"Bash\((.*)\)", rule, re.S).group(1)
    regex = ".*".join(re.escape(part) for part in pattern.split("*"))
    if pattern.endswith(" *"):
        regex = "(?:%s|%s)" % (regex, re.escape(pattern[:-2]))
    return re.fullmatch(regex, command, re.S) is not None


def allowed(command):
    return [rule for rule in CP.RULES if claude_code_matches(rule, command)]


#: (expanded command, the rule that must match it)
ALLOWED = (
    ('python3 "/root/.claude/plugins/cache/gms-marketplace/acs/0.5.0/hooks/scripts/acs.py" '
     'step start --step x', CP.ACS_SCRIPTS_RULE),
    ('python3 "/home/dev/.claude/plugins/cache/gms-marketplace/acs/0.7.12/hooks/scripts/'
     'new-ticket.py" --title "Bulk export" --type task', CP.ACS_SCRIPTS_RULE),
    ('python3 "/home/user/gms-marketplace/plugins/acs/hooks/scripts/acs.py" run next',
     CP.ACS_SCRIPTS_RULE),
    ("python3 plugins/acs/hooks/scripts/acs.py", CP.ACS_SCRIPTS_RULE),
    ("git status", "Bash(git status*)"),
    ("git status --porcelain=v1 -z", "Bash(git status*)"),
    ("git diff --stat main...HEAD", "Bash(git diff*)"),
    ("git log --oneline -5", "Bash(git log*)"),
    ("git rev-parse --show-toplevel", "Bash(git rev-parse*)"),
    ("git ls-files -z --others", "Bash(git ls-files*)"),
    ("git show HEAD:README.md", "Bash(git show*)"),
    ("git check-ignore -q .acs/state-machine/", "Bash(git check-ignore*)"),
)

#: Writes, pushes, GitHub calls and arbitrary code keep prompting by design.
PROMPTED = (
    "git add -A", "git commit -m wip", "git push origin HEAD", "git reset --hard",
    "git checkout -- .", "gh pr create --fill", "gh api repos/a/b", "python3 evil.py",
    'python3 -c "import os"', "python3 /tmp/x/hooks/scripts/acs.py", "rm -rf .acs",
    "bash plugins/acs/hooks/scripts/acs.py",
)


def git(root, *args):
    proc = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), proc.stderr))
    return proc.stdout


class RulesTest(unittest.TestCase):

    def test_each_expanded_command_is_allowed_by_its_rule(self):
        for command, rule in ALLOWED:
            with self.subTest(command=command):
                self.assertIn(rule, allowed(command))

    def test_nothing_that_writes_is_pre_approved(self):
        for command in PROMPTED:
            with self.subTest(command=command):
                self.assertEqual(allowed(command), [])

    def test_every_rule_is_used_and_the_set_is_fixed(self):
        self.assertIsInstance(CP.RULES, tuple)
        used = {rule for _command, rule in ALLOWED}
        self.assertEqual(used, set(CP.RULES))
        self.assertEqual(len(CP.RULES), len(set(CP.RULES)))

    def test_the_matcher_follows_the_documented_trailing_space_rule(self):
        self.assertTrue(claude_code_matches("Bash(npm run *)", "npm run"))
        self.assertTrue(claude_code_matches("Bash(npm run *)", "npm run build --x"))
        self.assertFalse(claude_code_matches("Bash(npm run *)", "npm runx"))
        self.assertTrue(claude_code_matches("Bash(a * b)", "a x y b"))


class RepoCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-perms-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(self.root)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        with open(os.path.join(self.root, "README.md"), "w") as fh:
            fh.write("r\n")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-qm", "init")

    def path(self, scope, root=None):
        name = "settings.json" if scope == "team" else "settings.local.json"
        return os.path.join(root or self.root, ".claude", name)

    def read(self, scope, root=None):
        with open(self.path(scope, root), encoding="utf-8") as fh:
            return fh.read()

    def seed(self, scope, doc):
        os.makedirs(os.path.dirname(self.path(scope)), exist_ok=True)
        with open(self.path(scope), "w", encoding="utf-8") as fh:
            fh.write(doc if isinstance(doc, str) else json.dumps(doc))


class DetectTest(RepoCase):

    def test_a_fresh_repo_has_none_of_the_rules(self):
        out = CP.detect(self.root)
        self.assertEqual(out["rules"], list(CP.RULES))
        for scope in ("team", "user"):
            self.assertEqual(out[scope]["path"], self.path(scope))
            self.assertFalse(out[scope]["exists"])
            self.assertEqual(out[scope]["present"], [])
            self.assertEqual(out[scope]["missing"], list(CP.RULES))
        self.assertFalse(out["user"]["ignored"])

    def test_it_reports_the_rules_a_file_already_carries(self):
        self.seed("team", {"permissions": {"allow": ["Bash(git log*)", "Bash(npm test)"]}})
        out = CP.detect(self.root)
        self.assertEqual(out["team"]["present"], ["Bash(git log*)"])
        self.assertNotIn("Bash(git log*)", out["team"]["missing"])

    def test_an_unreadable_file_is_reported_not_raised(self):
        self.seed("user", "{not json")
        out = CP.detect(self.root)
        self.assertIn("not valid JSON", out["user"]["error"])
        self.assertIsNone(out["team"]["error"])


class ApplyTest(RepoCase):

    def test_team_creates_the_file_with_every_rule(self):
        out = CP.apply(self.root, "team")
        self.assertEqual(out, {"scope": "team", "path": self.path("team"),
                               "added": list(CP.RULES)})
        doc = {"permissions": {"allow": list(CP.RULES)}}
        self.assertEqual(self.read("team"), json.dumps(doc, indent=2) + "\n")
        self.assertFalse(os.path.exists(self.path("user")))

    def test_user_writes_the_local_file(self):
        CP.apply(self.root, "user")
        self.assertEqual(json.loads(self.read("user"))["permissions"]["allow"], list(CP.RULES))
        self.assertFalse(os.path.exists(self.path("team")))

    def test_the_merge_keeps_every_other_key_and_rule(self):
        self.seed("team", {"enabledPlugins": {"acs@gms-marketplace": True},
                           "permissions": {"allow": ["Bash(npm test)", "Bash(git status*)"],
                                           "deny": ["Bash(rm *)"], "defaultMode": "default"},
                           "model": "x"})
        out = CP.apply(self.root, "team")
        self.assertNotIn("Bash(git status*)", out["added"])
        doc = json.loads(self.read("team"))
        self.assertEqual(doc["enabledPlugins"], {"acs@gms-marketplace": True})
        self.assertEqual(doc["model"], "x")
        self.assertEqual(doc["permissions"]["deny"], ["Bash(rm *)"])
        self.assertEqual(doc["permissions"]["defaultMode"], "default")
        allow = doc["permissions"]["allow"]
        self.assertEqual(allow[:2], ["Bash(npm test)", "Bash(git status*)"])
        self.assertEqual(sorted(allow[2:]), sorted(r for r in CP.RULES
                                                   if r != "Bash(git status*)"))
        self.assertEqual(len(allow), len(set(allow)))

    def test_a_re_run_adds_nothing_and_rewrites_nothing(self):
        CP.apply(self.root, "user")
        before = self.read("user")
        os.utime(self.path("user"), (1, 1))
        self.assertEqual(CP.apply(self.root, "user")["added"], [])
        self.assertEqual(self.read("user"), before)
        self.assertEqual(os.stat(self.path("user")).st_mtime, 1)
        self.assertEqual(CP.detect(self.root)["user"]["missing"], [])

    def test_dry_run_reports_and_writes_nothing(self):
        self.assertEqual(CP.apply(self.root, "team", dry_run=True)["added"], list(CP.RULES))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude")))

    def test_a_linked_worktree_writes_the_main_checkouts_local_file(self):
        wt = os.path.join(self.tmp, "wt")
        git(self.root, "worktree", "add", "-q", "-b", "feat", wt)
        self.assertEqual(CP.detect(wt)["user"]["path"], self.path("user"))
        out = CP.apply(wt, "user")
        self.assertEqual(out["path"], self.path("user"))
        self.assertTrue(os.path.isfile(self.path("user")))
        self.assertFalse(os.path.exists(os.path.join(wt, ".claude")))

    def test_files_it_cannot_merge_into_are_refused_untouched(self):
        for bad, why in (("{not json", "not valid JSON"), ("[]", "not a JSON object"),
                         ('{"permissions": []}', "permissions"),
                         ('{"permissions": {"allow": "Bash(x)"}}', "permissions.allow")):
            with self.subTest(bad=bad):
                self.seed("team", bad)
                errors = CP.errors(self.root, "team")
                self.assertTrue(errors and why in errors[0], errors)
                with self.assertRaises(lib.GateError):
                    CP.apply(self.root, "team")
                self.assertEqual(self.read("team"), bad)

    def test_the_answer_must_be_a_known_scope(self):
        self.assertEqual(CP.errors(self.root, "skip"), [])
        self.assertEqual(CP.errors(self.root, "team"), [])
        for bad in ("everyone", "", None, ["team"]):
            with self.subTest(bad=bad):
                self.assertIn("team, user or skip", CP.errors(self.root, bad)[0])
                with self.assertRaises(lib.GateError):
                    CP.apply(self.root, bad)

    def test_only_the_user_scope_needs_an_ignore_entry(self):
        self.assertEqual(CP.ignore_entries("user"), (".claude/settings.local.json",))
        self.assertEqual(CP.ignore_entries("team"), ())
        self.assertEqual(CP.ignore_entries("skip"), ())


if __name__ == "__main__":
    unittest.main()
