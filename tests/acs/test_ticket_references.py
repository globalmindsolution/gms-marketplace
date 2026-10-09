"""ADR-0140: the ticket, CLI, tracker and context halves of ticket references.

`test_doc_links.py` pins the lookup itself; this module pins what is built on
it, end to end through the real CLIs:

  * `references` on the ticket: the schema, `new_ticket_doc`, `ticket save`,
    and its place in ticket.md's front matter;
  * `record-external.py --url`, so a synced issue's URL is kept;
  * `acs.py ticket references` -- its JSON, `--write`, `--render`;
  * `acs.py tracker sync` -- the issue body gets the block before it is created;
  * `acs.py tracker refresh` with a replayed gh -- only the marker block
    changes, a failure is non-critical, `--pending` selects correctly, and
    `--dry-run` never edits;
  * the Start context's `references` and requirements.md's `## References`.

Run:  python3 -m unittest tests.acs.test_ticket_references -v
"""

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import artifacts, doc_links, schemasubset  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402

PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
GITHUB = "https://github.com/acme/shop.git"
TEMPLATES = ("epic-default", "story-default", "task-default", "bug-default")

REF = {"kind": "lld", "path": "docs/architecture/lld/wishlist/api/x.md", "title": "X",
       "status": "approved", "version": 2, "published": True,
       "url": "https://github.com/acme/shop/blob/main/docs/architecture/lld/wishlist/api/x.md"}


def schema(name):
    with open(os.path.join(PLUGIN, "schemas", name), encoding="utf-8") as fh:
        return json.load(fh)


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, "-c", "user.email=t@example.com",
                           "-c", "user.name=t", "-c", "commit.gpgsign=false"] + list(args),
                          check=True, capture_output=True, text=True).stdout.strip()


def write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# ---------------------------------------------------------------------------
# The field
# ---------------------------------------------------------------------------

class TicketFieldTest(unittest.TestCase):

    def doc(self, **extra):
        return dict(lib.new_ticket_doc("SHOP-2", "Share", "story"), **extra)

    def test_the_schema_declares_an_optional_array_of_entries(self):
        prop = schema("ticket.schema.json")["properties"]["references"]
        self.assertEqual(prop["type"], "array")
        self.assertEqual(prop["items"]["required"], ["kind", "path"])
        self.assertTrue(prop["items"]["additionalProperties"])
        self.assertNotIn("references", schema("ticket.schema.json")["required"])
        self.assertEqual(schemasubset.schema_errors(schema("ticket.schema.json"),
                                                    self.doc(references=[REF])), [])
        self.assertTrue(schemasubset.schema_errors(schema("ticket.schema.json"),
                                                   self.doc(references=[{"kind": "lld"}])))

    def test_jsonschema_agrees(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        jsonschema.validate(self.doc(references=[REF]), schema("ticket.schema.json"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.doc(references=[{"path": "x"}]), schema("ticket.schema.json"))

    def test_new_ticket_doc_takes_it_and_omits_it_when_absent(self):
        self.assertNotIn("references", lib.new_ticket_doc("SHOP-2", "Share", "story"))
        doc = lib.new_ticket_doc("SHOP-2", "Share", "story", references=[REF])
        self.assertEqual(doc["references"], [REF])

    def test_check_references_refuses_a_malformed_list(self):
        lib.check_references([REF])
        for bad in ({"kind": "lld"}, [{"kind": "lld"}], [{"kind": 1, "path": "x"}], ["x"]):
            with self.assertRaises(lib.GateError):
                lib.check_references(bad)

    def test_ticket_md_puts_it_after_features_and_round_trips(self):
        order = artifacts._FRONT_MATTER_ORDER
        self.assertEqual(order.index("references"), order.index("features") + 1)
        doc = self.doc(features=["wishlist"], references=[REF])
        parsed = artifacts.parse_ticket_md(artifacts.render_ticket_md(doc))
        self.assertEqual(parsed["references"], [REF])


class TemplatesTest(unittest.TestCase):

    def test_every_ticket_template_has_an_empty_references_section_before_notes(self):
        for name in TEMPLATES:
            with open(os.path.join(PLUGIN, "templates", name + ".md"), encoding="utf-8") as fh:
                body = fh.read()
            headings = [line[3:].strip() for line in body.splitlines() if line.startswith("## ")]
            self.assertEqual(headings[-2:], ["References", "Notes"], name)
            self.assertEqual(doc_links.current_block(body), "", name)
            self.assertLess(body.index(doc_links.END_MARKER), body.index("## Notes"), name)
            self.assertEqual(doc_links.apply_block(body, ""), body.replace(
                doc_links.START_MARKER + "\n" + doc_links.END_MARKER,
                doc_links.START_MARKER + "\n\n" + doc_links.END_MARKER), name)


# ---------------------------------------------------------------------------
# The CLIs
# ---------------------------------------------------------------------------

class CliCase(AcsWorkspaceCase):
    """A workspace whose origin is a temp bare repo reached through
    `url.<bare>.insteadOf` (so links read as GitHub's), with one feature's
    documents in the standard layout."""

    def setUp(self):
        super().setUp()
        self.bare = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.bare], check=True)
        git(self.repo, "config", "url.%s.insteadOf" % self.bare, GITHUB)
        git(self.repo, "checkout", "-q", "-b", "main")
        write(self.repo, "docs/product/prd.md", "# PRD\n\n### Feature: Wishlist\n\nShare.\n")
        write(self.repo, "docs/architecture/lld/wishlist/api/endpoints.md", "# Endpoints\n")
        git(self.repo, "add", "docs")
        git(self.repo, "commit", "-q", "-m", "docs")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "remote", "set-head", "origin", "main")
        # Written after the push: on disk, not on origin/main.
        write(self.repo, "docs/architecture/lld/wishlist/flows/share.md", "# Share flow\n")

    def json_of(self, *args, code=0):
        out = self.run_script("acs.py", *args)
        self.assertEqual(out.returncode, code, out.stderr)
        return json.loads(out.stdout) if code == 0 else out

    def ticket_doc(self, ticket_id):
        return lib.load_ticket(self.tdir(ticket_id))

    def patch_ticket(self, ticket_id, **fields):
        tdir = self.tdir(ticket_id)
        doc = lib.load_ticket(tdir)
        doc.update(fields)
        lib.save_ticket(tdir, doc)


