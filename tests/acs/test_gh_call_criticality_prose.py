"""MAR-403 (parent MAR-401) -- criticality-classification and MCP-fallback-
removal assertions over the three gh-calling skills (create-ticket, create-pr,
merge-pr) and their three executor agents.

Anti-drift discipline: hint text is imported from `acs_lib` (never
hardcoded) so a future edit to the canonical hint cannot silently desync from
the SKILL.md/agent prose that quotes it (Option F, T1). All other assertions
are whitespace-normalized substring/regex checks over file bodies, never
line-number matches -- prose is revised, line numbers drift.

Run:  python3 -m unittest tests.acs.test_gh_call_criticality_prose -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
if HOOKS_SCRIPTS not in sys.path:
    sys.path.insert(0, HOOKS_SCRIPTS)

import acs_lib  # noqa: E402

CREATE_TICKET_SKILL = os.path.join(PLUGIN, "skills", "create-ticket", "SKILL.md")
CREATE_PR_SKILL = os.path.join(PLUGIN, "skills", "create-pr", "SKILL.md")
MERGE_PR_SKILL = os.path.join(PLUGIN, "skills", "merge-pr", "SKILL.md")
CREATE_TICKET_EXECUTOR = os.path.join(PLUGIN, "agents", "create-ticket-executor.md")
CREATE_PR_EXECUTOR = os.path.join(PLUGIN, "agents", "create-pr-executor.md")
MERGE_PR_EXECUTOR = os.path.join(PLUGIN, "agents", "merge-pr-executor.md")

SKILLS = {
    "create-ticket": CREATE_TICKET_SKILL,
    "create-pr": CREATE_PR_SKILL,
    "merge-pr": MERGE_PR_SKILL,
}
EXECUTORS = {
    "create-ticket": CREATE_TICKET_EXECUTOR,
    "create-pr": CREATE_PR_EXECUTOR,
    "merge-pr": MERGE_PR_EXECUTOR,
}

# The one compact "GitHub call failure policy" heading each skill gains
# (verbatim, quoted text -- never a line number, per R-E).
HEADINGS = {
    "create-ticket": "### GitHub call failure policy",
    "create-pr": "### GitHub call failure policy (gh is acs's only transport)",
    "merge-pr": "## GitHub call failure policy",
}

# Rows 1, 3-5, 13-16 of the plan's classification table: calls whose failure
# leaves a gate input unevaluable, so they stop the run.
CRITICAL_TOKENS = {
    "create-ticket": ["gh issue view"],
    "create-pr": [
        "gh pr list",
        "gh repo view --json defaultBranchRef",
        "gh pr create",
        "gh pr edit",
    ],
    "merge-pr": [
        "gh pr view",
        "gh pr checks",
        "gh pr update-branch",
        "gh pr merge",
    ],
}

# Row 2 (create-ticket's `gh issue create` tracker-sync call) is a distinct
# hybrid disposition -- critical per ticket, soft per batch -- and is
# exercised separately by HybridClassificationTest /
# CreateTicketRowTwoClassificationTest below, per the plan's own
# classification table (plan.md row 2, design.md:464). It is deliberately
# absent from both CRITICAL_TOKENS and NONCRITICAL_TOKENS here.
HYBRID_LABEL = "Critical (per ticket, soft per batch)"
HYBRID_TOKENS = {
    "create-ticket": ["gh issue create"],
}

# Rows 8-9 (create-ticket) / 6-12 (create-pr): plain metadata/best-effort
# reads and writes.
NONCRITICAL_TOKENS = {
    "create-ticket": ["gh label list", "gh project item-add"],
    "create-pr": [
        "gh pr ready",
        "gh pr view",
        "gh label list",
        "gh project item-add",
        "gh pr diff",
        "gh issue comment",
        "gh run list",
    ],
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match, and strip markdown blockquote `> ` line markers so
    a multi-line `> quoted` hint normalizes to the same string as its
    unquoted source constant."""
    body = re.sub(r"(?m)^\s*>\s?", "", body)
    return re.sub(r"\s+", " ", body)


