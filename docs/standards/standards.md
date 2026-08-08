# Standards

A first-class, documentary record of the coding and testing standards this
repository holds itself to. It states what the codebase does today; it is not a
runtime-enforced settings surface (`standards_path` is intentionally left unset)
— the guard test and the pipeline guidance are the live enforcers.

## Naming conventions

### Test file naming

Test modules are named by the component/behavior under test, never by a ticket
id (`test_<component_or_behavior>.py`). The originating ticket reference lives
in the module docstring, not in the filename — a ticket
id in source (filename, comment, or docstring line that stands in for a name)
couples the test to tracker state and reads as noise to anyone browsing the
suite. This extends the standing "never a ticket id in source" rule from code
comments and docstrings to test filenames.

- Good: `test_release_notes.py`, `test_skill_contracts.py`,
  `test_changelog_unreleased_entry.py`.
- Avoid: `test_mar147_rename.py` (ticket id in the filename).

The `MAR-<NNN>` reference that motivated a test still belongs in the module
docstring — that is where the traceability lives.

## Testing conventions

New behavior is covered by a test that is named for the behavior it pins, so the
suite reads as a description of what the system does rather than a log of which
tickets touched it. A behavior-named guard test
(`tests/acs/test_test_naming_convention.py`) enforces the test-file-naming
standard above: it fails CI if any file under `tests/acs/` reintroduces a
ticket id in its filename.

Four further conventions govern how a test under `tests/` may assert, each
bought with a real failure during the coverage epic (MAR-168's C-9/C-10
clarification payload):

1. **Never assert equality or ordering on an `updated_at` value.**
   `acs_lib.now_iso()` is second-resolution (`acs_lib.py:391-392`), so a
   re-save inside the same second writes an identical string; such an
   assertion survived an injected mutant in 17 of 20 runs in MAR-169.
   **Enforced** — `tests/acs/test_testing_conventions_guard.py` detector 1,
   deliberately with no allowlist mechanism.
2. **Run all mutation testing on a copy taken outside the repo, synchronously
   — never in-tree, never backgrounded.** Two interrupted in-tree runs each
   left a MUTANT in `plugins/acs/hooks/scripts/clarify.py`, and one left an
   orphaned background mutator that corrupted a coordinator diagnosis into
   instructing a wrong fix (MAR-177). **Not enforceable by a test** — a
   completed in-tree run restores the file and leaves no durable trace, so
   no test here can detect that it happened; this convention is honour-system.
   If it recurs, the next lever is a pre-commit hook asserting
   `git diff --quiet origin/main -- plugins/` before a test-only commit.
3. **Wrap every `run_main()` call in a test in `with ... .pushd(<tmpdir>):`.**
   An unguarded call was proven able to flip a live coordinator run to
   `handed_off`, release the partition lock, and rewrite the operator's REAL
   `pipeline-state.json` (MAR-177). **Enforced** —
   `tests/acs/test_testing_conventions_guard.py` detector 2, with a
   staleness-checked allowlist of 7 legitimately-exempt sites, each carrying
   its own reason and on-disk evidence path.
4. **Never assert the absence of an artifact the code under test never
   creates.** This copy-pasted, always-passing shape recurred across
   MAR-175, MAR-172, MAR-169 and MAR-177 — six sites in total. **Enforced** —
   `tests/acs/test_testing_conventions_guard.py` detector 3, which resolves
   the module under test and abstains rather than guesses when it cannot.
