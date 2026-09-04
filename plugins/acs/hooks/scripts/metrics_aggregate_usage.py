"""metrics_aggregate_usage — the by-model and by-ticket usage panels
(extracted from metrics_aggregate.py by MAR-531).

The accumulate/finalize pair for each bucket lives together: an empty bucket, a
fold that adds one run to it, and a finalize that turns the running totals into
the shares the renderer prints -- three halves of one decision, and the seam
the splitting ticket names.
"""


import glob
import json
import os
import re
import sys
import acs_lib  # noqa: E402

from metrics_aggregate_common import _share_pct



def _empty_panel6_bucket():
    """Shared panel-6 bucket shape (MAR-4 spec 01): the four token classes plus a running cost.

    Replaces the two independent 3-key literals (the `burn` seed and _accumulate_burn's
    setdefault) that previously had to be kept in lockstep by hand. cost_seen mirrors
    _empty_model_bucket's pattern: True only once a numeric cost_usd has contributed.
    """
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "cost": 0.0,
            "cost_seen": False}


def _apply_panel6_shares(burn):
    """Repo-scope token_share_pct/cost_share_pct on every panel-6 bucket, computed once,
    post-loop (D2 placement; MAR-4 spec 01). Percentage scale is 0-100. Mutates `burn` in place.
    """
    token_total = sum(
        b["input"] + b["output"] + b["cache_creation"] + b["cache_read"] for b in burn.values()
    )
    cost_total = sum(b["cost"] for b in burn.values())
    for bucket in burn.values():
        token_sum = bucket["input"] + bucket["output"] + bucket["cache_creation"] + bucket["cache_read"]
        bucket["token_share_pct"] = _share_pct(token_sum, token_total)
        bucket["cost_share_pct"] = (
            _share_pct(bucket["cost"], cost_total) if bucket["cost_seen"] else None
        )


def _empty_model_bucket():
    """Raw (pre-finalization) per-model accumulator for usage_by_model (MAR-3 spec 04)."""
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0,
            "cost_sum": 0.0, "cost_seen": False}


def _empty_skill_duration_bucket():
    """Raw (pre-finalization) per-skill duration accumulator for usage_by_ticket.skills[] and
    panel 3's step_api_duration (MAR-7 spec 01). Mirrors _empty_model_bucket's seen/sum-pair
    pattern: a None-elapsed run or a None/non-numeric api_duration_ms is excluded from its own
    sum but never prevents the skill from appearing (never a fabricated 0)."""
    return {"api_duration_ms_sum": 0.0, "api_duration_seen": False,
            "run_seconds_sum": 0.0, "run_seconds_seen": False, "runs": []}


def _fold_model_bucket(dest, src):
    """Add one raw model accumulator's counts into another, in place."""
    dest["input"] += src["input"]
    dest["output"] += src["output"]
    dest["cache_creation"] += src["cache_creation"]
    dest["cache_read"] += src["cache_read"]
    dest["cost_sum"] += src["cost_sum"]
    dest["cost_seen"] = dest["cost_seen"] or src["cost_seen"]