def extract_section(body, heading):
    """Return the body slice from `heading` (a literal, exact heading line)
    up to the next heading of the same-or-higher markdown level, or EOF."""
    idx = body.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    rest = body[idx + len(heading):]
    m = re.search(r"\n#{1," + str(level) + r"}[^#]", rest)
    end = idx + len(heading) + (m.start() if m else len(rest))
    return body[idx:end]


def extract_bullet(section, label):
    """Return one top-level `- **Label**: ...` bullet's text, up to the next
    top-level `- **` bullet or the end of the section. The colon must
    immediately follow the bold label -- this is what distinguishes the
    per-call classification-LIST bullet (`- **Critical**: \\`gh pr list\\`...`)
    from the shared class-DEFINITION bullet, which instead follows the label
    with an em-dash or a parenthetical (`- **Critical** -- a gate input...`,
    `- **Critical** (a gate input...): ...`)."""
    pattern = re.compile(r"-\s+\*\*" + re.escape(label) + r"\*\*:")
    m = pattern.search(section)
    if m is None:
        raise AssertionError("bullet %r not found in section" % label)
    rest = section[m.end():]
    nxt = re.search(r"\n-\s+\*\*", rest)
    end = m.end() + (nxt.start() if nxt else len(rest))
    return section[m.start():end]


class HintDriftTest(unittest.TestCase):
    """AC-2/AC-5 (Option F): the canonical hint is quoted verbatim, sourced
    from acs_lib rather than hardcoded, in all three skills."""

    def test_each_skill_quotes_the_canonical_hint_verbatim(self):
        hint_norm = norm(acs_lib.GH_ACCESS_HINT)
        for name, path in SKILLS.items():
            body_norm = norm(read(path))
            self.assertIn(
                hint_norm, body_norm,
                "%s does not quote acs_lib.GH_ACCESS_HINT verbatim" % name,
            )

    def test_each_skill_names_the_canonical_constant_as_canon(self):
        for name, path in SKILLS.items():
            body = read(path)
            self.assertIn("gh_failure_hint", body, "%s must name gh_failure_hint" % name)
            self.assertIn("acs_lib", body, "%s must name acs_lib" % name)

    def test_each_skill_cites_adr_0088(self):
        for name, path in SKILLS.items():
            body = read(path)
            self.assertIn("ADR-0088", body, "%s must cite ADR-0088" % name)


class ExecutorHintDriftTest(unittest.TestCase):
    """A-P2: the three executor agents must carry the same classification
    canon as their SKILL.md, or a delegated run and an inline run diverge."""

    def test_each_executor_agent_quotes_the_canonical_hint(self):
        hint_norm = norm(acs_lib.GH_ACCESS_HINT)
        for name, path in EXECUTORS.items():
            body_norm = norm(read(path))
            self.assertIn(
                hint_norm, body_norm,
                "%s-executor does not quote acs_lib.GH_ACCESS_HINT verbatim" % name,
            )

    def test_each_executor_agent_names_canon_and_its_own_skill(self):
        for name, path in EXECUTORS.items():
            body = read(path)
            self.assertIn("gh_failure_hint", body, "%s-executor must name gh_failure_hint" % name)
            self.assertIn("acs_lib", body, "%s-executor must name acs_lib" % name)
            self.assertIn(
                "SKILL.md", body,
                "%s-executor must point at its own SKILL.md as the classification canon" % name,
            )


class ExecutorClassificationDriftTest(unittest.TestCase):
    """F1/F4 (iter-2 remediation, MAR-403 iter-1 verify): a prior draft
    quoted the canonical hint sentence (satisfying ExecutorHintDriftTest
    above) while still classifying the Step 5 `gh issue create`
    tracker-sync call as plain non-critical -- hint-sentence presence alone
    does not prove the stated CLASS is right. This pins the actual
    disposition for create-ticket-executor.md, the artifact where that
    drift was found."""

    def test_create_ticket_executor_gh_issue_create_is_hybrid_not_non_critical(self):
        body = read(CREATE_TICKET_EXECUTOR)
        norm_body = norm(body)
        self.assertRegex(
            norm_body, r"(?i)critical per ticket, soft per batch",
            "create-ticket-executor.md must state gh issue create's hybrid "
            "disposition (critical per ticket, soft per batch)",
        )
        self.assertNotIn(
            "non-critical for the Step 5 tracker-sync loop", body,
            "gh issue create must not be classified plain non-critical",
        )
        self.assertNotRegex(
            norm_body, r"(?i)is\s+non-critical:\s+it produces a finding",
            "the Step 5 gh issue create guard must not be classified plain "
            "non-critical",
        )
        self.assertRegex(norm_body, r"(?i)replayable:\s*false")
        self.assertIn("errors", body)


