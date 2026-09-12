"""acs_lib._common — extracted from acs_lib.py by MAR-522."""


import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
# The scripts dir, one level up from this package. Done ONCE, here: the
# facade imports _common first, so every sibling import in the package
# (claude_code_adapter in repo, markdown_headings in lanes) resolves
# without each module pushing its own duplicate entry onto sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import claude_code_adapter as cc  # noqa: E402



# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PRODUCT_SKILLS = ["create-prd", "create-architecture", "create-project", "create-quality", "create-operations", "create-principles", "create-standards", "create-requirements"]
# The ticket-flow skills. The five Build/Test additions (analyze-ticket,
# create-impl-plan, create-api-contract, create-test-docs, create-e2e-tests)
# join here rather than in a sixth list: they are ticket-scoped like the rest,
# so `flow = "product" if skill in PRODUCT_SKILLS else "ticket"` stays right,
# and HOOKED_SKILLS keeps its three-way shape. Their ORDER lives in
# workflows/ship.yaml, never in this list -- what a list position buys is the
# metrics funnel's column order, nothing else.
WORKFLOW_SKILLS = ["create-ticket", "analyze-ticket", "create-impl-plan", "create-api-contract",
                   "create-test-docs", "code", "docs-sync", "create-e2e-tests", "create-pr",
                   "merge-pr", "standardize-project"]
PLANNING_SKILLS = ["create-design"]
HOOKED_SKILLS = PRODUCT_SKILLS + WORKFLOW_SKILLS + PLANNING_SKILLS
# `run-e2e-tests` is the Test-phase suite runner (today's `test`, renamed) and
# stays UNHOOKED: it writes no run entry and spawns no reflection triad, so
# dispatch.py passes it through and skill-start.py cannot select it. `test` is
# retained beside it for one release as the alias directory that forwards
# there (workflows/phases.yaml `aliases`), so an existing /acs:test invocation
# keeps working.
# `project` is the design-phase fold's umbrella over create-project and
# standardize-project: like create-docs it owns no agents, no gate and no hook
# scripts -- it picks a mode (project_mode, below) and invokes that leg's own
# Start as a Skill-tool call -- so it is UNHOOKED and must never join
# HOOKED_SKILLS (dispatch.py would then look for a pre-project.py that does
# not exist, and skill-start.py would offer --skill project, which allocates
# nothing).
UNHOOKED_SKILLS = ["setup", "ship", "handoff", "update", "install-hooks", "metrics", "usage",
                   "test", "run-e2e-tests", "release", "create-docs", "project"]

# Mirrors pipeline-state.schema.json's steps.propertyNames.enum, in enum
# order. A schema-mirror equality test is what stops this list from drifting.
# `test` is kept beside `run-e2e-tests` so a ledger written before the rename
# still validates and still orders sensibly.
PIPELINE_STEP_ORDER = ["create-prd", "create-architecture", "create-project", "create-quality",
                        "create-operations", "create-principles", "create-standards",
                        "create-requirements", "create-ticket", "create-design", "analyze-ticket",
                        "create-impl-plan", "create-api-contract", "create-test-docs", "code",
                        "docs-sync", "create-e2e-tests", "test", "run-e2e-tests", "create-pr",
                        "merge-pr"]

# Explicit override for observed attributionSkill values (transcript records
# carry "acs:<value>") that do not literally match a skill name once the
# "acs:" prefix is stripped -- e.g. the setup skill's own attribution value
# is observed as "acs:init" or "acs:initialize", not "acs:setup" (its two
# historical names, from before MAR-184 and MAR-1 respectively). Covers both
# HOOKED_SKILLS and UNHOOKED_SKILLS, since unhooked skills (ship, setup)
# are observed as attributionSkill values even though they write no run entry.
ATTRIBUTION_SKILL_MAP = {"init": "setup", "initialize": "setup"}

RUN_STATUSES = ["in_progress", "completed", "failed", "interrupted", "handed_off"]
TICKET_TYPES = ["epic", "story", "task"]
TICKET_STATUSES = ["open", "in_progress", "in_review", "done"]
PRIORITIES = ["critical", "high", "medium", "low"]

