"""Shared, importable test fixture for the acs plugin's deterministic layer (MAR-175).

Exposes AcsWorkspaceCase (throwaway git repo + .acs settings + isolated
workspace, driving the real hook CLIs via subprocess) plus load_module(),
run_main(), pushd() and fake_gh() -- in-process helpers for driving a loaded
script's main() directly -- so sibling test modules can add independent
files instead of all editing test_acs_plugin.py.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402


#: The acs_lib package (MAR-522 split the single acs_lib.py into eight modules).
ACS_LIB_PKG = os.path.join(SCRIPTS, "acs_lib")


def tracker_body(case, text="## Description\n\nBulk import.\n"):
    """A REAL `tracker-body.md` on disk, removed when `case` finishes.

    `Gh(responses=...)` replays a transcript and never opens `--body-file`, so
    every tracker-sync fixture used to pass a path that did not exist -- and so
    none of them could notice that the file has to be written before the sync
    runs. `tracker_sync_one` now refuses a missing body, and this is what the
    fixtures hand it: the same file the executor writes, in the same shape."""
    workdir = tempfile.mkdtemp(prefix="acs-tracker-body-")
    case.addCleanup(shutil.rmtree, workdir, True)
    path = os.path.join(workdir, "tracker-body.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def acs_lib_paths():
    """Every module file of the acs_lib package, sorted for stable output.

    A text scan that used to open acs_lib.py must walk these instead, or it
    silently stops covering the code it was written to guard."""
    return [os.path.join(ACS_LIB_PKG, name)
            for name in sorted(os.listdir(ACS_LIB_PKG)) if name.endswith(".py")]


def acs_lib_source():
    """The package's concatenated source -- what reading acs_lib.py used to give."""
    parts = []
    for path in acs_lib_paths():
        with open(path, encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)


class AcsWorkspaceCase(unittest.TestCase):
    """Fixture: a consumer git repo with valid .acs settings + empty workspace."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "shop")
        self.ws = os.path.join(self.tmp, "workspace")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        subprocess.run(["git", "-C", self.repo, "remote", "add", "origin",
                        "https://github.com/acme/shop.git"], check=True)
        os.makedirs(os.path.join(self.repo, ".acs"))
        self.write_settings({"ticket_prefix": "SHOP", "test_coverage_percent": 90})
        with open(os.path.join(self.repo, ".acs", "settings.local.json"), "w") as fh:
            json.dump({"workspace_path": self.ws}, fh)
        self.seed_counters(next_n=1)

    def _counters_path(self, repo_id="acme-shop"):
        return os.path.join(lib.repo_dir(self.ws, repo_id), "counters.json")

    def seed_counters(self, next_n=1, repo_id="acme-shop"):
        """Seed a reconciled counters.json (MAR-402's fixture seam) so a fresh
        fixture workspace models the design's "existing repo" population
        instead of the unreconciled partition the reconciliation gate refuses."""
        path = self._counters_path(repo_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({
                "next": next_n,
                "reconciled": True,
                "seed_source": "explicit-user",
                "seeded_at": lib.now_iso(),
            }, fh)

    def unreconcile(self, repo_id="acme-shop"):
        """Delete the seeded counters.json, restoring the unreconciled partition
        state a test needs to exercise the reconciliation refusal."""
        path = self._counters_path(repo_id)
        if os.path.exists(path):
            os.unlink(path)

    def write_settings(self, data):
        with open(os.path.join(self.repo, ".acs", "settings.json"), "w") as fh:
            json.dump(data, fh)

    def run_script(self, script, *args, stdin=None, cwd=None, env=None):
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, script)] + list(args),
            input=stdin, capture_output=True, text=True, cwd=cwd or self.repo,
            env=env,
        )

    def pre(self, skill, args_text="", cwd=None):
        payload = json.dumps({
            "cwd": cwd or self.repo, "tool_name": "Skill",
            "tool_input": {"skill": "acs:" + skill, "args": args_text},
        })
        return self.run_script("dispatch.py", "pre", stdin=payload, cwd=cwd)

    def post(self, skill, ticket, result):
        return self.run_script("post-%s.py" % skill, "--ticket", ticket,
                               stdin=json.dumps(result))

    def start(self, skill, ticket):
        return self.run_script("skill-start.py", "--skill", skill, "--ticket", ticket)

    def new_ticket(self, title, ttype, *extra):
        out = self.run_script("new-ticket.py", "--title", title, "--type", ttype, *extra)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def tdir(self, ticket):
        return lib.ticket_dir(self.ws, "acme-shop", ticket)


def load_module(script_filename, alias=None):
    """Fresh-import a hyphenated hook script by path, popping any stale cache first."""
    name = alias or script_filename
    sys.modules.pop(name, None)
    # acs_lib is a package (MAR-522): popping the facade alone leaves its
    # submodules cached, so the "fresh import" would re-bind the SAME objects.
    for cached in [n for n in sys.modules if n == "acs_lib" or n.startswith("acs_lib.")]:
        sys.modules.pop(cached, None)
    path = os.path.join(SCRIPTS, script_filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_main(mod, argv, stdin=None):
    """Drive a loaded module's main() in-process; catch SystemExit, return (code, out, err)."""
    real_argv, real_stdin = sys.argv[:], sys.stdin
    real_stdout, real_stderr = sys.stdout, sys.stderr
    sys.argv = [mod.__name__] + list(argv)
    sys.stdin = io.StringIO(stdin) if stdin is not None else real_stdin
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        try:
            mod.main()
            code = 0
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
    finally:
        sys.argv = real_argv
        sys.stdin = real_stdin
        sys.stdout = real_stdout
        sys.stderr = real_stderr
    return code, out, err


@contextlib.contextmanager
def pushd(path):
    """Temporarily os.chdir to path, restoring the original cwd even on exception."""
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def fake_gh(bin_dir, gh_body):
    """Write an executable `gh` shim under bin_dir and return a PATH-prepended env.

    gh_body is the shell script body (after the shebang) the shim runs. A
    gh_body of None simulates the binary being entirely absent: PATH is
    replaced with bin_dir alone, populated with symlinks to the tools the
    fixture actually needs (git, sh) but never gh -- so those tools stay
    resolvable no matter where a given runner has them installed, while gh
    is guaranteed unresolvable even when it shares a directory with git
    (e.g. apt's /usr/bin/gh sitting next to /usr/bin/git, where filtering
    out gh's directory would otherwise take git with it).
    """
    env = dict(os.environ)
    if gh_body is None:
        for tool in ("git", "sh"):
            real = shutil.which(tool)
            if real is not None:
                os.symlink(real, os.path.join(bin_dir, tool))
        env["PATH"] = bin_dir
        return env
    gh = os.path.join(bin_dir, "gh")
    with open(gh, "w") as fh:
        fh.write("#!/bin/sh\n" + gh_body + "\n")
    os.chmod(gh, 0o755)
    env["PATH"] = bin_dir + os.pathsep + "/usr/bin:/bin"
    return env
