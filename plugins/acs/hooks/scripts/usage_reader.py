#!/usr/bin/env python3
"""usage_reader.py -- reads real per-role token usage from a Claude Code
transcript for a single run.

Stdlib-only (Python 3.9+, no pip). Given the exact transcript_path recorded
on a run entry (acs_lib.record_session_marker / append_in_progress_run) plus
its own <session>/subagents/ subtree, counts message.usage token classes and
buckets them by role. Fixes the three verified tabp port defects: never a
constructed cwd slug (P1), always all four usage-field classes -- input,
output, cache_creation, cache_read (P2), always a recursive subagents walk
(P3). Never raises: any I/O failure, missing session marker, empty/invalid
window, or a cap breach degrades instead (design R1) -- and a run that
resolves zero real tokens is degraded too, never a misleadingly valid 0.

Privacy boundary (mandatory NFR -- security): reads only the four integer
usage fields, message.model, timestamp, and the attribution fields
(attributionSkill on main-session records, attributionAgent in-record on a
subagent's own *.jsonl) -- never message.content, prompt text, or tool
results, and never opens a subagents/*.meta.json sidecar at all (only
"*.jsonl" files are ever enumerated/opened).

Unattributed-token / apportionment-denominator contract: unattributed
same-window tokens (C-8's "drop, don't redistribute" policy) are folded into
a `role_usage` entry with `"role": "unattributed"` -- the exact convention
cost_sampler.allocate_cost's own docstring documents expecting from its
caller -- rather than silently vanishing or inflating an attributed role's
bucket. `excluded_token_share` is additionally reported at the top level of
the result for direct/display consumers that do not want to re-derive it
from the role_usage list themselves. This bucket also absorbs any
attributionSkill that is present but not the run's own (`skill` argument):
`read_transcript_usage` filters to the run's own skill only, so a
same-window record attributed to a different acs skill (e.g. a concurrent
or adjacent step of a long-running /acs:ship session) is dropped exactly
like a genuinely unattributed record, never absorbed into this run's
coordinator share.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib  # noqa: E402

MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 64

_USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
_BUCKET_KEYS = ("input", "output", "cache_creation", "cache_read")

#: role bucket for same-window tokens with no attributionSkill/attributionAgent
#: -- matches cost_sampler.UNATTRIBUTED_ROLE's own documented expectation.
UNATTRIBUTED_ROLE = "unattributed"


class _CapExceeded(Exception):
    """Internal-only signal: stop scanning immediately; never escapes this module."""


def _degraded(reason):
    return {"degraded": True, "reason": reason, "model": None, "role_usage": []}


def _empty_bucket():
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}


def _normalize_skill(name):
    """Strip the observed "acs:" prefix and apply
    acs_lib.ATTRIBUTION_SKILL_MAP's override (e.g. "init" -> "initialize")."""
    if not isinstance(name, str) or not name:
        return None
    name = name[len("acs:"):] if name.startswith("acs:") else name
    return acs_lib.ATTRIBUTION_SKILL_MAP.get(name, name)


def _skill_role(attribution_skill, own_skill):
    """Main-session attribution -> role bucket, or None when unattributed.

    Normalizes both attribution_skill and own_skill the same way (strip
    "acs:", apply ATTRIBUTION_SKILL_MAP) and returns "coordinator" only when
    they match -- the run's own-skill filter (design.md "usage_reader
    filters to the run's own skill only"). ANY other value -- known or
    unknown skill name -- is treated exactly like a genuinely absent
    attributionSkill: dropped into the unattributed bucket (C-8), never
    silently absorbed into a foreign run's coordinator share."""
    normalized = _normalize_skill(attribution_skill)
    if normalized is None:
        return None
    return "coordinator" if normalized == _normalize_skill(own_skill) else None


def _agent_role(attribution_agent):
    """Subagent attribution -> role bucket, or None when unattributed.

    Suffix-matches the observed acs:<...>-<role> shape (the same
    planner/executor/verifier vocabulary acs's reflection-subagent protocol
    uses throughout); a present-but-unmatched value (e.g. "Explore") still
    counts as "other" rather than being dropped."""
    if not isinstance(attribution_agent, str) or not attribution_agent:
        return None
    for suffix, role in (("-planner", "planner"), ("-executor", "executor"), ("-verifier", "verifier")):
        if attribution_agent.endswith(suffix):
            return role
    return "other"


def _usage_total(usage):
    total = 0
    for field in _USAGE_FIELDS:
        value = usage.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += int(value)
    return total


def _add_usage(bucket, usage):
    for src, dst in zip(_USAGE_FIELDS, _BUCKET_KEYS):
        value = usage.get(src)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            bucket[dst] += int(value)


