"""Unit tests for the create-prd plan-conformance corroboration script
(`prd_conformance_check`). Mirrors `tests/acs/test_citation_check.py`'s shape:
helpers to build a plan/repo-root/clarifications-ledger fixture, then a
`_run_main`/`_run_cli` pair capturing stdout/stderr for the CLI, plus direct
unit coverage of the three importable rule-family functions. Written for
MAR-304.
"""

import builtins
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS_DIR)
import citation_check  # noqa: E402
import prd_conformance_check  # noqa: E402

SCRIPT_PATH = os.path.join(SCRIPTS_DIR, "prd_conformance_check.py")


def _mkroot():
    return tempfile.mkdtemp(prefix="prd_conformance_root_")


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


def _write_json_tmp(data, prefix):
    fd, path = tempfile.mkstemp(suffix=".json", prefix=prefix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _clarifications_path(entries):
    return _write_json_tmp({"ticket_id": "MAR-000", "clarifications": entries}, "clar_")


def _citation_line(claim, relpath, excerpt):
    return "- %s — `%s` — \"%s\"" % (claim, relpath, excerpt)


def _run_main(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = prd_conformance_check.main(["prd_conformance_check.py"] + argv)
    return code, out.getvalue(), err.getvalue()


def _run_cli(plan_path, mode, repo_root=None, clarifications_path=None,
             prd_path=None, roadmap_path=None, added_headings=None):
    if repo_root is None:
        repo_root = _mkroot()
    if clarifications_path is None:
        clarifications_path = _clarifications_path([])
    if prd_path is None:
        prd_path = _write_plan("")
    if roadmap_path is None:
        roadmap_path = _write_plan("")
    argv = [
        "--plan", plan_path, "--mode", mode,
        "--repo-root", repo_root,
        "--clarifications", clarifications_path,
        "--prd", prd_path, "--roadmap", roadmap_path,
    ]
    for h in (added_headings or []):
        argv += ["--added-heading", h]
    return _run_main(argv)


class CodeEvidenceFamilyTest(unittest.TestCase):
    """AC-3 sub-check b (brownfield): the code-evidence family."""

    def test_legitimate_excerpt_is_clean_and_manifested(self):
        root = _mkroot()
        _write(root, "src/api.py", "def handler():\n    return 200\n")
        plan = (
            "## Code evidence\n"
            + _citation_line("handler returns 200", "src/api.py", "return 200") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        manifest = [json.loads(l) for l in out.splitlines() if l.strip()]
        code_evidence = [m for m in manifest if m.get("family") == "code-evidence"]
        self.assertEqual(len(code_evidence), 1)

    def test_fabricated_excerpt_is_code_citation_excerpt_not_found(self):
        root = _mkroot()
        _write(root, "src/api.py", "def handler():\n    return 200\n")
        plan = (
            "## Code evidence\n"
            + _citation_line("fabricated claim", "src/api.py", "this text is not in the file") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-citation-excerpt-not-found", err)

    def test_traversal_path_is_code_citation_unresolved_without_open(self):
        root = _mkroot()
        outside = _mkroot()
        sentinel = _write(outside, "secret.md", "top secret content")
        rel_escape = os.path.relpath(sentinel, root)
        self.assertTrue(rel_escape.startswith(".."))
        plan = (
            "## Code evidence\n"
            + _citation_line("escaping claim", rel_escape, "top secret content") + "\n"
        )
        plan_path = _write_plan(plan)
        opened = []

        def spy_open(path, *a, **kw):
            opened.append(path)
            return builtins.open(path, *a, **kw)

        with mock.patch("citation_check.open", side_effect=spy_open, create=True):
            code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-citation-unresolved", err)
        self.assertNotIn(sentinel, opened)
        self.assertNotIn(os.path.realpath(sentinel), opened)

    def test_absolute_path_is_code_citation_unresolved(self):
        root = _mkroot()
        outside = _mkroot()
        sentinel = _write(outside, "secret.md", "top secret content")
        plan = (
            "## Code evidence\n"
            + _citation_line("absolute claim", sentinel, "top secret content") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-citation-unresolved", err)

    def test_symlink_escape_is_code_citation_unresolved(self):
        root = _mkroot()
        outside = _mkroot()
        target = _write(outside, "real-secret.md", "escaped content")
        link_path = os.path.join(root, "looks-safe.md")
        os.symlink(target, link_path)
        plan = (
            "## Code evidence\n"
            + _citation_line("symlink claim", "looks-safe.md", "escaped content") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-citation-unresolved", err)

    def test_nul_byte_path_is_a_finding_not_a_crash(self):
        root = _mkroot()
        plan = (
            "## Code evidence\n"
            + _citation_line("nul claim", "a\x00.py", "anything") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-citation-unresolved", err)
        self.assertNotIn("Traceback", err)

    def test_binary_cited_file_is_code_citation_unresolved(self):
        root = _mkroot()
        bad_path = os.path.join(root, "bad.py")
        with open(bad_path, "wb") as fh:
            fh.write(b"\xff\xfe not valid utf-8")
        plan = (
            "## Code evidence\n"
            + _citation_line("bad encoding claim", "bad.py", "anything") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-citation-unresolved", err)

    def test_empty_section_in_brownfield_is_code_evidence_empty(self):
        root = _mkroot()
        plan = "## Code evidence\nJust prose, no citation-shaped lines here.\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        self.assertIn("code-evidence-empty", err)

    def test_greenfield_skips_family_even_with_a_bad_citation(self):
        root = _mkroot()
        plan = (
            "## Code evidence\n"
            + _citation_line("fabricated claim", "does/not/exist.py", "anything") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield", repo_root=root)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        manifest = [json.loads(l) for l in out.splitlines() if l.strip()]
        code_evidence = [m for m in manifest if m.get("family") == "code-evidence"]
        self.assertEqual(code_evidence, [])


class AnswerFidelityFamilyTest(unittest.TestCase):
    """AC-3 sub-check a: the answer-fidelity family."""

    def test_dispositioned_anchor_present_in_named_file_is_clean(self):
        # greenfield mode: isolates this case from the mode-conditional
        # code-evidence family, which would otherwise report
        # code-evidence-empty for this section-less fixture plan.
        prd_path = _write_plan("The system enforces determinism as a core NFR.\n")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan = "## Answer fidelity\n- C-1 — prd.md — \"enforces determinism as a core NFR\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_ledger_entry_absent_from_plan_is_answer_not_dispositioned(self):
        prd_path = _write_plan("Some prd text.\n")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan_path = _write_plan("## Answer fidelity\nNo lines here.\n")
        code, out, err = _run_cli(plan_path, "brownfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("answer-not-dispositioned", err)

    def test_anchor_absent_from_named_file_is_answer_anchor_not_found(self):
        prd_path = _write_plan("Totally different content.\n")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan = "## Answer fidelity\n- C-1 — prd.md — \"text that is not present\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("answer-anchor-not-found", err)

    def test_anchor_matches_across_line_wrapping(self):
        # greenfield mode: isolates this case from the code-evidence family.
        prd_path = _write_plan("This   is\nwrapped   across\nlines with   extra spaces.\n")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "assumed"}])
        plan = ("## Answer fidelity\n"
                "- C-1 — prd.md — \"This is wrapped across lines with extra spaces.\"\n")
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_unknown_target_file_is_answer_anchor_file_unknown(self):
        prd_path = _write_plan("some text")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan = "## Answer fidelity\n- C-1 — design.md — \"some text\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("answer-anchor-file-unknown", err)

    def test_na_entry_is_clean_but_appears_on_the_manifest(self):
        # greenfield mode: isolates this case from the code-evidence family.
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan = "## Answer fidelity\n- C-1 N/A: answer produces no verbatim doc text\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        manifest = [json.loads(l) for l in out.splitlines() if l.strip()]
        af = [m for m in manifest if m.get("family") == "answer-fidelity"]
        self.assertEqual(len(af), 1)
        self.assertEqual(af[0]["id"], "C-1")
        self.assertTrue(af[0].get("na"))

    def test_open_status_ledger_entries_are_not_required(self):
        # greenfield mode: isolates this case from the code-evidence family.
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "open"}])
        plan_path = _write_plan("## Answer fidelity\nNo lines here.\n")
        code, out, err = _run_cli(plan_path, "greenfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_population_comes_from_ledger_not_plan(self):
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan = "## Answer fidelity\n- C-9 — prd.md — \"whatever\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("answer-not-dispositioned", err)

    def test_family_active_in_greenfield(self):
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan_path = _write_plan("## Answer fidelity\nNo lines here.\n")
        code, out, err = _run_cli(plan_path, "greenfield",
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("answer-not-dispositioned", err)


class RoadmapOutlineFamilyTest(unittest.TestCase):
    """AC-3 sub-check c: the roadmap-outline family."""

    def test_declared_milestone_present_in_roadmap_is_clean(self):
        # greenfield mode: isolates this case from the code-evidence family.
        roadmap_path = _write_plan("### M9 — a fast-follow milestone\nBody text.\n")
        prd_path = _write_plan("")
        plan = "## Roadmap milestones\n- Milestone: \"### M9 — a fast-follow milestone\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield",
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_declared_milestone_absent_is_roadmap_milestone_not_found(self):
        roadmap_path = _write_plan("### M9 — a fast-follow milestone\n")
        prd_path = _write_plan("")
        plan = "## Roadmap milestones\n- Milestone: \"### M99 — never shipped\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield",
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("roadmap-milestone-not-found", err)

    def test_semicolon_containing_milestone_title_matches(self):
        real_roadmap = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")
        with open(real_roadmap, encoding="utf-8") as fh:
            roadmap_text = fh.read()
        title = ("### M2.6 — v0.3.5–v0.3.7 fast-follows — complete tracker & "
                  "PR metadata sync; dynamic lane correctness")
        self.assertIn(title, roadmap_text)
        roadmap_path = _write_plan(roadmap_text)
        prd_path = _write_plan("")
        plan = "## Roadmap milestones\n- Milestone: \"%s\"\n" % title
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield",
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertNotIn("roadmap-milestone-not-found", err)

    def test_unplanned_roadmap_heading_in_brownfield_is_roadmap_milestone_unplanned(self):
        roadmap_path = _write_plan("### M9 — planned\n### M10 — never approved\n")
        prd_path = _write_plan("")
        plan = "## Roadmap milestones\n- Milestone: \"### M9 — planned\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield",
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 1)
        self.assertIn("roadmap-milestone-unplanned", err)

    def test_unplanned_heading_in_amend_only_flagged_when_added_heading_names_it(self):
        roadmap_path = _write_plan("### M9 — planned\n### M10 — new in this diff\n")
        prd_path = _write_plan("")
        plan = "## Roadmap milestones\n- Milestone: \"### M9 — planned\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "amend",
                                   prd_path=prd_path, roadmap_path=roadmap_path,
                                   added_headings=["### M10 — new in this diff"])
        self.assertEqual(code, 1)
        self.assertIn("roadmap-milestone-unplanned", err)

    def test_amend_ignores_pre_existing_roadmap_headings(self):
        # amend mode keeps the code-evidence family active, so this fixture
        # carries a clean citation to isolate the roadmap-outline behavior
        # under test.
        root = _mkroot()
        _write(root, "src/api.py", "return 200\n")
        roadmap_path = _write_plan("### M9 — planned\n### M-old — pre-existing, not in this diff\n")
        prd_path = _write_plan("")
        plan = (
            "## Code evidence\n"
            + _citation_line("returns 200", "src/api.py", "return 200") + "\n"
            "## Roadmap milestones\n"
            "- Milestone: \"### M9 — planned\"\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "amend", repo_root=root,
                                   prd_path=prd_path, roadmap_path=roadmap_path,
                                   added_headings=[])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_heading_marker_optional_in_declaration(self):
        # greenfield mode: isolates this case from the code-evidence family.
        roadmap_path = _write_plan("### M9 — planned milestone\n")
        prd_path = _write_plan("")
        plan = "## Roadmap milestones\n- Milestone: \"M9 — planned milestone\"\n"
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "greenfield",
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")


class CliContractTest(unittest.TestCase):

    def test_missing_plan_flag_exits_2(self):
        root = _mkroot()
        clar_path = _clarifications_path([])
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        code, out, err = _run_main([
            "--mode", "brownfield", "--repo-root", root,
            "--clarifications", clar_path, "--prd", prd_path, "--roadmap", roadmap_path,
        ])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_missing_mode_flag_exits_2(self):
        root = _mkroot()
        plan_path = _write_plan("")
        clar_path = _clarifications_path([])
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        code, out, err = _run_main([
            "--plan", plan_path, "--repo-root", root,
            "--clarifications", clar_path, "--prd", prd_path, "--roadmap", roadmap_path,
        ])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_unknown_mode_value_exits_2(self):
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "bogus-mode")
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_unknown_flag_exits_2(self):
        plan_path = _write_plan("")
        root = _mkroot()
        clar_path = _clarifications_path([])
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        code, out, err = _run_main([
            "--plan", plan_path, "--mode", "brownfield", "--repo-root", root,
            "--clarifications", clar_path, "--prd", prd_path, "--roadmap", roadmap_path,
            "--bogus", "x",
        ])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_unreadable_plan_exits_2(self):
        code, out, err = _run_cli("/tmp/does_not_exist_mar304_plan.md", "brownfield")
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_unreadable_clarifications_exits_2(self):
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "brownfield",
                                   clarifications_path="/tmp/does_not_exist_mar304_clar.json")
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_unreadable_prd_exits_2(self):
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "brownfield",
                                   prd_path="/tmp/does_not_exist_mar304_prd.md")
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_unreadable_roadmap_exits_2(self):
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "brownfield",
                                   roadmap_path="/tmp/does_not_exist_mar304_roadmap.md")
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_clarifications_not_a_list_exits_2(self):
        clar_path = _write_json_tmp({"ticket_id": "x", "clarifications": "not-a-list"}, "badclar2_")
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "brownfield", clarifications_path=clar_path)
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_flag_with_no_value_exits_2(self):
        code, out, err = _run_main(["--plan"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_malformed_clarifications_json_exits_2(self):
        fd, path = tempfile.mkstemp(suffix=".json", prefix="badclar_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("not valid json{{{")
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "brownfield", clarifications_path=path)
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_added_heading_outside_amend_mode_exits_2(self):
        plan_path = _write_plan("")
        code, out, err = _run_cli(plan_path, "brownfield", added_headings=["### M1"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_finding_line_uses_plan_locus_and_documented_format(self):
        root = _mkroot()
        _write(root, "src/api.py", "real content here.\n")
        plan = (
            "# Plan\n\n"
            "## Code evidence\n"
            + _citation_line("bad claim", "src/api.py", "text not present") + "\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root)
        self.assertEqual(code, 1)
        finding_lines = [l for l in err.splitlines() if l.startswith(plan_path + ":")]
        self.assertTrue(finding_lines)
        self.assertRegex(finding_lines[0], r"^.+:\d+: \[[a-z-]+\] .+$")
        # the citation line is line 4 (1-indexed) in the plan text above.
        self.assertTrue(finding_lines[0].startswith(plan_path + ":4:"))

    def test_clean_run_prints_one_json_line_per_manifest_entry_with_family_key(self):
        root = _mkroot()
        _write(root, "src/api.py", "return 200\n")
        prd_path = _write_plan("Determinism is required.\n")
        roadmap_path = _write_plan("### M9 — planned milestone\n")
        clar_path = _clarifications_path([{"id": "C-1", "status": "answered"}])
        plan = (
            "## Code evidence\n"
            + _citation_line("returns 200", "src/api.py", "return 200") + "\n"
            "## Answer fidelity\n"
            "- C-1 — prd.md — \"Determinism is required.\"\n"
            "## Roadmap milestones\n"
            "- Milestone: \"### M9 — planned milestone\"\n"
        )
        plan_path = _write_plan(plan)
        code, out, err = _run_cli(plan_path, "brownfield", repo_root=root,
                                   clarifications_path=clar_path,
                                   prd_path=prd_path, roadmap_path=roadmap_path)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertEqual(len(lines), 3)
        families = set()
        for l in lines:
            entry = json.loads(l)
            self.assertIn("family", entry)
            families.add(entry["family"])
        self.assertEqual(families, {"code-evidence", "answer-fidelity", "roadmap-outline"})

    def test_script_writes_no_file(self):
        root = _mkroot()
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([])
        plan_path = _write_plan("")

        def _snapshot():
            found = set()
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    found.add(os.path.join(dirpath, fn))
            return found

        before = _snapshot()
        _run_cli(plan_path, "brownfield", repo_root=root,
                  clarifications_path=clar_path, prd_path=prd_path, roadmap_path=roadmap_path)
        after = _snapshot()
        self.assertEqual(before, after)


class SubprocessInvocationTest(unittest.TestCase):
    """K8: the sibling `citation_check` import must resolve when the script is
    invoked by absolute path from an unrelated cwd, the way the verifier will
    actually invoke it."""

    def test_clean_run_via_subprocess_exits_zero(self):
        cwd = tempfile.mkdtemp(prefix="prd_conformance_cwd_")
        root = _mkroot()
        _write(root, "src/api.py", "return 200\n")
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([])
        plan = (
            "## Code evidence\n"
            + _citation_line("returns 200", "src/api.py", "return 200") + "\n"
        )
        plan_path = _write_plan(plan)
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH,
             "--plan", plan_path, "--mode", "brownfield",
             "--repo-root", root, "--clarifications", clar_path,
             "--prd", prd_path, "--roadmap", roadmap_path],
            cwd=cwd, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_finding_run_via_subprocess_exits_one(self):
        cwd = tempfile.mkdtemp(prefix="prd_conformance_cwd_")
        root = _mkroot()
        prd_path = _write_plan("")
        roadmap_path = _write_plan("")
        clar_path = _clarifications_path([])
        plan = (
            "## Code evidence\n"
            + _citation_line("fabricated claim", "does/not/exist.py", "anything") + "\n"
        )
        plan_path = _write_plan(plan)
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH,
             "--plan", plan_path, "--mode", "brownfield",
             "--repo-root", root, "--clarifications", clar_path,
             "--prd", prd_path, "--roadmap", roadmap_path],
            cwd=cwd, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("ModuleNotFoundError", result.stderr)


class HelperReuseTest(unittest.TestCase):
    """AC-4/C-1: the security-critical containment code is shared by import,
    never re-implemented."""

    def test_extract_citations_is_the_imported_citation_check_object(self):
        self.assertIs(prd_conformance_check.extract_citations, citation_check.extract_citations)

    def test_resolve_and_check_is_the_imported_citation_check_object(self):
        self.assertIs(prd_conformance_check.resolve_and_check, citation_check.resolve_and_check)

    def test_module_defines_no_private_path_helpers(self):
        self.assertFalse(hasattr(prd_conformance_check, "_is_unsafe_path"))
        self.assertFalse(hasattr(prd_conformance_check, "_resolve_under_roots"))


if __name__ == "__main__":
    unittest.main()
