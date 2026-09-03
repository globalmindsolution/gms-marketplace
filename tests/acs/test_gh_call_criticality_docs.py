"""MAR-403 (parent MAR-401) — documentation assertions for the gh-CLI
call-criticality classification and gh-only transport decision (AC-6).

Prose-contract tests over the architecture doc set T3 amends/adds, mirroring
the whitespace-normalized substring/regex discipline used elsewhere in this
repo (tests/acs/test_ticket_id_reconciliation_docs.py,
tests/acs/test_create_docs_skill.py): every assertion checks that a claim
from the design/plan is actually present in the shipped doc, never a
line-number match (prose is revised; line numbers drift). Kept in its own
module so T3's file map stays disjoint from T1's library-level tests
(tests/acs/test_gh_call_criticality.py) and T2's prose tests
(tests/acs/test_gh_call_criticality_prose.py).

Run:  python3 -m unittest tests.acs.test_gh_call_criticality_docs -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TECH_STACK = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "tech-stack.md")
C4_CONTEXT = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-context.md")
C4_CONTAINER = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md")
C4_COMPONENT = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md")
FLOW_DOC = os.path.join(
    REPO_ROOT, "docs", "architecture", "lld", "flows", "github-call-failure-policy.md"
)
TICKET_LIFECYCLE = os.path.join(
    REPO_ROOT, "docs", "architecture", "lld", "flows", "ticket-lifecycle.md"
)
SECURITY = os.path.join(REPO_ROOT, "docs", "requirements", "non-functional", "security.md")
ADR_0088 = os.path.join(
    REPO_ROOT,
    "docs",
    "adr",
    "0088-gh-only-github-transport-and-criticality-classification.md",
)
ADR_0087 = os.path.join(
    REPO_ROOT, "docs", "adr", "0087-ticket-id-allocation-fail-closed-reconciliation.md"
)
ADR_README = os.path.join(REPO_ROOT, "docs", "adr", "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


class TechStackDocsTest(unittest.TestCase):
    """tech-stack.md:11-12 names gh as the sole transport and the policy."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(TECH_STACK)
        cls.norm = norm(cls.body)

    def test_tech_stack_names_gh_as_the_sole_transport_and_the_failure_policy(self):
        self.assertIsNotNone(re.search(r"(?i)ADR-0088", self.norm))
        self.assertIsNotNone(re.search(r"(?i)sole.{0,20}GitHub transport", self.norm))
        self.assertIsNotNone(re.search(r"(?i)critical.{0,80}non-critical", self.norm))


class C4ContextDocsTest(unittest.TestCase):
    """c4-context.md:15,27 -- no second GitHub transport is sanctioned."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(C4_CONTEXT)
        cls.norm = norm(cls.body)

    def test_c4_context_states_no_second_github_transport_is_sanctioned(self):
        self.assertIsNotNone(re.search(r"(?i)ADR-0088", self.norm))
        self.assertIsNotNone(
            re.search(r"(?i)no second GitHub transport is sanctioned", self.norm)
        )
        self.assertIsNotNone(re.search(r"(?i)only.{0,20}credential holder", self.norm))


class C4ContainerDocsTest(unittest.TestCase):
    """c4-container.md:36 -- the trackers Rel annotates the classification."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(C4_CONTAINER)

    def test_c4_container_rel_annotates_the_classification(self):
        rel_match = re.search(r'Rel\(skills, trackers, ".*?"\)', self.body)
        self.assertIsNotNone(rel_match, "the skills->trackers Rel must exist")
        rel = rel_match.group(0)
        self.assertIn("critical", rel)
        self.assertIn("stop", rel)
        self.assertIn("gate-input", rel)
        self.assertIn("unevaluable", rel)
        self.assertIn("degrade", rel)
        self.assertIn("continue", rel)


