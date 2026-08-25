"""Unit tests for the upstream-citation corroboration script (`citation_check`).

Mirrors `tests/acs/test_structure_lint.py`'s shape: unit tests for the
extraction/resolution/match rules, then tests for the `main(argv)` CLI entry
point. Written for MAR-303.
"""

import builtins
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
import citation_check  # noqa: E402


def _mkroot():
    return tempfile.mkdtemp(prefix="citation_check_root_")


def _write(root, relpath, content):
    path = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _write_plan(content):
    fd, path = tempfile.mkstemp(suffix=".md", prefix="plan_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _citation_line(claim, relpath, excerpt):
    return "- %s — `%s` — \"%s\"" % (claim, relpath, excerpt)


class TestUpstreamInventoryExtraction(unittest.TestCase):
    """D5: heading found at any level 1-6; body bounded by next equal-or-higher heading."""

    def test_heading_found_at_level_2(self):
        text = (
            "## Upstream inventory\n"
            + _citation_line("claim one", "a.md", "hello world") + "\n"
            + "## Next section\n"
            + _citation_line("outside claim", "b.md", "nope") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].claim, "claim one")

    def test_heading_found_at_level_4(self):
        text = (
            "#### Upstream inventory\n"
            + _citation_line("claim one", "a.md", "hello world") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual(len(citations), 1)

    def test_body_bounded_by_next_equal_or_higher_heading(self):
        text = (
            "# Doc\n"
            "## Upstream inventory\n"
            + _citation_line("in scope", "a.md", "hello world") + "\n"
            "## Downstream\n"
            + _citation_line("out of scope", "b.md", "nope") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual([c.claim for c in citations], ["in scope"])

    def test_body_bounded_by_higher_level_heading(self):
        text = (
            "## Upstream inventory\n"
            + _citation_line("in scope", "a.md", "hello world") + "\n"
            "# Higher heading\n"
            + _citation_line("out of scope", "b.md", "nope") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual([c.claim for c in citations], ["in scope"])

    def test_citation_shaped_line_outside_section_yields_no_finding(self):
        root = _mkroot()
        _write(root, "a.md", "hello world")
        text = (
            _citation_line("before section", "a.md", "not real text") + "\n"
            "## Upstream inventory\n"
            + _citation_line("in scope", "a.md", "hello world") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_missing_heading_yields_no_citations(self):
        text = "## Some other section\nNo upstream inventory here.\n"
        citations = citation_check.extract_citations(text)
        self.assertEqual(citations, [])

    def test_non_citation_lines_in_section_are_ignored(self):
        text = (
            "## Upstream inventory\n"
            "principles/ N/A: this skill has no principles root\n"
            + _citation_line("real claim", "a.md", "hello world") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual([c.claim for c in citations], ["real claim"])


def _run_main(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = citation_check.main(["citation_check.py"] + argv)
    return code, out.getvalue(), err.getvalue()


class TestCleanRunExitsZeroWithManifest(unittest.TestCase):

    def test_valid_citation_exits_zero_with_manifest_line(self):
        root = _mkroot()
        _write(root, "prd.md", "Some PRD text.\nDeterminism is a stated NFR.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("Determinism NFR", "prd.md", "Determinism is a stated NFR.") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(set(entry.keys()), {"claim", "path", "line", "excerpt"})
        self.assertEqual(entry["claim"], "Determinism NFR")
        self.assertEqual(entry["path"], "prd.md")


class TestFabricatedExcerptFails(unittest.TestCase):

    def test_excerpt_absent_from_real_file_exits_one(self):
        root = _mkroot()
        _write(root, "prd.md", "Some real PRD text.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("fabricated claim", "prd.md", "text that is not in the file") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-excerpt-not-found", err)
        self.assertEqual(out, "")


class TestFabricatedPathFails(unittest.TestCase):

    def test_path_resolving_under_no_root_exits_one(self):
        root = _mkroot()
        _write(root, "prd.md", "Some real PRD text.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("nonexistent file claim", "does/not/exist.md", "anything") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-unresolved", err)


class TestTraversalAndAbsolutePathRejected(unittest.TestCase):

    def test_traversal_path_rejected_without_open(self):
        root = _mkroot()
        outside_dir = _mkroot()
        sentinel = _write(outside_dir, "secret.md", "top secret content")
        rel_escape = os.path.relpath(sentinel, root)
        self.assertTrue(rel_escape.startswith(".."))
        text = (
            "## Upstream inventory\n"
            + _citation_line("escaping claim", rel_escape, "top secret content") + "\n"
        )
        plan_path = _write_plan(text)
        opened_paths = []

        def spy_open(path, *a, **kw):
            opened_paths.append(path)
            return builtins.open(path, *a, **kw)

        with mock.patch("citation_check.open", side_effect=spy_open, create=True):
            code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-unresolved", err)
        self.assertEqual(out, "")
        self.assertNotIn(sentinel, opened_paths)
        self.assertNotIn(os.path.realpath(sentinel), opened_paths)

    def test_absolute_path_rejected_without_open(self):
        root = _mkroot()
        outside_dir = _mkroot()
        sentinel = _write(outside_dir, "secret.md", "top secret content")
        text = (
            "## Upstream inventory\n"
            + _citation_line("absolute claim", sentinel, "top secret content") + "\n"
        )
        plan_path = _write_plan(text)
        opened_paths = []

        def spy_open(path, *a, **kw):
            opened_paths.append(path)
            return builtins.open(path, *a, **kw)

        with mock.patch("citation_check.open", side_effect=spy_open, create=True):
            code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-unresolved", err)
        self.assertNotIn(sentinel, opened_paths)


class TestSymlinkEscapeRejected(unittest.TestCase):

    def test_symlink_inside_root_escaping_via_realpath_rejected(self):
        root = _mkroot()
        outside_dir = _mkroot()
        target = _write(outside_dir, "real-secret.md", "escaped content")
        link_path = os.path.join(root, "looks-safe.md")
        os.symlink(target, link_path)
        text = (
            "## Upstream inventory\n"
            + _citation_line("symlink claim", "looks-safe.md", "escaped content") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-unresolved", err)


class TestEmptyInventoryFails(unittest.TestCase):

    def test_section_present_with_zero_parseable_citations_exits_one(self):
        text = "## Upstream inventory\nJust prose, no citation-shaped lines here.\n"
        plan_path = _write_plan(text)
        root = _mkroot()
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-inventory-empty", err)

    def test_section_heading_entirely_absent_exits_one(self):
        text = "## Some other heading\nNo inventory section at all.\n"
        plan_path = _write_plan(text)
        root = _mkroot()
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-inventory-empty", err)


class TestWhitespaceNormalization(unittest.TestCase):

    def test_excerpt_differing_only_by_whitespace_passes(self):
        root = _mkroot()
        _write(root, "a.md", "This   is\nwrapped   across\nlines with   extra spaces.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("wrapped claim", "a.md", "This is wrapped across lines with extra spaces.") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_excerpt_differing_in_words_fails(self):
        root = _mkroot()
        _write(root, "a.md", "This is the actual text in the file.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("wrong words claim", "a.md", "This is a different sentence entirely.") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-excerpt-not-found", err)


class TestDistinctFileReadOnce(unittest.TestCase):

    def test_two_citations_to_same_path_read_file_once(self):
        root = _mkroot()
        cited = _write(root, "a.md", "shared content across two claims.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("claim one", "a.md", "shared content") + "\n"
            + _citation_line("claim two", "a.md", "across two claims") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual(len(citations), 2)
        call_count = {"a.md": 0}

        def counting_open(path, *a, **kw):
            if os.path.realpath(path) == os.path.realpath(cited):
                call_count["a.md"] += 1
            return builtins.open(path, *a, **kw)

        with mock.patch("citation_check.open", side_effect=counting_open, create=True):
            findings, manifest = citation_check.resolve_and_check(
                citations, {"prd": root}, "plan.md")
        self.assertEqual(findings, [])
        self.assertEqual(len(manifest), 2)
        self.assertEqual(call_count["a.md"], 1)


class TestUsageErrors(unittest.TestCase):

    def test_missing_plan_flag_exits_2(self):
        root = _mkroot()
        code, out, err = _run_main(["--root", "prd=" + root])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_plan_flag_with_no_value_exits_2(self):
        code, out, err = _run_main(["--plan"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_no_root_at_all_exits_2(self):
        plan_path = _write_plan("## Upstream inventory\n")
        code, out, err = _run_main(["--plan", plan_path])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_root_flag_with_no_value_exits_2(self):
        plan_path = _write_plan("## Upstream inventory\n")
        code, out, err = _run_main(["--plan", plan_path, "--root"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_malformed_root_missing_equals_exits_2(self):
        plan_path = _write_plan("## Upstream inventory\n")
        code, out, err = _run_main(["--plan", plan_path, "--root", "architecture-no-equals"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_root_with_empty_name_exits_2(self):
        plan_path = _write_plan("## Upstream inventory\n")
        code, out, err = _run_main(["--plan", plan_path, "--root", "=some/path"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_root_with_empty_value_exits_2(self):
        plan_path = _write_plan("## Upstream inventory\n")
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd="])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_unrecognized_argument_exits_2(self):
        plan_path = _write_plan("## Upstream inventory\n")
        code, out, err = _run_main(["--plan", plan_path, "--bogus", "x"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_unreadable_nonexistent_plan_file_exits_2(self):
        root = _mkroot()
        code, out, err = _run_main([
            "--plan", "/tmp/does_not_exist_mar303_plan.md",
            "--root", "prd=" + root,
        ])
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_plan_file_with_invalid_utf8_exits_2(self):
        fd, path = tempfile.mkstemp(suffix=".md", prefix="badplan_")
        with os.fdopen(fd, "wb") as fh:
            fh.write(b"\xff\xfe not valid utf-8 heading text")
        root = _mkroot()
        code, out, err = _run_main(["--plan", path, "--root", "prd=" + root])
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())


class TestFindingLineFormat(unittest.TestCase):

    def test_finding_matches_source_line_rule_message_and_uses_plan_locus(self):
        root = _mkroot()
        _write(root, "a.md", "real content here.\n")
        text = (
            "# Plan\n\n"
            "## Upstream inventory\n"
            + _citation_line("bad claim", "a.md", "text not present") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        finding_lines = [l for l in err.splitlines() if l.startswith(plan_path + ":")]
        self.assertTrue(finding_lines)
        self.assertRegex(finding_lines[0], r"^.+:\d+: \[[a-z-]+\] .+$")
        # the citation line is line 4 (1-indexed) in the plan file above.
        self.assertTrue(finding_lines[0].startswith(plan_path + ":4:"))


class TestResolutionAndMatch(unittest.TestCase):
    """Direct unit tests of resolve_and_check(), independent of the CLI."""

    def test_multiple_roots_resolves_against_correct_root(self):
        prd_root = _mkroot()
        arch_root = _mkroot()
        _write(prd_root, "prd.md", "prd fact text.\n")
        _write(arch_root, "architecture/hld.md", "architecture fact text.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("prd claim", "prd.md", "prd fact text") + "\n"
            + _citation_line("arch claim", "architecture/hld.md", "architecture fact text") + "\n"
        )
        citations = citation_check.extract_citations(text)
        findings, manifest = citation_check.resolve_and_check(
            citations, {"prd": prd_root, "architecture": arch_root}, "plan.md")
        self.assertEqual(findings, [])
        self.assertEqual(len(manifest), 2)

    def test_advisory_line_ref_in_path_is_stripped_before_resolution(self):
        root = _mkroot()
        _write(root, "prd.md", "line one\nline two\nline three\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("ref claim", "prd.md:2", "line two") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual(citations[0].path, "prd.md")
        findings, manifest = citation_check.resolve_and_check(
            citations, {"prd": root}, "plan.md")
        self.assertEqual(findings, [])
        self.assertEqual(manifest[0]["path"], "prd.md")

    def test_advisory_line_range_ref_in_path_is_stripped(self):
        root = _mkroot()
        _write(root, "prd.md", "line one\nline two\nline three\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("range claim", "prd.md:1-3", "line two") + "\n"
        )
        citations = citation_check.extract_citations(text)
        self.assertEqual(citations[0].path, "prd.md")

    def test_cited_file_with_invalid_utf8_is_citation_unresolved(self):
        root = _mkroot()
        bad_path = os.path.join(root, "bad.md")
        with open(bad_path, "wb") as fh:
            fh.write(b"\xff\xfe not valid utf-8")
        text = (
            "## Upstream inventory\n"
            + _citation_line("bad encoding claim", "bad.md", "anything") + "\n"
        )
        citations = citation_check.extract_citations(text)
        findings, manifest = citation_check.resolve_and_check(
            citations, {"prd": root}, "plan.md")
        self.assertEqual(manifest, [])
        self.assertEqual([f.rule for f in findings], ["citation-unresolved"])

    def test_finding_namedtuple_has_four_fields(self):
        self.assertEqual(
            citation_check.Finding._fields,
            ("source", "line", "rule", "message"))


class TestMalformedPathDoesNotCrash(unittest.TestCase):
    """F3: a NUL-byte (or otherwise unresolvable) citation path must become a
    citation-unresolved finding for that one citation, never a process crash
    that discards sibling citations' results."""

    def test_nul_byte_path_is_a_finding_not_a_crash(self):
        root = _mkroot()
        text = (
            "## Upstream inventory\n"
            + _citation_line("nul claim", "a\x00.md", "anything") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-unresolved", err)
        self.assertNotIn("Traceback", err)

    def test_sibling_citations_still_resolved_when_one_path_is_malformed(self):
        root = _mkroot()
        _write(root, "a.md", "first valid fact.\n")
        _write(root, "b.md", "second valid fact.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("first claim", "a.md", "first valid fact") + "\n"
            + _citation_line("nul claim", "bad\x00.md", "anything") + "\n"
            + _citation_line("second claim", "b.md", "second valid fact") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        out_lines = [l for l in out.splitlines() if l.strip()]
        self.assertEqual(len(out_lines), 2)
        claims = {json.loads(l)["claim"] for l in out_lines}
        self.assertEqual(claims, {"first claim", "second claim"})
        err_lines = [l for l in err.splitlines() if l.strip()]
        self.assertEqual(len(err_lines), 1)
        self.assertIn("citation-unresolved", err_lines[0])

    def test_malformed_path_finding_uses_documented_format(self):
        root = _mkroot()
        text = (
            "# Plan\n\n"
            "## Upstream inventory\n"
            + _citation_line("nul claim", "a\x00.md", "anything") + "\n"
        )
        plan_path = _write_plan(text)
        code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        finding_lines = [l for l in err.splitlines() if l.startswith(plan_path + ":")]
        self.assertTrue(finding_lines)
        self.assertRegex(finding_lines[0], r"^.+:\d+: \[citation-unresolved\] .+$")
        # the citation line is line 4 (1-indexed) in the plan file above.
        self.assertTrue(finding_lines[0].startswith(plan_path + ":4:"))

    def test_unexpected_valueerror_during_resolution_is_contained(self):
        root = _mkroot()
        _write(root, "a.md", "some real content.\n")
        text = (
            "## Upstream inventory\n"
            + _citation_line("claim one", "a.md", "some real content") + "\n"
        )
        plan_path = _write_plan(text)
        with mock.patch("citation_check.os.path.realpath", side_effect=ValueError("boom")):
            code, out, err = _run_main(["--plan", plan_path, "--root", "prd=" + root])
        self.assertEqual(code, 1)
        self.assertIn("citation-unresolved", err)
        self.assertNotIn("Traceback", err)

    def test_plan_path_with_nul_byte_exits_two(self):
        root = _mkroot()
        code, out, err = _run_main(["--plan", "pl\x00an.md", "--root", "prd=" + root])
        self.assertEqual(code, 2)
        self.assertIn("error reading", err.lower())
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
