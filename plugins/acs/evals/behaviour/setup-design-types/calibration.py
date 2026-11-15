"""Calibration plays for setup-design-types (see
tests/evals/check_grader_calibration.py). IDEAL is /acs:setup's Step 3 with
the one answer the user gave: `design` under `settings`, through
`acs.py setup apply`."""

import json

HLD = ["c4-context", "c4-container", "c4-component", "data-model", "integration-map",
       "deployment", "project-structure", "data-flow"]
LLD = ["api-contract", "logical-erd", "sequence", "activity", "state"]


def _apply(ws, answers):
    done = ws.acs("setup", "apply", "--answers", "-", stdin=json.dumps(answers))
    assert done.returncode == 0, done.stdout + done.stderr


def _design(hld, lld, ci=()):
    return {"settings": {"design": {"hld_types": hld, "lld_types": lld}}, "ci": list(ci)}


def IDEAL(ws):
    ws.skill("setup")
    _apply(ws, _design(HLD, LLD))
    ws.reply = ("Design documents set: added the data-flow diagram to the HLD and "
                "dropped the physical schema from the LLD; everything else is the default.")


BAD = {
    "wrote nothing": lambda ws: (
        ws.skill("setup"), setattr(ws, "reply", "data-flow added, physical schema dropped.")),
    "kept only what was named": lambda ws: (
        ws.skill("setup"), _apply(ws, _design(["data-flow"], ["logical-erd"]))),
    "kept the physical schema": lambda ws: (
        ws.skill("setup"), _apply(ws, _design(HLD, LLD + ["physical-schema"]))),
    "installed a CI gate too": lambda ws: (
        ws.skill("setup"), _apply(ws, _design(HLD, LLD, ci=["conventions"]))),
}
