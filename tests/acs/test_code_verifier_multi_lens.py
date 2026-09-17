"""MAR-158 spec 01 — code-verifier multi-lens adversarial rigor upgrade
(verify_depth=="full" only).

Prose-contract tests over `src/acs/agents/code-verifier.md` (new
dimension 14 "Regression-risk" + the 4-lens table) and
`src/acs/skills/code/SKILL.md`'s Verify section (the full-depth 4-lens
spawn + coordinator merge pass; the light-depth path stays byte-for-byte
unchanged), plus the docs/ADR deliverables (AC-4, requirements docs).

Stdlib-only (glob, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_code_verifier_multi_lens -v
"""

import glob
import io
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
REFLECTION_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "reflection.md")
SKILLS_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
PRD_MD = os.path.join(REPO_ROOT, "docs", "product", "prd.md")

VERIFY_HEADING = "### Verify (per iteration) — this IS the changeset review"


def _code_contract():
    """/acs:code's contract: the dispatcher, the four delivery-path legs, and
    the references they share.

    ADR-0095 split one 750-line body this way. These assertions pin what the
    SKILL SAYS, never which of its files says it, so reading the concatenation
    keeps the pin honest while the layout stays free to change -- and a rule
    that genuinely vanishes still fails.
    """
    import glob as _glob
    base = os.path.join(PLUGIN, "skills")
    parts = []
    for name in ("code", "code-trivial", "code-small", "code-standard", "code-complex"):
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            with io.open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    for path in sorted(_glob.glob(os.path.join(base, "code", "references", "*.md"))):
        with io.open(path, encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def code_verifier_body():
    return read(os.path.join(PLUGIN, "agents", "code-verifier.md"))


def leg_body(name):
    """One delivery-path leg's SKILL.md."""
    return read(os.path.join(PLUGIN, "skills", name, "SKILL.md"))


def skill_body():
    return _code_contract()


class LensTableTest(unittest.TestCase):
    """AC-1, AC-3: code-verifier.md documents a 4-lens table (A-D) whose
    dimension assignment is exhaustive and non-overlapping across all 16
    dimensions, plus the verify_lens constraint and -lens-<X>.md naming.

    MAR-74 (slice 4 of epic MAR-69) appended dimensions 15 and 16, so the
    lens table now covers 1-16."""

    ROW_RE = re.compile(r"(?m)^\|\s*([A-D])\s*—[^|]*\|\s*([0-9, ]+?)\s*\|")

    def _rows(self):
        body = code_verifier_body()
        rows = self.ROW_RE.findall(body)
        self.assertEqual(
            len(rows), 4,
            "code-verifier.md must document exactly 4 lens table rows "
            "(A, B, C, D), found %r" % (rows,))
        return rows

    def test_all_four_lenses_named(self):
        rows = self._rows()
        lenses = sorted(letter for letter, _ in rows)
        self.assertEqual(lenses, ["A", "B", "C", "D"],
                          "lens table must name exactly lenses A, B, C, D")

    def test_dimensions_exhaustive_and_non_overlapping(self):
        rows = self._rows()
        all_nums = []
        for _letter, nums in rows:
            parsed = [int(n.strip()) for n in nums.split(",") if n.strip()]
            self.assertTrue(parsed, "each lens row must list at least one "
                                     "dimension number")
            all_nums.extend(parsed)
        self.assertEqual(
            sorted(all_nums), list(range(1, 17)),
            "the 4 lenses together must cover dimensions 1-16 exactly once "
            "each (no omission, no double-assignment); got %r" % (
                sorted(all_nums),))

    def test_verify_lens_constraint_documented(self):
        body = code_verifier_body()
        self.assertIn("verify_lens", body,
                       "code-verifier.md must document the verify_lens "
                       "constraint name")

    def test_lens_artifact_naming_documented(self):
        body = code_verifier_body()
        self.assertRegex(
            body, r"iter-<n>-verify-lens-<A\|B\|C\|D>\.md",
            "code-verifier.md must document the -lens-<A|B|C|D>.md "
            "artifact naming")

    def test_fixed_literal_no_settings_key(self):
        window = section(code_verifier_body(), "## Multi-lens review")
        self.assertRegex(
            window, r"(?i)fixed literal",
            "the lens split must be documented as a fixed literal")
        self.assertNotIn("settings key", window.replace("no settings key", ""),
                          "sanity: 'settings key' should only appear inside "
                          "the 'no settings key' disclaimer")


class NewDimensionTest(unittest.TestCase):
    """AC-1: dimension 14 'Regression-risk' exists, is full-depth/lens-D-only,
    and dimensions 1-13's existing labels are unchanged (regression guard
    against accidental renumbering)."""

    EXISTING_LABELS = [
        "Acceptance-criteria conformance",
        "Tests",
        "Coverage",
        "Business logic",
        "Features",
        "Quality",
        "Technical standards",
        "Architecture",
        "System design",
        "Security",
        "Documentation",
        "Simplicity & scope",
        "Audience-style",
    ]

    def test_dimensions_1_through_13_labels_unchanged(self):
        body = code_verifier_body()
        for n, label in enumerate(self.EXISTING_LABELS, start=1):
            self.assertRegex(
                body,
                r"(?m)^%d\.\s+\*\*%s\*\*" % (n, re.escape(label)),
                "dimension %d must still read '**%s**' unchanged" % (
                    n, label))

    def test_dimension_14_regression_risk_exists(self):
        body = code_verifier_body()
        m = re.search(r"(?m)^14\.\s+\*\*Regression-risk.*$", body)
        self.assertIsNotNone(
            m, "code-verifier.md must have a '14. **Regression-risk**' "
               "dimension item")

    def test_dimension_14_is_full_depth_lens_d_only(self):
        body = code_verifier_body()
        m = re.search(r"(?m)^14\.\s+\*\*Regression-risk.*$", body)
        self.assertIsNotNone(m)
        window = body[m.start():m.start() + 800]
        self.assertRegex(
            window, r"(?i)full-depth",
            "dimension 14 must be documented as full-depth only")
        self.assertIn("lens D", window,
                       "dimension 14 must be documented as lens D")

    def test_dimension_14_appended_after_13_before_retired(self):
        body = code_verifier_body()
        m13 = re.search(r"(?m)^13\.\s+\*\*Audience-style\*\*", body)
        m14 = re.search(r"(?m)^14\.\s+\*\*Regression-risk", body)
        mret = re.search(r"(?m)^\*\*Retired dimensions\.\*\*", body)
        self.assertIsNotNone(m13)
        self.assertIsNotNone(m14)
        self.assertIsNotNone(mret)
        self.assertLess(m13.start(), m14.start(),
                         "dimension 14 must come after dimension 13")
        self.assertLess(m14.start(), mret.start(),
                         "dimension 14 must come before the Retired "
                         "dimensions paragraph")


class ComplexPathSpawnTest(unittest.TestCase):
    """The four-lens spawn and the coordinator-performed merge, now owned by
    the `code-complex` leg (ADR-0095).

    The branch used to be a `verify_depth == "full"` fork inside one body. It is
    a whole leg now, which is why these read code-complex/SKILL.md directly: a
    path that carries the spawn IS the deep path, and there is no depth to
    compute."""

    def _body(self):
        return leg_body("code-complex")

    def test_the_complex_path_spawns_four_parallel_lens_subagents(self):
        window = self._body()
        self.assertIn("4 parallel", window,
                      "must document spawning 4 parallel subagents")
        self.assertIn("acs:code-verifier", window,
                      "must name the acs:code-verifier subagent")
        self.assertIn("verify_lens", window,
                      "must document the verify_lens constraint passed to "
                      "each lens spawn")

    def test_it_does_not_branch_on_a_depth_that_no_longer_exists(self):
        """A leg IS its depth. A surviving verify_depth fork would mean the
        runtime computation ADR-0095 retired had come back."""
        for token in ("verify_depth", "derive_lane", "VERIFY_ITERATION_CAP"):
            with self.subTest(symbol=token):
                self.assertNotIn(token, self._body())

    def test_merge_algorithm_documented(self):
        window = self._body()
        self.assertRegex(window, r"(?i)2 or more.{0,40}lenses",
                         "must document the >=2-lenses-corroborated rule")
        self.assertRegex(window, r"(?i)exactly.{0,10}one.{0,40}lens",
                         "must document the exactly-one-lens re-scrutiny rule")
        self.assertRegex(window, r"(?is)never silently.{0,10}dropped",
                         "must document the never-silently-dropped downgrade rule")
        self.assertIn('severity="info"', window,
                      "must document the info-level downgrade")

    def test_coordinator_writes_single_merged_artifact(self):
        window = self._body()
        self.assertRegex(window, r"(?i)coordinator.{0,80}writes the single merged",
                         "must state the coordinator (never a subagent) writes the "
                         "single merged iter-<n>-verify.md")
        self.assertIn("never a subagent", window,
                      "must state explicitly that no subagent writes the "
                      "merged artifact")

    def test_the_merge_lands_before_the_next_iteration_reads_it(self):
        """The merged list is what the next iteration's executors are given.
        (It used to also feed escalation trigger (a), which ADR-0095 retired —
        the ordering property outlived the consumer that motivated it.)"""
        self.assertRegex(
            self._body(),
            r"(?is)merge write always happens before the next iteration",
            "must state that the merge write precedes the next iteration")


class SingleVerifierPathsTest(unittest.TestCase):
    """Regression guard: the three cheaper paths spawn exactly one verifier,
    write iter-<n>-verify.md directly, and never mention a lens constraint."""

    SINGLE = ("code-trivial", "code-small", "code-standard")

    def test_each_spawns_exactly_one_verifier(self):
        for leg in self.SINGLE:
            with self.subTest(leg=leg):
                body = leg_body(leg)
                self.assertIn("acs:code-verifier", body)
                self.assertRegex(body, r"(?i)One `acs:code-verifier` spawn")

    def test_each_writes_the_verify_artifact_directly(self):
        for leg in self.SINGLE:
            with self.subTest(leg=leg):
                self.assertIn("iter-<n>-verify.md", leg_body(leg))

    def test_none_of_them_passes_a_lens_constraint(self):
        for leg in self.SINGLE:
            with self.subTest(leg=leg):
                self.assertNotIn("verify_lens", leg_body(leg),
                                 "%s is a single-verifier path; a verify_lens "
                                 "constraint here is drift" % leg)


class Adr0067Test(unittest.TestCase):
    """AC-4: docs/adr/0067-*.md exists, Accepted, documents D4 Option B +
    the 4-lens split."""

    def _adr_path(self):
        hits = glob.glob(os.path.join(ADR_DIR, "0067-*.md"))
        self.assertEqual(len(hits), 1,
                          "exactly one docs/adr/0067-*.md must exist, "
                          "found %r" % hits)
        return hits[0]

    def test_adr_0067_exists_and_accepted(self):
        body = read(self._adr_path())
        self.assertRegex(body, r"(?i)status\W+accepted",
                          "ADR 0067 must be Status: Accepted")

    def test_adr_0067_covers_multi_lens_split(self):
        body = read(self._adr_path()).lower()
        self.assertIn("lens", body,
                      "ADR 0067 must document the multi-lens split")
        self.assertIn("verify_depth", body,
                      "ADR 0067 must scope the decision to verify_depth")


def _line_containing(body, anchor):
    """The single physical line containing `anchor` -- located by a stable
    substring that survives the substitution itself, mirroring
    PrdDimensionConsistencyTest's anchor technique, reused for
    reflection.md."""
    hits = [line for line in body.splitlines() if anchor in line]
    if len(hits) != 1:
        raise AssertionError(
            "expected exactly one reflection.md line containing anchor %r, "
            "found %d" % (anchor, len(hits)))
    return hits[0]


class RequirementsDocsUpdatedTest(unittest.TestCase):
    """reflection.md's dimension-count drift (12 -> 14 -> 16/15) is corrected
    and the full-depth multi-lens shape is described; skills.md's
    code-verifier MUST-review bullet mentions the full-depth multi-lens
    shape.

    MAR-74 (slice 4 of epic MAR-69) appends verifier dimensions 15 and 16:
    full verify now reviews 16 dimensions, light verify 15. Each line is
    located by a stable anchor substring that survives the substitution
    itself, plus a file-scope stale-count scan."""

    def test_reflection_md_multi_lens_line_states_16_dimension(self):
        line = _line_containing(read(REFLECTION_MD), "multi-lens review + e2e")
        self.assertIn("16-dimension", line)
        self.assertIn("multi-lens", line)

    def test_reflection_md_multi_lens_dimension_count_is_16(self):
        """Whitespace-normalized: this sentence wraps, and the count and the
        phrase it qualifies land on different source lines."""
        body = re.sub(r"\s+", " ", read(REFLECTION_MD))
        self.assertIn("its 16 dimensions are split across 4 parallel", body)

    def test_reflection_md_single_pass_line_states_15_dimension(self):
        line = _line_containing(read(REFLECTION_MD), "single-subagent")
        self.assertIn("15-dimension", line)

    def test_reflection_md_says_which_dimension_makes_the_difference(self):
        """16 vs 15 is not two review sets: it is one set with dimension 14
        gated on a lens. A doc that states the counts without that reads as an
        arbitrary trim, which is how a reader talks themselves into dropping
        another one."""
        body = re.sub(r"\s+", " ", read(REFLECTION_MD))
        self.assertRegex(
            body,
            r"(?i)dimension 14 \(Regression-risk, git-history\) is lens D's "
            r"alone")

    def test_reflection_md_has_no_stale_dimension_count(self):
        body = read(REFLECTION_MD)
        self.assertNotRegex(
            body, r"1[234][- ]dimension",
            "no 12/13/14-dimension phrase (hyphenated or spaced) may "
            "survive the MAR-74 dimension-count sweep")

    def test_skills_md_code_verifier_bullet_mentions_multi_lens(self):
        body = read(SKILLS_MD)
        window = section(body, "## 3. `/code`")
        self.assertRegex(
            window, r"(?i)multi-lens",
            "skills.md's code-verifier MUST-review bullet must mention the "
            "full-depth multi-lens shape")


class PrdDimensionConsistencyTest(unittest.TestCase):
    """MAR-158 iteration-2 remediation (iter-1-verify.md blocking finding):
    prd.md's 8 mentions of the retired '12-dimension' descriptor are
    corrected to '13-dimension' (lane-neutral gate-list mentions) or
    '14-dimension, multi-lens' (full-verify-specific mentions), mirroring
    reflection.md:56-63. Each line is located by a stable anchor substring
    that survives the substitution itself, not by hardcoded line number.

    MAR-74 (slice 4 of epic MAR-69) appends verifier dimensions 15 and 16,
    making the base set 13 -> 15 dimensions; the same 8 anchors now read
    '15-dimension' (lane-neutral) or '16-dimension, multi-lens'
    (full-verify-specific)."""

    # anchor substring -> the physical prd.md line it identifies (lane-neutral:
    # generic gate-list mentions, not singling out full verify).
    LANE_NEUTRAL_ANCHORS = [
        "G6 — Portability",
        "G11 — Tracker-first delivery",
        "N/A**, never a hard block",
        "gated pipeline (ordering/gating",
    ]

    # anchor substring -> the physical prd.md line it identifies (mentions
    # that explicitly describe only the full-depth verify loop).
    FULL_VERIFY_ANCHORS = [
        "full verify (the",
        "(≤ 3 iterations)",
        "never a per-iteration re-plan",
        "e2e when configured) for",
    ]

    def _line_containing(self, body, anchor):
        hits = [line for line in body.splitlines() if anchor in line]
        self.assertEqual(
            len(hits), 1,
            "expected exactly one prd.md line containing anchor %r, "
            "found %d" % (anchor, len(hits)))
        return hits[0]

    def test_no_stale_12_dimension_string(self):
        body = read(PRD_MD)
        self.assertNotIn(
            "12-dimension", body,
            "the stale '12-dimension' phrase must be fully corrected in "
            "docs/product/prd.md")

    def test_lane_neutral_lines_mention_15_dimension(self):
        body = read(PRD_MD)
        for anchor in self.LANE_NEUTRAL_ANCHORS:
            line = self._line_containing(body, anchor)
            self.assertIn(
                "15-dimension", line,
                "lane-neutral prd.md line near anchor %r must read "
                "'15-dimension'" % anchor)

    def test_full_verify_lines_mention_16_dimension_multi_lens(self):
        body = read(PRD_MD)
        for anchor in self.FULL_VERIFY_ANCHORS:
            line = self._line_containing(body, anchor)
            self.assertIn(
                "16-dimension", line,
                "full-verify-specific prd.md line near anchor %r must "
                "mention '16-dimension'" % anchor)
            self.assertIn(
                "multi-lens", line,
                "full-verify-specific prd.md line near anchor %r must "
                "mention 'multi-lens'" % anchor)


if __name__ == "__main__":
    unittest.main()