class TicketReferencesCliTest(CliCase):

    def test_a_tickets_references_with_links_and_pending_entries(self):
        ticket = self.new_ticket("Share", "story", "--features", "wishlist")
        out = self.json_of("ticket", "references", "--ticket", ticket)
        self.assertEqual(set(out) >= {"references", "default_branch", "web_base",
                                      "remote_checked", "ticket_id", "written"}, True)
        self.assertEqual(out["default_branch"], "main")
        self.assertEqual(out["web_base"], "https://github.com/acme/shop")
        self.assertFalse(out["written"])
        refs = {r["path"]: r for r in out["references"]}
        self.assertEqual(refs["docs/product/prd.md"]["url"],
                         "https://github.com/acme/shop/blob/main/docs/product/prd.md")
        self.assertIsNone(refs["docs/architecture/lld/wishlist/flows/share.md"]["url"])
        self.assertNotIn("references", self.ticket_doc(ticket))

    def test_write_stores_them_and_render_prints_the_block(self):
        ticket = self.new_ticket("Share", "story", "--features", "wishlist")
        out = self.json_of("ticket", "references", "--ticket", ticket, "--write", "--render",
                           "--fetch")
        self.assertTrue(out["written"])
        self.assertTrue(out["remote_checked"])
        self.assertEqual(self.ticket_doc(ticket)["references"], out["references"])
        self.assertIn("- `docs/architecture/lld/wishlist/flows/share.md`: lld, pending: "
                      "not on `main` yet", out["block"])
        self.assertIn("- [PRD](https://github.com/acme/shop/blob/main/docs/"
                      "product/prd.md): prd", out["block"])

    def test_features_with_a_parent_for_a_ticket_not_minted_yet(self):
        epic = self.new_ticket("Wishlist", "epic", "--features", "wishlist")
        write(self.repo, "docs/architecture/lld/wishlist/%s/tech-design.md" % epic, "# Epic\n")
        out = self.json_of("ticket", "references", "--features", "wishlist", "--parent", epic)
        self.assertEqual(out["features"], ["wishlist"])
        self.assertIn("docs/architecture/lld/wishlist/%s/tech-design.md" % epic,
                      [r["path"] for r in out["references"] if r["kind"] == "design"])

    def test_the_subject_is_exactly_one_of_ticket_or_features(self):
        ticket = self.new_ticket("Share", "story")
        for args in ((), ("--ticket", ticket, "--features", "wishlist")):
            out = self.json_of("ticket", "references", *args, code=2)
            self.assertIn("exactly one of --ticket", out.stderr)
        out = self.json_of("ticket", "references", "--features", "wishlist", "--write", code=2)
        self.assertIn("--write", out.stderr)
        out = self.json_of("ticket", "references", "--features", "Not A Slug", code=2)
        self.assertIn("slug", out.stderr)

    def test_ticket_save_accepts_references_and_refuses_a_bad_shape(self):
        ticket = self.new_ticket("Share", "story")
        out = self.run_script("acs.py", "ticket", "save", "--ticket", ticket,
                              stdin=json.dumps({"references": [REF]}))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.ticket_doc(ticket)["references"], [REF])
        out = self.run_script("acs.py", "ticket", "save", "--ticket", ticket,
                              stdin=json.dumps({"references": [{"title": "no kind"}]}))
        self.assertEqual(out.returncode, 2)
        self.assertIn("references", out.stderr)


