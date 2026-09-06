"""acs_lib.setup_helpers — extracted from acs_lib.py by MAR-522."""


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
import claude_code_adapter as cc  # noqa: E402

from ._common import DELIVERY_TICKET_TITLES, DOC_BOOTSTRAP_DEPENDENCIES, DOC_BOOTSTRAP_FANOUT_V1, DOC_BOOTSTRAP_SENTINEL, DOC_BOOTSTRAP_SETTINGS_KEY
from .settings import enforcement_value
from .repo import ticket_id_from_text



def doc_set_present_on_disk(checkout_root, settings, skill):
    """D4.2(a): a doc-bootstrap skill's doc set counts as shipped only when its
    own first output file exists at its configured path -- a populated but
    otherwise-produced directory does not count (fails toward re-bootstrapping)."""
    base = settings.get(DOC_BOOTSTRAP_SETTINGS_KEY[skill])
    if not base:
        return False
    return os.path.isfile(os.path.join(checkout_root, base, DOC_BOOTSTRAP_SENTINEL[skill]))


def _soft_peers(candidate, eligible):
    """AC-5: the soft edge is an UNDIRECTED batching constraint -- an edge
    counts whether the candidate declares it or the peer does, so the
    invariant cannot be broken by re-ordering the table or by declaring the
    edge on the other side."""
    declared = set(DOC_BOOTSTRAP_DEPENDENCIES[candidate]["soft"])
    reverse = {peer for peer in eligible
               if candidate in DOC_BOOTSTRAP_DEPENDENCIES[peer]["soft"]}
    return (declared | reverse) & set(eligible)


def fanout_batches(settings, tickets_index, checkout_root, candidates=None):
    """D4.1 eligibility (configured, not-shipped, no open delivery ticket, hard
    deps clear) plus D4.3 batching: group eligible candidates so a soft
    dependency edge never shares a batch with its eligible peer, in either
    direction. candidates defaults to the declared v1 fan-out set
    (DOC_BOOTSTRAP_FANOUT_V1); an explicit candidates argument exists so the
    general-case (future N-way) semantics stay unit-testable even though only
    the v1 pair is fanned out today. Names not present in
    DOC_BOOTSTRAP_DEPENDENCIES are skipped, never raised."""
    tickets = (tickets_index or {}).get("tickets") or {}

    def _open_ticket(skill):
        title = DELIVERY_TICKET_TITLES.get(skill)
        return any(
            isinstance(t, dict) and t.get("title") == title
            and t.get("type") == "task" and t.get("status") != "done"
            for t in tickets.values()
        )

    eligible = []
    for candidate in (DOC_BOOTSTRAP_FANOUT_V1 if candidates is None else candidates):
        if candidate not in DOC_BOOTSTRAP_DEPENDENCIES:
            continue  # unknown/non-doc-bootstrap name: never eligible, never raises
        deps = DOC_BOOTSTRAP_DEPENDENCIES[candidate]
        configured = settings.get(DOC_BOOTSTRAP_SETTINGS_KEY[candidate]) is not None
        not_shipped = not doc_set_present_on_disk(checkout_root, settings, candidate)
        not_open = not _open_ticket(candidate)
        hard_deps_clear = all(
            settings.get(DOC_BOOTSTRAP_SETTINGS_KEY[dep]) is None
            or doc_set_present_on_disk(checkout_root, settings, dep)
            for dep in deps["hard"]
        )
        if configured and not_shipped and not_open and hard_deps_clear:
            eligible.append(candidate)

    batches = []
    for candidate in eligible:
        soft_peers = _soft_peers(candidate, eligible)
        for batch in batches:
            if not soft_peers & set(batch):
                batch.append(candidate)
                break
        else:
            batches.append([candidate])
    return batches


# /acs:create-docs's only argument. Matched only as a whole flag ("--for",
# "--for=", or a bare trailing "--for") so an unrelated --for-* flag never
# triggers it.
_FANOUT_FOR_RE = re.compile(r"--for(?:=|\s|$)")


