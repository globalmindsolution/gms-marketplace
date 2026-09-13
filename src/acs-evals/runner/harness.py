"""Golden-dataset harness for the acs plugin.

Resolves the acs build under test, builds throwaway sandboxes for the
deterministic tier, and redacts run-specific values out of captured output so a
golden expectation can be compared byte for byte.

Stdlib only, Python >= 3.9 — same constraint the acs plugin itself keeps.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DATASET = os.path.join(REPO_ROOT, "dataset")
FIXTURES = os.path.join(DATASET, "fixtures")


class BuildError(Exception):
    """The acs build under test could not be resolved."""


# --------------------------------------------------------------------------
# Resolving the build under test
# --------------------------------------------------------------------------

def _plugin_version(root):
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json")) as fh:
            return json.load(fh).get("version") or "unknown"
    except (OSError, ValueError):
        return "unknown"


def _candidates():
    """Every plausible acs plugin root, in resolution order.

    ``ACS_PLUGIN_ROOT`` wins outright so a release engineer can point the suite
    at an unreleased working tree. Otherwise the *installed* build is preferred
    over a marketplace checkout, because the installed build is what a consumer
    actually runs — packaging drift between the two is a defect this dataset
    exists to catch.
    """
    env = os.environ.get("ACS_PLUGIN_ROOT")
    if env:
        yield os.path.abspath(os.path.expanduser(env))
        return
    home = os.path.expanduser("~")
    cache = os.path.join(home, ".claude", "plugins", "cache")
    if os.path.isdir(cache):
        found = []
        for marketplace in sorted(os.listdir(cache)):
            acs = os.path.join(cache, marketplace, "acs")
            if not os.path.isdir(acs):
                continue
            for version in os.listdir(acs):
                root = os.path.join(acs, version)
                if os.path.isdir(root):
                    found.append((_version_key(version), root))
        for _key, root in sorted(found, reverse=True):
            yield root
    markets = os.path.join(home, ".claude", "plugins", "marketplaces")
    if os.path.isdir(markets):
        for marketplace in sorted(os.listdir(markets)):
            root = os.path.join(markets, marketplace, "plugins", "acs")
            if os.path.isdir(root):
                yield root


def _version_key(text):
    return tuple(int(p) if p.isdigit() else -1
                 for p in re.split(r"[.\-+]", str(text).lstrip("v"))[:4])


class Build:
    """The acs plugin build the dataset is being evaluated against."""

    def __init__(self, root):
        self.root = root
        self.scripts = os.path.join(root, "hooks", "scripts")
        self.version = _plugin_version(root)
        if not os.path.isfile(os.path.join(self.scripts, "acs.py")):
            raise BuildError("no hooks/scripts/acs.py under %s" % root)

    def script(self, name):
        return os.path.join(self.scripts, name)

    def __repr__(self):
        return "<acs %s at %s>" % (self.version, self.root)


def resolve_build():
    tried = []
    for root in _candidates():
        tried.append(root)
        try:
            return Build(root)
        except BuildError:
            continue
    raise BuildError(
        "could not resolve an acs plugin build. Set ACS_PLUGIN_ROOT to a "
        "directory containing .claude-plugin/plugin.json and hooks/scripts/, "
        "or install the plugin.\nTried:\n  %s"
        % ("\n  ".join(tried) or "(nothing)"))


# --------------------------------------------------------------------------
# Sandbox profiles
# --------------------------------------------------------------------------

#: Settings every sandbox is seeded with. Pinned here rather than left to
#: /acs:setup's defaults so a settings-default change shows up as a dataset
#: diff instead of silently moving every expectation.
SETTINGS = {
    "ticket_prefix": "TKT",
    "workspace_path": "../ws",
    "test_coverage_percent": 90,
    "merge_strategy": "squash",
}

PROFILES = ("bare", "seeded", "ticketed", "epic", "app", "app-ticketed")

#: Settings for the fixture-app profiles: a real coverage floor the gate can
#: bite on, a payments path under high_stakes_paths so the stakes trigger can
#: fire, and the fixture's own test command.
APP_SETTINGS = dict(SETTINGS, test_coverage_percent=85,
                    high_stakes_paths=["orders/payments/**"],
                    tests={"command": "python3 -m coverage run -m unittest discover -s tests "
                                      "&& python3 -m coverage report --fail-under=$ACS_COVERAGE"})

APP_TICKET = {
    "title": "Let the API confirm and pay an order, charging through the gateway with one retry",
    "description": ("Today the HTTP API can only create a draft order; confirming and paying are CLI-only "
                    "(docs/api.md says so). Add POST /orders/<id>/confirm and POST /orders/<id>/pay to "
                    "orders/api.py, backed by OrderService.confirm/pay. When the gateway raises a timeout "
                    "during pay, retry the charge exactly once with a fresh idempotency key that includes "
                    "an attempt number, so a retried charge can never double-charge (see docs/adr/0002). "
                    "Update docs/api.md and the data-flow section of docs/architecture.md to match. "
                    "Keep the coverage floor in .coveragerc green."),
}

_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "acs evals",
    "GIT_AUTHOR_EMAIL": "evals@example.invalid",
    "GIT_COMMITTER_NAME": "acs evals",
    "GIT_COMMITTER_EMAIL": "evals@example.invalid",
}


class Sandbox:
    """A throwaway consumer repo plus an outside-the-repo acs workspace.

    Profiles stack: ``bare`` is a git repo with settings and nothing else;
    ``seeded`` adds the reconciled ``counters.json`` that lets the first
    allocation mint ``TKT-1``; ``ticketed`` mints that task; ``epic`` mints a
    needs_design epic instead. ``app`` is the fixture app (runner/fixture_app.py:
    a real codebase with tests, docs, a payments path and 32 commits of history)
    plus the reconciled counter; ``app-ticketed`` mints a task on it whose
    implementation touches the API, the payments path and the docs.
    """

    def __init__(self, build, profile="bare", keep=False):
        if profile not in PROFILES:
            raise ValueError("unknown profile %r" % profile)
        self.build = build
        self.profile = profile
        self.keep = keep
        self.base = tempfile.mkdtemp(prefix="acs-golden-")
        self.repo = os.path.join(self.base, "repo")
        self.ws = os.path.join(self.base, "ws")
        self.partition = os.path.join(self.ws, "repo")
        self.ticket_id = None
        self._build()

    # -- construction ----------------------------------------------------
    def _git(self, *args):
        subprocess.run(("git",) + args, cwd=self.repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       env=dict(os.environ, **_GIT_ENV))

    def _build(self):
        if self.profile in ("app", "app-ticketed"):
            return self._build_app()
        os.makedirs(os.path.join(self.repo, ".acs"))
        os.makedirs(self.partition)
        with open(os.path.join(self.repo, ".acs", "settings.json"), "w") as fh:
            json.dump(SETTINGS, fh, indent=2, sort_keys=True)
        with open(os.path.join(self.repo, "README.md"), "w") as fh:
            fh.write("# sandbox\n")
        self._git("init", "-q", "-b", "main", ".")
        self._git("add", "-A")
        self._git("commit", "-qm", "seed")
        if self.profile == "bare":
            return
        # MAR-402's fixture seam: without a reconciled counter the first
        # allocation refuses rather than restarting the sequence at 1.
        with open(os.path.join(self.partition, "counters.json"), "w") as fh:
            json.dump({"reconciled": True, "seed_source": "explicit-user",
                       "seeded_at": "2026-01-01T00:00:00Z", "next": 1},
                      fh, indent=2)
        if self.profile == "ticketed":
            self.ticket_id = self._mint("Add user login", "task",
                                        "--size", "small", "--stakes", "low")
        elif self.profile == "epic":
            self.ticket_id = self._mint("Checkout revamp", "epic",
                                        "--size", "large", "--stakes", "high")

    def _build_app(self):
        from fixture_app import build as build_fixture  # runner/ is on sys.path
        build_fixture(self.repo)
        os.makedirs(self.partition)
        os.makedirs(os.path.join(self.repo, ".acs"))
        with open(os.path.join(self.repo, ".acs", "settings.json"), "w") as fh:
            json.dump(APP_SETTINGS, fh, indent=2, sort_keys=True)
        self._git("add", "-A")
        self._git("commit", "-qm", "Configure acs")
        with open(os.path.join(self.partition, "counters.json"), "w") as fh:
            json.dump({"reconciled": True, "seed_source": "explicit-user",
                       "seeded_at": "2026-01-01T00:00:00Z", "next": 1},
                      fh, indent=2)
        if self.profile == "app-ticketed":
            self.ticket_id = self._mint(APP_TICKET["title"], "task",
                                        "--description", APP_TICKET["description"],
                                        "--size", "small", "--stakes", "normal")

    def _mint(self, title, kind, *extra):
        out = self.run("new-ticket.py", "--title", title, "--type", kind, *extra)
        if out["exit_code"] != 0:
            raise BuildError("could not mint a %s ticket in the %s profile: %s"
                             % (kind, self.profile, out["stderr"] or out["stdout"]))
        return json.loads(out["stdout"])["ticket_id"]

    # -- driving ---------------------------------------------------------
    def run(self, script, *argv, stdin=None):
        """Run one acs helper CLI inside the sandbox repo.

        `input=""` rather than `input=None` when a case supplies no stdin: hook
        scripts read their payload from stdin, and with `input=None` the child
        INHERITS the runner's stdin and blocks forever waiting for a payload
        that never arrives — which is exactly what happens when the suite runs
        detached from a terminal. An empty string closes it, so the script sees
        EOF and takes its no-payload path, which is what these cases exercise.

        The timeout is a backstop for the same failure mode: a hung child must
        fail one case, not the run.
        """
        proc = subprocess.run(
            ["python3", self.build.script(script)] + [str(a) for a in argv],
            cwd=self.repo, input=stdin if stdin is not None else "",
            capture_output=True, text=True, timeout=120,
            env=dict(os.environ, **_GIT_ENV))
        return {"exit_code": proc.returncode,
                "stdout": proc.stdout, "stderr": proc.stderr}

    def shell(self, command):
        """Run one shell command in the sandbox repo — a dataset setup step.

        Setup steps come verbatim from the curated dataset (a ticket branch
        with a committed change, say) and run once before a probe's first
        session; a failing step raises with its stderr, never silently.
        """
        subprocess.run(command, shell=True, cwd=self.repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, env=dict(os.environ, **_GIT_ENV))

    def ticket_dir(self, ticket_id=None):
        return os.path.join(self.partition, ticket_id or self.ticket_id or "")

    def write(self, base, rel, content):
        """Write one seed file under ``repo``, ``ws`` or ``ticket``."""
        root = {"repo": self.repo, "ws": self.partition,
                "ticket": self.ticket_dir()}[base]
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            if isinstance(content, str):
                fh.write(content)
            else:
                json.dump(content, fh, indent=2, sort_keys=True)
        return path

    # -- lifecycle -------------------------------------------------------
    def close(self):
        if not self.keep:
            shutil.rmtree(self.base, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------

#: Run-specific values that would otherwise make every expectation unstable.
#: Order matters: the workspace lives beside the repo, so the longer path is
#: replaced first. Note there is deliberately NO pid redaction: a pid only
#: reaches stdout by way of a fixture we wrote, and substituting a non-numeric
#: token into `"pid": 4242` would leave the captured JSON unparseable.
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?")
_CHECKOUT = re.compile(r"\brepo-[0-9a-f]{8}\b")


def redact(text, sb):
    """Replace this run's paths, ids and clock readings with stable tokens."""
    if not text:
        return text
    # The build root is redacted too, and it matters most for `--record`: a
    # surface that echoes it (`acs context` reports `plugin_root`) would
    # otherwise bake this machine's absolute install path into a golden, and
    # the recorded case would then pass only on the machine that recorded it.
    for real, token in ((sb.partition, "<WS>"), (sb.ws, "<WSROOT>"),
                        (sb.repo, "<REPO>"), (sb.base, "<BASE>"),
                        (sb.build.root, "<PLUGIN>")):
        text = text.replace(real, token)
        real_resolved = os.path.realpath(real)
        if real_resolved != real:
            text = text.replace(real_resolved, token)
    text = _TIMESTAMP.sub("<TS>", text)
    text = _CHECKOUT.sub("<CHECKOUT_ID>", text)
    return text
