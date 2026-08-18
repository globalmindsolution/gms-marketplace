"""acs behavioral eval harness — acs-specific layer under evals/acs/ (M2 epic E1.1).

This module is the acs eval harness.  It lives under ``evals/acs/`` (relocated
from the evals/ root in MAR-33) and contains only acs-specific symbols.  It is
imported by the acs scenario runner (``evals/acs/run_evals.py``) and by the 5
acs scenario files via a ``sys.path`` insertion that the runner performs at
module scope.

``SOURCE_SCRIPTS``, ``installed_scripts_dir()``, and ``Sandbox`` are
acs-scoped — they resolve the acs plugin build and drive the acs dispatch hook.
Skills-only plugins (e.g. tabp) use their own per-plugin runner and never
import this module.

``Check`` is plugin-agnostic and may be imported by any plugin's scenario
runner, though skills-only plugins are free to reimplement it.

Where ``tests/`` exercises the *deterministic* layer (hooks, gates, state) by
driving the Python scripts directly and runs in PR CI without ``claude``, this
harness exercises the *agentic* layer: it runs real ``claude -p`` sessions that
invoke acs skills end to end and asserts on the **workspace artifacts** they
produce (the JSON state the pipeline itself trusts) — never on prose output.

It is deliberately NOT under ``tests/``: PR CI runs ``python3 -m unittest
discover -s tests``, and these scenarios cost money, need network + an
authenticated ``claude`` CLI, and are non-deterministic.  They belong to the
nightly job (E1.4), not the PR gate.

Two tiers of scenario, by cost:

  * **free**  — no ``claude``. Drives the *installed* dispatch hook through
    pipeline states and asserts exit codes/messages. Catches packaging drift
    in the shipped build (the unittest suite only sees the source tree).
  * **paid**  — spawns ``claude -p``. Asserts on the artifacts the agents write.

Run:  python3 evals/run_evals.py            # free tier only (default, via dispatcher)
      python3 evals/acs/run_evals.py        # directly
      python3 evals/run_evals.py --paid     # include claude-driven scenarios
      python3 evals/run_evals.py --list
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

# REPO_ROOT: dirname x3 from evals/acs/harness.py reaches the repo root.
# (dirname x2 would stop at evals/, making SOURCE_SCRIPTS resolve to
# evals/plugins/acs/hooks/scripts — a nonexistent path that breaks the free tier.)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# acs-specific: SOURCE_SCRIPTS and installed_scripts_dir() are the acs cache-
# resolution seam.  They are deliberately NOT generalised to arbitrary plugins.
SOURCE_SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")


# --------------------------------------------------------------------------- #
# Locating the plugin under test
# --------------------------------------------------------------------------- #

def installed_scripts_dir():
    """Resolve the hook-scripts dir of the *installed* acs build, newest version.

    Marketplace-name-agnostic: scans every `<marketplace>/acs/<version>/` under
    the plugin cache and picks the newest version, so it keeps working across a
    marketplace rename (e.g. gms-plugins -> gms-marketplace). Falls back to the
    in-repo source tree when no install is present, so the free tier still runs
    in a checkout that never installed the plugin. The chosen path is what every
    gate check executes, so an eval against the installed build is faithful to
    what consumers actually load.

    Set `ACS_EVAL_SOURCE=1` to force the in-repo source tree regardless of what
    is installed — used by the pre-commit hook so it tests the code being
    committed, not a stale installed build.
    """
    if os.environ.get("ACS_EVAL_SOURCE"):
        return SOURCE_SCRIPTS, "source"
    cache = os.path.expanduser("~/.claude/plugins/cache")
    candidates = []  # (version, scripts_dir)
    for scripts in glob.glob(os.path.join(cache, "*", "acs", "*",
                                          "hooks", "scripts")):
        if os.path.isdir(scripts):
            candidates.append((scripts.split(os.sep)[-3], scripts))
    if candidates:
        version, scripts = max(candidates, key=lambda c: _version_key(c[0]))
        return scripts, version
    return SOURCE_SCRIPTS, "source"


def _version_key(v):
    parts = []
    for chunk in v.split("."):
        parts.append(int(chunk) if chunk.isdigit() else -1)
    return parts


# --------------------------------------------------------------------------- #
# Forge-tier target config: resolution + non-production guards
# --------------------------------------------------------------------------- #

class ForgeConfigError(RuntimeError):
    """Raised when the forge-tier target repo is unconfigured or fails a guard."""


FORGE_MARKER = ".acs-eval-target"
FORGE_NAME_RE = re.compile(r"^acs-eval(-[a-z0-9][a-z0-9-]*)?$")
FORGE_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def resolve_forge_target(env=None, repo_root=REPO_ROOT):
    """Resolve 'owner/name' for the forge tier and run its pre-clone guards.

    Precedence: ACS_FORGE_REPO overrides evals.forge_repo, read from
    <repo_root>/.acs/settings.json then .acs/settings.local.json (local
    wins). Guards, in order: G-a unconfigured/malformed, G-b naming
    convention, G-c never this repo's own remote. G-d (marker file) runs
    post-clone via check_forge_marker() -- there is no checkout yet here.
    """
    env = os.environ if env is None else env
    target = env.get("ACS_FORGE_REPO") or _forge_repo_from_settings(repo_root)

    if not target or not FORGE_REPO_RE.match(target):
        raise ForgeConfigError(
            "no forge target configured: set the ACS_FORGE_REPO env var or "
            "evals.forge_repo in .acs/settings.json to 'owner/name'"
        )

    _apply_target_guards(target, repo_root)
    return target


def _apply_target_guards(owner_name, repo_root=REPO_ROOT):
    """G-b (naming) + G-c (never-self): shared by every source of a target."""
    _, _, name = owner_name.partition("/")
    if not FORGE_NAME_RE.match(name):
        raise ForgeConfigError(
            "forge target %r fails the non-production naming guard: its repo "
            "name must match %s" % (owner_name, FORGE_NAME_RE.pattern)
        )

    self_target = _self_owner_name(repo_root)
    if self_target and owner_name.lower() == self_target.lower():
        raise ForgeConfigError(
            "forge target %r must not be this repo's own remote (%s)"
            % (owner_name, self_target)
        )


def check_forge_marker(checkout_root):
    """G-d: the cloned checkout must commit the FORGE_MARKER opt-in file."""
    if not os.path.isfile(os.path.join(checkout_root, FORGE_MARKER)):
        raise ForgeConfigError(
            "forge target checkout at %s is missing the required %s marker "
            "file; the target repo must commit it as an explicit "
            "non-production opt-in" % (checkout_root, FORGE_MARKER)
        )


def _forge_repo_from_settings(repo_root):
    """Read evals.forge_repo from project settings, then local (local wins)."""
    forge_repo = None
    for rel in (".acs/settings.json", ".acs/settings.local.json"):
        path = os.path.join(repo_root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        evals = data.get("evals") or {}
        if "forge_repo" in evals:
            forge_repo = evals["forge_repo"]
    return forge_repo


def _self_owner_name(repo_root):
    """This checkout's own 'owner/name', or None with no readable remote."""
    proc = subprocess.run(
        ["git", "-C", repo_root, "config", "--get", "remote.origin.url"],
        capture_output=True, text=True)
    url = proc.stdout.strip()
    return _owner_name_from_remote_url(url) if url else None


