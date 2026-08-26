"""cost_sampler.py — shape-agnostic statusLine cost sampling and cursor-based
cost allocation for acs.

Stdlib-only, sibling of acs_lib.py / metrics_aggregate.py.

Two responsibilities:

1. `record_cost_sample(payload)` — appends `{ts, total_cost_usd, src}` to a
   per-checkout, append-only sample log (`sessions/<ckid>-cost-samples.jsonl`,
   a sibling of the existing per-checkout pointer file). `total_cost_usd` is
   probed out of the payload by `_extract_total_cost`, shape-agnostically, so
   the sampler never depends on which of several possible statusLine payload
   shapes Claude Code actually emits (Assumption A1). No candidate match ->
   no sample written; this is not an error. The function never raises: any
   failure (uninitialized repo, malformed payload, I/O error) is swallowed,
   matching PRD G7 ("never crash") and the statusLine hook's own contract.

2. `allocate_cost(...)` — at run-finalize time, consumes the *unconsumed*
   portion of the sample log for the run's window via a per-checkout
   allocation cursor (`sessions/<ckid>-cost-cursor.json`), and apportions the
   resulting dollar delta across `role_usage`'s roles by measured token
   share. The cursor rule structurally prevents double-charging: a sample
   already consumed by one run can never again serve as another run's
   "after" (design.md SS1.3).

Role-usage / apportionment-denominator contract (this module's own decision,
since design.md leaves the hand-off shape loosely specified): `role_usage`
entries with `"role": "unattributed"` represent in-window tokens usage_reader
already excludes from its real per-skill role buckets (design.md C-8's
"drop, don't redistribute" policy). Such entries count toward the
apportionment denominator (all in-window usage) but never receive a dollar
share themselves — the fraction of the charged delta their token share
implies is dropped from `allocate_cost`'s returned `cost_usd` (the
attributed-only share of the session-window charge), and separately reported
as `excluded_cost_usd`/`excluded_token_share` on the return tuple for
callers that want to show what was dropped and why. A caller with no such
information to report simply omits the entry; nothing behaves differently
absent it.
"""

import json
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

MAX_LOG_BYTES = 64 * 1024

_TOTAL_COST_KEY_RE = re.compile(r"total_cost(_usd)?$")
_MAX_SCAN_DEPTH = 3

_TOKEN_FIELDS = ("input", "output", "cache_creation", "cache_read")
UNATTRIBUTED_ROLE = "unattributed"


# ---------------------------------------------------------------------------
# Paths — siblings of acs_lib.pointer_path, same sessions/ directory.
# ---------------------------------------------------------------------------

def cost_samples_path(workspace, repo_id, ckid):
    return os.path.join(lib.sessions_dir(workspace, repo_id), "%s-cost-samples.jsonl" % ckid)


def cost_cursor_path(workspace, repo_id, ckid):
    return os.path.join(lib.sessions_dir(workspace, repo_id), "%s-cost-cursor.json" % ckid)


# ---------------------------------------------------------------------------
# SS1.2 — shape-agnostic probe
# ---------------------------------------------------------------------------

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _recursive_scan(node, depth, prefix=""):
    """Depth-bounded (<=3) DFS for the first key matching total_cost(_usd)$ with
    a numeric value, in dict-insertion order. Returns (value, dotted_path) or None."""
    if depth > _MAX_SCAN_DEPTH or not isinstance(node, dict):
        return None
    for key, value in node.items():
        path = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(key, str) and _TOTAL_COST_KEY_RE.search(key) and _is_number(value):
            return float(value), path
        if isinstance(value, dict):
            found = _recursive_scan(value, depth + 1, path)
            if found is not None:
                return found
    return None


def _extract_total_cost(payload):
    """Probe, in order: cost.total_cost_usd, cost.total_cost, total_cost_usd,
    then a bounded recursive scan. Returns (value, src) or (None, None)."""
    if not isinstance(payload, dict):
        return None, None
    cost = payload.get("cost")
    if isinstance(cost, dict):
        value = cost.get("total_cost_usd")
        if _is_number(value):
            return float(value), "cost.total_cost_usd"
        value = cost.get("total_cost")
        if _is_number(value):
            return float(value), "cost.total_cost"
    value = payload.get("total_cost_usd")
    if _is_number(value):
        return float(value), "total_cost_usd"
    found = _recursive_scan(payload, 1)
    if found is not None:
        return found
    return None, None


# ---------------------------------------------------------------------------
# Sample log — append-only JSONL, rotated past MAX_LOG_BYTES.
# ---------------------------------------------------------------------------