PRODUCT_TICKET_TITLES = {
    "create-prd": "Product definition (PRD)",
    "create-architecture": "Product architecture doc set",
    "create-project": "Project scaffold",
    "create-quality": "Product quality doc set",
    "create-operations": "Product operations doc set",
    "create-principles": "Product principles doc set",
    "create-standards": "Product standards doc set",
    "create-requirements": "Product requirements doc set",
}

# Delivery-ticket predicate: PRODUCT_SKILLS plus standardize-project (D5 Option B —
# standardize-project gets allocate/in_review/pr_created semantics WITHOUT joining
# PRODUCT_SKILLS's doc-set-producer semantics, which stays unchanged).
DELIVERY_TICKET_SKILLS = PRODUCT_SKILLS + ["standardize-project"]
DELIVERY_TICKET_TITLES = dict(PRODUCT_TICKET_TITLES,
                               **{"standardize-project": "Brownfield project standardization"})

# Declared (never inferred) doc-bootstrap dependency edges for the fan-out
# eligibility predicate below. "hard" gates eligibility outright; "soft" only
# excludes a candidate from sharing a fan-out BATCH with an eligible peer it
# is tagged against -- it never makes the candidate ineligible on its own.
# No hard edge exists today: every list below is empty, stated explicitly.
DOC_BOOTSTRAP_DEPENDENCIES = {
    "create-quality": {"hard": [], "soft": []},
    "create-operations": {"hard": [], "soft": []},
    "create-principles": {"hard": [], "soft": []},
    "create-standards": {"hard": [], "soft": ["create-principles"]},
}

# Explicit skill -> settings-key map for the doc-bootstrap skills, resolved
# by lookup rather than string-built from the skill name.
DOC_BOOTSTRAP_SETTINGS_KEY = {
    "create-quality": "quality_path",
    "create-operations": "operations_path",
    "create-principles": "principles_path",
    "create-standards": "standards_path",
}

# Each doc-bootstrap skill's own first output file (its output contract),
# used as the D4.2(a) sentinel for "has this doc set actually shipped."
DOC_BOOTSTRAP_SENTINEL = {
    "create-quality": "test-strategy.md",
    "create-operations": "release-process.md",
    "create-principles": "principles.md",
    "create-standards": "coding-standards.md",
}

# The declared fan-out set: every doc-bootstrap leg /acs:create-docs may fan
# out. D7-A shipped this as the create-quality + create-operations pair; the
# design-phase consolidation made /acs:create-docs <set|all> the only
# user-facing doc command, so the set is now all four legs -- ONE constant
# edit, because DOC_BOOTSTRAP_DEPENDENCIES, DOC_BOOTSTRAP_SETTINGS_KEY and
# DOC_BOOTSTRAP_SENTINEL already covered four. A fifth doc-bootstrap skill
# becomes fan-out-eligible by being added here AND to those three
# (fanout_batches indexes them unguarded) -- all data changes, no code change.
DOC_BOOTSTRAP_FANOUT_V1 = ("create-quality", "create-operations",
                           "create-principles", "create-standards")
"""Iteration cap keyed by verify depth (AC-3: light=1; AC-4: full=3).

Used by the /acs:code coordinator to bound the reflection loop:
  depth = verify_depth(ticket.lane, ticket.stakes)
  ceiling = VERIFY_ITERATION_CAP[depth]
"""
"""Canonical lane ordering from lowest to highest rigor (ADR 0030).

Index 0 = TRIVIAL (lowest) … index 3 = COMPLEX (highest).
Used by lane_rank() for comparisons only; never use this list to produce
a lane value — derive_lane() is the single authoritative producer (ADR 0030:56-61).
"""
"""The six planner headings code/SKILL.md's Plan step requires on every lane."""
"""The five spec-authoring-fold sections, in the order structure_lint's
--ordered lint checks them (code/SKILL.md's fold contract)."""
"""The two mandatory verbatim clauses the fold requires (code/SKILL.md:398-401)."""