def _owner_name_from_remote_url(url):
    """Parse 'owner/name' out of a git remote URL (https, ssh, or scp form)."""
    path = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)
    path = re.sub(r"^[^/@]+@", "", path)
    path = path.replace(":", "/")
    path = re.sub(r"\.git/?$", "", path)
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2:
        return "%s/%s" % (segments[-2], segments[-1])
    return None


# --------------------------------------------------------------------------- #
# Sandbox: a throwaway consumer repo + workspace + valid .acs settings
# --------------------------------------------------------------------------- #

class Sandbox:
    """A throwaway consumer repo + outside-the-repo workspace.

    Use as a context manager so the temp dirs are always cleaned up::

        with Sandbox(prefix="TKT", slug="shop") as sb:
            sb.gate("create-ticket")          # free gate check
            sb.run_skill("/acs:create-ticket Add X")   # paid

    By default the settings are pre-seeded (the skill-under-test is isolated
    from `/acs:initialize`). Pass ``init=False`` to start uninitialized — e.g. to
    eval `/acs:initialize` itself, or assert the "run /acs:initialize first" gate.
    """

    def __init__(self, prefix="EVAL", slug="sandbox", init=True, keep=False,
                 coverage=90, tracker="local"):
        self.prefix = prefix
        self.slug = slug
        self._init = init
        self.keep = keep or os.environ.get("ACS_EVAL_KEEP") == "1"
        self.coverage = coverage
        self.tracker = tracker
        self.scripts, self.build = installed_scripts_dir()
        # Scrub inherited GIT_* vars (GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, …):
        # when the harness runs inside a git hook (pre-commit), git exports them
        # and they would override `git -C <sandbox>`, making every subprocess
        # operate on the OUTER repo instead of the throwaway sandbox.
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_")}

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-eval-")
        # Override HOME so sandbox git processes do not pick up the user global
        # .gitignore (which may ignore .acs/, blocking git add .acs/settings.json).
        self.env["HOME"] = self.tmp
        self.repo = os.path.join(self.tmp, self.slug)
        self.ws = os.path.join(self.tmp, "workspace")
        os.makedirs(self.repo)
        os.makedirs(self.ws)
        self._git("init", "-q")
        # A stable remote makes the workspace repo-id deterministic.
        self._git("remote", "add", "origin",
                  "https://github.com/example/%s.git" % self.slug)
        self._git("config", "user.email", "eval@example.com")
        self._git("config", "user.name", "eval")
        with open(os.path.join(self.repo, "app.py"), "w") as fh:
            fh.write('def health():\n    return "ok"\n')
        self._git("add", "-A")
        self._git("commit", "-qm", "seed")
        if self._init:
            self._seed_settings()
        # Baseline = seed + committed acs config, so changed_lines() later
        # measures only the feature diff (settings.json is committed in real
        # repos; settings.local.json stays gitignored).
        self.seed_sha = subprocess.run(
            ["git", "-C", self.repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, env=self.env).stdout.strip()
        return self

    def __exit__(self, *exc):
        if not self.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)
        else:
            sys.stderr.write("[harness] kept sandbox: %s\n" % self.tmp)
        return False

    # -- setup helpers ----------------------------------------------------- #

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args], check=True,
                       capture_output=True, env=self.env)

    def _seed_settings(self):
        os.makedirs(os.path.join(self.repo, ".acs"))
        self._write(".acs/settings.json", {
            "ticket_prefix": self.prefix,
            "test_coverage_percent": self.coverage,
            "merge_strategy": "squash",
            "tracker": {"provider": self.tracker},
        })
        self._write(".acs/settings.local.json", {"workspace_path": self.ws})
        with open(os.path.join(self.repo, ".gitignore"), "a") as fh:
            fh.write(".acs/settings.local.json\n")
        # Commit the shared config (the gitignored local file stays untracked).
        self._git("add", ".acs/settings.json", ".gitignore")
        self._git("commit", "-qm", "acs config")

    def _write(self, rel, data):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")

    # -- deterministic seeding via the installed helper CLIs -------------- #
    #
    # These let a scenario fast-forward the pipeline to a known state without
    # spending `claude` — e.g. seed "ready for /acs:code" so a single paid
    # session can be asserted on. Same scripts the skills themselves invoke.

    def run_script(self, script, *args, stdin=None):
        return subprocess.run(
            [sys.executable, os.path.join(self.scripts, script)] + list(args),
            input=stdin, capture_output=True, text=True, cwd=self.repo,
            env=self.env)

    def mint_ticket(self, title, ttype="task", needs_design=False, parent=None):
        extra = ["--needs-design", "true" if needs_design else "false"]
        if parent:
            extra += ["--parent", parent]
        out = self.run_script("new-ticket.py", "--title", title, "--type", ttype,
                              *extra)
        if out.returncode != 0:
            raise AssertionError("new-ticket failed: %s" % out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def start_run(self, skill, ticket):
        out = self.run_script("skill-start.py", "--skill", skill, "--ticket", ticket)
        if out.returncode != 0:
            raise AssertionError("skill-start %s failed: %s" % (skill, out.stderr))
        return out

    def complete_run(self, skill, ticket, result=None):
        out = self.run_script("post-%s.py" % skill, "--ticket", ticket,
                              stdin=json.dumps(result or {"status": "completed"}))
        if out.returncode != 0:
            raise AssertionError("post-%s failed: %s" % (skill, out.stderr))
        return out

    def write_repo_file(self, rel, content):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    # -- free tier: the real installed gate ------------------------------- #

    def gate(self, skill, args=""):
        """Run the installed PreToolUse dispatcher for `/acs:<skill>`.

        Returns (exit_code, stderr). exit 2 == blocked; the message explains
        what must run first. This is the exact path Claude Code takes when the
        Skill tool is about to launch an acs skill — no `claude` needed.
        """
        payload = json.dumps({
            "cwd": self.repo,
            "tool_name": "Skill",
            "tool_input": {"skill": "acs:" + skill, "args": args},
        })
        proc = subprocess.run(
            [sys.executable, os.path.join(self.scripts, "dispatch.py"), "pre"],
            input=payload, capture_output=True, text=True, cwd=self.repo,
            env=self.env,
        )
        return proc.returncode, (proc.stderr or "").strip()

    def session_end(self):
        """Run the installed SessionEnd hook for this checkout.

        Finalizes any run this checkout left in_progress as `interrupted` and
        releases the ticket lock — the abnormal-ending safety net. Returns
        (exit_code, stderr).
        """
        proc = subprocess.run(
            [sys.executable, os.path.join(self.scripts, "dispatch.py"),
             "session-end"],
            input=json.dumps({"cwd": self.repo}), capture_output=True,
            text=True, cwd=self.repo, env=self.env,
        )
        return proc.returncode, (proc.stderr or "").strip()

    def changed_lines(self):
        """Total added+deleted lines in the repo since the seed commit.

        Stages everything first so committed, uncommitted, and untracked
        changes all count — the same diff size a PR off the seed would show
        (the G4 ≤ ~400-line check, measured without needing a forge)."""
        self._git("add", "-A")
        out = subprocess.run(
            ["git", "-C", self.repo, "diff", "--numstat", "--cached",
             self.seed_sha], capture_output=True, text=True, env=self.env).stdout
        total = 0
        for line in out.splitlines():
            cols = line.split("\t")
            if len(cols) >= 2:
                total += sum(int(c) for c in cols[:2] if c.isdigit())
        return total

    # -- paid tier: a real claude session --------------------------------- #

    def run_skill(self, prompt, allowed_tools=("Bash", "Read", "Write", "Edit",
                                               "Glob", "Grep", "Task",
                                               "TodoWrite", "Skill"),
                  timeout=1800):
        """Drive a headless `claude -p` session in the sandbox repo.

        timeout defaults to 1800s (30 min): a full code TDD cycle (plan →
        execute → verify, up to 3 iterations, writing tests + impl + coverage)
        can run well past 15 min locally.

        Returns a dict: {ok, is_error, result, cost_usd, num_turns, raw}.
        Uses `--output-format json` for a single parseable envelope. The
        caller asserts on workspace artifacts afterwards, not on `result`.
        """
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "json",
            "--permission-mode", "acceptEdits",
            "--allowedTools", " ".join(allowed_tools),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=self.repo, timeout=timeout, env=self.env)
        out = {"ok": proc.returncode == 0, "is_error": None, "result": "",
               "cost_usd": None, "num_turns": None, "raw": proc.stdout,
               "stderr": proc.stderr, "returncode": proc.returncode}
        try:
            env = json.loads(proc.stdout)
            out["is_error"] = env.get("is_error")
            out["result"] = env.get("result", "")
            out["cost_usd"] = env.get("total_cost_usd")
            out["num_turns"] = env.get("num_turns")
            out["ok"] = proc.returncode == 0 and not env.get("is_error")
        except (json.JSONDecodeError, TypeError):
            out["ok"] = False
        return out

    def trigger(self, request, allow=("Skill",), timeout=120):
        """Return the first skill the model picks for a natural-language request.

        Drives `claude -p <request>` with stream-json and only the `Skill` tool
        allowed, and returns the `skill` of the first `Skill` tool_use (e.g.
        "acs:create-ticket"), or None if no skill was invoked before the model
        stopped or `timeout` elapsed. This is the description-trigger test
        (E1.2): does the right skill fire for a request? The process is killed
        the instant the first Skill call appears, so each probe costs only the
        time-to-route — the skill body never executes.
        """
        cmd = [
            "claude", "-p", request,
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits",
            "--allowedTools", " ".join(allow),
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True,
                                cwd=self.repo, env=self.env)
        found = None
        deadline = time.time() + timeout
        try:
            for line in proc.stdout:
                if time.time() > deadline:
                    break
                try:
                    ev = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if ev.get("type") != "assistant":
                    continue
                for block in ev.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use" and block.get("name") == "Skill":
                        found = (block.get("input") or {}).get("skill")
                        break
                if found:
                    break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        return found

    # -- artifact assertions ---------------------------------------------- #

    def partition_root(self):
        """The single <workspace>/<repo-id>/ dir created by the pipeline."""
        subdirs = [d for d in os.listdir(self.ws)
                   if os.path.isdir(os.path.join(self.ws, d))]
        if len(subdirs) != 1:
            raise AssertionError(
                "expected exactly one repo partition under %s, found %r"
                % (self.ws, subdirs))
        return os.path.join(self.ws, subdirs[0])

    def repo_json(self, name):
        """Load a repo-level workspace JSON (tickets-index/counters/metrics)."""
        return self._load(os.path.join(self.partition_root(), name))

    def ticket_json(self, ticket, name):
        """Load a ticket-partition JSON (ticket.json/pipeline-state.json/…)."""
        return self._load(os.path.join(self.partition_root(), ticket, name))

    def ticket_path(self, ticket, *rel):
        return os.path.join(self.partition_root(), ticket, *rel)

    def _load(self, path):
        if not os.path.isfile(path):
            raise AssertionError("expected artifact missing: %s" % path)
        with open(path) as fh:
            return json.load(fh)