def _finalize_model_bucket(model, bucket):
    """Raw accumulator -> the panel's public item shape (cost roll-up rule, spec 04).

    cost_usd is the sum of non-null contributing costs, never a fabricated 0: None with
    cost_basis "unavailable" when no contributing model_usage item carried a numeric cost,
    else "apportioned" with cost_usd rounded to 6 places (mirrors _accumulate_burn's rounding).
    """
    return {
        "model": model,
        "input": bucket["input"],
        "output": bucket["output"],
        "cache_creation": bucket["cache_creation"],
        "cache_read": bucket["cache_read"],
        "cost_usd": round(bucket["cost_sum"], 6) if bucket["cost_seen"] else None,
        "cost_basis": "apportioned" if bucket["cost_seen"] else "unavailable",
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


def _finalize_role_ticket_bucket(bucket, token_total, cost_total):
    """Raw per-role accumulator -> usage_by_ticket's public role-item shape (MAR-4 spec 01).

    cost_usd/cost_basis follow the model roll-up rule (None/"unavailable" when this role had no
    measured cost in this ticket, independent of sibling roles in the same ticket). Both
    percentages are ticket-scoped (token_total/cost_total are this ticket's own sums, never the
    repo total). cost_share_pct is None whenever cost_usd is None OR the ticket-scope cost total
    is zero/absent (a role with no measured cost cannot express a share of an unknown quantity).
    """
    token_sum = bucket["input"] + bucket["output"] + bucket["cache_creation"] + bucket["cache_read"]
    cost_usd = round(bucket["cost_sum"], 6) if bucket["cost_seen"] else None
    return {
        "input": bucket["input"],
        "output": bucket["output"],
        "cache_creation": bucket["cache_creation"],
        "cache_read": bucket["cache_read"],
        "cost_usd": cost_usd,
        "cost_basis": "apportioned" if bucket["cost_seen"] else "unavailable",
        "token_share_pct": _share_pct(token_sum, token_total),
        "cost_share_pct": _share_pct(cost_usd, cost_total) if cost_usd is not None else None,
    }


def _finalize_skill_bucket(skill, bucket):
    """Raw per-skill duration accumulator -> usage_by_ticket.skills[]'s public item shape
    (MAR-7 spec 01). Structural mirror of _finalize_model_bucket's cost roll-up rule: a rolled-up
    figure across possibly several run entries collapses to "apportioned"/"unavailable" (never a
    fabricated 0) -- distinct from _panel3_row's step_api_duration cell, which passes through a
    single contributing run's own literal basis rather than collapsing it.
    """
    return {
        "skill": skill,
        "run_seconds_sum": round(bucket["run_seconds_sum"], 4) if bucket["run_seconds_seen"] else None,
        "api_duration_ms": round(bucket["api_duration_ms_sum"], 4) if bucket["api_duration_seen"] else None,
        "api_duration_basis": "apportioned" if bucket["api_duration_seen"] else "unavailable",
        "runs": bucket["runs"],
    }


def _usage_by_ticket_panel(ticket_role_rows, ticket_skill_rows):
    """Build panels.usage_by_ticket: ticket-scoped role-share percentages (MAR-4 spec 01, AC-1),
    widened with ticket-scope api_duration_ms/api_duration_basis and a skills[] array (MAR-7
    spec 01, D5.4/S-C).

    ticket_role_rows: [(ticket_id, {role -> raw accumulator}), ...] in ticket iteration order.
    ticket_skill_rows: [(ticket_id, {skill -> raw duration accumulator}), ...], same order.
    A ticket's "roles" is the literal "no data" when it contributed no role_usage anywhere;
    otherwise a dict keyed by role name (no repeated "role" key inside each bucket), inserted in
    sorted() role-name order for determinism -- the renderer never re-sorts (D2 placement).
    api_duration_ms/api_duration_basis are ticket-scope siblings of "roles", folded across this
    ticket's own ticket_skills raw buckets (identical roll-up discipline to the skill-level
    figure, never double-derived from skills[]'s own already-rounded sums). "skills" is an EMPTY
    list -- never the string "no data" -- only when the ticket has NO run entries for any skill;
    a skill with run entries but no measured/apportioned duration still gets a row, with
    api_duration_ms/_basis degrading to null/"unavailable" independently (Risk 3 / test 8).
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
            cost_total = sum(b["cost_sum"] for b in roles_raw.values())
            roles = {
                role: _finalize_role_ticket_bucket(roles_raw[role], token_total, cost_total)
                for role in sorted(roles_raw)
            }

        ticket_skills = skill_map.get(ticket_id) or {}
        api_ms_sum = 0.0
        api_seen = False
        for bucket in ticket_skills.values():
            if bucket["api_duration_seen"]:
                api_ms_sum += bucket["api_duration_ms_sum"]
                api_seen = True

        # A skill row is emitted whenever the skill has any run entries at all -- either duration
        # figure having ever been measured/apportioned is enough; api_duration_ms/_basis then
        # degrade to null/"unavailable" independently via _finalize_skill_bucket. A skill with
        # zero run entries never reaches this list (it is simply absent from ticket_skills), which
        # is what keeps a genuinely-empty ticket's skills == [] (Risk 3 / test 8).
        skills = [
            _finalize_skill_bucket(skill, ticket_skills[skill])
            for skill in acs_lib.HOOKED_SKILLS
            if skill in ticket_skills and (ticket_skills[skill]["api_duration_seen"]
                                            or ticket_skills[skill]["run_seconds_seen"])
        ]

        tickets.append({
            "ticket_id": ticket_id,
            "roles": roles,
            "api_duration_ms": round(api_ms_sum, 4) if api_seen else None,
            "api_duration_basis": "apportioned" if api_seen else "unavailable",
            "skills": skills,
        })
    return {"tickets": tickets}