# ---------------------------------------------------------------------------
# /acs:project mode detection (the design-phase entry-point fold)
# ---------------------------------------------------------------------------
#
# /acs:project is an unhooked umbrella over two internal legs -- create-project
# (greenfield scaffold) and standardize-project (brownfield audit) -- and picks
# between them from DECLARED data plus a disk read, exactly as create-docs picks
# its fan-out set from the DOC_BOOTSTRAP_* tables above. The mechanism is the
# same settings-path + sentinel-file pair, read through the same presence
# primitive (`setup_helpers._sentinel_present`): each row below names one piece
# of evidence that this repo ALREADY has a project, its settings key resolves
# the directory that evidence lives in (None = the checkout root itself), and
# its sentinel is the file whose existence IS the evidence.
#
# Every shipped row is checkout-root-relative because a build manifest lives at
# the repo root and acs has no source-layout settings key; the settings-key
# column is kept because it is the shared mechanism, so evidence under a
# configured path stays a data row rather than a code change.
#
# The rows are the build manifests setup_wizard.TEST_COMMAND_CANDIDATES already
# declares as stack markers (widened to the JVM pair), plus two of
# create-project's own scaffold outputs -- its pre-commit config and its
# coverage config -- which are the evidence on a repo that keeps its sources
# without a package manifest. CI workflow files are deliberately NOT rows even
# though standardize-project audits them: /acs:setup writes acs-conventions.yml
# / acs-tests.yml / acs-e2e.yml onto a repo with no source at all, which would
# misread a greenfield repo as brownfield. The pre-commit row is safe from that
# same objection -- /acs:install-hooks only ever EDITS a .pre-commit-config.yaml
# that is already present (install-hooks/SKILL.md's Step 3 branches to raw git
# hooks when it is absent), and /acs:setup never writes one.
#
# Adding a marker (another stack's manifest, another scaffold output) is a row
# in both maps -- a data change, never an edit to project/SKILL.md.
PROJECT_MODE_SETTINGS_KEY = {
    "python-packaging": None,
    "python-setup": None,
    "node-packaging": None,
    "go-modules": None,
    "rust-packaging": None,
    "maven-build": None,
    "gradle-build": None,
    "gradle-kotlin-build": None,
    "pre-commit-config": None,
    "coverage-config": None,
}

PROJECT_MODE_SENTINEL = {
    "python-packaging": "pyproject.toml",
    "python-setup": "setup.py",
    "node-packaging": "package.json",
    "go-modules": "go.mod",
    "rust-packaging": "Cargo.toml",
    "maven-build": "pom.xml",
    "gradle-build": "build.gradle",
    "gradle-kotlin-build": "build.gradle.kts",
    "pre-commit-config": ".pre-commit-config.yaml",
    "coverage-config": ".coveragerc",
}

#: The two modes /acs:project dispatches on, in escalation order: no evidence
#: at all -> bootstrap; any evidence -> standardize.
PROJECT_MODES = ("bootstrap", "standardize")

#: Which internal leg each mode dispatches to. The umbrella invokes it as a
#: genuine Skill-tool call, so that leg's own hooks and gate fire unchanged.
PROJECT_MODE_LEG = {
    "bootstrap": "create-project",
    "standardize": "standardize-project",
}


TICKET_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]*-\d+)\b")


class GateError(Exception):
    """Raised when a pre-hook gate fails; message is user-facing (stderr, exit 2)."""


class ReconciliationRequired(GateError):
    """Raised by allocate_ticket_id when a (repo_id, prefix) partition has never
    allocated an id; carries the ranked local-evidence proposal for the caller
    to render as actionable stderr."""

    def __init__(self, prefix, repo_id, observed_max, seed_source, proposed_next):
        self.prefix = prefix
        self.repo_id = repo_id
        self.observed_max = observed_max
        self.seed_source = seed_source
        self.proposed_next = proposed_next
        super().__init__(self.render("--seed-next <n>"))

    def render(self, seed_command):
        """Pure: the three-part actionable stderr (blocked+why / local evidence
        as a FLOOR / the exact recovery command); seed_command is the caller's
        own command string so each CLI prints something a user can paste."""
        lines = [
            "blocked — workspace partition %s has never allocated a ticket id and "
            "carries no reconciliation marker, so allocating would restart the %s "
            "sequence at 1 and may collide with ids already used in this repo's "
            "history." % (self.repo_id, self.prefix)
        ]
        if self.observed_max is not None:
            lines.append(
                "Local evidence suggests the highest existing id is %s-%d (source: %s). "
                "Local evidence is a FLOOR, not the truth — the tracker may hold higher ids."
                % (self.prefix, self.observed_max, self.seed_source)
            )
        else:
            lines.append(
                "No local evidence found for the %s sequence." % self.prefix
            )
        lines.append("Confirm the first id to mint:  %s" % seed_command)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#: An ISO-8601 *instant*: a date AND a time, optional fractional seconds,
