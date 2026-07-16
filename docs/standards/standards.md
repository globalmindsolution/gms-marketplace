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