class RecordExternalUrlTest(CliCase):

    def test_the_url_is_kept_when_given(self):
        ticket = self.new_ticket("Share", "story")
        out = self.run_script("record-external.py", "--ticket", ticket, "--provider", "github",
                              "--key", "9", "--url", "https://github.com/acme/shop/issues/9")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.ticket_doc(ticket)["external"],
                         {"provider": "github", "key": "9",
                          "url": "https://github.com/acme/shop/issues/9"})
        self.assertEqual(json.loads(out.stdout)["external"]["url"],
                         "https://github.com/acme/shop/issues/9")

    def test_without_url_the_mapping_is_unchanged(self):
        ticket = self.new_ticket("Share", "story")
        out = self.run_script("record-external.py", "--ticket", ticket, "--provider", "github",
                              "--key", "9")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.ticket_doc(ticket)["external"], {"provider": "github", "key": "9"})


ISSUE_BODY = ("## Description\n\nShare.\n\n## References\n\n" + doc_links.START_MARKER + "\n"
              "- `docs/old.md`: lld, pending: not on `main` yet\n" + doc_links.END_MARKER
              + "\n\nEdited on the tracker.\n\nacs-ticket: SHOP-1\n")


class TrackerCliCase(CliCase):

    def setUp(self):
        super().setUp()
        self.write_settings({"ticket_prefix": "SHOP", "tests": {"coverage": 90},
                             "tracker": {"provider": "github", "github": {"owner": "acme"}}})
        self.replay = os.path.join(self.tmp, "gh.json")
        self.record()

    def record(self, **over):
        recorded = {
            "gh issue create": [0, "https://github.com/acme/shop/issues/9\n", ""],
            "gh issue view": [0, json.dumps({"body": ISSUE_BODY}), ""],
            "gh issue edit": [0, "", ""],
            "gh label create": [0, "", ""],
        }
        recorded.update(over)
        with open(self.replay, "w", encoding="utf-8") as fh:
            json.dump(recorded, fh)

    def synced(self, title="Share", features="wishlist", references=None):
        ticket = self.new_ticket(title, "story", "--features", features)
        fields = {"external": {"provider": "github", "key": "9"}}
        if references is not None:
            fields["references"] = references
        self.patch_ticket(ticket, **fields)
        return ticket


