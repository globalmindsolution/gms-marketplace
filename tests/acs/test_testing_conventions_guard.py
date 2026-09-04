"""tests/acs/test_testing_conventions_guard.py -- MAR-182: enforce three testing
conventions the coverage epic re-learned the hard way, and repair the one
live violation the prototype found.

Three conventions, each with the concrete failure that motivated it:

1. No updated_at-equality (or ordering) assertion under tests/. acs_lib.now_iso()
   is second-resolution (acs_lib.py:391-392), so a re-save inside the same
   second writes an identical string; such an assertion survived an injected
   mutant in 17 of 20 runs in MAR-169, and in 14 of 20 runs in this ticket's
   own experiment at the site AC-4 repairs, the parent-untouched assertion in
   TestRecordExternal.test_ac6_fanout_children_all_written_parent_untouched
   (named rather than line-anchored: the repair itself moved the line).
   Detection is AST-based rather than textual, and the counts measured on this
   tree say why: a naive substring sweep for the field name under tests/ matches
   66 lines, a tuned line regex over the assert* forms matches 4 -- all four
   false positives inside this very module, three in its own inline fixture
   strings and one on the detector's own assertEqual -- and the AST detector
   flags 0. Convention 2 compares the same way, sweeping for the call form --
   the helper's name immediately followed by an open paren, not the bare name
   (spelling it out here keeps this docstring from counting itself) -- and
   finds 138 substring lines against 7 real AST sites. The advantage is structural, not a headline number -- the
   AST sees a call split across lines, tells a value read from key-list
   membership, and cannot be fooled by a fixture that merely quotes the shape
   it forbids.
2. No acs_case.run_main() call outside a `with ... .pushd(...):`. MAR-177
   proved an unguarded call can flip a live coordinator run to handed_off,
   release the partition lock, and rewrite the operator's REAL
   pipeline-state.json -- not a fixture's throwaway one -- when the process
   cwd is wrong. Seven sites are legitimately exempt; see
   ALLOWED_UNGUARDED_RUN_MAIN below, each entry carrying its own reason and
   evidence, plus a staleness check so a retired exemption cannot rot into a
   silent blind spot.
3. No absence-assertion (assertFalse(os.path.<exists|isfile|isdir|islink|
   lexists>(...))) over a path the module under test never creates. This
   copy-pasted, always-passing shape recurred across the coverage epic
   (MAR-175, MAR-172, MAR-169, MAR-177). Detection resolves the module under
   test from the test module's own MODULE_FILENAME constant and builds a
   1-hop corpus (the target script's source plus the bodies of every
   acs_lib function the target calls as lib.<name>()); depth 1 is the unique
   measured setting with zero false positives on the 7 legitimate sites
   while still catching every negative control (depth 0 false-positives on
   5 of 7 -- lock_path/state_path/sessions_dir live one hop away in
   acs_lib.py; the planning prototype's transitive depth 2 additionally leaked
   index.json as "reachable" from handoff.py -- that leak is a prototype
   measurement and is not reproducible here, because build_corpus below
   implements the single hop only, which makes its depth argument effectively
   binary: 0, versus 1-or-more). No MODULE_FILENAME, or no derivable artifact
   token, and the site abstains rather than guesses.

A fourth convention -- all mutation testing on a copy OUTSIDE the repo, run
synchronously -- is documented in MAR-180 only: an in-tree mutation run that
completes restores the file and leaves no durable trace, so no test here can
detect it. If it recurs, the next lever is a pre-commit hook asserting
`git diff --quiet origin/main -- plugins/` before a test-only commit.

Each guard is demonstrated to FAIL against a deliberately-violating inline
fixture before it passes (AC-5) -- a guard never seen to fire is the exact
defect class this ticket exists to stop.

Stdlib-only (ast, collections, os, re, unittest); imports neither acs_case
nor subprocess, so this guard never couples itself to the fixture it
polices. Python 3.9 floor: no contextlib.chdir, no match statement, no
X | Y annotations, no ast.Str/ast.Num.

Run:
  python3 -m unittest tests.acs.test_testing_conventions_guard -v
"""

import ast
import collections
import os
import sys
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import acs_lib_source  # noqa: E402