class C4ComponentDocsTest(unittest.TestCase):
    """c4-component.md:33 lib gains gh_failure_hint/GH_ACCESS_HINT; :21
    release_notes discloses its own gh seam (drift D-3)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(C4_COMPONENT)
        cls.norm = norm(cls.body)

    def test_c4_component_lib_names_gh_failure_hint(self):
        lib_line_match = re.search(
            r'Component\(lib, "acs_lib\.py".*?\n', self.body, re.DOTALL
        )
        self.assertIsNotNone(lib_line_match, "the lib component entry must exist")
        lib_line = lib_line_match.group(0)
        self.assertIn("gh_failure_hint", lib_line)
        self.assertIn("GH_ACCESS_HINT", lib_line)
        # No new component: exactly one Component(lib, ...) entry.
        self.assertEqual(
            len(re.findall(r"Component\(lib,", self.body)),
            1,
            "gh_failure_hint must NOT introduce a new component (Option F, not Option E)",
        )

    def test_c4_component_discloses_release_notes_gh_seam(self):
        rn_line_match = re.search(
            r'Component\(release_notes, "release_notes\.py".*?\n', self.body, re.DOTALL
        )
        self.assertIsNotNone(rn_line_match, "the release_notes component entry must exist")
        rn_line = rn_line_match.group(0)
        self.assertIn("gh", rn_line)
        self.assertIsNotNone(
            re.search(r"(?i)gh_pr_list", rn_line),
            "release_notes.py's own gh seam (gh_pr_list) must be disclosed",
        )


class FailurePolicyFlowDocTest(unittest.TestCase):
    """docs/architecture/lld/flows/github-call-failure-policy.md (new)."""

    def test_failure_policy_flow_doc_exists_and_is_a_sequence_diagram(self):
        self.assertTrue(os.path.isfile(FLOW_DOC), "%s must exist" % FLOW_DOC)
        body = read(FLOW_DOC)
        self.assertIn("```mermaid", body)
        self.assertIn("sequenceDiagram", body)

    def test_failure_policy_flow_covers_both_classes_and_the_post_merge_arm(self):
        body = read(FLOW_DOC)
        norm_body = norm(body)
        self.assertIsNotNone(re.search(r"(?i)CRITICAL", norm_body))
        self.assertIsNotNone(re.search(r"(?i)NON-CRITICAL", norm_body))
        self.assertIsNotNone(re.search(r"(?i)STOP", norm_body))
        self.assertIsNotNone(re.search(r"(?i)continue", norm_body))
        self.assertIsNotNone(re.search(r"(?i)loud-but-non-reverting", norm_body))
        self.assertIsNotNone(re.search(r"(?i)gate-input", norm_body))
        self.assertIsNotNone(re.search(r"(?i)unevaluable", norm_body))
        self.assertIsNotNone(re.search(r"(?i)Step 1.{0,15}Merge", norm_body))
        self.assertIsNotNone(re.search(r"(?i)Step 2.{0,15}Cleanup", norm_body))
        self.assertIsNotNone(re.search(r"(?i)acs_lib\.gh_failure_hint", norm_body))


class TicketLifecycleDocsTest(unittest.TestCase):
    """ticket-lifecycle.md gains the post-merge rule on BOTH copies."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(TICKET_LIFECYCLE)

    def test_ticket_lifecycle_carries_the_post_merge_rule_on_both_paths(self):
        occurrences = re.findall(
            r"tracker sync to Done[\s\S]{0,300}?loud-but-non-reverting", self.body
        )
        self.assertGreaterEqual(
            len(occurrences),
            2,
            "the loud-but-non-reverting rule must follow BOTH copies of "
            "'tracker sync to Done' -- the primary ready path AND the "
            "BEHIND carve-out poll loop",
        )
        self.assertIn("ADR-0088", self.body)