#: optional `Z` or numeric offset. A bare date does not match, deliberately --
#: see parse_iso. The `T` separator is required; a space-separated or basic
#: ("20260620T090000Z") form is not an instant acs or Claude Code ever writes.
_ISO_INSTANT = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"T(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<frac>\d+))?"
    r"(?P<tz>Z|[+-]\d{2}:?\d{2})?$"
)


def parse_iso(value):
    """Parse an ISO-8601 instant as an aware UTC datetime, else None.

    acs writes the strict `%Y-%m-%dT%H:%M:%SZ` form, but this also reads
    timestamps produced elsewhere -- Claude Code transcript records above all,
    where fractional seconds and explicit offsets both occur. Rejecting those
    silently drops every such usage record.

    Two invariants bound that tolerance:

    * A bare date returns None. ADR 0020 requires it: the panel-7 lead/cycle
      callers read None as "no data" and degrade, and a date parsed as midnight
      would render a real-looking number instead. `metrics_aggregate` carries
      the same directive in code.
    * Acceptance does not vary by interpreter. `datetime.fromisoformat` gained
      most of this leniency in CPython 3.11, so leaning on it would accept
      records on 3.12 that are silently dropped on 3.9 -- this repo's support
      floor, and the exact failure this function exists to prevent. The regex
      and strptime below behave identically on both.

    A value with no timezone is read as UTC; an explicit offset is normalised
    to UTC.
    """
    if not isinstance(value, str):
        return None
    match = _ISO_INSTANT.match(value.strip())
    if not match:
        return None
    # strptime's %f accepts 1-6 digits: pad a shorter fraction, truncate a
    # longer one (sub-microsecond precision is below anything acs measures).
    frac = (match.group("frac") or "").ljust(6, "0")[:6]
    try:
        parsed = datetime.strptime(
            "%sT%s.%s" % (match.group("date"), match.group("time"), frac),
            "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        return None  # a well-shaped but impossible date, e.g. 2026-02-30
    tz = match.group("tz")
    if not tz or tz == "Z":
        return parsed.replace(tzinfo=timezone.utc)
    digits = tz[1:].replace(":", "")
    offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    if tz[0] == "-":
        offset = -offset
    return (parsed - offset).replace(tzinfo=timezone.utc)


def slugify(text, max_len=40):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].rstrip("-") or "change"


def read_json(path):
    """Tolerant read: returns None when the file is missing or corrupt (reported, never raises)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write("acs: warning: unreadable/corrupt JSON at %s (%s) — treated as absent\n" % (path, exc))
        return None


def write_json(path, data):
    """Atomic, pretty-printed write (the workspace doubles as a human-readable audit trail)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".acs-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_text(path, text):
    """Atomic text write, for the same reason write_json is atomic.

    A bare `open(path, "w")` truncates first, so a crash or a hook timeout
    mid-write leaves a file that is neither the old content nor the new one.
    That matters most for the artifacts written precisely so something survives
    a failure -- `handoff-context.md` is written because compaction is about to
    destroy the conversation, and truncating it is the one outcome worse than
    not writing it at all."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".acs-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def deep_merge(base, override):
    """Recursive per-key merge; override wins on leaves."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _git(args, cwd):
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def plugin_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ---------------------------------------------------------------------------
# Hook chatter
# ---------------------------------------------------------------------------
#
# Shared by lifecycle and filemap (MAR-572 split them apart); they live here
# rather than in either one so neither has to import the other for a logger.

def _warn(message):
    sys.stderr.write("acs: %s\n" % message)


def _note(message):
    """Progress chatter, only under $ACS_DEBUG — a hook that prints on every
    subagent turn is noise in the transcript."""
    if os.environ.get("ACS_DEBUG"):
        sys.stderr.write("acs: %s\n" % message)