def _rotate_if_needed(path):
    """Once the log exceeds MAX_LOG_BYTES, keep only the most recent lines that
    fit within half the budget -- a simple, bounded rotation (each line is
    well under 200 B, so this keeps hundreds of recent samples)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= MAX_LOG_BYTES:
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    budget = MAX_LOG_BYTES // 2
    kept, kept_bytes = [], 0
    for line in reversed(lines):
        line_bytes = len(line.encode("utf-8"))
        if kept and kept_bytes + line_bytes > budget:
            break
        kept.append(line)
        kept_bytes += line_bytes
    kept.reverse()
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".acs-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.writelines(kept)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _append_sample_line(path, sample):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample, ensure_ascii=False) + "\n")
    # 0600, matching every other acs workspace artifact's convention (this
    # file's content is the operator's cumulative AI spend) -- the default
    # umask (typically 0644) is not private enough, and this must hold from
    # the very first write, not just after the file's first rotation.
    os.chmod(path, 0o600)
    _rotate_if_needed(path)


def _read_samples(workspace, repo_id, ckid):
    path = cost_samples_path(workspace, repo_id, ckid)
    samples = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    samples.append(obj)
    except OSError:
        return []
    return samples


def read_latest_sample(workspace, repo_id, ckid):
    """Public accessor for the checkout's most recent recorded sample's
    total_cost_usd, or None when no valid sample exists yet -- the only
    piece of cost_sampler's sample log a caller outside this module (e.g.
    statusline.py's display) needs; the sample list itself stays private."""
    for sample in reversed(_read_samples(workspace, repo_id, ckid)):
        value = sample.get("total_cost_usd") if isinstance(sample, dict) else None
        if _is_number(value):
            return value
    return None


def record_cost_sample(payload):
    """Append a shape-agnostic cost sample for the checkout `payload` resolves
    to. Ticket-independent (needs only build_context(cwd)); never raises."""
    try:
        if not isinstance(payload, dict):
            return
        value, src = _extract_total_cost(payload)
        if value is None:
            return
        cwd = ((payload.get("workspace") or {}).get("current_dir")) or payload.get("cwd") or os.getcwd()
        ctx = lib.build_context(cwd)
        sample = {"ts": lib.now_iso(), "total_cost_usd": value, "src": src}
        path = cost_samples_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])
        _append_sample_line(path, sample)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# SS1.3 — cursor-based consumption rule
# ---------------------------------------------------------------------------

def _tokens(entry):
    total = 0
    for field in _TOKEN_FIELDS:
        value = entry.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += value
    return total


def _unavailable_role_usage(role_usage):
    out = []
    for entry in role_usage:
        item = dict(entry)
        item["cost_usd"] = None
        item["cost_basis"] = "unavailable"
        out.append(item)
    return out


def _unavailable_model_usage(model_usage):
    """Sibling of _unavailable_role_usage, for model_usage entries."""
    out = []
    for entry in model_usage:
        item = dict(entry)
        item["cost_usd"] = None
        item["cost_basis"] = "unavailable"
        out.append(item)
    return out


def _apportion(role_usage, delta):
    """Split `delta` across role_usage by token share, denominator = ALL
    in-window tokens (attributed + unattributed). Entries whose role is
    UNATTRIBUTED_ROLE count toward the denominator but never receive a
    dollar share; the fraction their tokens imply is returned as
    (excluded_cost_usd, excluded_token_share), computed the same
    proportional way as every attributed role's own share (delta *
    excluded_tokens / total_tokens) -- never as the subtractive complement
    of the accumulated per-role floats, which can drift marginally negative
    on an all-attributed input by float rounding, violating the schema's own
    minimum:0 constraint."""
    total_tokens = sum(_tokens(entry) for entry in role_usage)
    if total_tokens <= 0:
        return _unavailable_role_usage(role_usage), delta, 1.0

    out = []
    excluded_tokens = 0
    for entry in role_usage:
        item = dict(entry)
        tokens = _tokens(entry)
        if entry.get("role") == UNATTRIBUTED_ROLE:
            excluded_tokens += tokens
            item["cost_usd"] = None
            item["cost_basis"] = "unavailable"
        else:
            item["cost_usd"] = delta * (tokens / total_tokens)
            item["cost_basis"] = "apportioned"
        out.append(item)

    excluded_token_share = excluded_tokens / total_tokens
    excluded_cost_usd = max(0.0, delta * excluded_token_share)
    return out, excluded_cost_usd, excluded_token_share


def _apportion_models(model_usage, delta):
    """Split `delta` across model_usage by token share -- D1.2 Option A
    (design.md:173-200): the FULL delta, no unattributed exclusion, unlike
    _apportion's role-scoped split above. Denominator = all model_usage
    tokens; total_tokens <= 0 degrades every entry to unavailable, mirroring
    _apportion's own guard."""
    total_tokens = sum(_tokens(entry) for entry in model_usage)
    if total_tokens <= 0:
        return _unavailable_model_usage(model_usage)

    out = []
    for entry in model_usage:
        item = dict(entry)
        tokens = _tokens(entry)
        item["cost_usd"] = delta * (tokens / total_tokens)
        item["cost_basis"] = "apportioned"
        out.append(item)
    return out


