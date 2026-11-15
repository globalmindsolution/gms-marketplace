"""ADR-0130: document status moves and the versionable-document lister.

- design_docs.set_status records who (`status_by`), when (`status_at`) and,
  only when given, why (`status_reason`) of the last move.
- design_docs.set_status_many / `acs.py design status --set` is ATOMIC: every
  target is checked first and one refusal writes none.
- design_docs.list_documents / `acs.py design list` walks the Discovery and
  Design documents, groups them by phase and doc set (the doc_sets helper
  commit_plan shares) and gives each its legal moves.

Run:  python3 -m unittest tests.acs.test_design_doc_status -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))

import acs_lib as lib  # noqa: E402
from acs_lib import commit_plan, doc_sets  # noqa: E402
from acs_lib import design_docs as D  # noqa: E402
import acs_design_commands  # noqa: E402


def block(status="proposed", version=1, feature=None, extra=""):
    lines = ["---", "status: %s" % status, "version: %d" % version, 'tickets: ["SHOP-1"]']
    if feature:
        lines.append("feature: %s" % feature)
    return "\n".join(lines) + "\n" + extra + "---\n\n# Doc\n\nBody line.\n"


class TreeCase(unittest.TestCase):
    """A temp repo laid out with the default doc_layout folders."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-docstatus-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def put(self, rel, text=None):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(block() if text is None else text)
        return path

    def raw(self, rel):
        with open(os.path.join(self.root, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()

    def seed(self):
        self.put("docs/product/prd.md")
        self.put("docs/product/roadmap.md", "# Roadmap\n\nNo block yet.\n")
        self.put("docs/product/features/wishlist/analysis.md", block("approved", 2))
        self.put("docs/product/features/export/analysis.md")
        self.put("docs/product/features/export/notes.md")             # not an analysis
        self.put("docs/architecture/hld/tech-stack.md", block("implemented", 3))
        self.put("docs/architecture/hld/context.md", block("deprecated"))
        self.put("docs/architecture/hld/README.md", "# HLD\n")        # unversioned README
        self.put("docs/architecture/hld/deep/nested.md")              # hld/*.md only
        self.put("docs/architecture/lld/wishlist/data/erd.md", block(feature="wishlist"))
        self.put("docs/architecture/lld/wishlist/flows/add/add-item.md",
                 block("approved", feature="wishlist"))
        self.put("docs/architecture/lld/wishlist/api/README.md",
                 block(feature="wishlist"))                            # versioned README
        self.put("docs/architecture/lld/wishlist/SHOP-7/design.md")    # per-run record
        self.put("docs/architecture/lld/wishlist/notes.md")            # outside living dirs
        self.put("docs/architecture/lld/export/components/ui.md", "---\nstatus: [\n---\n")
        self.put("docs/development/wishlist/SHOP-7/plan.md")           # Development phase


class SetStatusMetadataTest(TreeCase):

    def test_records_by_at_and_reason(self):
        path = self.put("docs/architecture/hld/context.md")
        front = D.set_status(path, "approved", "SHOP-2", by="Ana <ana@example.com>",
                             at="2026-10-05T09:12:00Z", reason="reviewed in PR #12")
        self.assertEqual(front["status_by"], "Ana <ana@example.com>")
        stored = D.read(path)[0]
        self.assertEqual(stored["status"], "approved")
        self.assertEqual(stored["tickets"], ["SHOP-1", "SHOP-2"])
        self.assertEqual(stored["status_at"], "2026-10-05T09:12:00Z")
        self.assertEqual(stored["status_reason"], "reviewed in PR #12")
        self.assertEqual(D.check(path)["problems"], [])
        # The block keeps its key order: the ADR-0122 keys, then the move's.
        keys = [line.split(":", 1)[0] for line in self.raw("docs/architecture/hld/context.md")
                .split("---")[1].strip().splitlines() if not line.startswith(" ")]
        self.assertEqual(keys, ["status", "version", "tickets", "status_by", "status_at",
                                "status_reason"])

    def test_at_defaults_to_now_utc_and_reason_only_when_given(self):
        path = self.put("docs/architecture/hld/context.md")
        D.set_status(path, "approved", by="Ana", reason="first")
        D.set_status(path, "deprecated", by="Bo")
        front = D.read(path)[0]
        self.assertRegex(front["status_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(front["status_by"], "Bo")
        self.assertNotIn("status_reason", front)   # a stale reason is not kept

    def test_a_multiline_reason_is_folded(self):
        path = self.put("docs/architecture/hld/context.md")
        D.set_status(path, "deprecated", by="Ana", reason="split into\n  two docs: a # b")
        self.assertEqual(D.read(path)[0]["status_reason"], "split into two docs: a # b")

    def test_a_bad_status_at_is_refused_and_nothing_written(self):
        path = self.put("docs/architecture/hld/context.md")
        before = self.raw("docs/architecture/hld/context.md")
        with self.assertRaises(lib.GateError):
            D.set_status(path, "approved", by="Ana", at="yesterday")
        with self.assertRaises(lib.GateError):
            D.set_status_many([path], "approved", by="Ana", at="yesterday")
        self.assertEqual(self.raw("docs/architecture/hld/context.md"), before)

    def test_check_names_bad_metadata(self):
        path = self.put("docs/architecture/hld/x.md",
                        block(extra='status_by: ""\nstatus_at: "monday"\n'))
        found = " ".join(D.check(path)["problems"])
        self.assertIn("status_by", found)
        self.assertIn("status_at", found)

    def test_a_bump_that_reopens_drops_the_last_move(self):
        path = self.put("docs/architecture/hld/context.md")
        D.set_status(path, "approved", by="Ana", reason="ok")
        front = D.bump(path, "SHOP-3")
        self.assertEqual((front["status"], front["version"]), ("proposed", 2))
        for key in D.STATUS_META_KEYS:
            self.assertNotIn(key, D.read(path)[0])

    def test_the_metadata_keys_survive_the_front_matter_reader(self):
        # The yamlsubset key regex accepts the underscore keys (they round-trip).
        path = self.put("docs/architecture/hld/context.md")
        D.set_status(path, "approved", by='Ana "A" <a@b.c>', at="2026-10-05T09:12:00Z")
        self.assertEqual(D.read(path)[0]["status_by"], 'Ana "A" <a@b.c>')


class AtomicStatusTest(TreeCase):

    def test_one_refusal_writes_none_and_names_every_refused_doc(self):
        good = self.put("docs/architecture/hld/a.md")
        illegal = self.put("docs/architecture/hld/b.md", block("deprecated"))
        bare = self.put("docs/architecture/hld/c.md", "# no block\n")
        missing = os.path.join(self.root, "docs", "architecture", "hld", "gone.md")
        before = {p: open(p, encoding="utf-8").read() for p in (good, illegal, bare)}
        with self.assertRaises(lib.GateError) as ctx:
            D.set_status_many([good, illegal, bare, missing], "approved", by="Ana")
        message = str(ctx.exception)
        self.assertIn("refused 3 of 4", message)
        self.assertIn("nothing was written", message)
        self.assertIn("b.md: deprecated -> approved is not a legal transition", message)
        self.assertIn("c.md: no version front matter", message)
        self.assertIn("gone.md: no such document", message)
        self.assertNotIn("a.md:", message)
        for path, text in before.items():
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), text)

    def test_all_legal_moves_share_one_timestamp(self):
        a = self.put("docs/architecture/hld/a.md")
        b = self.put("docs/architecture/lld/w/data/b.md", block(feature="w"))
        out = D.set_status_many([a, b, a], "approved", by="Ana")
        self.assertEqual([f["path"] for f in out], [a, b])   # duplicates collapse
        self.assertEqual(D.read(a)[0]["status_at"], D.read(b)[0]["status_at"])

    def test_a_doc_already_at_the_target_is_left_untouched(self):
        a = self.put("docs/architecture/hld/a.md")
        b = self.put("docs/architecture/hld/b.md")
        D.set_status_many([a], "approved", by="Ana", reason="reviewed in sprint 9")
        with open(a, encoding="utf-8") as fh:
            before = fh.read()
        out = D.set_status_many([a, b], "approved", by="Bo")
        with open(a, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)   # who, when and why are kept
        self.assertEqual([(f["path"], f.get("unchanged", False)) for f in out],
                         [(a, True), (b, False)])
        self.assertEqual(D.read(b)[0]["status_by"], "Bo")

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(lib.GateError):
            D.set_status_many([self.put("docs/architecture/hld/a.md")], "done")


class ListDocumentsTest(TreeCase):

    def listing(self, **kw):
        return D.list_documents(self.root, **kw)

    def test_groups_by_phase_then_doc_set(self):
        self.seed()
        out = self.listing()
        self.assertTrue(out["ok"])
        self.assertEqual([(g["phase"], g["key"]) for g in out["groups"]], [
            ("discovery", "prd"),
            ("discovery", "prd/features/export"),
            ("discovery", "prd/features/wishlist"),
            ("design", "hld"),
            ("design", "lld/export"),
            ("design", "lld/wishlist"),
        ])
        by_key = {g["key"]: g for g in out["groups"]}
        self.assertEqual(by_key["prd/features/wishlist"]["feature"], "wishlist")
        self.assertEqual(by_key["lld/wishlist"]["feature"], "wishlist")
        self.assertEqual(by_key["lld/wishlist"]["label"], "LLD wishlist")
        self.assertNotIn("feature", by_key["prd"])
        self.assertNotIn("feature", by_key["hld"])

    def test_walks_only_the_living_documents(self):
        self.seed()
        paths = [d["path"] for g in self.listing()["groups"] for d in g["docs"]]
        self.assertEqual(paths, [
            "docs/product/prd.md",
            "docs/product/roadmap.md",
            "docs/product/features/export/analysis.md",
            "docs/product/features/wishlist/analysis.md",
            "docs/architecture/hld/context.md",
            "docs/architecture/hld/tech-stack.md",
            "docs/architecture/lld/export/components/ui.md",
            "docs/architecture/lld/wishlist/api/README.md",
            "docs/architecture/lld/wishlist/data/erd.md",
            "docs/architecture/lld/wishlist/flows/add/add-item.md",
        ])

    def test_each_entry_carries_its_legal_moves(self):
        self.seed()
        docs = {d["path"]: d for g in self.listing()["groups"] for d in g["docs"]}
        prd = docs["docs/product/prd.md"]
        self.assertEqual(set(prd), {"path", "status", "version", "problems", "allowed"})
        self.assertEqual((prd["status"], prd["version"], prd["problems"]), ("proposed", 1, []))
        self.assertEqual(prd["allowed"], ["approved", "deprecated"])
        self.assertEqual(docs["docs/product/features/wishlist/analysis.md"]["allowed"],
                         ["proposed", "implemented", "deprecated"])
        self.assertEqual(docs["docs/architecture/hld/tech-stack.md"]["allowed"],
                         ["proposed", "deprecated"])
        self.assertEqual(docs["docs/architecture/hld/context.md"]["allowed"], [])
        roadmap = docs["docs/product/roadmap.md"]
        self.assertEqual((roadmap["status"], roadmap["allowed"]), (None, []))
        self.assertTrue(roadmap["problems"])
        broken = docs["docs/architecture/lld/export/components/ui.md"]
        self.assertEqual((broken["status"], broken["allowed"]), (None, []))
        self.assertIn("does not parse", broken["problems"][0])

    def test_phase_and_feature_filters(self):
        self.seed()
        self.assertEqual({g["phase"] for g in self.listing(phase="design")["groups"]},
                         {"design"})
        self.assertEqual([g["key"] for g in self.listing(phase="discovery")["groups"]],
                         ["prd", "prd/features/export", "prd/features/wishlist"])
        self.assertEqual([g["key"] for g in self.listing(feature="wishlist")["groups"]],
                         ["prd/features/wishlist", "lld/wishlist"])
        self.assertEqual([g["key"] for g in self.listing(phase="design",
                                                         feature="wishlist")["groups"]],
                         ["lld/wishlist"])
        with self.assertRaises(lib.GateError):
            self.listing(phase="development")

    def test_follows_the_configured_doc_layout(self):
        subprocess.run(["git", "init", "-q", self.root], check=True)
        os.makedirs(os.path.join(self.root, ".acs"))
        with open(os.path.join(self.root, ".acs", "settings.json"), "w") as fh:
            json.dump({"docs": {"prd_dir": "spec", "architecture_dir": "arch"}}, fh)
        self.put("spec/prd.md")
        self.put("arch/hld/overview.md")
        self.put("docs/product/prd.md")   # not the configured PRD folder
        paths = [d["path"] for g in self.listing()["groups"] for d in g["docs"]]
        self.assertEqual(paths, ["spec/prd.md", "arch/hld/overview.md"])

    def test_an_empty_repo_lists_nothing(self):
        self.assertEqual(self.listing(), {"ok": True, "groups": []})


class EvidenceSidecarTest(TreeCase):
    """A `<doc>.evidence.md` sidecar (the architect charter's citations) carries no
    version block and is not a design document: the lister leaves it out, and a
    batch move that names it -- a shell glob over a folder does -- skips it rather
    than refusing every document beside it."""

    def seed_flows(self):
        doc = self.put("docs/architecture/lld/wishlist/flows/add-item.md",
                       block(feature="wishlist"))
        sidecar = self.put("docs/architecture/lld/wishlist/flows/add-item.evidence.md",
                           "# Evidence\n\n- add-item.md:3 -- src/cart.py:12\n")
        nested = self.put("docs/architecture/lld/wishlist/flows/add/remove.evidence.md",
                          "# Evidence\n")
        return doc, sidecar, nested

    def test_a_sidecar_is_not_listed(self):
        self.seed_flows()
        self.put("docs/architecture/hld/context.evidence.md", "# Evidence\n")
        paths = [d["path"] for g in D.list_documents(self.root)["groups"] for d in g["docs"]]
        self.assertEqual(paths, ["docs/architecture/lld/wishlist/flows/add-item.md"])
        self.assertFalse([p for p in paths if p.endswith(".evidence.md")])

    def test_a_listed_batch_moves_without_the_sidecar(self):
        doc, sidecar, _ = self.seed_flows()
        listed = [os.path.join(self.root, *d["path"].split("/"))
                  for g in D.list_documents(self.root)["groups"] for d in g["docs"]]
        out = D.set_status_many(listed, "approved", by="Ana")
        self.assertEqual([f["path"] for f in out], [doc])
        self.assertEqual(D.read(doc)[0]["status"], "approved")

    def test_a_batch_naming_a_sidecar_skips_it_and_moves_the_rest(self):
        doc, sidecar, nested = self.seed_flows()
        with open(sidecar, encoding="utf-8") as fh:
            before = fh.read()
        out = D.set_status_many([doc, sidecar, nested], "approved", by="Ana")
        self.assertEqual(D.read(doc)[0]["status"], "approved")
        with open(sidecar, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)   # never given a block
        by_path = {f["path"]: f for f in out}
        self.assertEqual(list(by_path), [doc, sidecar, nested])
        self.assertNotIn("skipped", by_path[doc])
        for path in (sidecar, nested):
            self.assertIn("evidence sidecar", by_path[path]["skipped"])
            self.assertNotIn("status", by_path[path])

    def test_a_refusal_still_names_only_the_documents(self):
        doc, sidecar, _ = self.seed_flows()
        bad = self.put("docs/architecture/lld/wishlist/flows/old.md", block("deprecated"))
        with self.assertRaises(lib.GateError) as ctx:
            D.set_status_many([doc, sidecar, bad], "approved", by="Ana")
        message = str(ctx.exception)
        self.assertIn("refused 1 of 2", message)
        self.assertNotIn("evidence", message)

    def test_is_sidecar(self):
        self.assertTrue(D.is_sidecar("lld/a/flows/x.evidence.md"))
        self.assertTrue(D.is_sidecar("X.EVIDENCE.MD"))
        self.assertFalse(D.is_sidecar("lld/a/flows/evidence.md"))
        self.assertFalse(D.is_sidecar("lld/a/flows/x.md"))


class DocSetsSharedTest(unittest.TestCase):

    def test_commit_plan_uses_the_shared_helper(self):
        self.assertIs(commit_plan.doc_set, doc_sets.doc_set)
        self.assertIs(commit_plan._doc_order, doc_sets.doc_order)
        self.assertEqual(commit_plan.doc_set("docs/architecture/lld/x/SHOP-1/design.md"),
                         ("lld/x/SHOP-1", "SHOP-1 design records"))


class DefaultActorTest(unittest.TestCase):

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="acs-actor-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                   GIT_CONFIG_NOSYSTEM="1")
        self.patch = mock.patch.dict(os.environ, env, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def config(self, key, value):
        subprocess.run(["git", "-C", self.repo, "config", key, value], check=True)

    def test_name_and_email(self):
        self.config("user.name", "Ana Li")
        self.config("user.email", "ana@example.com")
        self.assertEqual(acs_design_commands.default_actor(self.repo), "Ana Li <ana@example.com>")

    def test_one_half(self):
        self.config("user.email", "ana@example.com")
        self.assertEqual(acs_design_commands.default_actor(self.repo), "ana@example.com")

    def test_unknown(self):
        self.assertEqual(acs_design_commands.default_actor(self.repo), "unknown")


class CliTest(AcsWorkspaceCase):

    def put(self, rel, text=None):
        path = os.path.join(self.repo, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(block() if text is None else text)
        return path

    def acs(self, *args, cwd=None):
        return self.run_script("acs.py", "design", *args, cwd=cwd)

    def test_status_records_by_and_reason(self):
        path = self.put("docs/architecture/hld/overview.md")
        out = self.acs("status", "--set", "deprecated", "--by", "Ana", "--reason", "merged",
                       path)
        self.assertEqual(out.returncode, 0, out.stderr)
        files = json.loads(out.stdout)["files"]
        self.assertEqual(files[0]["path"], path)
        self.assertEqual((files[0]["status_by"], files[0]["status_reason"]), ("Ana", "merged"))
        self.assertIn("status_at", D.read(path)[0])

    def test_status_by_defaults_to_the_git_identity(self):
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "Ana Li"], check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.email", "ana@x.io"], check=True)
        path = self.put("docs/architecture/hld/overview.md")
        out = self.acs("status", "--set", "approved", path)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(D.read(path)[0]["status_by"], "Ana Li <ana@x.io>")
        self.assertNotIn("status_reason", D.read(path)[0])

    def test_status_is_atomic_across_documents(self):
        good = self.put("docs/architecture/hld/a.md")
        bad = self.put("docs/architecture/hld/b.md", block("deprecated"))
        before = [open(p, encoding="utf-8").read() for p in (good, bad)]
        out = self.acs("status", "--set", "approved", "--by", "Ana", good, bad)
        self.assertEqual(out.returncode, 2)
        self.assertIn("nothing was written", out.stderr)
        self.assertIn("b.md: deprecated -> approved", out.stderr)
        self.assertEqual([open(p, encoding="utf-8").read() for p in (good, bad)], before)

    def test_a_globbed_folder_moves_without_its_sidecars(self):
        doc = self.put("docs/architecture/lld/w/flows/checkout.md", block(feature="w"))
        sidecar = self.put("docs/architecture/lld/w/flows/checkout.evidence.md", "# Evidence\n")
        out = self.acs("status", "--set", "approved", "--by", "Ana", doc, sidecar)
        self.assertEqual(out.returncode, 0, out.stderr)
        files = json.loads(out.stdout)["files"]
        self.assertEqual([f["path"] for f in files], [doc, sidecar])
        self.assertEqual(D.read(doc)[0]["status"], "approved")
        self.assertIn("skipped", files[1])
        listed = json.loads(self.acs("list", "--root", self.repo).stdout)
        self.assertEqual([d["path"] for g in listed["groups"] for d in g["docs"]],
                         ["docs/architecture/lld/w/flows/checkout.md"])

    def test_list_from_the_checkout_and_from_root(self):
        self.put("docs/product/prd.md")
        self.put("docs/architecture/lld/w/data/erd.md", block(feature="w"))
        self.put("docs/architecture/lld/w/SHOP-1/design.md")
        sub = os.path.join(self.repo, "docs")
        out = self.acs("list", cwd=sub)
        self.assertEqual(out.returncode, 0, out.stderr)
        listing = json.loads(out.stdout)
        self.assertEqual([(g["phase"], g["key"], [d["path"] for d in g["docs"]])
                          for g in listing["groups"]],
                         [("discovery", "prd", ["docs/product/prd.md"]),
                          ("design", "lld/w", ["docs/architecture/lld/w/data/erd.md"])])
        narrowed = json.loads(self.acs("list", "--phase", "design", "--feature", "w",
                                       "--root", self.repo, cwd=self.tmp).stdout)
        self.assertEqual([g["key"] for g in narrowed["groups"]], ["lld/w"])

    def test_list_refuses_a_missing_root(self):
        out = self.acs("list", "--root", os.path.join(self.tmp, "nope"))
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
