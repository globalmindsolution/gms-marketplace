"""`acs.py handoff send|receive|list` -- member -> member TICKET handoff (ADR-0131).

Every test drives real git: a bare remote and two clones of it in a temp
directory, Alice's (the sender) and Bob's (the receiver), each with its own
workspace under `<clone>/.acs/state-machine/`. The CLI runs as a subprocess in
the clone, exactly as a skill calls it.

Run:  python3 -m unittest tests.acs.test_team_handoff -v
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import SCRIPTS, lib  # noqa: E402

from acs_lib import team_handoff as th  # noqa: E402
from acs_lib import team_handoff_receive as thr  # noqa: E402


def git(root, *args, check=True):
    proc = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), proc.stderr))
    return proc.stdout


def write(root, rel, text="x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def tree_digest(base):
    """{relative path: sha256} of every file under base -- a byte-exact picture."""
    out = {}
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, base)] = hashlib.sha256(fh.read()).hexdigest()
    return out


class TwoClonesCase(unittest.TestCase):
    """A bare `remote.git` with one commit on main, cloned as alice/ and bob/."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-team-handoff-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.remote = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.remote], check=True)
        seed = os.path.join(self.tmp, "seed")
        subprocess.run(["git", "init", "-q", "-b", "main", seed], check=True)
        self.identity(seed, "Seed")
        write(seed, ".acs/settings.json", json.dumps({"ticket_prefix": "SHOP"}))
        write(seed, "app.py", "line1\nline2\nline3\n")
        write(seed, "old.py", "remove me\n")
        write(seed, ".gitignore", "*.secret\n")
        git(seed, "add", "-A")
        git(seed, "commit", "-qm", "init")
        git(seed, "push", "-q", self.remote, "main")
        self.alice = self.clone("alice", "Alice")
        self.bob = self.clone("bob", "Bob")

    def identity(self, root, name):
        git(root, "config", "user.name", name)
        git(root, "config", "user.email", "%s@example.com" % name.lower())
        git(root, "config", "commit.gpgsign", "false")

    def clone(self, name, who):
        path = os.path.join(self.tmp, name)
        subprocess.run(["git", "clone", "-q", self.remote, path], check=True)
        self.identity(path, who)
        return path

    # -- workspace ---------------------------------------------------------

    def rpath(self, root):
        return lib.repo_dir(lib.default_state_root(root), lib.repo_partition_id(root))

    def rdir(self, root, run_id):
        return lib.run_dir(self.rpath(root), run_id)

    def seed_counters(self, root, next_n):
        lib.write_json(os.path.join(self.rpath(root), "counters.json"),
                       {"next": next_n, "reconciled": True, "seed_source": "explicit-user"})

    def acs(self, root, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "acs.py")] + list(args),
                              cwd=root, capture_output=True, text=True)

    def ok(self, root, *args):
        out = self.acs(root, *args)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def refused(self, root, *args):
        out = self.acs(root, *args)
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        return out.stderr

    def new_ticket(self, root, title="Bulk export"):
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "new-ticket.py"),
                              "--title", title, "--type", "task"], cwd=root,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def walk(self, root, ticket, steps=("analyze-requirements",)):
        """Run each step the way the hooks do: step start, then its post-hook
        with the first outcome of its vocabulary."""
        for step in steps:
            out = self.acs(root, "step", "start", "--step", step, "--ticket", ticket)
            self.assertEqual(out.returncode, 0, out.stderr)
            vocabulary = lib.outcome_vocabulary(step)
            result = {"skill": step, "run_id": ticket, "status": "completed"}
            if vocabulary:
                result["outcome"] = vocabulary[0]
            post = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-%s.py" % step),
                                   "--run", ticket], input=json.dumps(result), cwd=root,
                                  capture_output=True, text=True)
            self.assertEqual(post.returncode, 0, post.stderr)

    def remote_refs(self):
        return git(self.remote, "for-each-ref", "--format=%(refname)", "refs/acs/").split()

    def checkout_state(self, root):
        """What a receive must never disturb beyond the paths it applies: the
        real index (bytes), HEAD and its reflog, and the untracked/ignored files."""
        with open(os.path.join(root, ".git", "index"), "rb") as fh:
            index = hashlib.sha256(fh.read()).hexdigest()
        return {"index": index, "head": git(root, "rev-parse", "HEAD"),
                "reflog": git(root, "reflog", "show", "--format=%H %gs", "HEAD"),
                "untracked": git(root, "ls-files", "--others", "--exclude-standard"),
                "ignored": git(root, "ls-files", "--others", "--ignored",
                               "--exclude-standard"),
                "files": tree_digest(os.path.join(root, "loose"))}

    # -- the scenario most tests start from ---------------------------------

    def prepare_sender(self, attachments=True):
        """Alice: SHOP-5 analysed, two outside-repo documents, uncommitted work,
        and every kind of file that must never travel."""
        self.seed_counters(self.alice, 5)
        ticket = self.new_ticket(self.alice)
        self.assertEqual(ticket, "SHOP-5")
        self.walk(self.alice, ticket)
        rdir = self.rdir(self.alice, ticket)
        if attachments:
            outside = os.path.join(self.tmp, "downloads")
            self.spec = write(outside, "spec.md", "# Spec\n\nExport everything.\n")
            self.secret = write(outside, "secret.md", "# Private\n")
            self.ok(self.alice, "requirements", "add", "--args",
                    "%s %s" % (self.spec, self.secret))
        # work: a modification, an addition, a deletion and an ignored file
        write(self.alice, "app.py", "line1\nline2 alice\nline3\n")
        write(self.alice, "pkg/new.py", "print('new')\n")
        os.remove(os.path.join(self.alice, "old.py"))
        write(self.alice, "creds.secret", "never packaged\n")
        # the resume set's extras, and what must stay behind
        step = os.path.join(rdir, "steps", "analyze-requirements")
        write(step, "notes.md", "decided: CSV first\n")
        reviewed = lib.changes.snapshot(self.alice)
        lib.write_json(os.path.join(step, "iter-1", "verdict.json"),
                       {"skill": "analyze-requirements", "reviewed_sha": reviewed,
                        "passed": True, "findings": []})
        write(step, "iter-1/lens-correctness.md", "scratch\n")
        write(step, "debug.log", "noise\n")
        write(rdir, "jobs/gate-suite/out.log", "log\n")
        write(rdir, "agents/acs-x.json", "{}\n")
        write(rdir, "lock-events.jsonl", "{}\n")
        write(rdir, "handoff-context.md", "Context saved under %s/steps.\n" % rdir)
        self.reviewed = reviewed
        return ticket, rdir


