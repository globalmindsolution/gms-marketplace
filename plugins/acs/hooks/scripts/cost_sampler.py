"""cost_sampler.py — shape-agnostic statusLine cost sampling and cursor-based
cost allocation for acs.

Stdlib-only, sibling of acs_lib.py / metrics_aggregate.py.

Two responsibilities:

1. `record_cost_sample(payload)` — appends `{ts, total_cost_usd, src,
   total_api_duration_ms, duration_src}` to a per-checkout, append-only
   sample log (`sessions/<ckid>-cost-samples.jsonl`, a sibling of the
   existing per-checkout pointer file). `total_cost_usd` and
   `total_api_duration_ms` are each probed out of the payload independently
   (by `_extract_total_cost` / `_extract_api_duration`), shape-agnostically,
   so the sampler never depends on which of several possible statusLine
   payload shapes Claude Code actually emits (Assumption A1). Neither
   candidate matching -> no sample written; this is not an error (either
   quantity alone is enough to write a sample -- design.md D3). The function
   never raises: any failure (uninitialized repo, malformed payload, I/O
   error) is swallowed, matching PRD G7 ("never crash") and the statusLine
   hook's own contract.

2. `allocate_cost(...)` — at run-finalize time, consumes the *unconsumed*
   portion of the sample log for the run's window via a per-checkout
   allocation cursor (`sessions/<ckid>-cost-cursor.json`), and apportions the
   resulting dollar delta across `role_usage`'s roles by measured token
   share; the same cursor also tracks `total_api_duration_ms` and, when both
   cursor edges carry a numeric value, apportions the API-duration delta by
   the identical token-share mechanism (design.md D3/C-6). The cursor rule
   structurally prevents double-charging: a sample already consumed by one
   run can never again serve as another run's "after" (design.md SS1.3).

Role-usage / apportionment-denominator contract (this module's own decision,
since design.md leaves the hand-off shape loosely specified): `role_usage`
entries with `"role": "unattributed"` represent in-window tokens usage_reader
already excludes from its real per-skill role buckets (design.md C-8's
"drop, don't redistribute" policy). Such entries count toward the
apportionment denominator (all in-window usage) but never receive a dollar
(or API-duration millisecond) share themselves — the fraction of the charged
delta their token share implies is dropped from `allocate_cost`'s returned
`cost_usd`/`api_duration_ms` (the attributed-only share of the session-window
charge), and separately reported as `excluded_cost_usd`/`excluded_token_share`
on the return dict for callers that want to show what was dropped and why
(the API-duration side reuses this same `excluded_token_share`, never
recomputing it). A caller with no such information to report simply omits
the entry; nothing behaves differently absent it.
"""

import json
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
import claude_code_adapter as cc  # noqa: E402

MAX_LOG_BYTES = 64 * 1024

# Owned by the adapter: these spell Claude Code's own key names, and a regex
# source is invisible to the AST guard that keeps such literals in one place.
_TOTAL_COST_KEY_RE = cc.TOTAL_COST_KEY_RE
_TOTAL_API_DURATION_KEY_RE = cc.TOTAL_API_DURATION_KEY_RE
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


def claude_version_path(workspace, repo_id, ckid):
    """TTL cache for the `claude --version` probe recorded on each sample."""
    return os.path.join(lib.sessions_dir(workspace, repo_id), "%s-claude-version.json" % ckid)


# ---------------------------------------------------------------------------
# SS1.2 — shape-agnostic probe
# ---------------------------------------------------------------------------

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _recursive_scan(node, depth, prefix="", key_re=_TOTAL_COST_KEY_RE):
    """Depth-bounded (<=3) DFS for the first key matching `key_re` with a
    numeric value, in dict-insertion order. Returns (value, dotted_path) or
    None. `key_re` defaults to the cost pattern, preserving the original
    cost-only call site's behavior unchanged."""
    if depth > _MAX_SCAN_DEPTH or not isinstance(node, dict):
        return None
    for key, value in node.items():
        path = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(key, str) and key_re.search(key) and _is_number(value):
            return float(value), path
        if isinstance(value, dict):
            found = _recursive_scan(value, depth + 1, path, key_re=key_re)
            if found is not None:
                return found
    return None