class CriticalClassificationTest(unittest.TestCase):
    """AC-1/AC-2: every gate-input read/write is classified critical."""

    def test_every_critical_call_site_is_classified(self):
        for name, tokens in CRITICAL_TOKENS.items():
            body = read(SKILLS[name])
            section = extract_section(body, HEADINGS[name])
            bullet = norm(extract_bullet(section, "Critical"))
            for tok in tokens:
                self.assertIn(
                    tok, bullet,
                    "%s: %r not classified critical in its failure-policy section" % (name, tok),
                )


class NonCriticalClassificationTest(unittest.TestCase):
    """AC-1/AC-3: metadata/best-effort calls are classified non-critical."""

    def test_every_non_critical_call_site_is_classified(self):
        for name, tokens in NONCRITICAL_TOKENS.items():
            body = read(SKILLS[name])
            section = extract_section(body, HEADINGS[name])
            bullet = norm(extract_bullet(section, "Non-critical"))
            for tok in tokens:
                self.assertIn(
                    tok, bullet,
                    "%s: %r not classified non-critical in its failure-policy section" % (name, tok),
                )


class HybridClassificationTest(unittest.TestCase):
    """AC-1/row 2: the plan's own classification table (plan.md row 2,
    matching design.md:464) classifies create-ticket's `gh issue create`
    tracker-sync call as a distinct hybrid disposition -- critical per
    ticket, soft per batch -- not plain non-critical: a failed create is an
    error-severity finding naming that ticket's id + error + hint,
    `replayable: false`, while the loop still continues to other tickets
    (never a full-batch abort)."""

    def test_gh_issue_create_is_classified_critical_per_ticket_soft_per_batch(self):
        body = read(CREATE_TICKET_SKILL)
        section = extract_section(body, HEADINGS["create-ticket"])
        bullet = norm(extract_bullet(section, HYBRID_LABEL))
        for tok in HYBRID_TOKENS["create-ticket"]:
            self.assertIn(
                tok, bullet,
                "create-ticket: %r not classified %r" % (tok, HYBRID_LABEL),
            )
        self.assertRegex(bullet, r"(?i)error")
        self.assertRegex(bullet, r"replayable:\s*false")
        self.assertNotIn("info", bullet.lower())


class CreateTicketRowTwoClassificationTest(unittest.TestCase):
    """The plan's own classification table (plan.md row 2, matching
    design.md:464) is the authoritative source for this row: critical per
    ticket, soft per batch -- an error-severity finding naming that ticket's
    id + error + hint, `replayable: false`, while the batch still continues
    to other tickets. A prior draft mis-classified this row plain
    non-critical/info; that was corrected (coordinator-authorized fix,
    MAR-403 T2b) to match the plan's table."""

    def test_gh_issue_create_guard_is_preserved_verbatim_and_gains_the_hint(self):
        body = read(CREATE_TICKET_SKILL)
        # The pre-existing batch-continuation mechanics (byte-identical) must
        # survive untouched -- only the severity/replayable/class label changed.
        self.assertIn(
            "does not abort the batch (the loop continues to other",
            body,
        )
        self.assertIn(
            "that ticket's `external` stays null).",
            body,
        )
        norm_body = norm(body)
        self.assertIsNotNone(
            re.search(r"(?i)gh issue create.{0,400}gh_failure_hint", norm_body)
            or re.search(r"(?i)gh_failure_hint.{0,400}gh issue create", norm_body),
            "the gh issue create guard must gain the canonical hint nearby",
        )

    def test_gh_issue_create_call_site_states_error_severity_not_info(self):
        body = read(CREATE_TICKET_SKILL)
        idx = body.index("run the `gh issue create` sequence below once per ticket")
        window_norm = norm(body[idx: idx + 500])
        self.assertRegex(window_norm, r"(?i)error.{0,60}severity finding")
        self.assertIn("replayable: false", window_norm)
        self.assertNotIn("info` finding", window_norm)
        self.assertNotIn("**non-critical**", window_norm)


