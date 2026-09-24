"""Every free grader in the setup and artifact suites, calibrated -- locally.

Local-only like everything under tests/evals/ (ADR-0108): run by the
`acs-eval-checks` pre-commit hook and the release gate, never by CI.

A grader that cannot fail proves nothing, and one that cannot pass reads as a
plugin failure forever. So for each case this test builds the case's real
scaffold, plays an IDEAL run and one or more BAD runs through the plugin's own
writers -- `acs.py setup apply`, `acs.py step start --allocate`, `acs.py ticket
save`, `acs.py step finish` -- and grades the result the way `claude plugin
eval` does:

* the ideal run passes every free grader;
* every bad run fails at least one.

Because the ideal runs use the real writers, a change to what a skill writes
(a renamed key, a moved state file) fails here, where it is free, instead of
reading as a skill regression on a paid run.

The grading below mirrors the CLI's own graders (claude 2.1.281):

* `regex` reads `last_message`, `files` (the paths CREATED during the run,
  sorted, one per line) or `{source: file, path}`; a file that does not exist
  makes the grader throw, and a grader that throws FAILS in every match mode --
  so `not_contains` on a missing file fails rather than passes.
* `file_exists` globs the created paths (`*` within a segment, `**` across).
* `tool_used` counts calls whose tool matches and whose JSON input matches
  `input_match`, and passes inside `min`..`max` (default 1..inf).

`llm` graders are not calibrated here: they need a judge, which costs money.
Their calibration is the paid pilot the evals README describes.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_ACS = HERE  # the strict case reader lives beside these checks
sys.path.insert(0, TESTS_ACS)
import eval_cases as ec  # noqa: E402

ACS = os.path.join(ec.PLUGIN, "hooks", "scripts", "acs.py")
FREE = ("regex", "file_exists", "tool_used")
TICKET = ".acs/state-machine/example-shop/EVAL-1/ticket.json"


# --------------------------------------------------------------------------
# The CLI's grader semantics, mirrored.

def _glob_regex(pattern):
    out, i = "^", 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i + 1:i + 3] == "*/":
                out += "(?:.*/)?"
                i += 3
                continue
            if pattern[i + 1:i + 2] == "*":
                out += ".*"
                i += 2
                continue
            out += "[^/]*"
        elif ch == "?":
            out += "."
        else:
            out += re.escape(ch)
        i += 1
    return re.compile(out + "$")


def _flags(text):
    value = 0
    for ch in text or "":
        value |= {"m": re.M, "i": re.I, "s": re.S, "g": 0}[ch]
    return value


def grade(grader, ws, created, tool_calls, last_message=""):
    """True / False for a free grader; None for one this test cannot run."""
    fm = grader.fm
    kind = fm["type"]
    if kind == "file_exists":
        rx = _glob_regex(fm["path"])
        present = any(rx.match(p) for p in created)
        return present == fm.get("exists", True)
    if kind == "tool_used":
        count = 0
        for name, tool_input in tool_calls:
            if name != fm["tool"]:
                continue
            text = json.dumps(tool_input, separators=(",", ":"))
            if fm.get("input_match") and not re.search(fm["input_match"], text):
                continue
            count += 1
        lo, hi = fm.get("min", 1), fm.get("max")
        return count >= lo and (hi is None or count <= hi)
    if kind == "regex":
        target = fm.get("target", "last_message")
        if target == "last_message":
            text = last_message
        elif target == "files":
            text = "\n".join(created)
        else:
            path = os.path.join(ws, target["path"])
            if not os.path.isfile(path):
                return False  # the CLI's grader throws, and a throw is a fail
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        rx = re.compile(fm["pattern"], _flags(fm.get("flags")))
        match = str(fm.get("match", "contains"))
        if match == "contains":
            return rx.search(text) is not None
        if match == "not_contains":
            return rx.search(text) is None
        if match.startswith("count:"):
            return len(rx.findall(text)) == int(match.split(":", 1)[1])
        raise AssertionError("unknown match mode %r" % match)
    return None


# --------------------------------------------------------------------------
# Plays: what a run did, expressed through the plugin's real writers.

def _files(ws):
    out = set()
    for root, dirs, names in os.walk(ws):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            out.add(os.path.relpath(os.path.join(root, name), ws).replace(os.sep, "/"))
    return out


class Workspace(object):
    def __init__(self, case):
        self.case = case
        self.path = tempfile.mkdtemp(prefix="calib-")
        self.env = dict(os.environ, HOME=self.path)
        self.tools = []
        script = case.case_yaml["context"]["scaffold_script"]
        subprocess.run(["bash", os.path.join(case.path, script)], cwd=self.path,
                       env=self.env, check=True, capture_output=True)
        self.before = _files(self.path)

    def acs(self, *args, stdin=None):
        return subprocess.run([sys.executable, ACS] + list(args), cwd=self.path, env=self.env,
                              input=stdin, capture_output=True, text=True)

    def called(self, tool, **tool_input):
        self.tools.append((tool, tool_input))

    def skill(self, name):
        self.called("Skill", skill="acs:" + name)

    def write(self, rel, text, append=False):
        path = os.path.join(self.path, rel)
        os.makedirs(os.path.dirname(path) or self.path, exist_ok=True)
        with open(path, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(text)

    def setup_apply(self, settings, ci):
        return self.acs("setup", "apply", "--answers", "-",
                        stdin=json.dumps({"settings": settings, "ci": ci}))

    def created(self):
        return sorted(_files(self.path) - self.before)

    def close(self):
        shutil.rmtree(self.path, ignore_errors=True)


BRACKETED = {"formats": {"pr_title": "[{ticket_id}] {title}"}}
PYTEST = {"tests": {"command": "python3 -m pytest -q --cov=src --cov-fail-under=$ACS_COVERAGE"}}


def _ticket(ws, **overrides):
    """What /acs:create-ticket does: allocate (the mandatory first action),
    then the executor's rewrite of ticket.json."""
    ws.skill("create-ticket")
    start = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                   "--title", "(ticket under analysis)", "--args", "Add a /health endpoint")
    assert start.returncode == 0, start.stderr
    if overrides is None:
        return
    with open(os.path.join(ws.path, TICKET), encoding="utf-8") as fh:
        ticket = json.load(fh)
    ticket.update({"title": "Add a /health endpoint returning ok",
                   "description": "GET /health returns 200 with body ok.",
                   "acceptance_criteria": ["GET /health responds 200 with body \"ok\""]})
    ticket.update(overrides)
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-", stdin=json.dumps(ticket))
    assert saved.returncode == 0, saved.stderr


