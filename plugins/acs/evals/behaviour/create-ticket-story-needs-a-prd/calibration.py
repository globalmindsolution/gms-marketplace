"""Calibration plays for create-ticket-story-needs-a-prd (see
tests/evals/check_grader_calibration.py). The ideal run: the skill starts
(`acs step start --allocate`, a placeholder ticket), the story author finds no
PRD to link the wishlist to (ADR-0144), and Finish records the run failed with
a reply pointing at /acs:create-prd. The bad plays complete a ticket anyway."""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket"
REQUEST = "Add a wishlist"


def _start(ws):
    ws.skill("create-ticket")
    started = ws.acs("step", "start", "--step", "create-ticket", "--allocate", "--type", "task",
                     "--title", "(ticket under analysis)", "--args", REQUEST)
    assert started.returncode == 0, started.stderr
    ws.called("Agent", subagent_type="acs:create-ticket-story-author",
              prompt='<task skill="create-ticket" phase="story-author" ticket-id="EVAL-1" iteration="1">')


def _save(ws, fields):
    saved = ws.acs("ticket", "save", "--ticket", "EVAL-1", "--from", "-",
                   stdin=json.dumps(fields))
    assert saved.returncode == 0, saved.stderr


def _finish(ws, status, ttype):
    ws.write(STEP + "/result.json", json.dumps({
        "status": status, "summary": "wishlist: no PRD to make the story from",
        "states": {"ticket_id": "EVAL-1", "type": ttype, "children": [],
                   "prd_trace": {"feature": None, "divergence": None}},
        "findings": [], "errors": []}))
    # `|| true`: an unlinked story is refused here, which leaves the step open.
    ws.sh('python3 "%s/post-create-ticket.py" --result-file "%s/result.json" || true'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _finish(ws, "failed", "story")
    ws.reply = ("No ticket was created: a wishlist is product work, and product work is made "
                "from the PRD, which this repo does not have yet. Write it first with "
                "/acs:create-prd, then create the wishlist ticket from its features.")


def _relabelled_a_task(ws):
    """Got past the rule by calling the wishlist a technical task."""
    _start(ws)
    _save(ws, {"title": "Wishlist", "type": "task",
               "description": "A shopper saves products to a wishlist."})
    _finish(ws, "completed", "task")
    ws.reply = "Created EVAL-1 (task) for the wishlist; consider /acs:create-prd later."


def _completed_a_story(ws):
    """Tried to complete an unlinked story: the post-hook refuses it."""
    _start(ws)
    _save(ws, {"title": "Wishlist", "type": "story"})
    _finish(ws, "completed", "story")
    ws.reply = "Created EVAL-1 for the wishlist. Next: /acs:create-prd to back it."


def _no_pointer(ws):
    _start(ws)
    _finish(ws, "failed", "story")
    ws.reply = "I couldn't create the ticket."


BAD = {
    "relabelled the wishlist a task to escape the rule": _relabelled_a_task,
    "tried to complete an unlinked story": _completed_a_story,
    "stopped without pointing at the PRD": _no_pointer,
}