class CriticalRuleShapeTest(unittest.TestCase):
    """AC-2: the critical rule states verbatim stderr + one hint + stop, and
    forbids falling back to any other transport."""

    def test_critical_rule_stops_and_forbids_another_transport(self):
        for name in SKILLS:
            section_norm = norm(extract_section(read(SKILLS[name]), HEADINGS[name]))
            self.assertRegex(section_norm, r"(?i)verbatim")
            self.assertRegex(section_norm, r"(?i)\bstop\b")
            self.assertIn("fallback to any other transport", section_norm.lower())


class NonCriticalRuleShapeTest(unittest.TestCase):
    """AC-3: the non-critical rule never aborts and always emits a
    replayable command block."""

    def test_non_critical_rule_never_aborts(self):
        for name in ("create-ticket", "create-pr"):
            section_norm = norm(extract_section(read(SKILLS[name]), HEADINGS[name]))
            self.assertRegex(section_norm, r"(?i)never abort")
            self.assertRegex(section_norm, r"(?i)replayable")

    def test_merge_pr_loud_but_non_reverting_class_never_reverts(self):
        section_norm = norm(extract_section(read(MERGE_PR_SKILL), HEADINGS["merge-pr"]))
        self.assertRegex(section_norm, r"(?i)never reverts?")
        self.assertRegex(section_norm, r"(?i)replayable")


class MergePrStep2Test(unittest.TestCase):
    """AC-1's named case: the previously-unguarded merge-pr post-merge
    tracker sync now carries a loud-but-non-reverting rule."""

    def test_merge_pr_step_2_carries_the_loud_but_non_reverting_rule(self):
        section_norm = norm(extract_section(read(MERGE_PR_SKILL), "### Step 2 — Cleanup"))
        self.assertRegex(section_norm, r"(?i)never reverts? the merge")
        self.assertRegex(section_norm, r"(?i)never re-?attempted")
        self.assertRegex(section_norm, r"(?i)error-severity finding")
        self.assertRegex(section_norm, r"(?i)replayable")
        self.assertRegex(section_norm, r"merged:\s*true")


class MergePrExemptModeTest(unittest.TestCase):
    """C-10: the exempt --pr path's `gh pr merge` carries the identical
    critical rule as the ticketed path's Step 1."""

    def test_merge_pr_exempt_mode_carries_the_same_merge_rule(self):
        norm_body = norm(read(MERGE_PR_SKILL))
        # Target only the two REAL command invocations (Step 1's and the
        # exempt path's), not the classification section's own abbreviated
        # mention of the same command (`gh pr merge <number> --<strategy>`).
        matches = [
            m.start()
            for m in re.finditer(r"gh pr merge <(?:number|pr\.number)> --<settings\.merge_strategy>", norm_body)
        ]
        self.assertGreaterEqual(
            len(matches), 2,
            "expected both the ticketed Step 1 and exempt-mode gh pr merge call sites",
        )
        for idx in matches:
            window = norm_body[idx: idx + 600].lower()
            self.assertIn("critical", window)
            self.assertIn("stop", window)
            self.assertIn("fallback to any other transport", window)


