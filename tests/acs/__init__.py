"""Package init for the acs test suite.

Imported before any module in this package under both `python3 -m unittest
discover -s tests` (what CI and `.acs/settings.json`'s tests.command run) and
pytest, which makes it the one place that can set process-wide state for every
test that shells out to git.

Why it sets anything at all
---------------------------
Many modules here build a scratch git repo inside a `TemporaryDirectory` and
let the context manager delete it. Since git 2.30, `git commit` launches
`git maintenance run --auto --quiet` as a child, which writes into
`.git/objects`. When that child is still running as the temp dir is torn down,
cleanup fails:

    OSError: [Errno 39] Directory not empty: '/tmp/.../repo/.git/objects'

It is a race, so it surfaces on a fast runner and not on a slow one, in one
Python version and not another, and in whichever module happened to lose --
`test_release_notes.py` on CI, though `git init` appears in a dozen modules
here and none of them disabled maintenance. Nothing about the test under it is
wrong; the teardown is simply deleting a directory git has not finished with.

Disabling opportunistic maintenance removes the writer rather than tolerating
it. `TemporaryDirectory(ignore_cleanup_errors=True)` would have hidden it
instead, is 3.10+ (this suite supports 3.9), and would leave the same race
free to corrupt a test that reads the tree it is deleting.

`GIT_CONFIG_COUNT`/`KEY`/`VALUE` is used rather than `git config` calls in each
fixture because it reaches EVERY git subprocess any module spawns, including
ones that build their own env with `os.environ.copy()`, and needs no fixture to
remember it.
"""

import os

#: Config every git subprocess in this suite runs with. `gc.auto` covers older
#: git, `maintenance.auto` the `git maintenance` path that replaced it.
_GIT_CONFIG = (("gc.auto", "0"), ("maintenance.auto", "false"))


def _install_git_config(env=None):
    """Append our keys to GIT_CONFIG_* without clobbering any already set."""
    env = os.environ if env is None else env
    try:
        start = int(env.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        start = 0
    for offset, (key, value) in enumerate(_GIT_CONFIG):
        env["GIT_CONFIG_KEY_%d" % (start + offset)] = key
        env["GIT_CONFIG_VALUE_%d" % (start + offset)] = value
    env["GIT_CONFIG_COUNT"] = str(start + len(_GIT_CONFIG))
    return env


_install_git_config()
