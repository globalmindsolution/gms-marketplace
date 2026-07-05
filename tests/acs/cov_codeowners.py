#!/usr/bin/env python3
"""Reproducible stdlib-`trace` line-coverage harness for codeowners.py (MAR-103 spec 01).

The repo is Python 3.9+ stdlib-only (no pip) — the pip `coverage` package is NOT
installed — so coverage is measured with the stdlib `trace` module, mirroring
tests/acs/cov_pr_conventions.py. This harness drives find_codeowners_file,
parse_codeowners, match_owners, resolve, and main() across the 9-fixture matrix
(01-codeowners-helper.md Test plan) under trace.Trace(count=1, trace=0), then
reports:

    executed executable lines / total executable lines -> percentage  (gate: >= 90%)

and the missed-line list.  Run:  python3 tests/acs/cov_codeowners.py
(exit 0 iff coverage >= GATE).
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import trace

GATE = 90.0

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_TESTS_DIR))
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "plugins", "acs", "hooks", "scripts")
_TARGET = os.path.join(_SCRIPTS_DIR, "codeowners.py")

if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_target_fresh():
    """Import codeowners.py from source as a fresh module object (inside the tracer)."""
    sys.modules.pop("codeowners_cov_target", None)
    spec = importlib.util.spec_from_file_location("codeowners_cov_target", _TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["codeowners_cov_target"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_main(mod, argv):
    """Drive mod.main() in-process (sets sys.argv, catches its own sys.exit)."""
    real_argv = sys.argv[:]
    real_stdout = sys.stdout
    sys.argv = ["codeowners.py"] + argv
    sys.stdout = io.StringIO()
    try:
        try:
            mod.main()
            code = 0
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
        out = sys.stdout.getvalue()
    finally:
        sys.argv = real_argv
        sys.stdout = real_stdout
    return code, out


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _drive():
    """Fresh-import codeowners.py and exercise every branch — all inside the traced call."""
    mod = _load_target_fresh()
    tmp = tempfile.mkdtemp(prefix="acs-cov-codeowners-")
    try:
        # --- Fixture 1: no CODEOWNERS file at all ---
        empty_root = os.path.join(tmp, "empty_repo")
        os.makedirs(empty_root)
        result = mod.resolve(empty_root, ["src/foo.py"])
        assert result == {"source": None, "owners": [], "reason": "no_codeowners_file"}

        # --- Fixture 2: comment/blank-line skipping ---
        root2 = os.path.join(tmp, "repo2")
        os.makedirs(root2)
        _write(os.path.join(root2, "CODEOWNERS"), (
            "# top comment\n"
            "\n"
            "   \n"
            "*.py @alice\n"
            "# trailing comment\n"
        ))
        result = mod.resolve(root2, ["src/foo.py"])
        assert result["owners"] == ["@alice"]
        assert result["reason"] is None
        assert result["source"] == "CODEOWNERS"

        # --- Fixture 3: last-match-wins across multiple matching lines ---
        root3 = os.path.join(tmp, "repo3")
        os.makedirs(root3)
        _write(os.path.join(root3, "CODEOWNERS"), (
            "*.py @alice\n"
            "src/*.py @bob @carol\n"
        ))
        result = mod.resolve(root3, ["src/foo.py"])
        assert result["owners"] == ["@bob", "@carol"]
        result_rev = mod.resolve(root3, ["other/bar.py"])
        assert result_rev["owners"] == ["@alice"]

        # --- Fixture 4: @user vs @org/team tokens both pass through unchanged ---
        root4 = os.path.join(tmp, "repo4")
        os.makedirs(root4)
        _write(os.path.join(root4, "CODEOWNERS"), (
            "docs/*.md @alice\n"
            "src/*.py @org/team-frontend\n"
        ))
        result_docs = mod.resolve(root4, ["docs/readme.md"])
        assert result_docs["owners"] == ["@alice"]
        result_src = mod.resolve(root4, ["src/app.py"])
        assert result_src["owners"] == ["@org/team-frontend"]

        # --- Fixture 5: author present in raw matched set — returned unfiltered ---
        root5 = os.path.join(tmp, "repo5")
        os.makedirs(root5)
        _write(os.path.join(root5, "CODEOWNERS"), "*.py @author @bob\n")
        result = mod.resolve(root5, ["a.py"])
        assert "@author" in result["owners"]
        assert "@bob" in result["owners"]

        # --- Fixture 6: oversized file cap (>= 5000 lines) ---
        root6 = os.path.join(tmp, "repo6")
        os.makedirs(root6)
        big_lines = "\n".join("*.py @owner%d" % i for i in range(5000))
        _write(os.path.join(root6, "CODEOWNERS"), big_lines + "\n")
        result = mod.resolve(root6, ["a.py"])
        assert result == {"source": None, "owners": [], "reason": "file_too_large"}

        # a file just under the cap is fine
        root6b = os.path.join(tmp, "repo6b")
        os.makedirs(root6b)
        small_lines = "\n".join("*.py @owner%d" % i for i in range(10))
        _write(os.path.join(root6b, "CODEOWNERS"), small_lines + "\n")
        result_ok = mod.resolve(root6b, ["a.py"])
        assert result_ok["reason"] is None

        # --- no pattern matched ---
        root_nomatch = os.path.join(tmp, "repo_nomatch")
        os.makedirs(root_nomatch)
        _write(os.path.join(root_nomatch, "CODEOWNERS"), "*.rb @alice\n")
        result_nomatch = mod.resolve(root_nomatch, ["src/foo.py"])
        assert result_nomatch == {
            "source": "CODEOWNERS", "owners": [], "reason": "no_pattern_matched",
        }

        # --- Fixture 8: precedence-order file resolution ---
        root8 = os.path.join(tmp, "repo8")
        os.makedirs(os.path.join(root8, ".github"))
        os.makedirs(os.path.join(root8, "docs"))
        _write(os.path.join(root8, "CODEOWNERS"), "*.py @root_owner\n")
        _write(os.path.join(root8, "docs", "CODEOWNERS"), "*.py @docs_owner\n")
        _write(os.path.join(root8, ".github", "CODEOWNERS"), "*.py @github_owner\n")
        result8 = mod.resolve(root8, ["a.py"])
        assert result8["source"] == ".github/CODEOWNERS"
        assert result8["owners"] == ["@github_owner"]

        # docs beats root when .github is absent
        root8b = os.path.join(tmp, "repo8b")
        os.makedirs(os.path.join(root8b, "docs"))
        _write(os.path.join(root8b, "CODEOWNERS"), "*.py @root_owner\n")
        _write(os.path.join(root8b, "docs", "CODEOWNERS"), "*.py @docs_owner\n")
        result8b = mod.resolve(root8b, ["a.py"])
        assert result8b["source"] == "docs/CODEOWNERS"
        assert result8b["owners"] == ["@docs_owner"]

        # --- Fixture 9: stdin changed-files list ('-a') same shape as file-path arg ---
        changed_list_path = os.path.join(tmp, "changed.txt")
        _write(changed_list_path, "src/foo.py\nother/bar.py\n")
        with contextlib.redirect_stdout(io.StringIO()):
            code_file, out_file = _run_main(mod, [
                "resolve", "--repo-root", root3, "--changed-files", changed_list_path,
            ])
        assert code_file == 0
        parsed_file = json.loads(out_file)
        assert parsed_file["owners"] == ["@bob", "@carol", "@alice"] or \
            sorted(parsed_file["owners"]) == sorted(["@bob", "@carol", "@alice"])

        real_stdin = sys.stdin
        sys.stdin = io.StringIO("src/foo.py\nother/bar.py\n")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code_stdin, out_stdin = _run_main(mod, [
                    "resolve", "--repo-root", root3, "--changed-files", "-",
                ])
        finally:
            sys.stdin = real_stdin
        assert code_stdin == 0
        parsed_stdin = json.loads(out_stdin)
        assert sorted(parsed_stdin["owners"]) == sorted(parsed_file["owners"])
        assert parsed_stdin["reason"] == parsed_file["reason"]
        assert parsed_stdin["source"] == parsed_file["source"]

        # --- --codeowners-path override (fixture-driven bypass of precedence search) ---
        override_path = os.path.join(tmp, "override_CODEOWNERS")
        _write(override_path, "*.py @override_owner\n")
        with contextlib.redirect_stdout(io.StringIO()):
            code_override, out_override = _run_main(mod, [
                "resolve", "--repo-root", empty_root, "--changed-files", "-",
                "--codeowners-path", override_path,
            ])
        real_stdin = sys.stdin
        sys.stdin = io.StringIO("a.py\n")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code_override, out_override = _run_main(mod, [
                    "resolve", "--repo-root", empty_root, "--changed-files", "-",
                    "--codeowners-path", override_path,
                ])
        finally:
            sys.stdin = real_stdin
        assert code_override == 0
        parsed_override = json.loads(out_override)
        assert parsed_override["owners"] == ["@override_owner"]

        # --- Fixture 7: malformed invocation (omit --changed-files) -> exit 2 ---
        with contextlib.redirect_stderr(io.StringIO()):
            with contextlib.redirect_stdout(io.StringIO()):
                code_bad, _out_bad = _run_main(mod, ["resolve", "--repo-root", root3])
        assert code_bad == 2

        # --- no subcommand at all -> exit 2 ---
        with contextlib.redirect_stderr(io.StringIO()):
            with contextlib.redirect_stdout(io.StringIO()):
                code_none, _out_none = _run_main(mod, [])
        assert code_none == 2

        # --- union across multiple changed files (raw union, not deduped ordering assumption) ---
        result_union = mod.resolve(root3, ["src/foo.py", "other/bar.py"])
        assert set(result_union["owners"]) == {"@bob", "@carol", "@alice"}

        # --- parse_codeowners / match_owners white-box: direct calls for full branch coverage ---
        rules = mod.parse_codeowners("# c\n\n*.py @x\ndocs/** @y @z\n")
        assert rules == [("*.py", ["@x"]), ("docs/**", ["@y", "@z"])]
        assert mod.match_owners(rules, ["docs/a.md"]) == ["@y", "@z"]
        assert mod.match_owners(rules, ["nomatch.txt"]) == []
        assert mod.match_owners([], ["a.py"]) == []

        # --- find_codeowners_file white-box ---
        assert mod.find_codeowners_file(empty_root) is None
        assert mod.find_codeowners_file(root8) == os.path.join(root8, ".github", "CODEOWNERS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _count_from_cover(cover_path):
    """Parse a trace .cover file: count executed/total executable lines and collect misses."""
    import re
    executed = 0
    total = 0
    missed = []
    line_no = 0
    with open(cover_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line_no += 1
            if raw.startswith(">>>>>>"):
                total += 1
                missed.append((line_no, raw[6:].rstrip("\n")))
            else:
                m = re.match(r"\s*(\d+):", raw)
                if m:
                    total += 1
                    executed += 1
    return executed, total, missed


def main():
    covdir = tempfile.mkdtemp(prefix="acs-cov-codeowners-")
    try:
        tracer = trace.Trace(count=1, trace=0)
        devnull = open(os.devnull, "w")
        real_stdout = sys.stdout
        sys.stdout = devnull
        try:
            tracer.runfunc(_drive)
        finally:
            sys.stdout = real_stdout
            devnull.close()
        results = tracer.results()
        results.write_results(summary=False, coverdir=covdir)

        cover_file = None
        for name in os.listdir(covdir):
            if name == "codeowners.cover":
                cover_file = os.path.join(covdir, name)
                break
        if cover_file is None:
            print("ERROR: no codeowners .cover produced in %s" % covdir)
            return 2

        executed, total, missed = _count_from_cover(cover_file)
        pct = (executed * 100.0 / total) if total else 0.0
        print("codeowners.py coverage: %d/%d executable lines = %.1f%% (gate %.0f%%)"
              % (executed, total, pct, GATE))
        if missed:
            print("missed lines (>>>>>> in trace .cover):")
            for ln, src in missed:
                print("  L%d: %s" % (ln, src.strip()))
        else:
            print("missed lines: none")
        result = {"executed": executed, "total": total, "percent": round(pct, 1),
                  "gate": GATE, "passed": pct >= GATE,
                  "missed": [ln for ln, _ in missed]}
        print(json.dumps(result))
        return 0 if pct >= GATE else 1
    finally:
        shutil.rmtree(covdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