class McpRemovalTest(unittest.TestCase):
    """AC-4: no acs skill or agent offers or implies an MCP GitHub
    transport."""

    def test_create_pr_skill_has_no_mcp_fallback_section(self):
        body = read(CREATE_PR_SKILL)
        self.assertNotIn("GitHub MCP fallback", body)
        self.assertNotIn("mcp__github__", body)

    def test_no_acs_skill_or_agent_offers_an_mcp_transport(self):
        paths = (
            glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md"))
            + glob.glob(os.path.join(PLUGIN, "agents", "*.md"))
        )
        self.assertTrue(paths, "expected to find skill/agent files to scan")
        for p in paths:
            body = read(p)
            self.assertNotIn("mcp__", body, "%s references an mcp__ tool" % p)
            self.assertNotIn("MCP fallback", body, "%s references an MCP fallback" % p)
            self.assertNotIn("GitHub MCP", body, "%s references GitHub MCP" % p)


class FrozenPayloadTest(unittest.TestCase):
    """R-B/R-C: deleting the MCP-fallback section must not strand the
    frozen-payload troubleshooting section it used to point into."""

    FROZEN_HEADING = "### CI convention-check troubleshooting (frozen-payload gotcha)"

    def test_frozen_payload_section_is_still_reachable(self):
        body = read(CREATE_PR_SKILL)
        self.assertIn(self.FROZEN_HEADING, body)
        idx = body.index(self.FROZEN_HEADING)
        before = body[:idx]
        self.assertRegex(
            before, r"(?i)frozen-payload gotcha",
            "a pointer into the frozen-payload section must exist earlier in the file",
        )

    def test_frozen_payload_guidance_is_preserved(self):
        body = read(CREATE_PR_SKILL)
        self.assertIn(
            "Never treat a rerun of a stale/superseded run as a valid re-check.",
            body,
        )
        # rerun_workflow_run prohibitions stay byte-identical.
        self.assertIn("`rerun_workflow_run`", body)
        self.assertIn("Never call `rerun_workflow_run` on a stale/superseded run", body)

    def test_mcp_aside_removed_and_unverified_rule_added(self):
        section = extract_section(read(CREATE_PR_SKILL), self.FROZEN_HEADING)
        self.assertNotIn("actions_list", section)
        self.assertNotIn("actions_get", section)
        self.assertNotIn("when `gh` is unavailable", section)
        section_norm = norm(section)
        self.assertRegex(section_norm, r"(?i)non-critical")
        self.assertRegex(section_norm, r"(?i)unverified")
        self.assertRegex(section_norm, r"(?i)never assumed green")


class RuleX1Test(unittest.TestCase):
    """X-1: a label-create never fails the flow around it.

    Two of the three lines are still shell in the prose and stay byte-identical.
    The third -- create-pr's type-label create -- moved into `acs_lib.forge`
    with MAR-525, where the same property holds by CODE construction: the call
    is made and its result deliberately not checked, which is what
    `2>/dev/null || true` meant. Asserted there rather than dropped, because
    X-1 is about the property, not about which language expresses it."""

    def test_rule_x1_label_create_lines_are_unchanged(self):
        create_pr_body = read(CREATE_PR_SKILL)
        create_ticket_body = read(CREATE_TICKET_SKILL)
        self.assertIn(
            'gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true',
            create_pr_body,
        )
        # create-ticket's own label-create moved into acs_lib.forge with
        # MAR-525; the property is asserted below, in the language it now
        # lives in, rather than as a shell line the skill no longer carries.
        self.assertNotIn("gh label create", create_ticket_body)

    def test_rule_x1_holds_for_the_label_create_that_moved_into_code(self):
        gh = acs_lib.Gh(responses={"gh label create": (1, "", "already exists"),
                               "gh pr edit": (0, "", ""),
                               "gh pr diff": (0, "", "")})
        out = acs_lib.pr_metadata_fill(
            gh, {}, {"id": "SHOP-1", "type": "task"},
            {"number": 42, "url": "u"}, "/repo", author="@me",
            resolver=lambda root, files: {"owners": [], "reason": "no_codeowners_file"})
        self.assertIn("gh label create task --description Created by the acs pipeline",
                      gh.calls)
        self.assertIn("label:task", out["applied"],
                      "a failing label create must not stop the label from being applied")
        self.assertFalse([f for f in out["findings"] if "label create" in (f.get("command") or "")],
                         "a label create that fails is not a finding -- it is expected "
                         "when the label already exists")


if __name__ == "__main__":
    unittest.main()