# --------------------------------------------------------------------------- #
# ForgeSandbox: real target-repo checkout, ephemeral run branch, teardown
# --------------------------------------------------------------------------- #

def _partition_id_from_remote(remote_url):
    """Mirror acs_lib.repo_partition_id's owner-name derivation for a remote
    URL, without importing acs_lib (harness stays stdlib-only)."""
    path = remote_url
    path = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", path)
    path = re.sub(r"^[^/@]+@", "", path)
    path = path.replace(":", "/")
    path = re.sub(r"\.git/?$", "", path)
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2:
        raw = "%s-%s" % (segments[-2], segments[-1])
    elif segments:
        raw = segments[-1]
    else:
        return None
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw)


class ForgeSandbox:
    """A real checkout of the forge-tier target repo, on its own run branch.

    Use as a context manager: ``__enter__`` resolves/guards/clones the target,
    wipes this run's workspace partition, and seeds a throwaway-prefixed
    ``.acs/settings.json`` on an ephemeral run branch; ``__exit__`` is a
    best-effort teardown (closes the run's PRs, deletes its remote branches,
    verifies the default branch is unchanged) that never raises — failures
    land in ``self.teardown_errors`` instead::

        with ForgeSandbox() as sb:
            ...  # drive the real pipeline against sb.repo
        assert not sb.teardown_errors
    """

    def __init__(self, slug=None, keep=False, remote_url=None, workspace=None,
                 coverage=90):
        self.slug = slug
        self.keep = keep or os.environ.get("ACS_EVAL_KEEP") == "1"
        self.remote_url = remote_url
        self._workspace_override = workspace
        self.coverage = coverage
        self.teardown_errors = []
        # Scrub inherited GIT_* vars for the same reason Sandbox does: a git
        # hook (e.g. pre-commit) exports GIT_DIR/GIT_WORK_TREE/etc, which would
        # otherwise redirect every subprocess here onto the OUTER repo.
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_")}

    def __enter__(self):
        self._resolve_target()
        self.run_id = uuid.uuid4().hex[:8].upper()
        self.prefix = "FORGE" + self.run_id
        self._clone()
        try:
            check_forge_marker(self.repo)
        except ForgeConfigError:
            shutil.rmtree(self.tmp, ignore_errors=True)
            raise
        self._capture_baseline()
        self._create_run_branch()
        self.ws = (self._workspace_override or os.environ.get("ACS_FORGE_WORKSPACE")
                  or os.path.join(self.tmp, "workspace"))
        os.makedirs(self.ws, exist_ok=True)
        self._wipe_partition()
        self._seed_settings()
        return self

    def __exit__(self, exc_type, exc, tb):
        for step in (self._close_open_prs, self._delete_remaining_remote_branches,
                    self._verify_default_branch_unchanged):
            try:
                step()
            except Exception as err:  # best-effort teardown: never raise
                self.teardown_errors.append("%s: %s" % (step.__name__, err))
        if self.keep:
            sys.stderr.write("[harness] kept forge checkout: %s\n" % self.tmp)
        else:
            shutil.rmtree(self.tmp, ignore_errors=True)
        return False

    # -- __enter__ steps ---------------------------------------------------- #

    def _resolve_target(self):
        """AC-2 resolve + guard, unless remote_url overrides it for a test."""
        if self.remote_url is not None:
            owner_name = _owner_name_from_remote_url(self.remote_url) or self.remote_url
            _apply_target_guards(owner_name)
            self.owner_name = owner_name
            self.clone_url = self.remote_url
        else:
            self.owner_name = resolve_forge_target()
            self.clone_url = "https://github.com/%s.git" % self.owner_name

    def _clone(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-forge-")
        # Unlike Sandbox, this class talks to a real authenticated GitHub
        # remote: keep the real HOME so git/gh credential resolution works.
        name = self.slug or self.owner_name.rsplit("/", 1)[-1]
        self.repo = os.path.join(self.tmp, name)
        proc = subprocess.run(["git", "clone", "-q", self.clone_url, self.repo],
                              capture_output=True, text=True, env=self.env)
        if proc.returncode != 0:
            shutil.rmtree(self.tmp, ignore_errors=True)
            raise ForgeConfigError("failed to clone forge target %r: %s"
                                   % (self.clone_url, proc.stderr.strip()))
        self._git("config", "user.email", "acs-forge@example.com")
        self._git("config", "user.name", "acs-forge")

    def _capture_baseline(self):
        """Default branch + its SHA, so teardown can assert no drift."""
        proc = subprocess.run(
            ["git", "-C", self.repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True, env=self.env)
        branch = proc.stdout.strip()
        if proc.returncode == 0 and branch.startswith("origin/"):
            branch = branch[len("origin/"):]
        else:
            branch = "main"
        self.default_branch = branch
        self.baseline_sha = subprocess.run(
            ["git", "-C", self.repo, "rev-parse", "origin/%s" % branch],
            capture_output=True, text=True, env=self.env).stdout.strip()

    def _create_run_branch(self):
        self.run_branch = "acs-eval/%s" % self.run_id
        self._git("checkout", "-q", "-b", self.run_branch,
                  "origin/%s" % self.default_branch)

    def _wipe_partition(self):
        """AC-4: unconditionally wipe this target's workspace partition."""
        remote = subprocess.run(
            ["git", "-C", self.repo, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, env=self.env).stdout.strip()
        self.partition_id = _partition_id_from_remote(remote) if remote else None
        if self.partition_id:
            shutil.rmtree(os.path.join(self.ws, self.partition_id), ignore_errors=True)

    def _seed_settings(self):
        """AC-5: seed the throwaway prefix; mirrors Sandbox._seed_settings."""
        os.makedirs(os.path.join(self.repo, ".acs"), exist_ok=True)
        self._write(".acs/settings.json", {
            "ticket_prefix": self.prefix,
            "test_coverage_percent": self.coverage,
            "merge_strategy": "squash",
            "tracker": {"provider": "github"},
        })
        self._write(".acs/settings.local.json", {"workspace_path": self.ws})
        with open(os.path.join(self.repo, ".gitignore"), "a") as fh:
            fh.write(".acs/settings.local.json\n")
        self._git("add", ".acs/settings.json", ".gitignore")
        self._git("commit", "-q", "-m", "acs forge config")

    # -- __exit__ steps ------------------------------------------------------ #

    def _close_open_prs(self):
        proc = self._gh("pr", "list", "--repo", self.owner_name, "--state", "open",
                        "--json", "number,headRefName")
        if proc.returncode != 0:
            self.teardown_errors.append(
                "gh pr list failed: %s" % (proc.stderr or proc.stdout).strip())
            return
        try:
            prs = json.loads(proc.stdout or "[]")
        except ValueError:
            self.teardown_errors.append(
                "gh pr list returned unparseable JSON: %r" % proc.stdout)
            return
        for pr in prs:
            head = pr.get("headRefName") or ""
            if self.run_id not in head:
                continue
            close = self._gh("pr", "close", str(pr.get("number")), "--repo",
                             self.owner_name, "--delete-branch")
            if close.returncode != 0:
                self.teardown_errors.append(
                    "gh pr close %s failed: %s"
                    % (pr.get("number"), (close.stderr or close.stdout).strip()))

    def _delete_remaining_remote_branches(self):
        proc = subprocess.run(["git", "-C", self.repo, "ls-remote", "--heads", "origin"],
                              capture_output=True, text=True, env=self.env)
        if proc.returncode != 0:
            self.teardown_errors.append(
                "git ls-remote --heads origin failed: %s" % proc.stderr.strip())
            return
        for line in proc.stdout.splitlines():
            _, _, ref = line.partition("\t")
            if not ref.startswith("refs/heads/"):
                continue
            branch = ref[len("refs/heads/"):]
            if self.run_id not in branch:
                continue
            delete = subprocess.run(["git", "-C", self.repo, "push", "origin",
                                     "--delete", branch],
                                    capture_output=True, text=True, env=self.env)
            if delete.returncode != 0:
                self.teardown_errors.append(
                    "git push origin --delete %s failed: %s" % (branch, delete.stderr.strip()))

    def _verify_default_branch_unchanged(self):
        proc = subprocess.run(
            ["git", "-C", self.repo, "ls-remote", "origin",
             "refs/heads/%s" % self.default_branch],
            capture_output=True, text=True, env=self.env)
        if proc.returncode != 0:
            self.teardown_errors.append(
                "could not verify default branch %r sha: %s"
                % (self.default_branch, proc.stderr.strip()))
            return
        sha, _, _ = proc.stdout.strip().partition("\t")
        if sha != self.baseline_sha:
            if not sha:
                self.teardown_errors.append(
                    "default branch %r no longer exists on the remote (was %s) "
                    "-- never auto-repaired, a human must investigate"
                    % (self.default_branch, self.baseline_sha))
            else:
                self.teardown_errors.append(
                    "default branch %r drifted: baseline=%s now=%s -- never auto-repaired, "
                    "a human must investigate"
                    % (self.default_branch, self.baseline_sha, sha))

    # -- seams ---------------------------------------------------------------- #

    def _gh(self, *args):
        """gh invocation seam; tests subclass/override this, never the network."""
        return subprocess.run(["gh", *args], capture_output=True, text=True, env=self.env)

    def _git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args], check=True,
                       capture_output=True, env=self.env)

    def _write(self, rel, data):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")


# --------------------------------------------------------------------------- #
# Scenario result + assertion helpers
# --------------------------------------------------------------------------- #

class Check:
    """Collects named assertions for one scenario into a pass/fail report."""

    def __init__(self, name):
        self.name = name
        self.results = []   # (label, ok, detail)

    def ok(self, label, condition, detail=""):
        self.results.append((label, bool(condition), detail))
        return bool(condition)

    def eq(self, label, got, want):
        return self.ok(label, got == want, "got=%r want=%r" % (got, want))

    @property
    def passed(self):
        return all(ok for _, ok, _ in self.results)

    def lines(self):
        for label, ok, detail in self.results:
            mark = "PASS" if ok else "FAIL"
            tail = "" if ok else ("  (%s)" % detail if detail else "")
            yield "    [%s] %s%s" % (mark, label, tail)
