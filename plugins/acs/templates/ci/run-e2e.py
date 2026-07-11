#!/usr/bin/env python3
"""run-e2e.py — acs required e2e merge gate.

Installed by /acs:init Step 7f into the consumer repo at .acs/ci/run-e2e.py and
run by .github/workflows/acs-e2e.yml on every PR. The CI runner has no acs
install, so this reads the raw committed <repo>/.acs/settings.json directly
(no acs_lib import) and replicates its e2e/suites["e2e"] alias fallback,
runs the optional setup then the command then optional teardown (always, in a
finally block — a non-zero teardown is a warning, never flips a green result
to red), and exits 0 on a green command or 1 otherwise.
"""

import json
import os
import subprocess
import sys

SETTINGS = os.path.join(".acs", "settings.json")


def fail(msg):
    sys.stderr.write("acs run-e2e: %s\n" % msg)
    sys.exit(1)


def resolve_e2e(settings):
    """suites["e2e"] takes precedence; falls back to the raw `e2e` alias.
    Tolerates `suites` being absent, null, or present without an "e2e" key."""
    suites = settings.get("suites") or {}
    return suites.get("e2e") or settings.get("e2e")


def run_step(name, command, env):
    print("::group::acs e2e — %s\n$ %s" % (name, command), flush=True)
    rc = subprocess.run(command, shell=True, env=env).returncode
    print("::endgroup::", flush=True)
    return rc


def main():
    if not os.path.isfile(SETTINGS):
        fail("%s not found — commit project settings, or run /acs:init." % SETTINGS)
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        fail("cannot read %s: %s" % (SETTINGS, exc))

    e2e = resolve_e2e(settings)
    if not isinstance(e2e, dict) or not e2e.get("command"):
        fail("no e2e command in %s — re-run /acs:init and enable the e2e CI "
             "gate." % SETTINGS)

    env = dict(os.environ)
    teardown = e2e.get("teardown")
    command_rc = 1

    try:
        setup = e2e.get("setup")
        if setup:
            rc = run_step("setup", setup, env)
            if rc != 0:
                fail("setup failed (exit %d): %s" % (rc, setup))

        command = e2e["command"]
        print("acs e2e\n$ %s" % command, flush=True)
        command_rc = subprocess.run(command, shell=True, env=env).returncode
    finally:
        if teardown:
            rc = run_step("teardown", teardown, env)
            if rc != 0:
                sys.stderr.write(
                    "acs run-e2e: teardown warning (exit %d) — does not "
                    "affect the suite result.\n" % rc)

    if command_rc != 0:
        fail("suite failed (exit %d)." % command_rc)
    print("acs e2e — passed (suite green).")


if __name__ == "__main__":
    main()