def parse_fanout_for_arg(args_text):
    """Parse /acs:create-docs's `--for <skill>[,<skill>...]` argument against
    the declared v1 fan-out gate (D7-A).

    Returns (candidates, rejected):
      candidates is None when no --for flag is present -- the caller hands that
        straight to fanout_batches, which then applies its own
        DOC_BOOTSTRAP_FANOUT_V1 default;
      otherwise candidates is the requested names that ARE in
        DOC_BOOTSTRAP_FANOUT_V1 (order-preserving, de-duplicated) and rejected
        is every other requested name -- an unknown name and a real but non-v1
        doc-bootstrap skill (e.g. create-principles) alike. A rejected name is
        reported ("not in v1's fan-out set") and never fanned out; it is
        deliberately kept OUT of fanout_batches's candidates, whose own
        contract is to skip unknown names silently (see above)."""
    text = args_text or ""
    m = _FANOUT_FOR_RE.search(text)
    if not m:
        return (None, [])
    candidates, rejected = [], []
    for name in text[m.end():].replace(",", " ").split():
        if name.startswith("-"):
            break
        bucket = candidates if name in DOC_BOOTSTRAP_FANOUT_V1 else rejected
        if name not in bucket:
            bucket.append(name)
    return (candidates, rejected)


# ---------------------------------------------------------------------------
# CLAUDE.md managed-block helpers (written/refreshed by /acs:setup). Pure string
# functions so the splice and the placeholder substitution are unit-testable.
# The markers MUST match templates/CLAUDE.acs.md exactly.
# ---------------------------------------------------------------------------

ACS_BLOCK_BEGIN = "<!-- BEGIN acs-managed (do not edit inside this block) -->"
ACS_BLOCK_END = "<!-- END acs-managed -->"


def render_managed_block(template_text, ticket_prefix, exempt_label):
    """Substitute the {ticket_prefix} and {exempt_label} placeholders in the
    CLAUDE.acs.md template text. Pure str.replace so a literal '{' elsewhere in
    the template is never treated as a format field."""
    return (template_text
            .replace("{ticket_prefix}", ticket_prefix or "")
            .replace("{exempt_label}", exempt_label or ""))


def _managed_body(text):
    """Reduce *text* to the guidance body that belongs INSIDE a managed block.

    The writer (upsert_managed_block) owns the markers, so a body must never
    carry its own — otherwise wrapping doubles them. This reducer makes that
    impossible regardless of what the caller/template supplies:
      * if a full BEGIN..END pair is present, take the slice strictly between the
        FIRST begin and the LAST end (dropping any maintainer header above BEGIN
        and the markers themselves);
      * then remove any stray marker strings that survived (unpaired or nested);
      * finally trim surrounding blank lines so wrapping is deterministic.
    Pure function; no I/O."""
    begin = text.find(ACS_BLOCK_BEGIN)
    end = text.rfind(ACS_BLOCK_END)
    if begin != -1 and end != -1 and end > begin:
        text = text[begin + len(ACS_BLOCK_BEGIN):end]
    text = text.replace(ACS_BLOCK_BEGIN, "").replace(ACS_BLOCK_END, "")
    return text.strip("\n")


def managed_body_from_template(template_text, ticket_prefix, exempt_label):
    """Render CLAUDE.acs.md down to the guidance BODY only, ready to wrap.

    Substitutes the two placeholders (render_managed_block) and then extracts the
    text strictly between the template's own ACS_BLOCK_BEGIN/END markers — the
    maintainer header and the markers themselves are dropped, so upsert_managed_block
    injects exactly one clean marker pair around just the guidance. A template with
    no markers degrades gracefully to the whole (substituted) text. Pure function."""
    return _managed_body(render_managed_block(template_text, ticket_prefix, exempt_label))


