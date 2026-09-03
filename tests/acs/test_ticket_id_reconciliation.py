"""Library-level behaviour tests for the ticket-id allocation reconciliation
gate: allocate_ticket_id's three-arm gate (refuse / reconciled / seed-next),
the ranked local-evidence scan, the additive counters.json fields, and the
counters schema's additive shape.

Originating ticket: MAR-402 (Seam B of the split of epic MAR-401, C-12).
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

lib = acs_case.lib

SCHEMA_PATH = os.path.join(
    acs_case.REPO_ROOT, "plugins", "acs", "schemas", "counters.schema.json"
)


def _load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


class _FakeProc:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def _run_git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True, capture_output=True, text=True)


class GitEvidenceCase(unittest.TestCase):
    """A throwaway real git repo for evidence-scan tests. The scan shells out
    to real `git` here except where a test deliberately mocks subprocess.run
    to inspect argv/kwargs or inject a degrade."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-evidence-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        _run_git(self.repo, "init", "-q")
        _run_git(self.repo, "config", "user.email", "test@example.com")
        _run_git(self.repo, "config", "user.name", "Test")
        # Ensure HEAD exists before any test relies on git log/grep.
        self.commit("README.md", "seed\n", "initial commit")

    def commit(self, filename, content, message):
        path = os.path.join(self.repo, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        _run_git(self.repo, "add", filename)
        _run_git(self.repo, "commit", "-q", "-m", message)

    def untracked(self, filename, content):
        path = os.path.join(self.repo, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    def branch(self, name):
        _run_git(self.repo, "branch", name)


class TestScanRanking(GitEvidenceCase):
    """AC-2: ranked, bounded evidence proposal; observed_max is the maximum
    over all three sources, and seed_source is the tie-break/provenance."""

    def test_observed_max_is_the_maximum_over_all_three_sources(self):
        self.commit("ids.md", "SHOP-5 tracked\n", "note SHOP-5")
        self.commit("other.md", "no ids here\n", "SHOP-3 in commit message only")
        self.branch("work/SHOP-9-thing")
        result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertEqual(result["observed_max"], 9)
        self.assertEqual(result["seed_source"], "branch-names")

    def test_seed_source_labels_the_highest_ranked_source_that_saw_the_max(self):
        self.commit("committed.md", "SHOP-3 only\n", "commit body mentions SHOP-8")
        self.branch("release/SHOP-8-cut")
        result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        # git-history rank (2) and branch-names rank (3) both see 8; rank 2 wins.
        self.assertEqual(result["observed_max"], 8)
        self.assertEqual(result["seed_source"], "git-history")

    def test_committed_files_source_wins_a_tie_with_git_history(self):
        self.commit("ids.md", "SHOP-6 tracked\n", "SHOP-6 in the message too")
        self.branch("work/SHOP-2-thing")
        result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertEqual(result["observed_max"], 6)
        self.assertEqual(result["seed_source"], "committed-files")

    def test_branch_names_source_is_used_when_the_higher_ranks_are_empty(self):
        self.branch("work/SHOP-4-thing")
        result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertEqual(result["observed_max"], 4)
        self.assertEqual(result["seed_source"], "branch-names")

    def test_scan_reads_tracked_files_only(self):
        self.commit("tracked.md", "SHOP-2 tracked\n", "add tracked file")
        self.untracked("untracked.md", "SHOP-99 should not be observed\n")
        result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertEqual(result["per_source"]["committed-files"], 2)
        self.assertEqual(result["observed_max"], 2)

    def test_ids_of_other_prefixes_are_not_observed(self):
        self.commit("ids.md", "OTHER-999 tracked\n", "OTHER-50 in message")
        self.branch("work/OTHER-77-thing")
        result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertIsNone(result["observed_max"])
        self.assertIsNone(result["seed_source"])

    def test_no_git_repo_degrades_to_no_local_evidence(self):
        not_a_repo = tempfile.mkdtemp(prefix="acs-not-a-repo-")
        self.addCleanup(shutil.rmtree, not_a_repo, True)
        result = lib.scan_local_ticket_evidence(not_a_repo, "SHOP")
        self.assertEqual(result, {
            "observed_max": None, "seed_source": None,
            "per_source": {"committed-files": None, "git-history": None, "branch-names": None},
        })

    def test_repo_root_none_degrades_to_no_local_evidence(self):
        result = lib.scan_local_ticket_evidence(None, "SHOP")
        self.assertEqual(result, {
            "observed_max": None, "seed_source": None,
            "per_source": {"committed-files": None, "git-history": None, "branch-names": None},
        })

    def test_a_timed_out_source_yields_nothing_and_lower_ranks_still_count(self):
        self.commit("ids.md", "SHOP-1 tracked\n", "SHOP-1 in message")
        self.branch("work/SHOP-7-thing")
        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            if "log" in cmd:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)
            return real_run(cmd, **kwargs)

        with mock.patch("subprocess.run", side_effect=fake_run):
            result = lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertIsNone(result["per_source"]["git-history"])
        self.assertEqual(result["observed_max"], 7)
        self.assertEqual(result["seed_source"], "branch-names")

    def test_git_history_scan_is_capped_at_400_commits(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _FakeProc()

        with mock.patch("subprocess.run", side_effect=fake_run):
            lib.scan_local_ticket_evidence(self.repo, "SHOP")
        history_call = next(c for c in calls if "log" in c)
        self.assertIn("-400", history_call)

    def test_ref_scan_is_capped_at_400_refs(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _FakeProc()

        with mock.patch("subprocess.run", side_effect=fake_run):
            lib.scan_local_ticket_evidence(self.repo, "SHOP")
        ref_call = next(c for c in calls if "for-each-ref" in c)
        self.assertIn("--count=400", ref_call)

    def test_each_git_subprocess_uses_the_ten_second_timeout(self):
        kwargs_list = []

        def fake_run(cmd, **kwargs):
            kwargs_list.append(kwargs)
            return _FakeProc()

        with mock.patch("subprocess.run", side_effect=fake_run):
            lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertEqual(len(kwargs_list), 3)
        for kwargs in kwargs_list:
            self.assertEqual(kwargs.get("timeout"), 10)

    def test_scan_shells_out_only_to_git(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _FakeProc()

        with mock.patch("subprocess.run", side_effect=fake_run):
            lib.scan_local_ticket_evidence(self.repo, "SHOP")
        self.assertEqual(len(calls), 3)
        for cmd in calls:
            self.assertEqual(cmd[0], "git")

    def test_all_sources_empty_still_refuses_with_no_local_evidence_wording(self):
        workspace = tempfile.mkdtemp(prefix="acs-ws-")
        self.addCleanup(shutil.rmtree, workspace, True)
        with self.assertRaises(lib.ReconciliationRequired) as ctx:
            lib.allocate_ticket_id(workspace, "acme-shop", "SHOP", repo_root=self.repo)
        self.assertIn("No local evidence", ctx.exception.render("new-ticket.py --seed-next <n>"))


class TestReconciliationGate(unittest.TestCase):
    """AC-1, AC-3: the fail-closed gate inside the O_EXCL critical section, and
    the already-reconciled no-regression path."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="acs-gate-")
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.rdir = lib.repo_dir(self.workspace, "acme-shop")
        self.counters_path = os.path.join(self.rdir, "counters.json")
        self.guard_path = os.path.join(self.rdir, "counters.json.lock")

    def test_unreconciled_partition_raises_reconciliation_required(self):
        with self.assertRaises(lib.ReconciliationRequired):
            lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")

    def test_reconciliation_required_is_a_gate_error_subclass(self):
        self.assertTrue(issubclass(lib.ReconciliationRequired, lib.GateError))

    def test_refusal_mints_no_id_and_writes_no_counters_file(self):
        with self.assertRaises(lib.ReconciliationRequired):
            lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertFalse(os.path.exists(self.counters_path))

    def test_refusal_releases_the_counters_guard(self):
        with self.assertRaises(lib.ReconciliationRequired):
            lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertFalse(os.path.exists(self.guard_path))

    def test_gate_runs_while_the_guard_is_held(self):
        seen = {}

        def fake_scan(repo_root, prefix):
            seen["guard_exists"] = os.path.exists(self.guard_path)
            return {"observed_max": None, "seed_source": None,
                    "per_source": {"committed-files": None, "git-history": None, "branch-names": None}}

        with mock.patch.object(lib, "scan_local_ticket_evidence", side_effect=fake_scan):
            with self.assertRaises(lib.ReconciliationRequired):
                lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertTrue(seen.get("guard_exists"))

    def test_corrupt_counters_json_is_treated_as_unreconciled(self):
        os.makedirs(self.rdir, exist_ok=True)
        with open(self.counters_path, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        with self.assertRaises(lib.ReconciliationRequired):
            lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")

    def test_refusal_message_names_the_prefix_the_floor_and_the_seed_command(self):
        repo = tempfile.mkdtemp(prefix="acs-evidence-repo-")
        self.addCleanup(shutil.rmtree, repo, True)
        _run_git(repo, "init", "-q")
        _run_git(repo, "config", "user.email", "test@example.com")
        _run_git(repo, "config", "user.name", "Test")
        with open(os.path.join(repo, "ids.md"), "w", encoding="utf-8") as fh:
            fh.write("SHOP-5 tracked\n")
        _run_git(repo, "add", "ids.md")
        _run_git(repo, "commit", "-q", "-m", "add ids")
        with self.assertRaises(lib.ReconciliationRequired) as ctx:
            lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP", repo_root=repo)
        message = ctx.exception.render("new-ticket.py --seed-next <n>")
        self.assertIn("SHOP", message)
        self.assertIn("5", message)
        self.assertIn("new-ticket.py --seed-next <n>", message)

    def test_populated_next_allocates_without_running_the_scan(self):
        os.makedirs(self.rdir, exist_ok=True)
        lib.write_json(self.counters_path, {"next": 10})
        with mock.patch.object(lib, "scan_local_ticket_evidence") as scan:
            result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertEqual(result, "SHOP-10")
        scan.assert_not_called()

    def test_reconciled_true_without_next_allocates(self):
        os.makedirs(self.rdir, exist_ok=True)
        lib.write_json(self.counters_path, {"reconciled": True})
        result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertEqual(result, "SHOP-1")

    def test_reconciled_partition_gains_no_new_counter_keys(self):
        os.makedirs(self.rdir, exist_ok=True)
        seeded = {"next": 5, "reconciled": True, "seed_source": "explicit-user",
                  "seeded_at": "2020-01-01T00:00:00Z"}
        lib.write_json(self.counters_path, seeded)
        lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        after = lib.read_json(self.counters_path)
        self.assertEqual(set(after.keys()), set(seeded.keys()))
        self.assertEqual(after["next"], 6)

    def test_migrated_partition_with_a_copied_counters_file_is_reconciled(self):
        tmp = tempfile.mkdtemp(prefix="acs-migrate-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo_root = os.path.join(tmp, "repo")
        os.makedirs(repo_root)
        _run_git(repo_root, "init", "-q")
        _run_git(repo_root, "remote", "add", "origin", "https://github.com/acme/shop.git")
        old_ws = os.path.join(tmp, "old-workspace")
        new_ws = os.path.join(tmp, "new-workspace")
        os.makedirs(old_ws)
        os.makedirs(new_ws)
        old_rdir = lib.repo_dir(old_ws, "acme-shop")
        os.makedirs(old_rdir)
        lib.write_json(os.path.join(old_rdir, "counters.json"), {"next": 7})

        mod = acs_case.load_module("migrate_workspace.py")
        with acs_case.pushd(tmp):
            code, _out, err = acs_case.run_main(mod, [
                "--from", old_ws, "--to", new_ws, "--repo-root", repo_root,
            ])
        self.assertEqual(code, 0, err)

        result = lib.allocate_ticket_id(new_ws, "acme-shop", "SHOP")
        self.assertEqual(result, "SHOP-7")


class TestSeedNext(unittest.TestCase):
    """AC-4: --seed-next's authoritative write at the acs_lib level (confirm
    and record provenance; CLI wiring and its own tests are T2's scope)."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="acs-seed-")
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.counters_path = os.path.join(lib.repo_dir(self.workspace, "acme-shop"), "counters.json")

    def test_seeding_writes_reconciled_seed_source_and_seeded_at(self):
        result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP", seed_next=5)
        self.assertEqual(result, "SHOP-5")
        counters = lib.read_json(self.counters_path)
        self.assertEqual(counters["next"], 6)
        self.assertTrue(counters["reconciled"])
        self.assertEqual(counters["seed_source"], "explicit-user")
        self.assertIn("seeded_at", counters)

    def test_seeded_at_is_iso_8601_utc(self):
        lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP", seed_next=1)
        counters = lib.read_json(self.counters_path)
        self.assertIsNotNone(lib.parse_iso(counters["seeded_at"]))

    def test_explicit_seed_records_explicit_user_provenance_and_no_observed_max(self):
        lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP", seed_next=3)
        counters = lib.read_json(self.counters_path)
        self.assertEqual(counters["seed_source"], "explicit-user")
        self.assertNotIn("observed_max", counters)

    def test_seed_next_lowering_an_existing_next_warns_on_stderr(self):
        os.makedirs(lib.repo_dir(self.workspace, "acme-shop"), exist_ok=True)
        lib.write_json(self.counters_path, {"next": 10})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP", seed_next=3)
        self.assertEqual(result, "SHOP-3")
        self.assertIn("--seed-next", stderr.getvalue())
        self.assertIn("10", stderr.getvalue())
        counters = lib.read_json(self.counters_path)
        self.assertEqual(counters["next"], 4)

    def test_seed_next_below_one_is_refused_before_any_write(self):
        for bad in (0, -5):
            with self.subTest(seed_next=bad):
                with self.assertRaises(ValueError):
                    lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP", seed_next=bad)
                self.assertFalse(os.path.exists(self.counters_path))


class TestCountersSchema(unittest.TestCase):
    """AC-4: the additive shape of counters.schema.json. observed_max is never
    persisted (it is surfaced only in ReconciliationRequired's refusal message
    for the human to read) and so is deliberately absent from this schema."""

    def test_schema_declares_the_three_fields_and_stays_additive(self):
        schema = _load_schema()
        self.assertEqual(schema["required"], ["next"])
        self.assertIs(schema["additionalProperties"], True)
        for field in ("reconciled", "seed_source", "seeded_at"):
            self.assertIn(field, schema["properties"])

    def test_schema_does_not_declare_observed_max(self):
        schema = _load_schema()
        self.assertNotIn("observed_max", schema["properties"])

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
    def test_a_legacy_next_only_counters_file_still_validates(self):
        jsonschema.validate({"next": 5}, _load_schema())

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
    def test_counters_document_validates_against_counters_schema(self):
        document = {
            "next": 6, "reconciled": True, "seed_source": "explicit-user",
            "seeded_at": "2026-01-01T00:00:00Z",
        }
        jsonschema.validate(document, _load_schema())


class TestGateBypassGuard(unittest.TestCase):
    """AC-6 (library half): no production call site mints without going
    through the gate."""

    def test_no_production_call_site_bypasses_the_gate(self):
        scripts_dir = os.path.join(acs_case.REPO_ROOT, "plugins", "acs", "hooks", "scripts")
        callers = []
        for name in sorted(os.listdir(scripts_dir)):
            if not name.endswith(".py") or name == "acs_lib.py":
                continue
            with open(os.path.join(scripts_dir, name), encoding="utf-8") as fh:
                if re.search(r"allocate_ticket_id\(", fh.read()):
                    callers.append(name)
        self.assertEqual(sorted(callers), ["new-ticket.py", "skill-start.py"])


if __name__ == "__main__":
    unittest.main()
