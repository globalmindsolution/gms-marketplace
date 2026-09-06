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
WORKFLOW_SKILLS = ["create-ticket", "code", "docs-sync", "create-pr", "merge-pr", "standardize-project"]
PLANNING_SKILLS = ["create-design"]
HOOKED_SKILLS = PRODUCT_SKILLS + WORKFLOW_SKILLS + PLANNING_SKILLS
UNHOOKED_SKILLS = ["setup", "ship", "handoff", "update", "install-hooks", "metrics", "usage", "test", "release", "create-docs"]

# Mirrors pipeline-state.schema.json's steps.propertyNames.enum, in enum
# order. Unused within this ticket -- a later ticket is its first consumer;
# a schema-mirror equality test is what stops this list from drifting.
PIPELINE_STEP_ORDER = ["create-prd", "create-architecture", "create-project", "create-quality",
                        "create-operations", "create-principles", "create-standards",
                        "create-requirements", "create-ticket", "create-design", "code", "test",
                        "docs-sync", "create-pr", "merge-pr"]

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

# D7-A: v1 fans out exactly this pair. A third doc-bootstrap skill becomes
# fan-out-eligible by being added here AND to DOC_BOOTSTRAP_DEPENDENCIES AND
# DOC_BOOTSTRAP_SETTINGS_KEY AND DOC_BOOTSTRAP_SENTINEL (fanout_batches also
# indexes those two, unguarded) -- all four are data changes, no code change.
DOC_BOOTSTRAP_FANOUT_V1 = ("create-quality", "create-operations")
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