def _strip_stray_markers(text):
    """Remove any lone acs marker LINES from *text* (belt-and-suspenders for the
    content SURROUNDING the managed span in upsert_managed_block).

    The acs markers are acs-owned — user-authored CLAUDE.md content is never
    expected to contain them — so this only ever deletes stray markers a prior
    buggy write left OUTSIDE the span (an orphaned END before the block, a lone
    BEGIN after it). Returns *text* unchanged byte-for-byte when it holds no
    marker, so well-formed surrounding content is never perturbed. Pure."""
    if ACS_BLOCK_BEGIN not in text and ACS_BLOCK_END not in text:
        return text
    kept = [ln for ln in text.split("\n")
            if ln.strip() != ACS_BLOCK_BEGIN and ln.strip() != ACS_BLOCK_END]
    text = "\n".join(kept)
    # scrub any inline residue (a marker not alone on its line) as well
    return text.replace(ACS_BLOCK_BEGIN, "").replace(ACS_BLOCK_END, "")


def upsert_managed_block(existing_text, block_body):
    """Return existing_text with the acs-managed block inserted or replaced.

    The block is ACS_BLOCK_BEGIN + newline + block_body + newline + ACS_BLOCK_END,
    where block_body is first reduced via _managed_body so it can never re-introduce
    a marker (no caller — however buggy — can cause doubling).

    When markers are already present, replace the inclusive span from the FIRST
    BEGIN to the LAST END (rfind), preserving everything before and after byte for
    byte. Using rfind self-heals a legacy DOUBLED block: the whole nested mess
    collapses to one clean pair rather than leaving an orphaned outer END, and any
    stray marker left in the surrounding text (an orphan END before the span or a
    lone BEGIN after it) is scrubbed via _strip_stray_markers so no orphan can
    survive a heal. When no markers are present, append the block separated by
    exactly one blank line; an empty (or marker-only) existing_text yields just the
    block. Idempotent: a second call with the same block_body yields output
    byte-identical to the first (and self-healing is itself idempotent). Every
    return path ends with exactly one trailing newline."""
    block = "%s\n%s\n%s" % (ACS_BLOCK_BEGIN, _managed_body(block_body), ACS_BLOCK_END)
    begin = existing_text.find(ACS_BLOCK_BEGIN)
    end = existing_text.rfind(ACS_BLOCK_END)
    if begin != -1 and end != -1 and end > begin:
        before = _strip_stray_markers(existing_text[:begin])
        after = _strip_stray_markers(existing_text[end + len(ACS_BLOCK_END):])
        result = before + block + after
    else:
        # No full pair: drop any lone orphan marker, then append after existing content.
        stripped = _strip_stray_markers(existing_text)
        if not stripped.strip():
            result = block
        else:
            # Append, separated from preceding content by exactly one blank line.
            result = stripped.rstrip("\n") + "\n\n" + block
    return result.rstrip("\n") + "\n"


def managed_block_is_malformed(text):
    """True when *text* does NOT contain exactly one acs-managed marker pair.

    Pure detector used by /acs:setup Step 7e to decide whether the consumer
    CLAUDE.md needs REPAIR before the refresh: a doubled block (2+ BEGIN and/or
    END) or an orphaned marker (unequal counts, a lone BEGIN or END) all read as
    malformed. Note a file with NO markers is likewise "not exactly one pair" and
    so reports True — callers distinguish an ABSENT block (a normal first write)
    from a CORRUPTED one by additionally checking that at least one marker is
    present (Step 7e only reports a repair when a marker was already there)."""
    return text.count(ACS_BLOCK_BEGIN) != 1 or text.count(ACS_BLOCK_END) != 1


# ---------------------------------------------------------------------------
# Exempt non-ticket /acs:merge-pr argument classifier (MAR-9, clarification C-3).
# Pure: given the raw arg string it decides ticket-backed vs exempt-pr and parses
# the PR ref for the exempt case. The caller supplies ticket_resolves (whether a
# pointer/branch already yields a ticket) to disambiguate a bare integer.
# ---------------------------------------------------------------------------

_PR_URL_RE = re.compile(r"/pull/(\d+)\b")
_PR_FLAG_RE = re.compile(r"--pr[=\s]+(\d+)\b")
_PR_HASH_RE = re.compile(r"#(\d+)\b")
_BARE_INT_RE = re.compile(r"^\s*(\d+)\s*$")