SECOND_RESOLUTION_REASON = (
    "acs_lib.now_iso() is second-resolution (acs_lib.py:391-392), so a "
    "re-save inside the same second writes an identical string"
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse whitespace/newlines to single spaces, so a prose substring
    check tolerates docstring line-wrapping."""
    return re.sub(r"\s+", " ", text)


def py_files():
    """Every .py file under tests/, sorted -- including this module itself."""
    found = []
    for dirpath, dirnames, filenames in os.walk(TESTS_DIR):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                found.append(os.path.join(dirpath, filename))
    return sorted(found)


def dotted_name(node):
    """Resolve a Name/Attribute chain to its dotted string, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return base + "." + node.attr if base is not None else None
    return None


def parents_map(tree):
    """Map every node to its parent, so ancestors can be walked without re-walking."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_function(node, parents):
    """The nearest ancestor FunctionDef/AsyncFunctionDef name, or None."""
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return None


# ---------------------------------------------------------------------------
# Detector 1 -- updated_at-equality/ordering assertions (AC-1)
# ---------------------------------------------------------------------------

UPDATED_AT_OPERATORS = {
    "assertEqual", "assertEquals", "assertNotEqual", "assertIs", "assertIsNot",
    "assertGreater", "assertGreaterEqual", "assertLess", "assertLessEqual",
}
_UPDATED_AT_CMPOPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _reads_updated_at(node):
    """True for a value-position read of updated_at -- a["updated_at"],
    .get/.pop("updated_at"), .updated_at -- never a key-list membership,
    kwarg, parameter default, or bare name/string mention."""
    if isinstance(node, ast.Subscript):
        s = node.slice
        return isinstance(s, ast.Constant) and s.value == "updated_at"
    if isinstance(node, ast.Call):
        name = dotted_name(node.func)
        if name is not None and name.rsplit(".", 1)[-1] in ("get", "pop"):
            return (bool(node.args) and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "updated_at")
        return False
    if isinstance(node, ast.Attribute):
        return node.attr == "updated_at"
    return False


def scan_updated_at_equality(tree):
    """[(lineno, enclosing_function)] for every matching call/bare-assert in `tree`."""
    parents = parents_map(tree)
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            method = name.rsplit(".", 1)[-1] if name else None
            if method in UPDATED_AT_OPERATORS and any(_reads_updated_at(a) for a in node.args):
                sites.append((node.lineno, enclosing_function(node, parents)))
        elif isinstance(node, ast.Assert):
            test = node.test
            if isinstance(test, ast.Compare) and all(isinstance(op, _UPDATED_AT_CMPOPS) for op in test.ops):
                operands = [test.left] + list(test.comparators)
                if any(_reads_updated_at(o) for o in operands):
                    sites.append((node.lineno, enclosing_function(node, parents)))
    return sites


def scan_updated_at_equality_repo():
    sites = []
    for path in py_files():
        try:
            tree = ast.parse(read(path), filename=path)
        except SyntaxError:
            continue
        relpath = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
        for lineno, func in scan_updated_at_equality(tree):
            sites.append((relpath, lineno, func))
    return sites


def assert_no_updated_at_equality(sites):
    """No exemption parameter on purpose (AC-4): detector 1 has no allowlist."""
    if sites:
        lines = ["%s:%d in %s()" % (f, l, fn or "<module>") for f, l, fn in sites]
        raise AssertionError(
            "found updated_at-equality/ordering assertion(s) a same-second "
            "re-save cannot be distinguished from a real change by (%s):\n  %s"
            % (SECOND_RESOLUTION_REASON, "\n  ".join(lines)))


class TestNoUpdatedAtEqualityAssertions(unittest.TestCase):
    """AC-1/AC-4/AC-5: no test may assert equality or ordering on a value read
    from an updated_at field -- see SECOND_RESOLUTION_REASON above."""

    def test_no_updated_at_equality_assertion_under_tests(self):
        assert_no_updated_at_equality(scan_updated_at_equality_repo())

    def test_docstring_states_the_second_resolution_reason(self):
        self.assertIn(SECOND_RESOLUTION_REASON, norm(__doc__))

    def test_detector_has_no_allowlist_mechanism(self):
        exemption_like = [name for name in globals()
                           if "ALLOW" in name and "UPDATED_AT" in name]
        self.assertEqual(
            exemption_like, [],
            "detector 1 must have no exemption mechanism (AC-4): found %r" % exemption_like)
        self.assertEqual(
            assert_no_updated_at_equality.__code__.co_argcount, 1,
            "assert_no_updated_at_equality must accept only the scan result -- "
            "an allowlist parameter would create the exemption path AC-4 forbids")

    def test_detector_silent_on_legitimate_shapes(self):
        source = '''
def write_archive_ticket(ws, ticket_id, updated_at="2026-12-31T00:00:00Z"):
    pass


def write_ticket_json_full(ws, tid, created_at, updated_at=None):
    pass


def test_merge_time_boundary_ignores_ticket_updated_at(self):
    """A docstring naming updated_at must never fire the guard."""
    # neither does this comment about updated_at
    self.assertEqual(sorted(t), ["created_at", "id", "updated_at"])
    self.assertIn("updated_at", ticket)
    self.assertIsNotNone(t.get("updated_at"))
    self.assertRegex(t["updated_at"], r"Z$")
'''
        tree = ast.parse(source)
        self.assertEqual(scan_updated_at_equality(tree), [])

    def test_detector_fires_on_a_violating_fixture(self):
        source = '''
def test_bad(self):
    self.assertEqual(
        a.get("updated_at"),
        b.get("updated_at"))


def test_also_bad(self):
    self.assertGreaterEqual(after["updated_at"], before["updated_at"])


def test_bare_assert_bad(self):
    assert a.updated_at == b.updated_at
'''
        tree = ast.parse(source)
        sites = scan_updated_at_equality(tree)
        self.assertEqual(len(sites), 3)
        with self.assertRaises(AssertionError):
            assert_no_updated_at_equality(
                [("fixture.py", lineno, fn) for lineno, fn in sites])


# ---------------------------------------------------------------------------
# Detector 2 -- run_main() outside a pushd() (AC-2), plus its allowlist
# ---------------------------------------------------------------------------

Justification = collections.namedtuple("Justification", "target calls reason evidence")

MIN_REASON_LEN = 60

ALLOWED_UNGUARDED_RUN_MAIN = {
    ("tests/acs/test_codeowners.py", "test_resolve_from_a_changed_files_path_prints_json_and_exits_0"):
        Justification(
            target="codeowners.py",
            calls=1,
            reason="codeowners.py imports no acs_lib and its only open() calls "
                   "(codeowners.py:87, :102) are both mode \"r\"; --repo-root and "
                   "--changed-files here are both absolute tempfile paths, so resolve() "
                   "only ever reads and a wrong cwd cannot make it write against the "
                   "operator's real workspace.",
            evidence="plugins/acs/hooks/scripts/codeowners.py"),
    ("tests/acs/test_codeowners.py", "test_resolve_reads_changed_files_from_stdin_when_dash"):
        Justification(
            target="codeowners.py",
            calls=1,
            reason="--changed-files - reads from stdin (codeowners.py:102), so the only "
                   "filesystem input is the absolute --repo-root; codeowners.py imports no "
                   "acs_lib and its only open() calls (:87, :102) are read-only, so resolve() "
                   "cannot write regardless of cwd.",
            evidence="plugins/acs/hooks/scripts/codeowners.py"),
    ("tests/acs/test_codeowners.py", "test_blank_only_stdin_lines_are_dropped_before_matching"):
        Justification(
            target="codeowners.py",
            calls=1,
            reason="same stdin-only filesystem path as the sibling dash test (codeowners.py:102) "
                   "-- blank-line filtering happens after the read, so the absolute --repo-root "
                   "is again the sole filesystem input and resolve() stays read-only.",
            evidence="plugins/acs/hooks/scripts/codeowners.py"),
    ("tests/acs/test_codeowners.py", "test_missing_required_argument_exits_2"):
        Justification(
            target="codeowners.py",
            calls=1,
            reason="argv omits the required --changed-files (codeowners.py:109 "
                   "required=True), so argparse raises SystemExit(2) inside parse_args() "
                   "(codeowners.py:118) before _read_changed_files/resolve ever run -- zero "
                   "filesystem contact, so cwd is irrelevant.",
            evidence="plugins/acs/hooks/scripts/codeowners.py"),
    ("tests/acs/test_codeowners.py", "test_no_subcommand_exits_2"):
        Justification(
            target="codeowners.py",
            calls=1,
            reason="argv is empty and add_subparsers(dest=\"cmd\", required=True) "
                   "(codeowners.py:116) raises at parse time (codeowners.py:118) before any "
                   "subcommand logic runs -- zero filesystem contact.",
            evidence="plugins/acs/hooks/scripts/codeowners.py"),
    ("tests/acs/test_acs_case_fixture.py", "test_run_main_captures_systemexit_and_stdout"):
        Justification(
            target="new-ticket.py",
            calls=1,
            reason="argv is [\"--help\"]; new-ticket.py:50's parser.parse_args() is the "
                   "first statement after parser construction, so --help exits via "
                   "SystemExit(0) there -- lib.build_context is never reached, so no "
                   "workspace is resolved or written despite new-ticket.py importing "
                   "acs_lib and writing a workspace on its normal path.",
            evidence="plugins/acs/hooks/scripts/new-ticket.py"),
    ("tests/acs/test_acs_case_fixture.py", "test_run_main_returns_cli_exit_code_without_raising"):
        Justification(
            target="new-ticket.py",
            calls=1,
            reason="argv is []; --title and --type are required=True (new-ticket.py:28-29), "
                   "so parse_args() (new-ticket.py:50) exits 2 before any workspace "
                   "resolution -- proving exactly this SystemExit-to-return-code conversion "
                   "is the test's own purpose, so a pushd would add nothing.",
            evidence="plugins/acs/hooks/scripts/new-ticket.py"),
}


def _is_pushd_call(call):
    name = dotted_name(call.func) if isinstance(call, ast.Call) else None
    return name is not None and (name == "pushd" or name.endswith(".pushd"))


def _enclosed_by_pushd(node, parents):
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.With, ast.AsyncWith)):
            for item in cur.items:
                if isinstance(item.context_expr, ast.Call) and _is_pushd_call(item.context_expr):
                    return True
    return False


def scan_unguarded_run_main(tree):
    """[(lineno, enclosing_function)] for every acs_case.run_main(...) / bare
    run_main(...) (only when `from acs_case import run_main`) call with no
    lexically-enclosing `with ... .pushd(...):`."""
    parents = parents_map(tree)
    bare_imported = any(
        isinstance(n, ast.ImportFrom) and n.module == "acs_case"
        and any(alias.name == "run_main" for alias in n.names)
        for n in ast.walk(tree)
    )
    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted_name(node.func)
        fires = name == "acs_case.run_main" or (bare_imported and name == "run_main")
        if fires and not _enclosed_by_pushd(node, parents):
            sites.append((node.lineno, enclosing_function(node, parents)))
    return sites


def scan_unguarded_run_main_repo():
    sites = []
    for path in py_files():
        try:
            tree = ast.parse(read(path), filename=path)
        except SyntaxError:
            continue
        relpath = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
        for lineno, func in scan_unguarded_run_main(tree):
            sites.append((relpath, lineno, func))
    return sites


def _site_key(site):
    file, _lineno, func = site
    return (file, func)


def assert_every_site_allowlisted(sites, allowlist):
    missing = sorted({_site_key(s) for s in sites} - set(allowlist))
    if missing:
        lines = ["%s::%s" % key for key in missing]
        raise AssertionError(
            "unguarded acs_case.run_main() call(s) with no allowlist entry -- wrap it in "
            "`with acs_case.pushd(<tmpdir>):` or add a justified allowlist entry: "
            + ", ".join(lines))


def assert_allowlist_not_stale(sites, allowlist):
    present = {_site_key(s) for s in sites}
    stale = sorted(set(allowlist) - present)
    if stale:
        lines = ["%s::%s" % key for key in stale]
        raise AssertionError(
            "DELETE this entry -- it no longer corresponds to an unguarded run_main call, "
            "and leaving it silently pre-authorises a future unguarded call in that "
            "function: " + ", ".join(lines))


def assert_allowlist_call_counts_match(sites, allowlist):
    counts = collections.Counter(_site_key(s) for s in sites)
    mismatched = []
    for key, justification in allowlist.items():
        if key in counts and counts[key] != justification.calls:
            mismatched.append(
                "%s::%s expected %d unguarded call(s), found %d -- an additional unguarded "
                "run_main appeared inside an already-exempt test"
                % (key[0], key[1], justification.calls, counts[key]))
    if mismatched:
        raise AssertionError("; ".join(mismatched))


def assert_every_entry_states_a_reason(allowlist):
    problems = []
    for key, justification in allowlist.items():
        if not justification.reason or len(justification.reason) < MIN_REASON_LEN:
            problems.append("%s::%s reason is missing or shorter than %d chars"
                             % (key[0], key[1], MIN_REASON_LEN))
        evidence_path = os.path.join(REPO_ROOT, justification.evidence)
        if not os.path.isfile(evidence_path):
            problems.append("%s::%s evidence path does not exist on disk: %s"
                             % (key[0], key[1], justification.evidence))
    if problems:
        raise AssertionError("; ".join(problems))


class TestRunMainIsPushdGuarded(unittest.TestCase):
    """AC-2: every acs_case.run_main() call must be lexically enclosed by a
    `with ... .pushd(...):`, or be named in ALLOWED_UNGUARDED_RUN_MAIN with a
    concrete, evidenced reason -- see the module docstring's convention 2."""

    def test_every_run_main_call_is_pushd_guarded_or_allowlisted(self):
        assert_every_site_allowlisted(scan_unguarded_run_main_repo(), ALLOWED_UNGUARDED_RUN_MAIN)

    def test_allowlist_has_no_stale_entries(self):
        assert_allowlist_not_stale(scan_unguarded_run_main_repo(), ALLOWED_UNGUARDED_RUN_MAIN)

    def test_allowlist_call_counts_match_exactly(self):
        assert_allowlist_call_counts_match(scan_unguarded_run_main_repo(), ALLOWED_UNGUARDED_RUN_MAIN)

    def test_every_allowlist_entry_states_a_reason(self):
        assert_every_entry_states_a_reason(ALLOWED_UNGUARDED_RUN_MAIN)

    def test_detector_silent_on_local_underscore_run_main_helpers(self):
        source = '''
class T(unittest.TestCase):
    def _run_main(self, argv):
        return acs_case.load_module("x.py")

    def test_uses_local_helper(self):
        self._run_main(["a"])
'''
        tree = ast.parse(source)
        self.assertEqual(scan_unguarded_run_main(tree), [])

    def test_detector_fires_on_an_unguarded_fixture(self):
        source = '''
def test_bad():
    acs_case.run_main(mod, [])
'''
        tree = ast.parse(source)
        sites = scan_unguarded_run_main(tree)
        self.assertEqual(len(sites), 1)
        fake_sites = [("fixture.py", sites[0][0], sites[0][1])]
        with self.assertRaises(AssertionError):
            assert_every_site_allowlisted(fake_sites, {})

    def test_staleness_check_fires_on_a_bogus_allowlist_entry(self):
        bogus = {
            ("tests/acs/does_not_exist.py", "test_nope"): Justification(
                target="nowhere.py", calls=1,
                reason="x" * MIN_REASON_LEN,
                evidence="plugins/acs/hooks/scripts/acs_lib.py"),
        }
        with self.assertRaises(AssertionError):
            assert_allowlist_not_stale([], bogus)


# ---------------------------------------------------------------------------
# Detector 3 -- absence-assertion over a never-created path (AC-3)
# ---------------------------------------------------------------------------

FS_CHECKS = {"exists", "isfile", "isdir", "islink", "lexists"}


def _artifact_token(path_expr):
    """One token from an assertFalse(os.path.<check>(<path_expr>)) argument:
    the last string literal for os.path.join(...), else the resolved call's
    own name for a helper call such as acs_case.lib.lock_path(tdir). None
    for anything else (e.g. a bare variable) -- the site then abstains."""
    if isinstance(path_expr, ast.Call):
        name = dotted_name(path_expr.func)
        if name == "os.path.join":
            literals = [a.value for a in path_expr.args
                        if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            return literals[-1] if literals else None
        if name is not None:
            return name.rsplit(".", 1)[-1]
    return None


def scan_vacuous_absence_sites(tree):
    """[(lineno, artifact_token_or_None)] for every assertFalse(os.path.<check>(...))
    call in `tree`; the caller resolves vacuousness against a corpus."""
    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted_name(node.func)
        if name is None or not name.endswith(".assertFalse") or not node.args:
            continue
        inner = node.args[0]
        if not isinstance(inner, ast.Call):
            continue
        inner_name = dotted_name(inner.func)
        if inner_name is None or not inner_name.startswith("os.path.") or not inner.args:
            continue
        if inner_name.rsplit(".", 1)[-1] not in FS_CHECKS:
            continue
        sites.append((node.lineno, _artifact_token(inner.args[0])))
    return sites


def module_under_test(tree):
    """The test module's own top-level `MODULE_FILENAME = "<script>.py"`, or None."""
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "MODULE_FILENAME"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            return node.value.value
    return None


def _lib_referenced_names(tree):
    """Every name the tree calls as `lib.<name>(...)`, anywhere in the module."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name is not None and name.startswith("lib."):
                names.add(name.split(".")[1])
    return names


def build_corpus(target_source, lib_source, depth=1):
    """Pure over two source strings: target_source, plus (at depth >= 1) the
    source of every acs_lib function the target calls as lib.<name>() -- the
    unique depth measured false-positive-free; see the module docstring."""
    corpus = target_source
    if depth >= 1:
        try:
            target_tree = ast.parse(target_source)
            lib_tree = ast.parse(lib_source)
        except SyntaxError:
            return corpus
        wanted = _lib_referenced_names(target_tree)
        bodies = []
        for node in lib_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                segment = ast.get_source_segment(lib_source, node)
                if segment:
                    bodies.append(segment)
        corpus += "\n".join(bodies)
    return corpus


def _verdict(token, corpus):
    return "pass" if token in corpus else "flag"


def scan_vacuous_absence_repo():
    """[(relpath, lineno, token, verdict)]; verdict is "flag", "pass", or "abstain"
    (no MODULE_FILENAME or no derivable token)."""
    lib_source = acs_lib_source()
    results = []
    for path in py_files():
        try:
            tree = ast.parse(read(path), filename=path)
        except SyntaxError:
            continue
        sites = scan_vacuous_absence_sites(tree)
        if not sites:
            continue
        relpath = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
        target_name = module_under_test(tree)
        target_source = None
        if target_name:
            target_path = os.path.join(SCRIPTS_DIR, target_name)
            if os.path.isfile(target_path):
                target_source = read(target_path)
        for lineno, token in sites:
            if token is None or target_source is None:
                results.append((relpath, lineno, token, "abstain"))
                continue
            corpus = build_corpus(target_source, lib_source, depth=1)
            results.append((relpath, lineno, token, _verdict(token, corpus)))
    return results


def assert_no_vacuous_absence(results):
    flagged = [(f, l, t) for f, l, t, v in results if v == "flag"]
    if flagged:
        lines = ["%s:%d token=%r" % (f, l, t) for f, l, t in flagged]
        raise AssertionError(
            "absence-assertion(s) over a path the module under test never creates:\n  "
            + "\n  ".join(lines))


# A floor, not an inventory: the (file, artifact-token) pairs detector 3 decides
# today, and how many sites stand behind them. New checked sites are welcome;
# losing these is the signal that the repo arm stopped resolving anything.
CHECKED_ABSENCE_SITES = {
    ("tests/acs/test_clarify.py", "clarifications.json"),
    ("tests/acs/test_handoff.py", "state_path"),
    ("tests/acs/test_handoff.py", "lock_path"),
    ("tests/acs/test_skill_start.py", "sessions_dir"),
    ("tests/acs/test_skill_start.py", "lock_path"),
}
MIN_CHECKED_ABSENCE_SITES = 7


def assert_repo_arm_still_checks_known_sites(results):
    """Canary: detector 3 flags nothing today, so an all-abstain scan is
    otherwise indistinguishable from a scan that checked everything."""
    checked = [(f, l, t) for f, l, t, v in results if v != "abstain"]
    missing = sorted(CHECKED_ABSENCE_SITES - {(f, t) for f, _lineno, t in checked})
    if missing or len(checked) < MIN_CHECKED_ABSENCE_SITES:
        raise AssertionError(
            "detector 3 stopped deciding sites it used to decide -- %d non-abstaining "
            "site(s), expected at least %d; missing %s. Either the resolution layer "
            "(MODULE_FILENAME -> a script under SCRIPTS_DIR) broke and every site now "
            "abstains silently, or a checked site was legitimately retired and this "
            "floor must be re-derived from scan_vacuous_absence_repo()."
            % (len(checked), MIN_CHECKED_ABSENCE_SITES, missing or "nothing"))


class TestNoVacuousAbsenceAssertions(unittest.TestCase):
    """AC-3: assertFalse(os.path.<check>(...)) must target a path the module
    under test can actually create -- see the module docstring's convention 3
    for the 1-hop closure and its measured depth choice."""

    def test_absence_assertions_target_creatable_paths(self):
        assert_no_vacuous_absence(scan_vacuous_absence_repo())

    def test_detector_silent_on_a_genuinely_creatable_path(self):
        lib_source = acs_lib_source()
        clarify_source = read(os.path.join(SCRIPTS_DIR, "clarify.py"))
        corpus = build_corpus(clarify_source, lib_source, depth=1)
        self.assertEqual(_verdict("clarifications.json", corpus), "pass")

    def test_repo_arm_still_resolves_and_checks_its_known_sites(self):
        """Canary (AC-5) for the real-repo arm, which every other detector-3
        test here bypasses: module_under_test() returning None unconditionally
        left every one of these tests green while the detector checked nothing
        and a planted vacuous assertion went undetected. Pin the resolution
        step in the positive direction, and pin the floor of sites the repo
        scan actually decides -- detector 2's test_allowlist_has_no_stale_entries
        is the in-file precedent."""
        self.assertEqual(module_under_test(ast.parse('MODULE_FILENAME = "clarify.py"\n')),
                         "clarify.py")
        assert_repo_arm_still_checks_known_sites(scan_vacuous_absence_repo())

    def test_canary_fires_when_every_site_abstains(self):
        with self.assertRaises(AssertionError):
            assert_repo_arm_still_checks_known_sites(
                [("fixture.py", 1, "phantom.json", "abstain")])

    def test_abstains_without_a_resolvable_module_under_test(self):
        source = '''
class T(unittest.TestCase):
    def test_x(self):
        self.assertFalse(os.path.exists(os.path.join(tdir, "whatever.json")))
'''
        tree = ast.parse(source)
        self.assertIsNone(module_under_test(tree))

    def test_one_hop_closure_resolves_lib_helpers(self):
        lib_source = acs_lib_source()
        handoff_source = read(os.path.join(SCRIPTS_DIR, "handoff.py"))
        corpus_depth0 = build_corpus(handoff_source, lib_source, depth=0)
        self.assertNotIn("lock_path", corpus_depth0)
        corpus_depth1 = build_corpus(handoff_source, lib_source, depth=1)
        self.assertIn("lock_path", corpus_depth1)

    def test_detector_fires_on_a_never_created_path(self):
        fixture = '''
class T(unittest.TestCase):
    def test_x(self):
        self.assertFalse(os.path.exists(os.path.join(tdir, "phantom.json")))
'''
        tree = ast.parse(fixture)
        sites = scan_vacuous_absence_sites(tree)
        self.assertEqual(len(sites), 1)
        lineno, token = sites[0]
        self.assertEqual(token, "phantom.json")
        corpus = build_corpus("def main():\n    pass\n", "def helper():\n    return 1\n", depth=1)
        self.assertEqual(_verdict(token, corpus), "flag")
        with self.assertRaises(AssertionError):
            assert_no_vacuous_absence([("fixture.py", lineno, token, _verdict(token, corpus))])

    def test_negative_controls_flag_against_real_scripts(self):
        """Coupled to live production content on purpose: it holds only while
        clarify.py never gains the token "pipeline-state.json" and codeowners.py
        never gains "lock_path". If either script legitimately does, re-point the
        control at a token that script still cannot create rather than deleting
        it; the hermetic twin (test_detector_fires_on_a_never_created_path) is
        the primary firing evidence, this control proves it on real sources."""
        lib_source = acs_lib_source()
        clarify_source = read(os.path.join(SCRIPTS_DIR, "clarify.py"))
        corpus_clarify = build_corpus(clarify_source, lib_source, depth=1)
        self.assertEqual(_verdict("pipeline-state.json", corpus_clarify), "flag")

        codeowners_source = read(os.path.join(SCRIPTS_DIR, "codeowners.py"))
        corpus_codeowners = build_corpus(codeowners_source, lib_source, depth=1)
        self.assertEqual(_verdict("lock_path", corpus_codeowners), "flag")


if __name__ == "__main__":
    unittest.main()