def _placeholder_only(ws):
    ws.skill("create-ticket")
    ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
           "--title", "(ticket under analysis)", "--args", "Add a /health endpoint")


def _code(ws, app, status="completed"):
    """What /acs:code does on the seeded ticket: start the step, change app.py,
    finish the step."""
    ws.skill("code")
    assert ws.acs("step", "start", "--step", "code", "--ticket", "EVAL-1").returncode == 0
    if app is not None:
        ws.write("app.py", app)
    assert ws.acs("step", "finish", "--step", "code", "--run", "EVAL-1",
                  "--status", status, "--summary", "calibration").returncode == 0


ROUTE = ('def health():\n    return "ok"\n\n\n'
         'def handle(path):\n    if path == "/health":\n        return 200, health()\n')

#: case -> (ideal play, {bad play label: bad play})
PLAYS = {
    "01-keep-defaults": (
        lambda ws: (ws.skill("setup"), ws.setup_apply({}, [])),
        {"wrote CI, a settings file and an answers file": lambda ws: (
            ws.skill("setup"), ws.write("answers.json", "{}"), ws.setup_apply({}, ["conventions"]),
            ws.write(".acs/settings.json", '{"formats": {"branch_name": "{type}/{ticket_id}-{slug}"}}\n'))},
    ),
    "02-custom-pr-title": (
        lambda ws: (ws.skill("setup"), ws.setup_apply(BRACKETED, ["conventions"])),
        {"kept the default title, wrote the prefix, added a tests gate, changed protection":
            lambda ws: (ws.skill("setup"), ws.setup_apply({}, []),
                        ws.write(".acs/settings.json", '{"ticket_prefix": "ACS"}\n'),
                        ws.write(".github/workflows/acs-tests.yml", "x"),
                        ws.called("Bash", command="gh api -X PUT repos/example/shop/branches/main/protection"))},
    ),
    "03-tests-gate": (
        lambda ws: (ws.skill("setup"), ws.setup_apply(PYTEST, ["tests"])),
        {"a command with no pytest and no floor, and the wrong gate": lambda ws: (
            ws.skill("setup"), ws.write(".acs/settings.json", '{"tests": {"command": "true"}}\n'),
            ws.write(".github/workflows/acs-conventions.yml", "x"))},
    ),
    "04-rerun": (
        lambda ws: (ws.skill("setup"), ws.setup_apply(BRACKETED, ["conventions"])),
        {"lost the custom format, duplicated the ignore line, added a gate": lambda ws: (
            ws.skill("setup"), ws.write(".acs/settings.json", "{}\n"),
            ws.write(".gitignore", ".acs/state-machine/\n", append=True),
            ws.write(".acs/ci/run-tests.py", "x"))},
    ),
    "05-no-choices": (
        lambda ws: ws.skill("setup"),
        {"configured without asking": lambda ws: (
            ws.skill("setup"), ws.setup_apply({}, ["conventions"]),
            ws.write(".acs/settings.json", "{}\n"))},
    ),
    "06-invalid-branch-format": (
        # The wizard validates before writing and refuses: nothing is written.
        lambda ws: (ws.skill("setup"),
                    ws.setup_apply({"formats": {"branch_name": "{type}/{slug}"}}, [])),
        {"wrote the invalid format, then refused": lambda ws: (
            ws.skill("setup"),
            ws.write(".acs/settings.json", '{"formats": {"branch_name": "{type}/{slug}"}}\n'))},
    ),
    "07-neg-github-actions": (
        lambda ws: ws.write(".github/workflows/ci.yml", "on: [push]\n"),
        {"setup fired and installed its gate": lambda ws: (
            ws.skill("setup"), ws.setup_apply({}, ["conventions"]))},
    ),
    "08-neg-pre-commit": (
        lambda ws: ws.write(".pre-commit-config.yaml", "repos: []\n"),
        {"setup fired instead of doing the request": lambda ws: (
            ws.skill("setup"), ws.setup_apply({}, ["conventions"]))},
    ),
    "create-ticket-artifacts": (
        lambda ws: _ticket(ws, needs_design=False),
        {"started the skill and wrote nothing": _placeholder_only,
         "re-litigated needs_design": lambda ws: _ticket(ws, needs_design=True),
         "hand-wrote the ticket without the skill": lambda ws: (
             ws.write(TICKET, '{"id": "EVAL-1", "type": "task", "needs_design": false}\n'),
             ws.write(".acs/state-machine/example-shop/tickets-index.json", '{"EVAL-1": {}}\n'))},
    ),
    "resume-and-verify": (
        lambda ws: _code(ws, ROUTE),
        {"never implemented": lambda ws: _code(ws, None, status="failed"),
         "mentioned /health only in a comment": lambda ws: _code(
             ws, 'def health():\n    return "ok"\n# TODO: wire up /health\n')},
    ),
}

