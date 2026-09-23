"""Scenario registry for the acs eval harness.

Each scenario module exposes a ``META`` dict ({name, tier, goal, summary}) and a
``run()`` returning a ``harness.Check``. Order here is the run order.

s04_skill_triggers is absent deliberately. It measured routing for all 32 skills
off its own hard-coded probe list -- the third of three implementations of the
same question, alongside a tier-3 measurer and the `claude plugin eval` tree.
The tree is the one that remains, rendered from `evals/dataset/routing.json`;
see `plugins/acs/evals/README.md`. What did NOT survive the consolidation is
s04's explicit-invocation probes, which it decided from the session
REGISTRATION LIST before any model turn -- a signal no grader in the guide's
format can observe.
"""

from . import s01_install_gate_smoke
from . import s02_create_ticket_artifacts
from . import s03_resume_and_verify
from . import s05_session_end
from . import s06_update_migration
from . import s07_fanout_tracker_sync
from . import s08_create_pr_forge

SCENARIOS = [
    s01_install_gate_smoke,
    s02_create_ticket_artifacts,
    s03_resume_and_verify,
    s05_session_end,
    s06_update_migration,
    s07_fanout_tracker_sync,
    s08_create_pr_forge,
]
