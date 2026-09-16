"""s06 — /acs:update local logic: semver compare + Step-6 migration checks (free).

The /acs:update skill is mostly a paid workflow (it reasons over a changelog
delta with a real model), but two of its load-bearing steps are pure,
deterministic logic that the free tier can certify offline:

  * Step 3 — semver compare: installed vs latest must classify into exactly
    "update available" (installed < latest), "up to date" (==), or "dev copy"
    (installed > latest), compared numerically (split on ".", compare tuples),
    never as strings (so "0.10.0" > "0.9.0").
  * Step 6 — post-update migration checks: settings still validate against the
    schema (`acs_lib.validate_settings`), and workspace resolution is
    exercised (explicit override honored; absent -> in-repo default). On
    INVALID the skill recommends `/acs:setup`.

This scenario drives the *installed build's* `acs_lib` directly (the same module
the skill's Step-6 snippet imports) so it certifies the shipped behavior, and
replicates the documented Step-3 comparison rule to prove it is sound and
unambiguous on the cases the skill must distinguish. `tests/` covers
`validate_settings` on the source tree; this asserts it against the packaged
build the way `/acs:update` actually calls it.
"""

import importlib.util
import os
import sys

from harness import Sandbox, Check, _version_key

META = {
    "name": "update_migration",
    "tier": "free",
    "goal": "update",
    "summary": "/acs:update semver compare + Step-6 migration checks (settings valid, workspace enforced)",
}


def _classify(installed, latest):
    """Replicate the skill's Step-3 numeric semver verdict.

    Returns "update-available" | "up-to-date" | "dev-copy". Uses the harness's
    _version_key (split on '.', integer tuples) — the exact "compare as tuples,
    never as strings" rule the skill mandates.
    """
    ik, lk = _version_key(installed), _version_key(latest)
    if ik < lk:
        return "update-available"
    if ik > lk:
        return "dev-copy"
    return "up-to-date"


def _load_acs_lib(scripts_dir):
    """Import the *installed build's* acs_lib — the module /acs:update Step 6 uses.

    acs_lib is a package (MAR-522), so the spec needs the package's search
    location, and the module must be in sys.modules before exec or its own
    relative imports cannot resolve. Its submodules import flat siblings
    (claude_code_adapter), so scripts_dir goes on sys.path for the load."""
    name = "acs_lib_under_test"
    pkg = os.path.join(scripts_dir, "acs_lib")
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(pkg, "__init__.py"), submodule_search_locations=[pkg])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    added = scripts_dir not in sys.path
    if added:
        sys.path.insert(0, scripts_dir)
    try:
        spec.loader.exec_module(mod)
    finally:
        # Pop the SUBMODULES too: leaving "<name>.state" cached means a second
        # load re-execs only __init__.py, whose relative imports then resolve
        # from the first build -- certifying a build it never loaded.
        for cached in [n for n in sys.modules
                       if n == name or n.startswith(name + ".")]:
            sys.modules.pop(cached, None)
        if added:
            sys.path.remove(scripts_dir)
    return mod


def run():
    check = Check(META["name"])

    # -- Step 3: semver compare (pure logic, no sandbox needed) ------------- #
    # Numeric tuple comparison, not lexical: 0.10.0 must beat 0.9.0.
    check.eq("0.2.0 < 0.3.0 -> update available",
             _classify("0.2.0", "0.3.0"), "update-available")
    check.eq("0.3.0 == 0.3.0 -> up to date",
             _classify("0.3.0", "0.3.0"), "up-to-date")
    check.eq("0.4.0 > 0.3.0 -> dev copy",
             _classify("0.4.0", "0.3.0"), "dev-copy")
    check.eq("0.10.0 > 0.9.0 -> numeric, not lexical",
             _classify("0.10.0", "0.9.0"), "dev-copy")

    # -- Step 6: migration checks against the installed build's acs_lib ----- #
    with Sandbox(prefix="EVAL", slug="upd", init=True) as sb:
        lib = _load_acs_lib(sb.scripts)

        # Healthy repo: settings load and validate -> migration "settings: valid".
        settings, found = lib.load_settings(sb.repo)
        check.ok("migration: seeded settings load", len(found) >= 1,
                 "found=%r" % found)
        try:
            ws = lib.validate_settings(settings, sb.repo)
            check.ok("migration: valid settings pass validate_settings", True)
            check.ok("migration: explicit workspace_path override honored verbatim",
                     ws == os.path.abspath(sb.ws),
                     "ws=%r sb.ws=%r" % (ws, sb.ws))
        except lib.GateError as exc:
            check.ok("migration: valid settings pass validate_settings", False,
                     "unexpected GateError: %s" % exc)

        # Broken settings: a bad merge_strategy must be caught -> skill says
        # "settings: INVALID" and recommends /acs:setup.
        bad = dict(settings)
        bad["merge_strategy"] = "fast-forward"  # not squash|merge|rebase
        try:
            lib.validate_settings(bad, sb.repo)
            check.ok("migration: invalid settings flagged (recommend /acs:setup)",
                     False, "validate_settings accepted a bad merge_strategy")
        except lib.GateError as exc:
            check.ok("migration: invalid settings flagged (recommend /acs:setup)",
                     "merge_strategy" in str(exc), str(exc))

        # Workspace resolution: an absent workspace_path derives the in-repo
        # default (the Step-6 "workspace reachable" case, post-MAR-2).
        no_ws = {k: v for k, v in settings.items() if k != "workspace_path"}
        derived = lib.validate_settings(no_ws, sb.repo)
        expected = os.path.join(sb.repo, ".acs", "state-machine")
        check.ok("migration: absent workspace_path derives the in-repo default",
                 derived == expected and os.path.commonpath([derived, sb.repo]) == sb.repo,
                 "derived=%r expected=%r" % (derived, expected))

    return check
