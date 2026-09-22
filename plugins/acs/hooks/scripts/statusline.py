#!/usr/bin/env python3
"""statusline.py — optional Claude Code status line for acs.

Renders the current RUN's workflow at a glance, straight from the run ledger
(the same file the hooks gate on — no model involvement):

    Opus 4.8 · MAR-590 · ✓requirements ✓plan ▶code ○review ○docs ○pr · ~$4.21

The steps come from the resolved `ship.yaml`, in its order: a workflow is a
list, so the status line is that list with a glyph each. Nothing here knows
which steps exist.

Wire-up (offered by /acs:setup, or manually) — statusLine is a USER setting,
never forced by the plugin. In ~/.claude/settings.json or
<repo>/.claude/settings.json:

    {"statusLine": {"type": "command",
                    "command": "python3 /abs/path/to/plugins/acs/hooks/scripts/statusline.py"}}

Claude Code pipes a JSON payload on stdin (model, workspace, session, cost);
we parse it defensively and NEVER crash — on any problem we print a minimal
fallback line, because a broken status line is worse than none.

Every invocation also records a shape-agnostic cost sample from that payload
(cost_sampler.record_cost_sample) — ticket-independent, so samples exist even
before a ticket's first run can be measured against them.

Diagnostics: set ACS_STATUSLINE_DEBUG_PAYLOAD=<path> to dump the raw stdin
payload JSON to <path> on every invocation, for one-time inspection of what
Claude Code actually sends (verifying the statusLine cost-payload shape).
Permanent, env-gated debug code: unset (the default), it is a complete
no-op with zero behavior change.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claude_code_adapter as cc  # noqa: E402

GLYPHS = {"completed": "✓", "in_progress": "▶", "failed": "✗",
          "interrupted": "⏸"}

#: A step name shortened for a one-line display. Anything not named here keeps
#: its own name minus a leading `create-`; the table is a nicety, never the
#: source of truth for which steps exist.
SHORT = {"analyze-requirements": "requirements", "create-impl-plan": "plan",
         "create-api-contract": "contract", "create-test-docs": "cases",
         "review-code": "review", "create-e2e-tests": "e2e",
         "run-e2e-tests": "e2e-run", "docs-sync": "docs"}


def short(step):
    return SHORT.get(step) or (step[len("create-"):] if step.startswith("create-") else step)


def fallback(payload):
    model = cc.status_model_display_name(payload)
    cwd = cc.payload_cwd(payload)
    return "%s · %s" % (model, os.path.basename(cwd.rstrip("/")) or cwd)


def _display_cost(ctx, pipeline):
    """Prefer the latest real cost_sampler sample (design conformance item
    31) over pipeline.totals.cost_usd, which lags the just-finalized run and
    predates this ticket's own recompute; falls back to the pipeline figure
    only when no sample has been recorded yet for this checkout."""
    try:
        import cost_sampler
        value = cost_sampler.read_latest_sample(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    except Exception:
        pass
    return (pipeline.get("totals") or {}).get("cost_usd") or 0.0


def render(payload):
    import acs_lib as lib

    cwd = cc.payload_cwd(payload)
    ctx = lib.build_context(cwd)  # raises GateError when not initialized

    run_id = lib.current_run_id(ctx)
    if not run_id:
        return "%s · acs: no active run" % fallback(payload)

    rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
    doc = lib.load_run(rdir)
    if doc is None:
        return "%s · acs: %s (no run on disk)" % (fallback(payload), run_id)
    steps = doc.get("steps") or {}

    # The ORDER is the workflow's, and so is the membership: no list here.
    try:
        wf = lib.validate_workflow_file(
            lib.resolve_workflow(ctx["checkout_root"])["path"])
        order = lib.steps_of(wf)
    except Exception:  # noqa: BLE001 -- a status line never crashes
        order = sorted(steps)

    parts = []
    for step in order:
        glyph = GLYPHS.get((steps.get(step) or {}).get("status"), "○")
        parts.append("%s%s" % (glyph, short(step)))

    loop = (doc.get("loops") or {}).get("review-code") or {}
    cost = _display_cost(ctx, doc)
    bits = [
        cc.status_model_display_name(payload),
        run_id,
        " ".join(parts) if parts else "run not started",
    ]
    if int(loop.get("iteration") or 1) > 1:
        bits.append("review %s/%s" % (loop.get("iteration"), loop.get("max")))
    if cost:
        bits.append("~$%.2f" % cost)
    lock = lib.read_lock(rdir)
    if isinstance(lock, dict) and lock.get("checkout_id") not in (None, ctx["checkout_id"]):
        bits.append("🔒other session")
    return " · ".join(bits)


def _maybe_dump_debug_payload(payload):
    """ACS_STATUSLINE_DEBUG_PAYLOAD=<path>: dump the raw stdin payload JSON to
    <path>, for one-time diagnostic use. Unset: a complete no-op."""
    path = os.environ.get("ACS_STATUSLINE_DEBUG_PAYLOAD")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
    except Exception:
        pass


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    _maybe_dump_debug_payload(payload)
    try:
        import cost_sampler
        cost_sampler.record_cost_sample(payload)  # ticket-independent; swallows all
    except Exception:
        pass
    try:
        print(render(payload))
    except Exception:
        # any failure (uninitialized repo, corrupt state, no git): minimal line
        try:
            print(fallback(payload))
        except Exception:
            print("Claude")


if __name__ == "__main__":
    main()