CALIBRATED_GROUPS = ("setup", "artifacts")


def calibrated_cases():
    return sorted((c for c in ec.all_cases() if c.group in CALIBRATED_GROUPS),
                  key=lambda c: c.name)


def play(case, action):
    ws = Workspace(case)
    try:
        action(ws)
        created = ws.created()
        return {g.name: grade(g, ws.path, created, ws.tools) for g in case.graders}
    finally:
        ws.close()


class CalibrationTest(unittest.TestCase):

    def test_every_case_in_the_calibrated_suites_has_plays(self):
        """A new setup or artifact case must arrive with its calibration."""
        self.assertEqual(sorted(c.name for c in calibrated_cases()), sorted(PLAYS))

    def test_the_ideal_run_passes_every_free_grader(self):
        for case in calibrated_cases():
            ideal, _ = PLAYS[case.name]
            verdicts = play(case, ideal)
            for name, passed in sorted(verdicts.items()):
                if passed is None:
                    continue
                with self.subTest(case=case.name, grader=name):
                    self.assertTrue(passed, "the ideal run fails this grader")

    def test_every_bad_run_fails_a_free_grader(self):
        for case in calibrated_cases():
            _, bad = PLAYS[case.name]
            self.assertTrue(bad, "%s has no bad run" % case.name)
            for label, action in sorted(bad.items()):
                verdicts = play(case, action)
                with self.subTest(case=case.name, bad=label):
                    self.assertIn(False, verdicts.values(), "no free grader catches it")

    def test_every_case_carries_a_free_grader_on_what_it_produced(self):
        """A case graded only by a judge, or only by whether the skill fired,
        cannot be calibrated here -- and cannot tell a right result from a
        confident reply."""
        for case in calibrated_cases():
            with self.subTest(case=case.name):
                self.assertTrue(any(g.type in ("regex", "file_exists") for g in case.graders))


class MirroredSemanticsTest(unittest.TestCase):
    """The mirror's own edges, pinned so a change to it is a deliberate one."""

    def test_the_glob_matches_within_and_across_segments(self):
        self.assertTrue(_glob_regex(".github/workflows/*.yml").match(".github/workflows/ci.yml"))
        self.assertFalse(_glob_regex(".github/workflows/*.yml").match(".github/workflows/a/ci.yml"))
        self.assertTrue(_glob_regex("**/state.json").match("runs/R/steps/code/state.json"))
        self.assertTrue(_glob_regex("**/state.json").match("state.json"))

    def test_a_missing_file_fails_even_not_contains(self):
        grader = type("G", (), {"fm": {"type": "regex", "target": {"source": "file",
                                                                   "path": "absent.json"},
                                       "pattern": "x", "match": "not_contains"}})()
        self.assertFalse(grade(grader, tempfile.gettempdir(), [], []))

    def test_tool_input_is_matched_as_compact_json(self):
        grader = type("G", (), {"fm": {"type": "tool_used", "tool": "Skill",
                                       "input_match": '"skill":"acs:setup"'}})()
        self.assertTrue(grade(grader, "", [], [("Skill", {"skill": "acs:setup"})]))


if __name__ == "__main__":
    unittest.main()
