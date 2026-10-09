"""ADR-0140: a ticket carries links to the documents that exist for its features.

`acs_lib.doc_links` finds them in the STANDARD LAYOUT (so a ticket minted
before the change finds them too), builds a clickable link to the remote's
default branch for each one that is published there, and marks the rest
pending. These cases pin each piece against a temp repo laid out the way the
skills write it:

  * the web base of every remote spelling, and GitHub's heading anchors;
  * each kind collected (prd, analysis, hld, lld, design, development), the
    parent epic's records, and the no-features fallback;
  * published versus pending against a temp bare remote, with
    `origin/<default>` present, absent, and refreshed by a fetch;
  * the `## References` block: render, insert, replace, idempotency.

Run:  python3 -m unittest tests.acs.test_doc_links -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import doc_links  # noqa: E402

GITHUB = "https://github.com/acme/shop.git"


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


def versioned(title, status="approved", version=2, feature=None):
    front = ["---", "status: %s" % status, "version: %d" % version, "tickets: []"]
    if feature:
        front.append("feature: %s" % feature)
    return "\n".join(front + ["---", "", "# %s" % title, "", "Body.", ""])


PRD = """# PRD — Shop

## Goals & success metrics

G1: wishlist sharing grows retention.

## Features (prioritized)

### Must have

- [Wishlist sharing](features/wishlist-sharing/prd.md) — share a wishlist (supports G1)
- [Checkout](features/checkout/prd.md) — pay (supports G1)
"""

#: The standard layout, with a second feature's documents that must NOT show up.
LAYOUT = {
    "docs/product/prd.md": PRD,
    "docs/product/features/wishlist-sharing/prd.md": versioned("Wishlist sharing", "proposed", 1),
    "docs/product/features/checkout/prd.md": "# Checkout\n\nPay.\n",
    "docs/product/features/wishlist-sharing/analysis/README.md": "# Wishlist analysis\n",
    "docs/product/features/wishlist-sharing/analysis/sharing.md": "# Sharing context\n",
    "docs/product/features/wishlist-sharing/analysis/sharing.evidence.md": "evidence\n",
    "docs/product/features/checkout/analysis/README.md": "# Checkout analysis\n",
    "docs/architecture/hld/tech-stack.md": "# Tech stack\n\nPython.\n",
    "docs/architecture/hld/overview.md": versioned("Overview", "implemented", 4),
    "docs/architecture/hld/c4-container.md": "# Containers\n\nThe WISHLIST-SHARING service.\n",
    "docs/architecture/hld/data-model.md": "# Data model\n\nThe Wishlist sharing table.\n",
    "docs/architecture/hld/deployment.md": "# Deployment\n\nNothing about it.\n",
    "docs/architecture/lld/wishlist-sharing/api/endpoints.md":
        versioned("Endpoints", "approved", 2, "wishlist-sharing"),
    "docs/architecture/lld/wishlist-sharing/api/endpoints.evidence.md": "evidence\n",
    "docs/architecture/lld/wishlist-sharing/flows/share.md": "no front matter here\n",
    "docs/architecture/lld/wishlist-sharing/SHOP-1/tech-design.md":
        versioned("Epic design", "approved", 1, "wishlist-sharing"),
    "docs/architecture/lld/wishlist-sharing/SHOP-1/api-contract.md": "# Epic API contract\n",
    "docs/architecture/lld/wishlist-sharing/SHOP-2/tech-design.md":
        versioned("Story design", "proposed", 1, "wishlist-sharing"),
    "docs/architecture/lld/checkout/api/pay.md": versioned("Pay", "approved", 1, "checkout"),
    "docs/architecture/lld/checkout/SHOP-9/tech-design.md": "# Other\n",
    "docs/development/wishlist-sharing/SHOP-2/analysis/README.md": "# SHOP-2 analysis\n",
    "docs/development/wishlist-sharing/SHOP-2/analysis/ui.md": "# UI context\n",
    "docs/development/wishlist-sharing/SHOP-2/plan.md": "# Plan\n",
    "docs/development/wishlist-sharing/SHOP-2/test-cases.md": "# Test cases\n",
    "docs/development/checkout/SHOP-9/plan.md": "# Other plan\n",
}

STORY = {"id": "SHOP-2", "type": "story", "parent": "SHOP-1",
         "features": ["wishlist-sharing"]}


class RepoCase(unittest.TestCase):
    """A git repo whose origin is a temp BARE repo that git reaches through
    `url.<bare>.insteadOf <github url>`: `remote.origin.url` still reads as
    GitHub (so links are built), while fetch and push stay on disk."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-doc-links-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bare = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.bare], check=True)
        self.root = os.path.join(self.tmp, "shop")
        os.makedirs(self.root)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "url.%s.insteadOf" % self.bare, GITHUB)
        git(self.root, "remote", "add", "origin", GITHUB)
        for rel, text in LAYOUT.items():
            write(self.root, rel, text)

    def ctx(self):
        return {"checkout_root": self.root, "settings": {}}

    def publish(self, *paths):
        """Commit `paths` (all when none) on main and push them to origin."""
        git(self.root, "add", "--", *(paths or (".",)))
        git(self.root, "commit", "-q", "-m", "docs")
        git(self.root, "push", "-q", "origin", "main")
        git(self.root, "remote", "set-head", "origin", "main")