class TrackerSyncBodyTest(TrackerCliCase):

    def test_the_issue_body_gets_the_block_before_the_issue_is_created(self):
        ticket = self.new_ticket("Share", "story", "--features", "wishlist")
        body = write(self.tdir(ticket), "tracker-body.md",
                     "## Description\n\nShare.\n\n## Notes\n\nacs-ticket: %s\n" % ticket)
        out = self.json_of("tracker", "sync", "--ticket", ticket, "--gh-replay", self.replay)
        self.assertEqual(out["synced"][ticket]["key"], "9")
        with open(body, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("## References\n\n" + doc_links.START_MARKER, text)
        self.assertIn("(https://github.com/acme/shop/blob/main/docs/product/prd.md): prd", text)
        self.assertTrue(text.rstrip().endswith("acs-ticket: %s" % ticket))
        self.assertTrue(self.ticket_doc(ticket)["references"])
        self.assertIn("remote_checked", out)

    def test_a_dry_run_leaves_the_body_alone(self):
        ticket = self.new_ticket("Share", "story", "--features", "wishlist")
        body = write(self.tdir(ticket), "tracker-body.md", "## Description\n\nShare.\n")
        self.json_of("tracker", "sync", "--ticket", ticket, "--dry-run")
        with open(body, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "## Description\n\nShare.\n")


class TrackerRefreshTest(TrackerCliCase):

    def test_only_the_marker_block_of_the_issue_changes(self):
        ticket = self.synced()
        out = self.json_of("tracker", "refresh", "--ticket", ticket, "--gh-replay", self.replay)
        self.assertEqual(out["findings"], [])
        row = out["tickets"][0]
        self.assertEqual((row["ticket_id"], row["changed"], row["edited"]), (ticket, True, True))
        self.assertTrue(row["stored"])
        self.assertEqual(row["pending"], 1)
        self.assertIn("gh issue view 9 --json body", out["calls"])
        self.assertTrue([c for c in out["calls"] if c.startswith("gh issue edit 9 --body-file")])
        stored = self.ticket_doc(ticket)["references"]
        self.assertIn("docs/architecture/lld/wishlist/flows/share.md",
                      [r["path"] for r in stored if not r["published"]])

    def test_a_failed_gh_call_is_a_finding_not_a_stop(self):
        self.record(**{"gh issue view": [1, "", "HTTP 404: Not Found"]})
        ticket = self.synced()
        out = self.json_of("tracker", "refresh", "--ticket", ticket, "--gh-replay", self.replay)
        self.assertEqual([f["severity"] for f in out["findings"]], ["info"])
        self.assertEqual(out["findings"][0]["ticket_id"], ticket)
        self.assertFalse(out["tickets"][0]["edited"])
        self.assertTrue(self.ticket_doc(ticket)["references"])

    def test_dry_run_makes_no_edit_and_stores_nothing(self):
        ticket = self.synced()
        out = self.json_of("tracker", "refresh", "--ticket", ticket, "--dry-run",
                           "--gh-replay", self.replay)
        self.assertTrue(out["dry_run"])
        self.assertTrue(out["tickets"][0]["changed"])
        self.assertFalse([c for c in out["calls"] if c.startswith("gh issue edit")])
        self.assertNotIn("references", self.ticket_doc(ticket))

    def test_pending_selects_open_synced_tickets_with_a_pending_entry(self):
        pending = dict(REF, published=False, url=None)
        wanted = self.synced("Wanted", references=[pending])
        self.synced("All linked", references=[REF])
        self.synced("Never computed")
        done = self.synced("Done", references=[pending])
        self.patch_ticket(done, status="done")
        unsynced = self.new_ticket("Local only", "story", "--features", "wishlist")
        self.patch_ticket(unsynced, references=[pending])
        out = self.json_of("tracker", "refresh", "--pending", "--dry-run",
                           "--gh-replay", self.replay)
        self.assertEqual([row["ticket_id"] for row in out["tickets"]], [wanted])

    def test_a_ticket_with_no_issue_still_gets_its_references_stored(self):
        ticket = self.new_ticket("Share", "story", "--features", "wishlist")
        out = self.json_of("tracker", "refresh", "--ticket", ticket, "--gh-replay", self.replay)
        self.assertEqual(out["calls"], [])
        self.assertIn("no tracker issue", out["tickets"][0]["skipped"])
        self.assertTrue(self.ticket_doc(ticket)["references"])

    def test_a_local_tracker_skips_the_issue(self):
        self.write_settings({"ticket_prefix": "SHOP", "tests": {"coverage": 90}})
        ticket = self.synced()
        out = self.json_of("tracker", "refresh", "--ticket", ticket)
        self.assertIn("local", out["tickets"][0]["skipped"])
        self.assertEqual(out["calls"], [])

    def test_the_subject_is_exactly_one_of_ticket_or_pending(self):
        out = self.json_of("tracker", "refresh", code=2)
        self.assertIn("exactly one of --ticket", out.stderr)


# ---------------------------------------------------------------------------
# The context and requirements.md
# ---------------------------------------------------------------------------

class ContextReferencesTest(CliCase):

    def test_step_start_carries_the_tickets_references(self):
        ticket = self.new_ticket("Share", "story", "--features", "wishlist")
        out = self.start("analyze-requirements", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        context = json.loads(out.stdout)
        paths = [r["path"] for r in context["references"]]
        self.assertEqual(paths, ["docs/product/prd.md",
                                 "docs/architecture/lld/wishlist/api/endpoints.md",
                                 "docs/architecture/lld/wishlist/flows/share.md"])
        with open(os.path.join(self.rdir(ticket), "requirements.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("## References", text)
        self.assertIn("- [Endpoints](https://github.com/acme/shop/blob/main/docs/architecture/"
                      "lld/wishlist/api/endpoints.md) — lld — "
                      "`docs/architecture/lld/wishlist/api/endpoints.md`", text)
        self.assertIn("- Share flow — lld — `docs/architecture/lld/wishlist/flows/share.md` "
                      "— pending: not on `main` yet", text)

    def test_a_ticket_with_nothing_in_the_layout_has_an_empty_list(self):
        ticket = self.new_ticket("Share", "story", "--features", "loyalty")
        context = json.loads(self.start("analyze-requirements", ticket).stdout)
        self.assertEqual([r["kind"] for r in context["references"]], ["prd"])

    def test_a_ticketless_feature_run_and_a_bare_one(self):
        ctx = {"checkout_root": self.repo, "settings": {}, "workspace": self.ws,
               "repo_id": "acme-shop"}
        rdir = os.path.join(self.tmp, "run")
        os.makedirs(rdir)
        self.assertEqual(lib.requirements.run_references(ctx, rdir, {"subject": {}}), [])
        lib.write_json(lib.requirements.refined_path(rdir), {"feature": "wishlist"})
        refs = lib.requirements.run_references(ctx, rdir, {"subject": {}})
        self.assertEqual({r["kind"] for r in refs}, {"prd", "lld"})
        lines = lib.requirements.render_references(refs, "main")
        self.assertEqual(lines[0], "## References")


if __name__ == "__main__":
    unittest.main()
