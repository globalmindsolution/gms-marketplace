"""metrics_aggregate_usage — the by-model and by-ticket usage panels
(extracted from metrics_aggregate.py by MAR-531).

The accumulate/finalize pair for each bucket lives together: an empty bucket, a
fold that adds one run to it, and a finalize that turns the running totals into
the shares the renderer prints -- three halves of one decision, and the seam
the splitting ticket names.
"""


import acs_lib  # noqa: E402

from metrics_aggregate_common import _share_pct



def _empty_panel6_bucket():
    """Shared panel-6 bucket shape (MAR-4 spec 01): the four token classes.

    Replaces the two independent 3-key literals (the `burn` seed and _accumulate_burn's
    setdefault) that previously had to be kept in lockstep by hand.
    """
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}


def _apply_panel6_shares(burn):
    """Repo-scope token_share_pct on every panel-6 bucket, computed once, post-loop (D2
    placement; MAR-4 spec 01). Percentage scale is 0-100. Mutates `burn` in place.
    """
    token_total = sum(
        b["input"] + b["output"] + b["cache_creation"] + b["cache_read"] for b in burn.values()
    )
    for bucket in burn.values():
        token_sum = bucket["input"] + bucket["output"] + bucket["cache_creation"] + bucket["cache_read"]
        bucket["token_share_pct"] = _share_pct(token_sum, token_total)


def _empty_model_bucket():
    """Raw (pre-finalization) per-model accumulator for usage_by_model (MAR-3 spec 04)."""
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}


def _empty_skill_duration_bucket():
    """Raw (pre-finalization) per-skill wall-clock accumulator for usage_by_ticket.skills[]
    (MAR-7 spec 01). A None-elapsed run is excluded from the sum but still listed in `runs`,
    and run_seconds_seen stays False until a timed run contributes (never a fabricated 0)."""
    return {"run_seconds_sum": 0.0, "run_seconds_seen": False, "runs": []}


def _fold_model_bucket(dest, src):
    """Add one raw model accumulator's counts into another, in place."""
    dest["input"] += src["input"]
    dest["output"] += src["output"]
    dest["cache_creation"] += src["cache_creation"]
    dest["cache_read"] += src["cache_read"]


def _finalize_model_bucket(model, bucket):
    """Raw accumulator -> the panel's public item shape (spec 04): the model name and its
    four token classes."""
    return {
        "model": model,
        "input": bucket["input"],
        "output": bucket["output"],
        "cache_creation": bucket["cache_creation"],
        "cache_read": bucket["cache_read"],
    }


def _usage_by_model_panel(repo_models, ticket_model_rows):
    """Build panels.usage_by_model: repo scope + per-ticket scope (MAR-3 spec 04, AC-2).

    repo_models: {model -> raw accumulator} folded across every ticket/skill.
    ticket_model_rows: [(ticket_id, {model -> raw accumulator}), ...] in ticket iteration order.
    "no data" (repo, or a ticket's own "models") when nothing contributed at that scope --
    e.g. a legacy pre-MAR-3 run entry with no model_usage (AC-6 forward-only gap, disclosed).
    """
    if repo_models:
        repo = [_finalize_model_bucket(m, repo_models[m]) for m in sorted(repo_models)]
    else:
        repo = "no data"

    tickets = []
    for ticket_id, models in ticket_model_rows:
        if models:
            models_list = [_finalize_model_bucket(m, models[m]) for m in sorted(models)]
        else:
            models_list = "no data"
        tickets.append({"ticket_id": ticket_id, "models": models_list})

    return {"repo": repo, "tickets": tickets}


def _finalize_role_ticket_bucket(bucket, token_total):
    """Raw per-role accumulator -> usage_by_ticket's public role-item shape (MAR-4 spec 01).

    token_share_pct is ticket-scoped: token_total is this ticket's own sum, never the repo
    total.
    """
    token_sum = bucket["input"] + bucket["output"] + bucket["cache_creation"] + bucket["cache_read"]
    return {
        "input": bucket["input"],
        "output": bucket["output"],
        "cache_creation": bucket["cache_creation"],
        "cache_read": bucket["cache_read"],
        "token_share_pct": _share_pct(token_sum, token_total),
    }


def _finalize_skill_bucket(skill, bucket):
    """Raw per-skill accumulator -> usage_by_ticket.skills[]'s public item shape (MAR-7 spec 01):
    the summed wall-clock of the skill's timed runs (None, never a fabricated 0, if none was
    timed) and the per-run detail, untimed runs included."""
    return {
        "skill": skill,
        "run_seconds_sum": round(bucket["run_seconds_sum"], 4) if bucket["run_seconds_seen"] else None,
        "runs": bucket["runs"],
    }


def _usage_by_ticket_panel(ticket_role_rows, ticket_skill_rows):
    """Build panels.usage_by_ticket: ticket-scoped role-share percentages (MAR-4 spec 01, AC-1),
    widened with a skills[] array (MAR-7 spec 01, D5.4/S-C).

    ticket_role_rows: [(ticket_id, {role -> raw accumulator}), ...] in ticket iteration order.
    ticket_skill_rows: [(ticket_id, {skill -> raw accumulator}), ...], same order.
    A ticket's "roles" is the literal "no data" when it contributed no role_usage anywhere;
    otherwise a dict keyed by role name (no repeated "role" key inside each bucket), inserted in
    sorted() role-name order for determinism -- the renderer never re-sorts (D2 placement).
    "skills" holds one row per hooked skill with at least one timed run entry, in HOOKED_SKILLS
    order; it is an EMPTY list -- never the string "no data" -- when the ticket has none
    (Risk 3 / test 8).
    """
    skill_map = dict(ticket_skill_rows)
    tickets = []
    for ticket_id, roles_raw in ticket_role_rows:
        if not roles_raw:
            roles = "no data"
        else:
            token_total = sum(
                b["input"] + b["output"] + b["cache_creation"] + b["cache_read"]
                for b in roles_raw.values()
            )
            roles = {
                role: _finalize_role_ticket_bucket(roles_raw[role], token_total)
                for role in sorted(roles_raw)
            }

        # A skill with zero run entries never reaches this list (it is simply absent from
        # ticket_skills), which is what keeps a genuinely-empty ticket's skills == [].
        ticket_skills = skill_map.get(ticket_id) or {}
        skills = [
            _finalize_skill_bucket(skill, ticket_skills[skill])
            for skill in acs_lib.HOOKED_SKILLS
            if skill in ticket_skills and ticket_skills[skill]["run_seconds_seen"]
        ]

        tickets.append({
            "ticket_id": ticket_id,
            "roles": roles,
            "skills": skills,
        })
    return {"tickets": tickets}