# ---------------------------------------------------------------------------
# Remotes and anchors
# ---------------------------------------------------------------------------

class WebBaseTest(unittest.TestCase):

    def test_every_github_spelling_has_one_web_base(self):
        for url in ("https://github.com/acme/shop.git", "https://github.com/acme/shop",
                    "git@github.com:acme/shop.git", "ssh://git@github.com/acme/shop.git",
                    "ssh://git@github.com:22/acme/shop.git",
                    "https://token@github.com/acme/shop.git/"):
            self.assertEqual(doc_links.web_base_for_url(url), "https://github.com/acme/shop", url)

    def test_an_enterprise_host_is_github(self):
        self.assertEqual(doc_links.web_base_for_url("git@github.acme.io:team/shop.git"),
                         "https://github.acme.io/team/shop")
        self.assertEqual(doc_links.web_base_for_url("https://acme.ghe.com/team/shop"),
                         "https://acme.ghe.com/team/shop")

    def test_gitlab_keeps_its_subgroups_and_bitbucket_its_workspace(self):
        self.assertEqual(doc_links.web_base_for_url("git@gitlab.com:group/sub/shop.git"),
                         "https://gitlab.com/group/sub/shop")
        self.assertEqual(doc_links.web_base_for_url("https://me@bitbucket.org/team/shop.git"),
                         "https://bitbucket.org/team/shop")

    def test_an_unknown_host_or_a_local_path_has_none(self):
        for url in ("https://git.example.org/a/b.git", "/srv/git/shop.git",
                    "file:///srv/git/shop.git", "", None):
            self.assertIsNone(doc_links.web_base_for_url(url), url)

    def test_each_host_family_spells_its_blob_path(self):
        self.assertEqual(
            doc_links.blob_url("https://github.com/acme/shop", "main", "docs/a b.md", "x-1"),
            "https://github.com/acme/shop/blob/main/docs/a%20b.md#x-1")
        self.assertEqual(doc_links.blob_url("https://gitlab.com/g/s", "trunk", "d.md"),
                         "https://gitlab.com/g/s/-/blob/trunk/d.md")
        self.assertEqual(doc_links.blob_url("https://bitbucket.org/t/s", "main", "d.md"),
                         "https://bitbucket.org/t/s/src/main/d.md")
        self.assertIsNone(doc_links.blob_url(None, "main", "d.md"))
        self.assertIsNone(doc_links.blob_url("https://github.com/a/b", None, "d.md"))

    def test_the_partition_id_reads_the_same_shared_parser(self):
        """repo_partition_id was refactored onto `remote_segments`; every
        spelling it already handled still yields the same id."""
        for url, expected in (("git@github.com:acme/shop.git", ["github.com", "acme", "shop"]),
                              ("https://u@gitlab.com/g/s/p.git/", ["gitlab.com", "g", "s", "p"]),
                              ("/srv/git/shop.git", ["srv", "git", "shop"])):
            self.assertEqual(lib.repo.remote_segments(url), expected)

    def test_web_base_reads_the_checkouts_origin(self):
        tmp = tempfile.mkdtemp(prefix="acs-web-base-")
        self.addCleanup(shutil.rmtree, tmp, True)
        git(tmp, "init", "-q")
        self.assertIsNone(doc_links.web_base(tmp))
        git(tmp, "remote", "add", "origin", "git@github.com:acme/shop.git")
        self.assertEqual(doc_links.web_base(tmp), "https://github.com/acme/shop")