def allocate_cost(workspace, repo_id, checkout_id, started_at, ended_at, role_usage, model_usage=None):
    """Implements SS1.3's cursor-consumption rule. `started_at` is accepted for
    the caller's own informational/logging use only -- the "before" edge for
    the delta is always the persisted cursor, never started_at.

    Returns a dict: {role_usage, model_usage, cost_usd, cost_basis,
    cost_scope, excluded_cost_usd, excluded_token_share}. `cost_scope` carries
    "session_total" on a measured charge, and doubles as the degraded reason
    ("no_unconsumed_sample_in_window" / "cost_total_reset") when cost_usd is
    None -- design.md's cost_scope enum has no dedicated reason field, and
    this reuse is this module's own documented choice.

    `role_usage`'s `cost_usd` is the ATTRIBUTED-ONLY share of the
    session-window charge -- the full delta minus `excluded_cost_usd` --
    never the raw full delta. C-8's "drop, don't redistribute" policy means
    the unattributed slice is dropped from the run's (and therefore the
    ticket's/repo's) cost, not merely reported alongside a charge that still
    includes it.

    `model_usage` is None when the `model_usage` argument was None; otherwise
    each entry's `cost_usd` is priced from the SAME delta charged to
    `role_usage`, apportioned by token share across ALL model_usage tokens --
    D1.2 Option A, no unattributed exclusion (deliberate, documented gap, not
    a bug): sum(model_usage.cost_usd) - sum(role_usage.cost_usd, attributed
    roles only) == excluded_cost_usd, whenever any tokens in the window are
    unattributed.
    """
    role_usage = [dict(entry) for entry in (role_usage or [])]
    model_usage = [dict(entry) for entry in model_usage] if model_usage is not None else None
    end_dt = lib.parse_iso(ended_at)

    cursor = lib.read_json(cost_cursor_path(workspace, repo_id, checkout_id))
    if not isinstance(cursor, dict):
        cursor = {}
    cursor_ts = lib.parse_iso(cursor.get("ts"))
    cursor_total = cursor.get("total_cost_usd")
    if not isinstance(cursor_total, (int, float)) or isinstance(cursor_total, bool):
        cursor_total = 0.0

    after, after_ts = None, None
    if end_dt is not None:
        for sample in _read_samples(workspace, repo_id, checkout_id):
            sample_ts = lib.parse_iso(sample.get("ts"))
            sample_value = sample.get("total_cost_usd")
            if sample_ts is None or not _is_number(sample_value):
                continue
            if sample_ts > end_dt:
                continue
            if after_ts is None or sample_ts > after_ts:
                after, after_ts = sample, sample_ts

    if after is None or (cursor_ts is not None and after_ts <= cursor_ts):
        return {
            "role_usage": _unavailable_role_usage(role_usage),
            "model_usage": _unavailable_model_usage(model_usage) if model_usage is not None else None,
            "cost_usd": None, "cost_basis": "unavailable",
            "cost_scope": "no_unconsumed_sample_in_window",
            "excluded_cost_usd": None, "excluded_token_share": None,
        }

    delta = float(after["total_cost_usd"]) - float(cursor_total)
    if delta < 0:
        lib.write_json(cost_cursor_path(workspace, repo_id, checkout_id),
                        {"ts": after["ts"], "total_cost_usd": after["total_cost_usd"]})
        return {
            "role_usage": _unavailable_role_usage(role_usage),
            "model_usage": _unavailable_model_usage(model_usage) if model_usage is not None else None,
            "cost_usd": None, "cost_basis": "unavailable",
            "cost_scope": "cost_total_reset",
            "excluded_cost_usd": None, "excluded_token_share": None,
        }

    role_usage_with_cost, excluded_cost_usd, excluded_token_share = _apportion(role_usage, delta)
    model_usage_with_cost = _apportion_models(model_usage, delta) if model_usage is not None else None
    lib.write_json(cost_cursor_path(workspace, repo_id, checkout_id),
                    {"ts": after["ts"], "total_cost_usd": after["total_cost_usd"]})
    attributed_cost_usd = max(0.0, delta - excluded_cost_usd)
    return {
        "role_usage": role_usage_with_cost,
        "model_usage": model_usage_with_cost,
        "cost_usd": attributed_cost_usd, "cost_basis": "measured",
        "cost_scope": "session_total",
        "excluded_cost_usd": excluded_cost_usd, "excluded_token_share": excluded_token_share,
    }