def classify_merge_pr_arg(args_text, ticket_prefix=None, ticket_resolves=False):
    """Classify a /acs:merge-pr argument string.

    Returns (kind, pr_ref):
      ("exempt-pr", "<n>") for the non-ticket merge forms — an explicit
        --pr <n> flag, a #<n> token, a PR URL (.../pull/<n>), or a bare integer
        that is NOT a ticket id AND no ticket already resolves from pointer/branch.
      ("ticket", None) for a ticket-id-shaped token (the ticket gate always wins),
        a bare integer when a ticket resolves (prefer ticket when ambiguous), and
        any empty/unrecognized input (let the existing ticket gate produce its
        existing error). Per clarification C-3."""
    text = args_text or ""
    # A ticket-id-shaped token always wins — preserves AC-8.
    if ticket_id_from_text(text, ticket_prefix):
        return ("ticket", None)
    # Explicit forms are ALWAYS exempt (C-3), regardless of ticket_resolves.
    m = _PR_FLAG_RE.search(text)
    if m:
        return ("exempt-pr", m.group(1))
    m = _PR_URL_RE.search(text)
    if m:
        return ("exempt-pr", m.group(1))
    m = _PR_HASH_RE.search(text)
    if m:
        return ("exempt-pr", m.group(1))
    # A bare integer is exempt only when no ticket resolves (C-3: prefer ticket).
    m = _BARE_INT_RE.match(text)
    if m and not ticket_resolves:
        return ("exempt-pr", m.group(1))
    return ("ticket", None)


def _pr_labels(pr):
    """gh pr view --json labels yields [{"name": ...}, ...]; normalize to names."""
    out = []
    for label in pr.get("labels") or []:
        if isinstance(label, dict) and label.get("name"):
            out.append(label["name"])
        elif isinstance(label, str):
            out.append(label)
    return out


def validate_exempt_pr(pr, settings):
    """Validate a PR (the parsed `gh pr view` JSON object) for the exempt-pr merge
    path. Returns (ok, message): ok True means the PR is a sanctioned exempt PR;
    ok False means refuse, and `message` is the user-facing reason (already
    carrying the /acs:merge-pr <ticket> redirect when the PR looks ticket-backed).
    Mirrors templates/ci/check-conventions.py is_exempt (label first, then branch
    glob) and the C-3 ticket-backed refusal."""
    branch = pr.get("headRefName") or ""
    labels = _pr_labels(pr)
    exempt_label = enforcement_value(settings, "exempt_label")
    require_label = enforcement_value(settings, "require_label")
    exempt_branches = enforcement_value(settings, "exempt_branches") or []
    prefix = (settings or {}).get("ticket_prefix")

    # OPEN + not draft.
    state = (pr.get("state") or "").upper()
    if state != "OPEN":
        return (False, "PR #%s is %s, not OPEN — only an open PR can be merged."
                % (pr.get("number"), state or "in an unknown state"))
    if pr.get("isDraft"):
        return (False, "PR #%s is a draft — mark it ready for review before merging."
                % pr.get("number"))

    # Ticket-backed → refuse + redirect (C-3). Checked before the exempt grant so
    # a PR that is BOTH ticket-labelled and exempt-labelled still routes to the
    # ticket path.
    embedded = ticket_id_from_text(branch, prefix)
    if require_label in labels or embedded:
        target = embedded or "<TICKET-ID>"
        return (False,
                "PR #%s looks ticket-backed (%s) — merge it through the ticket "
                "path: /acs:merge-pr %s, not the exempt --pr path."
                % (pr.get("number"),
                   "carries the '%s' label" % require_label if require_label in labels
                   else "branch '%s' embeds %s" % (branch, embedded),
                   target))

    # Exempt grant: label first, then branch glob.
    if exempt_label and exempt_label in labels:
        return (True, "label '%s' present" % exempt_label)
    for pattern in exempt_branches:
        if branch and fnmatch.fnmatch(branch, pattern):
            return (True, "branch matches exempt pattern '%s'" % pattern)

    return (False,
            "PR #%s is not a sanctioned exempt PR — label it '%s' (or use an "
            "exempt branch) for the --pr path, or merge it through a ticket: "
            "/acs:merge-pr <TICKET-ID>." % (pr.get("number"), exempt_label))


