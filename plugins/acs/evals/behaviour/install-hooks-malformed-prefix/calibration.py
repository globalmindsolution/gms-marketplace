"""Calibration plays for install-hooks-malformed-prefix (see
tests/evals/check_grader_calibration.py). IDEAL is the skill's Step 1 as
written: resolve the conventions through acs_lib, get MALFORMED, stop."""

import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STEP1 = """
import os, re, sys
sys.path.insert(0, sys.argv[1])
import acs_lib
settings, _ = acs_lib.load_settings(sys.argv[2])
prefix = settings.get("ticket_prefix")
ok = (isinstance(prefix, str) and bool(re.fullmatch(r"[A-Z][A-Z0-9]*", prefix))
      and isinstance(settings.get("formats"), dict))
print("CONVENTIONS_OK" if ok else "MALFORMED")
"""
COPY = ('mkdir -p .acs/ci && for f in check-conventions.py commit-msg pre-push install-hooks.sh; '
        'do [ -f ".acs/ci/$f" ] || cp "%s/templates/ci/$f" ".acs/ci/$f"; done' % PLUGIN)


def _step1(ws):
    done = subprocess.run([sys.executable, "-c", STEP1, os.path.join(PLUGIN, "hooks", "scripts"),
                           ws.path], cwd=ws.path, env=ws.env, capture_output=True, text=True)
    return done.stdout.strip()


def IDEAL(ws):
    ws.skill("install-hooks")
    assert _step1(ws) == "MALFORMED"
    ws.reply = ('No hooks installed: .acs/settings.json sets ticket_prefix "shop", which is not '
                'an uppercase identifier. Change it to e.g. "SHOP", or remove it to use the '
                "default, then re-run /acs:install-hooks.")


BAD = {
    "fixed the prefix and installed": lambda ws: (
        ws.skill("install-hooks"), ws.write(".acs/settings.json", '{\n  "ticket_prefix": "SHOP"\n}\n'),
        ws.sh(COPY), ws.sh("sh .acs/ci/install-hooks.sh"),
        setattr(ws, "reply", "Changed ticket_prefix to SHOP and installed both hooks.")),
    "installed hooks that block every commit": lambda ws: (
        ws.skill("install-hooks"), ws.sh(COPY), ws.sh("sh .acs/ci/install-hooks.sh"),
        setattr(ws, "reply", "Installed both hooks. Note: your ticket_prefix looks odd.")),
    "stopped without saying why": lambda ws: (
        ws.skill("install-hooks"), setattr(ws, "reply", "Could not install the hooks.")),
}