class SecurityDocsTest(unittest.TestCase):
    """security.md:13-14 no longer claims an auth check (drift D-1)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SECURITY)
        cls.norm = norm(cls.body)

    def test_security_md_no_longer_claims_an_auth_check(self):
        self.assertNotIn("installed and authenticated", self.norm)
        self.assertIsNotNone(
            re.search(r"(?i)configured tracker's CLI is installed\.", self.norm)
        )

    def test_gh_owns_auth_sentence_is_unchanged(self):
        self.assertIsNotNone(
            re.search(
                r"(?i)which manage their own authentication.{0,10}gh auth login",
                self.norm,
            )
        )


class Adr0088Test(unittest.TestCase):
    """AC-6: ADR-0088 exists, is Accepted, scoped to the gh transport."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_0088)
        cls.norm = norm(cls.body)

    def test_adr_0088_exists_is_accepted_and_is_scoped_to_the_gh_transport(self):
        self.assertIsNotNone(re.search(r"\*\*Status\*\*:\s*Accepted", self.body))
        self.assertIsNotNone(
            re.search(r"(?i)(only|sole|single) GitHub transport", self.norm)
        )
        for term in (
            "critical",
            "non-critical",
            "GitHub MCP fallback",
            "MAR-307",
        ):
            self.assertIn(term, self.body, "ADR-0088 missing term %r" % term)
        self.assertIsNotNone(re.search(r"(?i)C-6", self.norm))
        self.assertIsNotNone(re.search(r"(?i)removed", self.norm))

    def test_adr_0088_states_gh_issue_create_hybrid_disposition_not_plain_critical(self):
        """F3/F4 (iter-2 remediation): the plain-Critical bullet must not
        list `gh issue create` alongside gh pr create/gh pr merge -- it
        carries its own hybrid-disposition bullet instead."""
        critical_bullet_match = re.search(
            r"-\s+\*\*Critical\*\*\s+—.*?(?=\n-\s+\*\*)", self.body, re.DOTALL
        )
        self.assertIsNotNone(critical_bullet_match, "the plain Critical bullet must exist")
        self.assertNotIn("gh issue create", critical_bullet_match.group(0))
        self.assertIsNotNone(
            re.search(r"(?i)critical per ticket, soft per batch", self.norm),
            "ADR-0088 must state gh issue create's hybrid disposition",
        )

    def test_adr_0088_post_merge_sync_appears_only_in_loud_but_non_reverting_context(self):
        """F2/F4 (iter-2 remediation): the post-merge tracker sync must not
        also be listed in the plain Non-critical bullet -- its sole home is
        the loud-but-non-reverting paragraph."""
        non_critical_bullet_match = re.search(
            r"-\s+\*\*Non-critical\*\*\s+—.*?(?=\n\n|\Z)", self.body, re.DOTALL
        )
        self.assertIsNotNone(non_critical_bullet_match, "the Non-critical bullet must exist")
        self.assertNotIn("post-merge", non_critical_bullet_match.group(0))
        self.assertNotIn("Status→Done", non_critical_bullet_match.group(0))
        self.assertIsNotNone(
            re.search(r"(?i)post-merge tracker sync is loud-but-non-reverting", self.norm),
            "the post-merge sync's sole disposition statement must be the "
            "loud-but-non-reverting paragraph",
        )

    def test_adr_0088_does_not_claim_the_reconciliation_decision(self):
        # Inverse fence of ADR-0087's own scoping guard: ADR-0088 must not
        # restate ADR-0087's ticket-id-allocation subject.
        for term in ("ReconciliationRequired", "seed_source", "observed_max", "--seed-next"):
            self.assertNotIn(term, self.body)
        self.assertNotIn("ticket-id allocation fail-closed reconciliation gate\n\n**Status**", self.body)

    def test_adr_0088_is_indexed(self):
        body = read(ADR_README)
        self.assertIsNotNone(
            re.search(r"\[0088\]\(0088-[a-z0-9-]+\.md\)", body),
            "docs/adr/README.md must index ADR-0088",
        )
        self.assertTrue(os.path.isfile(ADR_0088))

    def test_adr_0087_is_untouched_by_this_ticket(self):
        # R-D guard: writing to 0088 must never touch the merged 0087 record.
        self.assertTrue(os.path.isfile(ADR_0087))
        body = read(ADR_0087)
        self.assertNotIn("GH_ACCESS_DENIED_MARKER", body)
        self.assertNotIn("gh_failure_hint", body)


class ChangelogDocsTest(unittest.TestCase):
    """[Unreleased] records the behaviour change and the MCP removal (R12)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CHANGELOG)
        cls.norm = norm(cls.body)

    def test_changelog_unreleased_records_the_behaviour_change(self):
        unreleased_match = re.search(
            r"## \[Unreleased\](.*?)## \[0\.4\.8\]", self.body, re.DOTALL
        )
        self.assertIsNotNone(unreleased_match, "[Unreleased] section must exist")
        section = unreleased_match.group(1)
        section_norm = norm(section)
        self.assertIn("ADR-0088", section)
        self.assertIsNotNone(re.search(r"(?i)MCP.{0,150}removed outright", section_norm))
        self.assertIsNotNone(
            re.search(r"(?i)gate-input read.{0,80}stops (a|the) run", section_norm)
        )
        self.assertIsNotNone(re.search(r"(?i)loud-but-non-reverting", section_norm))
        self.assertIn("**Migration:** none", section)


if __name__ == "__main__":
    unittest.main()