class AnchorTest(unittest.TestCase):

    def test_githubs_algorithm(self):
        seen = {}
        self.assertEqual(doc_links.github_anchor("Feature: Wishlist sharing", seen),
                         "feature-wishlist-sharing")
        self.assertEqual(doc_links.github_anchor("Goals & success metrics", seen),
                         "goals--success-metrics")
        self.assertEqual(doc_links.github_anchor("What's new?", seen), "whats-new")
        self.assertEqual(doc_links.github_anchor("`acs.py` CLI", seen), "acspy-cli")
        self.assertEqual(doc_links.github_anchor("Café über_x", seen), "café-über_x")
        self.assertEqual(doc_links.github_anchor("A [link](https://x.io) here", seen),
                         "a-link-here")

    def test_headings_in_a_code_fence_are_not_headings(self):
        text = "# Top\n\n```md\n# Not a heading\n~~~\n# Still not\n```\n\n## Wishlist\n"
        self.assertEqual(doc_links.headings(text), [(1, "Top", "top"), (2, "Wishlist", "wishlist")])

    def test_duplicates_are_numbered(self):
        seen = {}
        got = [doc_links.github_anchor("Notes", seen) for _ in range(3)]
        self.assertEqual(got, ["notes", "notes-1", "notes-2"])


class DefaultBranchTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-default-branch-")
        self.addCleanup(shutil.rmtree, self.root, True)
        git(self.root, "init", "-q", "-b", "trunk")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")

    def test_origin_head_decides(self):
        git(self.root, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.assertEqual(doc_links.default_branch(self.root), "trunk")

    def test_main_or_master_when_origin_head_is_unset(self):
        self.assertIsNone(doc_links.default_branch(self.root))
        git(self.root, "branch", "master")
        self.assertEqual(doc_links.default_branch(self.root), "master")

    def test_setup_wizard_delegates_to_it(self):
        import setup_wizard
        with mock.patch.object(lib.doc_links, "default_branch", return_value="dev") as fn:
            self.assertEqual(setup_wizard.default_branch(self.root), "dev")
        fn.assert_called_once_with(self.root)


# ---------------------------------------------------------------------------
# Collection from the standard layout
# ---------------------------------------------------------------------------

def rows(refs):
    return [(r["kind"], r["path"]) for r in refs]


class CollectTest(RepoCase):

    def test_every_kind_for_a_story_in_the_standard_layout(self):
        refs = doc_links.references_for_ticket(self.ctx(), STORY)
        self.assertEqual(rows(refs), [
            ("prd", "docs/product/features/wishlist-sharing/prd.md"),
            ("prd", "docs/product/prd.md"),
            ("analysis", "docs/product/features/wishlist-sharing/analysis/README.md"),
            ("analysis", "docs/product/features/wishlist-sharing/analysis/sharing.md"),
            ("hld", "docs/architecture/hld/c4-container.md"),
            ("hld", "docs/architecture/hld/data-model.md"),
            ("hld", "docs/architecture/hld/overview.md"),
            ("lld", "docs/architecture/lld/wishlist-sharing/api/endpoints.md"),
            ("lld", "docs/architecture/lld/wishlist-sharing/flows/share.md"),
            ("design", "docs/architecture/lld/wishlist-sharing/SHOP-1/api-contract.md"),
            ("design", "docs/architecture/lld/wishlist-sharing/SHOP-1/tech-design.md"),
            ("design", "docs/architecture/lld/wishlist-sharing/SHOP-2/tech-design.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/analysis/README.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/analysis/ui.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/plan.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/test-cases.md"),
        ])

    def test_each_entry_carries_its_title_status_and_version(self):
        refs = {r["path"]: r for r in doc_links.references_for_ticket(self.ctx(), STORY)}
        endpoints = refs["docs/architecture/lld/wishlist-sharing/api/endpoints.md"]
        self.assertEqual((endpoints["title"], endpoints["status"], endpoints["version"]),
                         ("Endpoints", "approved", 2))
        share = refs["docs/architecture/lld/wishlist-sharing/flows/share.md"]
        self.assertEqual((share["title"], share["status"], share["version"]),
                         ("share.md", None, None))
        prd = refs["docs/product/features/wishlist-sharing/prd.md"]
        self.assertEqual((prd["title"], prd["status"], prd["version"]),
                         ("Wishlist sharing", "proposed", 1))
        for ref in refs.values():
            self.assertEqual(set(ref), {"kind", "path", "title", "status", "version",
                                        "published", "url"})

    def test_a_feature_links_its_own_prd_then_the_product_prd(self):
        refs = doc_links.references_for_features(self.ctx(), ["checkout"])
        self.assertEqual([r["path"] for r in refs if r["kind"] == "prd"],
                         ["docs/product/features/checkout/prd.md", "docs/product/prd.md"])

    def test_a_feature_without_a_prd_of_its_own_links_the_product_prd_only(self):
        refs = doc_links.references_for_features(self.ctx(), ["loyalty"])
        self.assertEqual(rows(refs), [("prd", "docs/product/prd.md"),
                                      ("hld", "docs/architecture/hld/overview.md")])

    def test_feature_runs_get_the_same_set_without_the_tickets_records(self):
        refs = doc_links.references_for_features(self.ctx(), ["wishlist-sharing"])
        self.assertEqual({r["kind"] for r in refs}, {"prd", "analysis", "hld", "lld"})
        with_parent = doc_links.references_for_features(self.ctx(), ["wishlist-sharing"],
                                                        parent="SHOP-1")
        self.assertEqual([r["path"] for r in with_parent if r["kind"] == "design"], [
            "docs/architecture/lld/wishlist-sharing/SHOP-1/api-contract.md",
            "docs/architecture/lld/wishlist-sharing/SHOP-1/tech-design.md"])

    def test_the_epics_own_records_reach_its_child(self):
        child = dict(STORY, id="SHOP-3")
        design = [r["path"] for r in doc_links.references_for_ticket(self.ctx(), child)
                  if r["kind"] in ("design", "development")]
        self.assertEqual(design, [
            "docs/architecture/lld/wishlist-sharing/SHOP-1/api-contract.md",
            "docs/architecture/lld/wishlist-sharing/SHOP-1/tech-design.md"])

    def test_no_features_falls_back_to_the_id_glob(self):
        refs = doc_links.references_for_ticket(self.ctx(), {"id": "SHOP-2", "parent": "SHOP-1"})
        self.assertEqual(rows(refs), [
            ("prd", "docs/product/prd.md"),
            ("design", "docs/architecture/lld/wishlist-sharing/SHOP-1/api-contract.md"),
            ("design", "docs/architecture/lld/wishlist-sharing/SHOP-1/tech-design.md"),
            ("design", "docs/architecture/lld/wishlist-sharing/SHOP-2/tech-design.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/analysis/README.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/analysis/ui.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/plan.md"),
            ("development", "docs/development/wishlist-sharing/SHOP-2/test-cases.md"),
        ])

    def test_two_features_are_deduplicated_and_stay_in_order(self):
        refs = doc_links.references_for_ticket(
            self.ctx(), dict(STORY, features=["wishlist-sharing", "checkout",
                                              "wishlist-sharing"]))
        paths = [r["path"] for r in refs]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(paths[:3], ["docs/product/features/checkout/prd.md",
                                     "docs/product/features/wishlist-sharing/prd.md",
                                     "docs/product/prd.md"])
        self.assertIn("docs/architecture/lld/checkout/api/pay.md", paths)

    def test_a_legacy_single_file_analysis_is_listed(self):
        write(self.root, "docs/product/features/checkout/analysis.md", "# Old analysis\n")
        refs = doc_links.references_for_features(self.ctx(), ["checkout"])
        self.assertIn(("analysis", "docs/product/features/checkout/analysis.md"), rows(refs))

    def test_no_origin_means_no_fetch(self):
        git(self.root, "remote", "remove", "origin")
        self.assertFalse(doc_links.fetch_default(self.root))
        self.assertFalse(doc_links.fetch_default(None))

    def test_an_empty_repo_has_no_references_and_never_raises(self):
        empty = tempfile.mkdtemp(prefix="acs-empty-")
        self.addCleanup(shutil.rmtree, empty, True)
        git(empty, "init", "-q")
        self.assertEqual(doc_links.references_for_ticket(
            {"checkout_root": empty, "settings": {}}, STORY), [])

    def test_a_front_matter_that_does_not_parse_is_still_listed(self):
        write(self.root, "docs/architecture/lld/wishlist-sharing/api/broken.md",
              "---\n: : :\n---\n# Broken\n")
        refs = {r["path"]: r for r in doc_links.references_for_ticket(self.ctx(), STORY)}
        broken = refs["docs/architecture/lld/wishlist-sharing/api/broken.md"]
        self.assertEqual((broken["status"], broken["version"]), (None, None))


# ---------------------------------------------------------------------------
# Published versus pending
# ---------------------------------------------------------------------------

class PublishedTest(RepoCase):

    def test_nothing_is_published_while_origin_has_no_default_branch(self):
        report = doc_links.report(self.ctx(), ticket=STORY)
        self.assertEqual(report["web_base"], "https://github.com/acme/shop")
        self.assertFalse(report["remote_checked"])
        self.assertTrue(report["references"])
        for ref in report["references"]:
            self.assertFalse(ref["published"])
            self.assertIsNone(ref["url"])

    def test_a_pushed_document_links_to_the_default_branch_and_the_rest_wait(self):
        self.publish("docs/product/features/wishlist-sharing/prd.md",
                     "docs/architecture/hld/tech-stack.md",
                     "docs/architecture/lld/wishlist-sharing/api/endpoints.md")
        report = doc_links.report(self.ctx(), ticket=STORY)
        self.assertEqual(report["default_branch"], "main")
        refs = {r["path"]: r for r in report["references"]}
        prd = refs["docs/product/features/wishlist-sharing/prd.md"]
        self.assertTrue(prd["published"])
        self.assertEqual(prd["url"], "https://github.com/acme/shop/blob/main/docs/product/"
                                     "features/wishlist-sharing/prd.md")
        endpoints = refs["docs/architecture/lld/wishlist-sharing/api/endpoints.md"]
        self.assertEqual(endpoints["url"], "https://github.com/acme/shop/blob/main/docs/"
                                           "architecture/lld/wishlist-sharing/api/endpoints.md")
        plan = refs["docs/development/wishlist-sharing/SHOP-2/plan.md"]
        self.assertEqual((plan["published"], plan["url"]), (False, None))

    def test_a_fetch_turns_a_pending_entry_into_a_link(self):
        self.publish("docs/product/prd.md")
        other = os.path.join(self.tmp, "other")
        subprocess.run(["git", "clone", "-q", self.bare, other], check=True)
        write(other, "docs/development/wishlist-sharing/SHOP-2/plan.md", "# Plan\n")
        git(other, "add", ".")
        git(other, "commit", "-q", "-m", "plan")
        git(other, "push", "-q", "origin", "HEAD:main")
        path = "docs/development/wishlist-sharing/SHOP-2/plan.md"
        stale = {r["path"]: r for r in doc_links.report(self.ctx(), ticket=STORY)["references"]}
        self.assertFalse(stale[path]["published"])
        fresh = doc_links.report(self.ctx(), ticket=STORY, fetch=True)
        self.assertTrue(fresh["remote_checked"])
        self.assertTrue({r["path"]: r for r in fresh["references"]}[path]["published"])

    def test_a_failed_fetch_is_recorded_not_raised(self):
        git(self.root, "config", "--unset", "url.%s.insteadOf" % self.bare)
        git(self.root, "remote", "set-url", "origin", os.path.join(self.tmp, "missing.git"))
        out = doc_links.published(self.root, ["docs/product/prd.md"], fetch=True)
        self.assertFalse(out["remote_checked"])
        self.assertEqual(out["published"], {"docs/product/prd.md": False})

    def test_no_web_remote_publishes_without_a_url(self):
        self.publish()
        git(self.root, "config", "--unset", "url.%s.insteadOf" % self.bare)
        git(self.root, "remote", "set-url", "origin", self.bare)
        report = doc_links.report(self.ctx(), ticket=STORY)
        self.assertIsNone(report["web_base"])
        self.assertEqual(report["web_base_reason"], doc_links.NO_WEB_REMOTE)
        self.assertTrue(all(r["published"] and r["url"] is None for r in report["references"]))


# ---------------------------------------------------------------------------
# The ## References block
# ---------------------------------------------------------------------------

LINKED = {"kind": "lld", "path": "docs/a.md", "title": "API", "status": "approved",
          "version": 3, "published": True, "url": "https://github.com/a/b/blob/main/docs/a.md"}
PENDING = {"kind": "development", "path": "docs/dev/plan.md", "title": "Plan",
           "status": None, "version": None, "published": False, "url": None}


class RenderBlockTest(unittest.TestCase):

    def test_a_published_entry_links_and_a_pending_one_says_why_not(self):
        block = doc_links.render_block([LINKED, PENDING], "main")
        self.assertEqual(block.splitlines(), [
            "- [API](https://github.com/a/b/blob/main/docs/a.md): lld, v3 approved",
            "- `docs/dev/plan.md`: development, pending: not on `main` yet",
        ])

    def test_no_entries_says_so(self):
        self.assertEqual(doc_links.render_block([], "main"),
                         "_No documents for this ticket's features yet._")

    def test_a_published_entry_with_no_web_remote_is_its_path(self):
        block = doc_links.render_block([dict(LINKED, url=None, status=None)], "main")
        self.assertEqual(block, "- `docs/a.md`: lld, v3")


class ApplyBlockTest(unittest.TestCase):

    BLOCK = "- [API](https://x/a.md): lld"
    TEMPLATE = ("## Description\n\nWork.\n\n## References\n\n"
                "<!-- acs:references -->\n<!-- /acs:references -->\n\n"
                "## Notes\n\nNone.\n\nacs-ticket: SHOP-2\n")

    def test_the_markers_content_is_replaced_and_nothing_else(self):
        out = doc_links.apply_block(self.TEMPLATE, self.BLOCK)
        self.assertIn("<!-- acs:references -->\n%s\n<!-- /acs:references -->" % self.BLOCK, out)
        self.assertEqual(out.replace(self.BLOCK + "\n", ""), self.TEMPLATE)
        again = doc_links.apply_block(out, "_No documents for this ticket's features yet._")
        self.assertNotIn(self.BLOCK, again)
        self.assertEqual(again.count(doc_links.START_MARKER), 1)

    def test_it_is_idempotent(self):
        once = doc_links.apply_block(self.TEMPLATE, self.BLOCK)
        self.assertEqual(doc_links.apply_block(once, self.BLOCK), once)
        bare = "## Description\n\nWork.\n"
        once = doc_links.apply_block(bare, self.BLOCK)
        self.assertEqual(doc_links.apply_block(once, self.BLOCK), once)

    def test_a_heading_without_markers_gets_them_under_it(self):
        text = "## References\n\nHand-written.\n\n## Notes\n\nacs-ticket: SHOP-2\n"
        out = doc_links.apply_block(text, self.BLOCK)
        self.assertTrue(out.startswith(
            "## References\n\n<!-- acs:references -->\n%s\n<!-- /acs:references -->\n"
            % self.BLOCK), out)
        self.assertIn("Hand-written.", out)
        self.assertEqual(out.count("## References"), 1)

    def test_no_heading_appends_the_section_before_the_ticket_line(self):
        text = "## Description\n\nWork.\n\n## Notes\n\nNone.\n\nacs-ticket: SHOP-2\n"
        out = doc_links.apply_block(text, self.BLOCK)
        self.assertTrue(out.endswith(
            "## References\n\n<!-- acs:references -->\n%s\n<!-- /acs:references -->\n\n"
            "acs-ticket: SHOP-2\n" % self.BLOCK), out)

    def test_no_heading_and_no_ticket_line_appends_at_the_end(self):
        out = doc_links.apply_block("Body", self.BLOCK)
        self.assertEqual(out, "Body\n\n## References\n\n<!-- acs:references -->\n%s\n"
                              "<!-- /acs:references -->\n" % self.BLOCK)

    def test_a_lone_start_marker_is_completed(self):
        out = doc_links.apply_block("A\n<!-- acs:references -->\nB\n", self.BLOCK)
        self.assertEqual(out, "A\n<!-- acs:references -->\n%s\n<!-- /acs:references -->\nB\n"
                         % self.BLOCK)

    def test_write_body_block_reports_whether_the_file_changed(self):
        tmp = tempfile.mkdtemp(prefix="acs-body-")
        self.addCleanup(shutil.rmtree, tmp, True)
        path = write(tmp, "tracker-body.md", self.TEMPLATE)
        self.assertTrue(doc_links.write_body_block(path, [LINKED], "main"))
        self.assertFalse(doc_links.write_body_block(path, [LINKED], "main"))
        with open(path, encoding="utf-8") as fh:
            self.assertIn("- [API](%s): lld, v3 approved" % LINKED["url"], fh.read())

    def test_the_issues_block_is_read_back(self):
        out = doc_links.apply_block(self.TEMPLATE, self.BLOCK)
        self.assertEqual(doc_links.current_block(out), self.BLOCK)
        self.assertIsNone(doc_links.current_block("no markers"))


class RefreshIssueTest(unittest.TestCase):
    """`refresh_issue`: read the issue, swap only the marker block, write it
    back -- non-critical (ADR-0088) at every gh call."""

    BODY = ("## Description\n\nWork.\n\n## References\n\n<!-- acs:references -->\n"
            "- `docs/dev/plan.md`: development, pending: not on `main` yet\n"
            "<!-- /acs:references -->\n\nA remote edit someone made.\n\nacs-ticket: SHOP-2\n")

    def fake_gh(self, view=(0, None, ""), edit=(0, "", "")):
        written = {}

        def gh(argv):
            gh.calls.append(" ".join(argv))
            if argv[:3] == ["gh", "issue", "view"]:
                code, out, err = view
                return code, (out if out is not None else
                              '{"body": %s}' % __import__("json").dumps(self.BODY)), err
            if argv[:3] == ["gh", "issue", "edit"]:
                with open(argv[argv.index("--body-file") + 1], encoding="utf-8") as fh:
                    written["body"] = fh.read()
                return edit
            return 1, "", "unexpected"
        gh.calls = []
        return gh, written

    def test_only_the_marker_block_changes(self):
        gh, written = self.fake_gh()
        block = doc_links.render_block([dict(PENDING, published=True,
                                             url="https://x/plan.md")], "main")
        out = doc_links.refresh_issue(gh, "9", block)
        self.assertTrue(out["edited"])
        self.assertEqual(out["findings"], [])
        expected = self.BODY.replace(
            "- `docs/dev/plan.md`: development, pending: not on `main` yet",
            "- [Plan](https://x/plan.md): development")
        self.assertEqual(written["body"], expected)

    def test_an_unchanged_block_makes_no_edit(self):
        gh, _written = self.fake_gh()
        block = doc_links.current_block(self.BODY)
        out = doc_links.refresh_issue(gh, "9", block)
        self.assertFalse(out["edited"])
        self.assertFalse(out["changed"])
        self.assertFalse([c for c in gh.calls if c.startswith("gh issue edit")])

    def test_dry_run_reads_but_never_edits(self):
        gh, _written = self.fake_gh()
        out = doc_links.refresh_issue(gh, "9", "- new", dry_run=True)
        self.assertTrue(out["changed"])
        self.assertFalse(out["edited"])
        self.assertFalse([c for c in gh.calls if c.startswith("gh issue edit")])

    def test_a_failed_view_or_edit_is_an_info_finding(self):
        gh, _written = self.fake_gh(view=(1, "", "HTTP 404"))
        out = doc_links.refresh_issue(gh, "9", "- new")
        self.assertFalse(out["edited"])
        self.assertEqual([f["severity"] for f in out["findings"]], ["info"])
        self.assertTrue(out["findings"][0]["replayable"])
        self.assertIn("hint", out["findings"][0])
        gh, _written = self.fake_gh(edit=(1, "", "denied"))
        out = doc_links.refresh_issue(gh, "9", "- new")
        self.assertFalse(out["edited"])
        self.assertEqual([f["area"] for f in out["findings"]], ["references"])

    def test_an_unreadable_view_is_a_finding_too(self):
        gh, _written = self.fake_gh(view=(0, "not json", ""))
        out = doc_links.refresh_issue(gh, "9", "- new")
        self.assertFalse(out["edited"])
        self.assertEqual(len(out["findings"]), 1)


class CriticalityRegistryTest(unittest.TestCase):

    def test_tracker_refresh_is_registered_non_critical(self):
        self.assertEqual(lib.forge.GH_FLOW_CRITICALITY["tracker refresh"], "non-critical")
        self.assertEqual(lib.forge.GH_FLOW_CRITICALITY["tracker sync"],
                         "critical per ticket, soft per batch")
        self.assertEqual(lib.forge.GH_FLOW_CRITICALITY["pr metadata fill"], "non-critical")


if __name__ == "__main__":
    unittest.main()