def _probe(payload, order, key_re):
    """Probe `payload` for a quantity: the adapter's explicit key order
    first, then a bounded recursive scan. Returns (value, src) or
    (None, None). The key names themselves live in claude_code_adapter --
    this function knows only how to look, never what to look for."""
    if not isinstance(payload, dict):
        return None, None
    for container, key in order:
        node = payload if container is None else payload.get(container)
        if not isinstance(node, dict):
            continue
        value = node.get(key)
        if _is_number(value):
            return float(value), cc.probe_source(container, key)
    found = _recursive_scan(payload, 1, key_re=key_re)
    if found is not None:
        return found
    return None, None


def _extract_total_cost(payload):
    """Probe the session's total cost. See _probe; order from the adapter."""
    return _probe(payload, cc.COST_PROBE_ORDER, _TOTAL_COST_KEY_RE)


def _extract_api_duration(payload):
    """Probe the session's total API duration -- the cost probe's twin."""
    return _probe(payload, cc.DURATION_PROBE_ORDER, _TOTAL_API_DURATION_KEY_RE)


# ---------------------------------------------------------------------------
# Sample log — append-only JSONL, rotated past MAX_LOG_BYTES.
# ---------------------------------------------------------------------------

def _rotate_if_needed(path):
    """Once the log exceeds MAX_LOG_BYTES, keep only the most recent lines that
    fit within half the budget -- a simple, bounded rotation.

    Measured: a sample line is ~180 B, of which `claude_version` (MAR-520) is
    ~42 B, so half of a 64 KiB budget retains ~182 recent samples (~237 before
    that field). Rotation drops the OLDEST lines and the cursor consumes the
    newest, so the reduction does not make an unconsumed sample likelier; the
    figure is recorded here because "well under 200 B" was an estimate that had
    already drifted once."""
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
    """Append a shape-agnostic cost/duration sample for the checkout
    `payload` resolves to. Ticket-independent (needs only
    build_context(cwd)); never raises. F5: writes a sample when EITHER
    quantity is found -- only when both are absent is this a no-op."""
    try:
        if not isinstance(payload, dict):
            return
        value, src = _extract_total_cost(payload)
        dvalue, dsrc = _extract_api_duration(payload)
        if value is None and dvalue is None:
            return
        cwd = cc.payload_cwd(payload)
        ctx = lib.build_context(cwd)
        sample = {
            "ts": lib.now_iso(), "total_cost_usd": value, "src": src,
            "total_api_duration_ms": dvalue, "duration_src": dsrc,
            "claude_version": cc.claude_version(
                claude_version_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])),
        }
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


def _unavailable_role_usage(role_usage, value_field="cost_usd", basis_field="cost_basis"):
    """Degrade every entry's `value_field`/`basis_field` pair to
    None/"unavailable". Defaults preserve the original cost-only call
    sites' behavior; the same helper degrades api_duration_ms/basis too."""
    out = []
    for entry in role_usage:
        item = dict(entry)
        item[value_field] = None
        item[basis_field] = cc.UNAVAILABLE
        out.append(item)
    return out


