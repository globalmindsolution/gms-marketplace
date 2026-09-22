"""MAR-587 -- a schema the mutation sweep cannot measure must be tracked, not forgotten.

`make -C src/acs-evals mutation` is `release.pre_release_gate[2]`. A schema
carrying no constraint cases contributes 0/0, so it cannot pull the percentage
down: the sweep can report 100% while whole schemas are entirely unexercised.
The sweep names them, but a name printed into a terminal is not a commitment to
fix anything.

AC-10: every schema the sweep reports as unexercised is recorded on an open
follow-up ticket. The set is derived from the sweep on every run rather than
listed here, so this does not rot into an allowlist -- when cases are added the
sweep stops naming that schema and nothing here needs editing.

No model, no network, no cost.

Run:  python3 -m unittest tests.acs.test_eval_zero_coverage_schemas_tracked -v
"""

import glob
import json
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVALS = os.path.join(REPO_ROOT, "src", "acs-evals")
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SCHEMA_DIR = os.path.join(PLUGIN, "schemas")

#: A ticket in one of these states is no longer a commitment to do the work.
SETTLED = frozenset({"done", "closed", "merged", "cancelled", "rejected"})

#: The sweep's summary sentence, and the per-schema rows it summarises.
SUMMARY = re.compile(r"^\s*\d+ schema\(s\) have NO cases at all[^:]*:\s*(.+)$", re.M)
TABLE_ROW = re.compile(r"^\s{2}(\S+\.schema\.json)\s+no cases\s*$", re.M)
MEASURED_ROW = re.compile(r"^\s{2}(\S+\.schema\.json)\s+\d+/\d+", re.M)


def sweep():
    """Run the mutation sweep the way the Makefile's `mutation` target does."""
    env = dict(os.environ, ACS_PLUGIN_ROOT=PLUGIN)
    done = subprocess.run(
        [sys.executable, os.path.join("runner", "mutation_sweep.py"),
         "--threshold", "0.9"],
        cwd=EVALS, env=env, capture_output=True, text=True)
    return done.stdout


def unexercised(output):
    """The schemas the sweep's summary sentence names as carrying no cases."""
    found = SUMMARY.search(output)
    if not found:
        return set()
    return {name.strip() for name in found.group(1).split(",") if name.strip()}


def live_tickets():
    """{ticket id: description} for every ticket partition not yet settled."""
    tickets = {}
    pattern = os.path.join(REPO_ROOT, ".acs", "state-machine", "*", "*", "ticket.json")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, encoding="utf-8") as fh:
                ticket = json.load(fh)
        except (OSError, ValueError):
            continue
        if str(ticket.get("status", "")).lower() in SETTLED:
            continue
        tickets[ticket.get("id", os.path.basename(os.path.dirname(path)))] = " ".join(
            str(ticket.get(field, "")) for field in ("title", "description"))
    return tickets


class ZeroCoverageSchemasAreTrackedTest(unittest.TestCase):
    """AC-10: the sweep's blind spots are owned by a ticket, not by a printout."""

    @classmethod
    def setUpClass(cls):
        cls.output = sweep()
        cls.unexercised = unexercised(cls.output)

    def test_the_summary_agrees_with_the_table_it_summarises(self):
        # A summary that names a different set than its own rows would let a
        # schema be reported as covered in one half of the same output.
        self.assertEqual(self.unexercised, set(TABLE_ROW.findall(self.output)),
                         "mutation sweep's summary and its per-schema table "
                         "disagree about which schemas carry no cases:\n%s"
                         % self.output)

    def test_every_unexercised_schema_is_named_by_an_open_followup_ticket(self):
        tickets = live_tickets()
        untracked = {}
        for schema in sorted(self.unexercised):
            stem = schema.replace(".schema.json", "")
            owners = sorted(tid for tid, text in tickets.items()
                            if re.search(r"\b%s\b" % re.escape(stem), text))
            if not owners:
                untracked[schema] = owners
        self.assertEqual(untracked, {},
                         "these schemas carry no constraint cases and no open "
                         "ticket records them: %s" % sorted(untracked))

    def test_every_shipped_schema_is_either_measured_or_named_as_unexercised(self):
        # The sweep must account for every schema the build ships. One it never
        # mentions is invisible in both directions: not measured, not tracked.
        shipped = {name for name in os.listdir(SCHEMA_DIR)
                   if name.endswith(".schema.json")}
        accounted = set(MEASURED_ROW.findall(self.output)) | self.unexercised
        self.assertEqual(sorted(shipped - accounted), [],
                         "shipped schemas the mutation sweep does not report "
                         "at all: %s" % sorted(shipped - accounted))


if __name__ == "__main__":
    unittest.main()