class RoundTripTest(TwoClonesCase):

    def test_send_then_receive_restores_the_work_and_the_state(self):
        ticket, sender_rdir = self.prepare_sender()
        sender_ws = lib.default_state_root(self.alice)
        before = (tree_digest(sender_ws), git(self.alice, "status", "--porcelain"),
                  git(self.alice, "for-each-ref"), git(self.alice, "diff", "--cached"))
        baseline = lib.read_json(os.path.join(sender_rdir, "baseline.json"))

        sent = self.ok(self.alice, "handoff", "send", "--ticket", ticket,
                       "--note", "done: analysis\nnext: plan", "--attach", self.spec)
        self.assertTrue(sent["pushed"])
        self.assertEqual(sent["ref"], "refs/acs/handoff/SHOP-5")
        self.assertEqual(sent["attachments"], [self.spec])
        self.assertEqual(sent["withheld_attachments"], [self.secret])
        self.assertIn(baseline["tree"], sent["trees"])
        self.assertIn(self.reviewed, sent["trees"])
        self.assertEqual(self.remote_refs(), ["refs/acs/handoff/SHOP-5"])

        # The sender keeps everything: workspace, index, status and refs.
        after = (tree_digest(sender_ws), git(self.alice, "status", "--porcelain"),
                 git(self.alice, "for-each-ref"), git(self.alice, "diff", "--cached"))
        self.assertEqual(before, after)

        # The package: one commit on the base, holding only the resume set.
        commit = sent["commit"]
        self.assertEqual(git(self.alice, "rev-parse", commit + "^").strip(), baseline["base_sha"])
        names = git(self.alice, "ls-tree", "-r", "--name-only", commit).split("\n")
        for path in ("work/app.py", "work/pkg/new.py", "note.md", "manifest.json",
                     "acs/ticket/ticket.json", "acs/run/run.json", "acs/run/baseline.json",
                     "acs/run/handoff-context.md", "acs/run/subject/sources.json",
                     "acs/run/steps/analyze-requirements/state.json",
                     "acs/run/steps/analyze-requirements/result.json",
                     "acs/run/steps/analyze-requirements/notes.md",
                     "acs/run/steps/analyze-requirements/iter-1/verdict.json"):
            self.assertIn(path, names)
        attached = [n for n in names if n.startswith("attachments/")]
        self.assertEqual(len(attached), 1)
        self.assertTrue(attached[0].endswith("spec.md"))
        for never in ("work/old.py", "work/creds.secret", "lock", ".log", "jobs/", "agents/",
                      "sessions/", "lens-correctness", "secret.md", "counters.json"):
            self.assertFalse([n for n in names if never in n], never)
        for name in names:
            if name.startswith("acs/"):
                blob = git(self.alice, "show", "%s:%s" % (commit, name))
                self.assertNotIn(self.alice, blob, name)
        manifest = json.loads(git(self.alice, "show", commit + ":manifest.json"))
        self.assertEqual(manifest["sender"]["name"], "Alice")
        self.assertEqual(manifest["counters_next"], 6)
        self.assertIn("acs/run/handoff-context.md", manifest["rewritten"])

        listed = self.ok(self.bob, "handoff", "list")
        self.assertEqual([r["ticket"] for r in listed["handoffs"]], [ticket])

        got = self.ok(self.bob, "handoff", "receive", ticket)
        self.assertEqual(got["continue_with"], "/acs:create-impl-plan SHOP-5")
        self.assertEqual(got["note"], "done: analysis\nnext: plan")
        self.assertEqual(got["sender"]["email"], "alice@example.com")
        self.assertTrue(got["ref_deleted"])
        self.assertEqual(got["steps"], {"analyze-requirements": "completed"})

        # the work, uncommitted and unstaged
        with open(os.path.join(self.bob, "app.py")) as fh:
            self.assertEqual(fh.read(), "line1\nline2 alice\nline3\n")
        self.assertTrue(os.path.isfile(os.path.join(self.bob, "pkg", "new.py")))
        self.assertFalse(os.path.exists(os.path.join(self.bob, "old.py")))
        self.assertFalse(os.path.exists(os.path.join(self.bob, "creds.secret")))
        self.assertEqual(git(self.bob, "diff", "--cached", "--name-only"), "")
        status = git(self.bob, "status", "--porcelain")
        self.assertIn(" M app.py", status)
        self.assertIn("?? pkg/", status)

        # the state, with this machine's paths
        bob_rdir = self.rdir(self.bob, ticket)
        self.assertEqual(lib.load_run(bob_rdir)["run_id"], ticket)
        self.assertTrue(os.path.isfile(os.path.join(
            bob_rdir, "steps", "analyze-requirements", "notes.md")))
        for gone in ("jobs", "agents", "lock.json", "lock-events.jsonl",
                     "steps/analyze-requirements/debug.log",
                     "steps/analyze-requirements/iter-1/lens-correctness.md"):
            self.assertFalse(os.path.exists(os.path.join(bob_rdir, gone)), gone)
        with open(os.path.join(bob_rdir, "handoff-context.md")) as fh:
            self.assertEqual(fh.read(),
                             "Context saved under %s/steps.\n" % os.path.abspath(bob_rdir))
        sources = lib.read_json(os.path.join(bob_rdir, "subject", "sources.json"))
        docs = [s for s in sources if s["kind"] == "document"]
        spec = [s for s in docs if s["ref"] == self.spec][0]
        secret = [s for s in docs if s["ref"] == self.secret][0]
        self.assertTrue(spec["copy"].startswith(os.path.abspath(bob_rdir)))
        self.assertTrue(os.path.isfile(spec["copy"]))
        self.assertIsNone(secret["copy"])
        self.assertTrue(secret["handoff_withheld"])
        self.assertEqual(got["withheld_attachments"], [self.secret])

        # every tree id the state cites resolves here
        for ident in (baseline["tree"], self.reviewed):
            self.assertEqual(subprocess.run(["git", "-C", self.bob, "cat-file", "-e", ident])
                             .returncode, 0, ident)
        self.assertEqual(git(self.bob, "rev-parse", "refs/acs/received/SHOP-5").strip(), commit)

        # indexes, counters, pointer
        rpath = self.rpath(self.bob)
        self.assertIn(ticket, lib.read_json(os.path.join(rpath, "tickets-index.json"))["tickets"])
        self.assertIn(ticket, [r["run_id"] for r in
                               lib.read_json(os.path.join(rpath, "runs-index.json"))["runs"]])
        counters = lib.read_json(os.path.join(rpath, "counters.json"))
        self.assertEqual(counters["next"], 6)
        self.assertEqual(counters["seed_source"], "handoff")
        self.assertEqual(lib.sessions.current_run_id(rpath, lib.checkout_id(self.bob)), ticket)

        # the ref is gone, and the run resumes here
        self.assertEqual(self.remote_refs(), [])
        self.assertEqual(self.ok(self.bob, "run", "next")["next"], "create-impl-plan")
        self.ok(self.bob, "step", "start", "--step", "create-impl-plan")
        self.assertEqual(self.ok(self.bob, "handoff", "list")["handoffs"], [])

    def test_keep_ref_leaves_the_package_on_the_remote(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        got = self.ok(self.bob, "handoff", "receive", "--ticket", ticket, "--keep-ref")
        self.assertFalse(got["ref_deleted"])
        self.assertEqual(self.remote_refs(), ["refs/acs/handoff/SHOP-5"])

    def test_a_receiver_whose_head_moved_on_still_applies(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        write(self.bob, "app.py", "line0\nline1\nline2\nline3\n")
        write(self.bob, "other.py", "bob\n")
        git(self.bob, "commit", "-qam", "bob moves on")
        git(self.bob, "add", "other.py")
        git(self.bob, "commit", "-qm", "and adds a file")
        self.ok(self.bob, "handoff", "receive", ticket)
        with open(os.path.join(self.bob, "app.py")) as fh:
            self.assertEqual(fh.read(), "line0\nline1\nline2 alice\nline3\n")
        self.assertEqual(git(self.bob, "diff", "--cached", "--name-only"), "")

    def test_a_ticket_without_a_run_travels_alone(self):
        self.seed_counters(self.alice, 3)
        ticket = self.new_ticket(self.alice, "Just filed")
        sent = self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        self.assertIsNone(sent["run_id"])
        self.assertEqual(sent["work_changes"], [])
        got = self.ok(self.bob, "handoff", "receive", ticket)
        self.assertEqual(got["continue_with"], "/acs:ship %s" % ticket)
        self.assertTrue(os.path.isfile(os.path.join(self.rpath(self.bob), ticket, "ticket.json")))
        self.assertFalse(got["work_applied"])

    def test_list_details_reads_each_manifest(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.assertEqual(self.ok(self.bob, "handoff", "list")["count"], 0)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket, "--note", "over to you")
        rows = self.ok(self.bob, "handoff", "list", "--details")["handoffs"]
        self.assertEqual(rows[0]["note"], "over to you")
        self.assertEqual(rows[0]["sender"]["name"], "Alice")
        self.assertEqual(rows[0]["branch"], "main")

    def test_note_file_and_dry_run(self):
        ticket, _rdir = self.prepare_sender()
        note = write(self.tmp, "note.md", "from a file\n")
        dry = self.ok(self.alice, "handoff", "send", "--ticket", ticket, "--dry-run",
                      "--note-file", note)
        self.assertTrue(dry["dry_run"])
        self.assertIsNone(dry["commit"])
        self.assertEqual(self.remote_refs(), [])
        self.assertEqual(sorted(a["ref"] for a in dry["attachments_available"]),
                         sorted([self.spec, self.secret]))
        self.assertIn("work/app.py", dry["package"])
        self.assertIn("run/jobs/gate-suite/out.log", dry["excluded"])
        sent = self.ok(self.alice, "handoff", "send", "--ticket", ticket, "--note-file", note,
                       "--attach", "subject/" + os.path.basename(
                           [a for a in dry["attachments_available"]
                            if a["ref"] == self.spec][0]["name"]))
        self.assertEqual(git(self.alice, "show", sent["commit"] + ":note.md"), "from a file\n")
        self.assertEqual(sent["attachments"], [self.spec])


class RefusalTest(TwoClonesCase):

    def test_an_existing_ref_is_refused_without_replace(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        first = self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        err = self.refused(self.alice, "handoff", "send", "--ticket", ticket)
        self.assertIn("already waiting", err)
        self.assertIn("--replace", err)
        write(self.alice, "app.py", "line1\nline2 again\nline3\n")
        second = self.ok(self.alice, "handoff", "send", "--ticket", ticket, "--replace")
        self.assertTrue(second["replaced"])
        self.assertNotEqual(first["commit"], second["commit"])
        self.assertEqual(git(self.remote, "rev-parse", "refs/acs/handoff/SHOP-5").strip(),
                         second["commit"])

    def test_an_archived_ticket_is_refused(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        rpath = self.rpath(self.alice)
        os.makedirs(os.path.join(rpath, "archive"))
        shutil.move(os.path.join(rpath, ticket), os.path.join(rpath, "archive", ticket))
        self.assertIn("archived", self.refused(self.alice, "handoff", "send", "--ticket", ticket))
        self.assertEqual(self.remote_refs(), [])

    def test_a_run_that_is_not_about_a_ticket_is_refused(self):
        rpath = self.rpath(self.alice)
        wf_path = lib.default_workflow_path()
        lib.create_run(rpath, {"kind": "prompt", "text": "tidy up"},
                       lib.validate_workflow_file(wf_path), wf_path, run_id="SHOP-9")
        err = self.refused(self.alice, "handoff", "send", "--ticket", "SHOP-9")
        self.assertIn("not a ticket", err)

    def test_an_unknown_or_malformed_ticket_is_refused(self):
        self.assertIn("no ticket SHOP-77",
                      self.refused(self.alice, "handoff", "send", "--ticket", "SHOP-77"))
        self.assertIn("not a ticket id",
                      self.refused(self.alice, "handoff", "send", "--ticket", "../main"))
        self.assertIn("not a ticket id",
                      self.refused(self.bob, "handoff", "receive", "OTHER-1"))

    def test_an_attachment_the_run_does_not_hold_is_refused(self):
        ticket, _rdir = self.prepare_sender()
        stray = write(self.tmp, "stray.md")
        err = self.refused(self.alice, "handoff", "send", "--ticket", ticket, "--attach", stray)
        self.assertIn("not one of this run's outside-repo attachments", err)
        self.assertEqual(self.remote_refs(), [])

    def test_note_and_note_file_together_are_refused(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        note = write(self.tmp, "n.md")
        self.assertIn("not both", self.refused(self.alice, "handoff", "send", "--ticket",
                                               ticket, "--note", "x", "--note-file", note))
        self.assertIn("cannot read --note-file", self.refused(
            self.alice, "handoff", "send", "--ticket", ticket, "--note-file",
            os.path.join(self.tmp, "missing.md")))

    def test_nothing_waiting_is_refused(self):
        self.assertIn("no handoff of SHOP-1 is waiting",
                      self.refused(self.bob, "handoff", "receive", "--ticket", "SHOP-1"))
        self.assertIn("name the ticket", self.refused(self.bob, "handoff", "receive"))

    def test_a_dirty_receiver_is_refused_and_nothing_changes(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        write(self.bob, "scratch.txt", "bob's own work\n")
        err = self.refused(self.bob, "handoff", "receive", ticket)
        self.assertIn("not clean", err)
        self.assertIn("scratch.txt", err)
        self.assertFalse(os.path.exists(self.rdir(self.bob, ticket)))
        self.assertEqual(self.remote_refs(), ["refs/acs/handoff/SHOP-5"])
        with open(os.path.join(self.bob, "app.py")) as fh:
            self.assertEqual(fh.read(), "line1\nline2\nline3\n")

    def test_a_conflict_is_reported_with_its_paths_and_nothing_changes(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        write(self.bob, "app.py", "line1\nline2 bob\nline3\n")
        git(self.bob, "commit", "-qam", "bob edits the same line")
        head = git(self.bob, "rev-parse", "HEAD")
        err = self.refused(self.bob, "handoff", "receive", ticket)
        self.assertIn("conflicts with this checkout in: app.py", err)
        self.assertEqual(git(self.bob, "status", "--porcelain"), "")
        self.assertEqual(git(self.bob, "rev-parse", "HEAD"), head)
        self.assertFalse(os.path.exists(self.rdir(self.bob, ticket)))
        self.assertEqual(self.remote_refs(), ["refs/acs/handoff/SHOP-5"])

    def test_an_existing_local_run_is_refused_then_replaced_with_a_backup(self):
        ticket, rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        # Alice kept everything, so receiving her own handoff meets her own run.
        err = self.refused(self.alice, "handoff", "receive", ticket)
        self.assertIn("already holds SHOP-5", err)
        self.assertIn("--replace", err)
        git(self.alice, "stash", "-u", "-q")
        write(rdir, "steps/analyze-requirements/notes.md", "a local edit\n")
        got = self.ok(self.alice, "handoff", "receive", ticket, "--replace")
        self.assertTrue(os.path.isdir(os.path.join(got["backup"], "run")))
        self.assertTrue(os.path.isdir(os.path.join(got["backup"], "ticket")))
        with open(os.path.join(got["backup"], "run", "steps", "analyze-requirements",
                               "notes.md")) as fh:
            self.assertEqual(fh.read(), "a local edit\n")
        with open(os.path.join(rdir, "steps", "analyze-requirements", "notes.md")) as fh:
            self.assertEqual(fh.read(), "decided: CSV first\n")
        with open(os.path.join(self.alice, "app.py")) as fh:
            self.assertEqual(fh.read(), "line1\nline2 alice\nline3\n")


class NoCollateralDamageTest(TwoClonesCase):
    """A receive writes the paths it applies and nothing else: never a reset,
    a clean or an index rewrite -- failed or successful."""

    def test_a_refused_dirty_receive_leaves_index_untracked_and_ignored_files_alone(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        write(self.bob, "loose/notes.txt", "untracked\n")
        write(self.bob, "loose/local.secret", "ignored\n")
        write(self.bob, "app.py", "line1\nline2 staged by bob\nline3\n")
        git(self.bob, "add", "app.py")
        before = self.checkout_state(self.bob)
        self.assertIn("not clean", self.refused(self.bob, "handoff", "receive", ticket))
        self.assertEqual(self.checkout_state(self.bob), before)
        self.assertEqual(git(self.bob, "diff", "--cached", "--name-only"), "app.py\n")

    def test_a_conflicting_receive_leaves_index_reflog_and_ignored_files_alone(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        write(self.bob, "app.py", "line1\nline2 bob\nline3\n")
        git(self.bob, "commit", "-qam", "bob edits the same line")
        write(self.bob, "loose/local.secret", "ignored\n")
        before = self.checkout_state(self.bob)
        self.assertIn("conflicts", self.refused(self.bob, "handoff", "receive", ticket))
        self.assertEqual(self.checkout_state(self.bob), before)

    def test_a_successful_receive_touches_only_the_applied_paths(self):
        ticket, _rdir = self.prepare_sender(attachments=False)
        self.ok(self.alice, "handoff", "send", "--ticket", ticket)
        write(self.bob, "loose/local.secret", "ignored\n")
        before = self.checkout_state(self.bob)
        staged = git(self.bob, "ls-files", "-s")
        got = self.ok(self.bob, "handoff", "receive", ticket)
        after = self.checkout_state(self.bob)
        for key in ("head", "reflog", "files"):
            self.assertEqual(after[key], before[key], key)
        # the only new ignored files are the workspace the receive restored
        self.assertEqual([p for p in after["ignored"].splitlines()
                          if not p.startswith(".acs/state-machine/")],
                         before["ignored"].splitlines())
        self.assertNotIn("reset", after["reflog"])
        self.assertEqual(git(self.bob, "ls-files", "-s"), staged)
        self.assertEqual(sorted(c["path"] for c in got["work_changes"]),
                         ["app.py", "old.py", "pkg/new.py"])
        self.assertFalse(os.path.exists(os.path.join(self.bob, "old.py")))
        self.assertEqual(git(self.bob, "status", "--porcelain").splitlines(),
                         [" M app.py", " D old.py", "?? pkg/"])


class UnitTest(TwoClonesCase):

    def test_counters_are_raised_never_lowered(self):
        rpath = self.rpath(self.bob)
        self.assertIsNone(thr.raise_counters(rpath, None))
        self.assertEqual(thr.raise_counters(rpath, 4), 4)
        self.seed_counters(self.bob, 10)
        self.assertEqual(thr.raise_counters(rpath, 6), 10)
        self.assertEqual(thr.raise_counters(rpath, 12), 12)
        doc = lib.read_json(os.path.join(rpath, "counters.json"))
        self.assertEqual((doc["next"], doc["seed_source"]), (12, "explicit-user"))

    def test_tokens_respect_path_boundaries_and_round_trip(self):
        pairs = [("/w/runs/SHOP-1", "${ACS_RUN_DIR}"), ("/w", "${ACS_REPO_DIR}")]
        text = '"/w/runs/SHOP-1/a.md" and /w/runs/SHOP-10/b and /w2/x and /w'
        out = th.to_tokens(text, pairs)
        self.assertEqual(out, '"${ACS_RUN_DIR}/a.md" and ${ACS_REPO_DIR}/runs/SHOP-10/b '
                              'and /w2/x and ${ACS_REPO_DIR}')
        back = th.from_tokens(out, {"${ACS_RUN_DIR}": "/r/runs/SHOP-1",
                                    "${ACS_REPO_DIR}": "/r"})
        self.assertEqual(back, '"/r/runs/SHOP-1/a.md" and /r/runs/SHOP-10/b and /w2/x and /r')

    def test_the_resume_set_rule(self):
        kept = th._run_file_kept
        for rel in ("run.json", "baseline.json", "subject/sources.json",
                    "steps/code/state.json", "steps/code/plan.md",
                    "steps/review-code/iter-2/verdict.json"):
            self.assertTrue(kept(rel), rel)
        for rel in ("lock.json", "lock-events.jsonl", "jobs/a/out.log", "agents/a.json",
                    "steps/code/iter-1/filemap.json", "steps/code/run.log",
                    "steps/code/sub/x.md", "steps/code/.acs-tmp-1", "subject/1-spec.pdf",
                    "steps/code/lock.json"):
            self.assertFalse(kept(rel), rel)

    def test_object_types_and_cited_ids(self):
        tree = git(self.alice, "rev-parse", "HEAD^{tree}").strip()
        commit = git(self.alice, "rev-parse", "HEAD").strip()
        ids = th._cited([{"tree": tree, "x": {"reviewed_sha": commit}, "tree2": tree},
                         {"reviewed_sha": "0000000"}, {"tree": "f" * 40}])
        self.assertEqual(ids, [tree, commit, "f" * 40])
        self.assertEqual(th.object_types(self.alice, ids),
                         {tree: "tree", commit: "commit", "f" * 40: None})
        self.assertEqual(th.object_types(self.alice, []), {})

    def test_a_manifest_must_be_valid_and_name_the_ticket(self):
        with self.assertRaises(lib.GateError):
            thr._validate_manifest(None, "SHOP-1")
        with self.assertRaises(lib.GateError):
            thr._validate_manifest({"format": 1}, "SHOP-1")
        good = {"format": 1, "ticket": "SHOP-2", "run_id": None, "sender": {},
                "sent_at": "x", "base_sha": None, "work_tree": "t", "files": [],
                "attachments": [], "withheld_attachments": [], "trees": [],
                "path_tokens": {}}
        with self.assertRaisesRegex(lib.GateError, "carries a handoff of SHOP-2"):
            thr._validate_manifest(good, "SHOP-1")
        with self.assertRaisesRegex(lib.GateError, "format"):
            thr._validate_manifest(dict(good, format=99), "SHOP-2")
        thr._validate_manifest(good, "SHOP-2")

    def test_an_unreachable_remote_is_an_error_not_an_empty_list(self):
        git(self.bob, "remote", "set-url", "origin", os.path.join(self.tmp, "gone.git"))
        self.assertIn("cannot read origin", self.refused(self.bob, "handoff", "list"))


if __name__ == "__main__":
    unittest.main()