def _apportion_by_tokens(usage, delta, value_key, basis_key, exclude_unattributed):
    """The one token-share split the three apportioners below are made of.

    Splits `delta` across `usage` in proportion to each entry's tokens, writing
    `value_key`/`basis_key` per item. When `exclude_unattributed`, an entry whose
    role is UNATTRIBUTED_ROLE still counts toward the denominator but receives
    None + UNAVAILABLE instead of a share -- the rule that makes the cost and
    duration splits agree by construction rather than by two matching copies.

    Returns (items, excluded_tokens, total_tokens). `total_tokens <= 0` is the
    degraded case: `items` is already the all-unavailable form, and the caller
    supplies whatever else its own return contract owes.
    """
    total_tokens = sum(_tokens(entry) for entry in usage)
    if total_tokens <= 0:
        return _unavailable_role_usage(usage, value_key, basis_key), 0, total_tokens

    out = []
    excluded_tokens = 0
    for entry in usage:
        item = dict(entry)
        tokens = _tokens(entry)
        if exclude_unattributed and entry.get("role") == UNATTRIBUTED_ROLE:
            excluded_tokens += tokens
            item[value_key] = None
            item[basis_key] = cc.UNAVAILABLE
        else:
            item[value_key] = delta * (tokens / total_tokens)
            item[basis_key] = "apportioned"
        out.append(item)
    return out, excluded_tokens, total_tokens


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
    out, excluded_tokens, total_tokens = _apportion_by_tokens(
        role_usage, delta, "cost_usd", "cost_basis", True)
    if total_tokens <= 0:
        return out, delta, 1.0
    excluded_token_share = excluded_tokens / total_tokens
    return out, max(0.0, delta * excluded_token_share), excluded_token_share


def _apportion_duration(role_usage, duration_delta):
    """Split `duration_delta` across role_usage by token share -- the same
    split as _apportion (same denominator, same UNATTRIBUTED_ROLE exclusion),
    writing api_duration_ms/api_duration_basis instead of cost_usd/cost_basis
    per item (design.md C-6, "identical mechanism" as cost). The caller
    (allocate_cost) derives the top-level attributed api_duration_ms from
    the excluded_token_share already computed by the cost-side _apportion
    call, not from summing this function's own per-item output. Callers must
    guarantee duration_delta >= 0 -- mirroring _apportion's own delta >= 0
    precondition, enforced by allocate_cost's guard before this function is
    ever called; no internal clamp happens here, exactly as _apportion's own
    per-item cost_usd does not clamp."""
    out, _excluded, _total = _apportion_by_tokens(
        role_usage, duration_delta, "api_duration_ms", "api_duration_basis", True)
    return out


def _apportion_models(model_usage, delta):
    """Split `delta` across model_usage by token share -- D1.2 Option A
    (design.md:173-200): the FULL delta, no unattributed exclusion, unlike
    _apportion's role-scoped split above. Denominator = all model_usage
    tokens; total_tokens <= 0 degrades every entry to unavailable, mirroring
    _apportion's own guard."""
    out, _excluded, _total = _apportion_by_tokens(
        model_usage, delta, "cost_usd", "cost_basis", False)
    return out