def _iter_capped_lines(path, cap_state):
    """Yield each raw line of `path`, enforcing the shared 32 MiB / 64 file caps.

    Raises _CapExceeded the instant either cap is met -- before open for the
    file-count cap, mid-file for the byte cap -- so a breach stops the scan
    immediately rather than finishing the current file."""
    if cap_state["files"] >= MAX_FILES:
        raise _CapExceeded()
    cap_state["files"] += 1
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            cap_state["bytes"] += len(line.encode("utf-8", errors="replace"))
            if cap_state["bytes"] > MAX_BYTES:
                raise _CapExceeded()
            yield line


def _scan_file(path, start_dt, end_dt, cap_state, is_subagent, model_holder, role_totals, acc, own_skill):
    """Fold one transcript JSONL file's in-window usage into role_totals/acc.

    Skips (never raises on) a corrupt line, a non-dict record, an
    out-of-window timestamp, or a record with no usable message.usage.
    `own_skill` is the run's own skill name, used to filter main-session
    attributionSkill records (see _skill_role); ignored for subagent files."""
    for line in _iter_capped_lines(path, cap_state):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        ts = acs_lib.parse_iso(record.get("timestamp"))
        if ts is None or ts < start_dt or (end_dt is not None and ts > end_dt):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        total = _usage_total(usage)
        if total == 0:
            continue
        if model_holder[0] is None:
            model = message.get("model")
            if isinstance(model, str) and model:
                model_holder[0] = model
        role = (_agent_role(record.get("attributionAgent")) if is_subagent
                else _skill_role(record.get("attributionSkill"), own_skill))
        acc["total"] += total
        if role is None:
            role = UNATTRIBUTED_ROLE
            acc["excluded"] += total
        _add_usage(role_totals.setdefault(role, _empty_bucket()), usage)


def _walk_jsonl(root):
    """Recursive walk yielding only "*.jsonl" paths under root (P3 guard) --
    a "*.meta.json" sidecar never matches this suffix, so it is never yielded
    and therefore never opened (privacy boundary)."""
    if not os.path.isdir(root):
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".jsonl"):
                yield os.path.join(dirpath, name)


def read_transcript_usage(transcript_path, started_at, ended_at, skill):
    """Real per-role token usage for one run's [started_at, ended_at] window.

    Reads the exact transcript_path plus dirname(transcript_path)/<session_id>/
    subagents/ (session_id derived from transcript_path's own basename -- the
    recorded shape is "<...>/<session_id>.jsonl" -- never a cwd-constructed
    slug: P1). `skill` is the run's own skill name (e.g. "code"); only
    main-session records whose attributionSkill normalizes to this same
    skill land in the "coordinator" bucket -- any other acs:*-attributed
    record in the window (a concurrent or adjacent run's own skill) is
    dropped, never absorbed. Never raises."""
    try:
        return _read(transcript_path, started_at, ended_at, skill)
    except Exception:
        return _degraded("unexpected_error")


def _read(transcript_path, started_at, ended_at, skill):
    if not isinstance(transcript_path, str) or not transcript_path:
        return _degraded("no_session_marker")

    start_dt = acs_lib.parse_iso(started_at)
    if start_dt is None:
        return _degraded("empty_window")
    end_dt = None
    if ended_at is not None:
        end_dt = acs_lib.parse_iso(ended_at)
        if end_dt is None or end_dt < start_dt:
            return _degraded("empty_window")

    cap_state = {"bytes": 0, "files": 0}
    model_holder = [None]
    role_totals = {}
    acc = {"total": 0, "excluded": 0}

    try:
        _scan_file(transcript_path, start_dt, end_dt, cap_state, False, model_holder, role_totals, acc, skill)
    except _CapExceeded:
        return _degraded("cap_exceeded")
    except OSError:
        return _degraded("unreadable_transcript")

    session_id = os.path.splitext(os.path.basename(transcript_path))[0]
    subagents_dir = os.path.join(os.path.dirname(transcript_path), session_id, "subagents")
    for file_path in _walk_jsonl(subagents_dir):
        try:
            _scan_file(file_path, start_dt, end_dt, cap_state, True, model_holder, role_totals, acc, skill)
        except _CapExceeded:
            return _degraded("cap_exceeded")
        except OSError:
            continue  # one unreadable subagent file does not sink the whole run

    if acc["total"] == 0:
        return _degraded("no_tokens_in_window")

    role_usage = [dict(role=role, **bucket) for role, bucket in sorted(role_totals.items())]
    return {
        "degraded": False,
        "reason": None,
        "model": model_holder[0],
        "role_usage": role_usage,
        "excluded_token_share": acc["excluded"] / acc["total"],
    }