def tracker_cli_warning(settings):
    provider = (settings.get("tracker") or {}).get("provider", "local")
    if provider == "github" and not shutil.which("gh"):
        return "tracker.provider is 'github' but the gh CLI is not installed — tracker sync will fail."
    if provider == "jira" and not shutil.which("acli"):
        return "tracker.provider is 'jira' but the acli CLI is not installed — tracker sync will fail."
    return None


# Every external tool the full acs workflow touches. kind: required (no pipeline
# without it), recommended (a major capability needs it), optional (graceful
# fallback). gh/acli are bumped to required by tracker provider. /setup's Step 0b
# preflight reports these and offers to install the missing ones.
TOOLCHAIN = [
    {"name": "git", "kind": "required",
     "why": "version control — every skill operates on the repo and its branches",
     "install": {"macos": "xcode-select --install", "debian": "apt-get install -y git"}},
    {"name": "python3", "kind": "required",
     "why": "runs the hooks, gates, convention checker, and helper CLIs (stdlib only)",
     "install": {"macos": "brew install python", "debian": "apt-get install -y python3"}},
    {"name": "gh", "kind": "recommended",
     "why": "create-pr / merge-pr, labels, branch protection; required for github tracker sync",
     "install": {"macos": "brew install gh",
                 "debian": "see https://github.com/cli/cli/blob/trunk/docs/install_linux.md"}},
    {"name": "pre-commit", "kind": "recommended",
     "why": "shared, tracked local convention hooks (commit-msg + pre-push)",
     "install": {"macos": "brew install pre-commit",
                 "any": "pipx install pre-commit   # or: pip install --user pre-commit"}},
    {"name": "xmllint", "kind": "optional",
     "why": "full XSD validation of acs XML messages (structural fallback otherwise)",
     "install": {"macos": "preinstalled with libxml2", "debian": "apt-get install -y libxml2-utils"}},
    {"name": "acli", "kind": "optional",
     "why": "Jira tracker sync (only when tracker.provider = jira)",
     "install": {"any": "see https://developer.atlassian.com/cloud/acli/"}},
]


def _tool_version(name):
    """Best-effort one-line version string for an installed tool, or None."""
    try:
        out = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        lines = (out.stdout or out.stderr or "").splitlines()
        return lines[0].strip() if lines else None
    except (OSError, subprocess.SubprocessError):
        return None


def check_toolchain(settings=None):
    """Status of every tool the full acs workflow uses (for /setup's preflight).

    Returns a list of dicts: name, kind (required|recommended|optional), present
    (bool), version (str|None), why, install (platform -> command). A tool's kind
    is bumped to 'required' when settings make it mandatory (tracker provider).
    """
    provider = ((settings or {}).get("tracker") or {}).get("provider", "local")
    rows = []
    for spec in TOOLCHAIN:
        kind = spec["kind"]
        if spec["name"] == "gh" and provider == "github":
            kind = "required"
        if spec["name"] == "acli" and provider == "jira":
            kind = "required"
        present = shutil.which(spec["name"]) is not None
        rows.append({
            "name": spec["name"], "kind": kind, "present": present,
            "version": _tool_version(spec["name"]) if present else None,
            "why": spec["why"], "install": spec["install"],
        })
    return rows


def missing_tools(settings=None, kinds=("required", "recommended"), rows=None):
    """Names of not-present tools in the given kinds — what /setup should offer to install.

    `rows` reuses an already-probed check_toolchain() result. Without it, a
    caller wanting both the table and the missing list either probes every tool
    twice — each probe a subprocess with a 5s timeout — or re-implements this
    predicate, and the two answers to "which tools are missing?" drift apart."""
    return [r["name"] for r in (check_toolchain(settings) if rows is None else rows)
            if r["kind"] in kinds and not r["present"]]