def allocate_cost(workspace, repo_id, checkout_id, started_at, ended_at, role_usage, model_usage=None):
    """Implements SS1.3's cursor-consumption rule. `started_at` is accepted for
    the caller's own informational/logging use only -- the "before" edge for
    the delta is always the persisted cursor, never started_at.

    Returns a dict: {role_usage, model_usage, cost_usd, cost_basis,
    cost_scope, excluded_cost_usd, excluded_token_share, api_duration_ms,
    api_duration_basis, api_duration_scope}. `cost_scope` carries
    "session_total" on a measured charge, and doubles as the degraded reason
    ("no_unconsumed_sample_in_window" / "cost_total_reset") when cost_usd is
    None -- design.md's cost_scope enum has no dedicated reason field, and
    this reuse is this module's own documented choice.

    `api_duration_ms`/`api_duration_basis`/`api_duration_scope` are the
    coupled-degradation, apportioned-duration counterparts (design.md D3):
    a duration-only charge requires numeric `total_api_duration_ms` on BOTH
    the persisted cursor and the selected `after` sample, independent of
    cost's own success -- a cost reset or a missing prior duration degrades
    duration only, never cost, and vice versa. `api_duration_scope`'s
    "duration_unavailable_on_cursor" value has no cost-side analogue since
    cost's own cursor always defaults to 0.0, never "unavailable".

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
    cursor_duration = cursor.get("total_api_duration_ms")
    cursor_duration = cursor_duration if _is_number(cursor_duration) else None

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
        scope = cc.unavailable("no_unconsumed_sample_in_window", source="cost_sampler")
        return {
            "role_usage": _unavailable_role_usage(
                _unavailable_role_usage(role_usage), "api_duration_ms", "api_duration_basis"),
            "model_usage": _unavailable_role_usage(model_usage) if model_usage is not None else None,
            "cost_usd": None, "cost_basis": cc.UNAVAILABLE,
            "cost_scope": scope,
            "excluded_cost_usd": None, "excluded_token_share": None,
            "api_duration_ms": None, "api_duration_basis": cc.UNAVAILABLE,
            # The same degradation, so the SAME switch result: a bare literal
            # here left api_duration_scope untraceable in $ACS_DEGRADATION_LOG,
            # and calling the switch twice would log one event as two.
            "api_duration_scope": scope,
        }

    after_duration = after.get("total_api_duration_ms")
    after_duration = after_duration if _is_number(after_duration) else None

    delta = float(after["total_cost_usd"]) - float(cursor_total)
    if delta < 0:
        scope = cc.unavailable("cost_total_reset", source="cost_sampler")
        lib.write_json(cost_cursor_path(workspace, repo_id, checkout_id),
                        {"ts": after["ts"], "total_cost_usd": after["total_cost_usd"],
                         "total_api_duration_ms": after_duration})
        return {
            "role_usage": _unavailable_role_usage(
                _unavailable_role_usage(role_usage), "api_duration_ms", "api_duration_basis"),
            "model_usage": _unavailable_role_usage(model_usage) if model_usage is not None else None,
            "cost_usd": None, "cost_basis": cc.UNAVAILABLE,
            "cost_scope": scope,
            "excluded_cost_usd": None, "excluded_token_share": None,
            "api_duration_ms": None, "api_duration_basis": cc.UNAVAILABLE,
            "api_duration_scope": scope,
        }

    role_usage_with_cost, excluded_cost_usd, excluded_token_share = _apportion(role_usage, delta)
    model_usage_with_cost = _apportion_models(model_usage, delta) if model_usage is not None else None
    lib.write_json(cost_cursor_path(workspace, repo_id, checkout_id),
                    {"ts": after["ts"], "total_cost_usd": after["total_cost_usd"],
                     "total_api_duration_ms": after_duration})
    attributed_cost_usd = max(0.0, delta - excluded_cost_usd)

    if cursor_duration is not None and after_duration is not None:
        duration_delta = after_duration - cursor_duration
    else:
        duration_delta = None

    if duration_delta is not None and duration_delta >= 0:
        role_usage_with_duration = _apportion_duration(role_usage_with_cost, duration_delta)
        api_duration_ms = max(0.0, duration_delta * (1 - excluded_token_share))
        api_duration_basis = "apportioned"
        api_duration_scope = "session_total"
    else:
        role_usage_with_duration = _unavailable_role_usage(
            role_usage_with_cost, "api_duration_ms", "api_duration_basis")
        api_duration_ms = None
        api_duration_basis = cc.UNAVAILABLE
        api_duration_scope = cc.unavailable("duration_unavailable_on_cursor",
                                             source="cost_sampler")

    return {
        "role_usage": role_usage_with_duration,
        "model_usage": model_usage_with_cost,
        "cost_usd": attributed_cost_usd, "cost_basis": "measured",
        "cost_scope": "session_total",
        "excluded_cost_usd": excluded_cost_usd, "excluded_token_share": excluded_token_share,
        "api_duration_ms": api_duration_ms, "api_duration_basis": api_duration_basis,
        "api_duration_scope": api_duration_scope,
    }
