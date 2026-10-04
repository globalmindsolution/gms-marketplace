"""acs_lib.migrate_settings — rewrite an old settings file to the current shape.

Settings changed shape three times (ADR-0115, ADR-0116 and this one), and a hard
break is only kind if the way across is one command. `migrate` takes the parsed
content of ONE settings file and returns the new content and a list of what it
did; `legacy_problems` names what a loaded settings object still carries from
the old shapes, so a validator can refuse it loudly instead of silently reading
the wrong thing (an ignored `suites` block is a test suite that quietly stops
running).

    test_coverage_percent      -> tests.coverage
    suites.<name>              -> tests.<name>
    e2e (and suites.e2e)       -> tests.e2e
    tests.command / tests.setup (the CI gate) -> tests.unit
    per_iteration              -> dropped (it was accepted and inert)
    models tiers / overrides   -> dropped, replaced by the full models.<skill>.<role> block
    tracker.milestone / .jira  -> dropped; provider jira -> local
    formats / enforcement / hook_gates -> dropped
    models.<removed skill>     -> dropped (ADR-0118: create-project,
                                  standardize-project, create-requirements)

Nothing here reads the disk; the CLI (`acs.py settings migrate`) does that.
"""

import copy

from . import models

#: Keys the model tiers used; any of them marks an old `models` block.
MODEL_TIER_KEYS = ("planner", "executor", "verifier", "overrides")

#: Blocks that are simply gone.
DROPPED_BLOCKS = ("formats", "enforcement", "hook_gates")

#: Skills ADR-0118 removed. A scaffolded `models` block names them, and
#: validate_models would refuse an unknown skill outright.
RETIRED_MODEL_SKILLS = ("create-project", "standardize-project", "create-requirements")

#: Key of `tests` that is a number, not a suite.
COVERAGE_KEY = "coverage"


def legacy_problems(settings):
    """What `settings` (a merged object) carries from the old shapes that would
    now be misread rather than ignored. [] when it is clean."""
    problems = []
    settings = settings or {}
    if "test_coverage_percent" in settings:
        problems.append("test_coverage_percent is now tests.coverage")
    if "suites" in settings:
        problems.append("suites.<name> is now tests.<name>")
    if "e2e" in settings:
        problems.append("e2e is now tests.e2e")
    tests = settings.get("tests")
    if isinstance(tests, dict) and any(isinstance(tests.get(k), str) for k in ("command", "setup")):
        problems.append("tests.command / tests.setup (the CI gate) are now tests.unit")
    block = settings.get("models")
    if isinstance(block, dict) and any(k in block for k in MODEL_TIER_KEYS):
        problems.append("models.planner/executor/verifier/overrides are now models.<skill>.<role>")
    if isinstance(block, dict):
        retired = [k for k in RETIRED_MODEL_SKILLS if k in block]
        if retired:
            problems.append("models.%s name skills that were removed (ADR-0118)"
                            % "/".join(retired))
    tracker = settings.get("tracker")
    if isinstance(tracker, dict) and (tracker.get("provider") == "jira" or "jira" in tracker):
        problems.append("tracker.jira is no longer supported (provider is local or github)")
    return problems


def _strip(suite):
    if isinstance(suite, dict):
        suite = {k: v for k, v in suite.items() if k != "per_iteration"}
    return suite


def migrate(data):
    """(new_settings, notes) for one settings file's parsed content."""
    out = copy.deepcopy(data) if isinstance(data, dict) else {}
    notes = []

    for key in DROPPED_BLOCKS:
        if key in out:
            del out[key]
            notes.append("removed %s (retired; ADR-0116)" % key)

    touches_tests = any(k in out for k in ("test_coverage_percent", "suites", "e2e")) \
        or (isinstance(out.get("tests"), dict)
            and any(isinstance(out["tests"].get(k), str) for k in ("command", "setup")))
    if touches_tests:
        tests = out.get("tests") if isinstance(out.get("tests"), dict) else {}
        position_after = [k for k in out if k == "tests"]
        if "test_coverage_percent" in out:
            tests[COVERAGE_KEY] = out.pop("test_coverage_percent")
            notes.append("test_coverage_percent -> tests.coverage")
        suites = out.pop("suites", None)
        if isinstance(suites, dict):
            for name, suite in suites.items():
                tests.setdefault(name, _strip(suite))
                notes.append("suites.%s -> tests.%s" % (name, name))
        if "e2e" in out:
            tests["e2e"] = _strip(out.pop("e2e"))
            notes.append("e2e -> tests.e2e")
        gate = {k: tests.pop(k) for k in ("command", "setup") if isinstance(tests.get(k), str)}
        if gate:
            tests.setdefault("unit", gate)
            notes.append("tests.command/setup -> tests.unit")
        for name, suite in list(tests.items()):
            if name != COVERAGE_KEY:
                tests[name] = _strip(suite)
        out["tests"] = tests
        del position_after

    block = out.get("models")
    if isinstance(block, dict):
        for key in RETIRED_MODEL_SKILLS:
            if key in block:
                del block[key]
                notes.append("removed models.%s (the skill was removed; ADR-0118)" % key)
    if isinstance(block, dict) and any(k in block for k in MODEL_TIER_KEYS):
        out["models"], _added = models.merge_missing(
            {k: v for k, v in block.items() if k not in MODEL_TIER_KEYS})
        notes.append("models tiers/overrides -> the full models.<skill>.<role> block")

    tracker = out.get("tracker")
    if isinstance(tracker, dict):
        for key in ("milestone", "jira"):
            if key in tracker:
                del tracker[key]
                notes.append("removed tracker.%s" % key)
        if tracker.get("provider") == "jira":
            tracker["provider"] = "local"
            notes.append("tracker.provider jira -> local (Jira is no longer supported)")
    return out, notes
