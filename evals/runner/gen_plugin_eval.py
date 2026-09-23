#!/usr/bin/env python3
"""Render dataset/routing.json into `claude plugin eval` case files.

    python3 runner/gen_plugin_eval.py            # write the case tree
    python3 runner/gen_plugin_eval.py --check    # fail if the tree is out of date

A probe removed or renamed in the JSON has its rendered case REMOVED here, and
--check fails on an orphan rather than reporting the tree up to date: a left-over
case keeps asserting a routing claim the dataset has withdrawn.

dataset/routing.json is the source of truth: the prompts and the skill each
must (or must not) route to are curated there, reviewed there, and rendered
from there. Editing a generated file by hand loses the edit on the next run —
change the JSON instead.

WHERE THIS WRITES, AND WHY IT MOVED
-----------------------------------
`claude plugin eval` resolves cases at `<plugin>/<eval dir>/`, so the tree is
rendered into `plugins/acs/evals/routing/`. It used to sit at the repo-root
eval suite, which produced a silent wrong answer rather than an error: pointing
the CLI at the repo root found the cases and reported

    Plugin under test: none resolved — cases run against baseline Claude Code

i.e. it graded "did this route to acs" with acs NOT LOADED. Pointing it at the
plugin resolved acs correctly and found no cases. Writing here satisfies the
lookup, and incidentally retires the `evals/evals/` path collision.

THE CASE FORMAT, DERIVED BY RUNNING IT
--------------------------------------
This file previously rendered `case.yaml` in a shape authored from
`claude plugin eval --help`, which documents flags and not the case schema.
None of it loaded. The format below was derived on 2026-09-23 by running the
CLI and reading its validator, and every claim here was observed:

    <case>/prompt.md            --- max_turns, allowed_tools ---  prompt text
    <case>/graders/<name>.md    --- type, weight, ... ---         grader body

    regex       `target` accepts ONLY `last_message` — it cannot see tool
                calls, so it cannot assert which skill was invoked
    tool_used   `tool` is required; `min`/`max` bound the call count and `min`
                defaults to 1. It proves a skill fired, never WHICH skill:
                `input_contains` and friends are rejected as unknown keys
    tool_order  requires `before` and `after` — sequencing, not identity
    llm         judge; criteria in the body
    file_exists, baseline — not applicable to routing

So a routing probe cannot be graded deterministically on today's schema. Every
acs skill invocation goes through the same `Skill` tool, and no free grader can
read its argument. Each probe therefore carries an `llm` grader naming the
expected skill, and positive probes additionally carry a free `tool_used`
grader proving a skill fired at all — a deterministic floor under the judge,
which catches "routed nowhere" without paying for a verdict.

THE TREE RUNS. THE RESULTS ARE NOT YET VALID ROUTING MEASUREMENTS.
------------------------------------------------------------------
First full execution, 2026-09-23: 40 cases, $3.87, and the numbers cannot be
read as routing health. Two instrument defects, both in THIS file, both proven
from a kept trace rather than inferred:

1. THE SANDBOX HAS NO ACS WORKSPACE. `route-code` scored 0.50, and its trace
   shows `{"skill": "acs:code", "args": "TKT-1"}` — it routed EXACTLY as the
   probe asserts. Its final message is then "the acs plugin isn't set up in
   this repo yet — /acs:code requires .acs/settings.json, which doesn't
   exist". The skill routed and its precondition gate refused, and the judge,
   which reads the last message, scored the GATE REFUSAL as a routing failure.
   Every gated skill is mis-scored this way. The CLI supports `scaffold_script`
   (`--scaffold`) for exactly this; tier 3 already solved the same problem with
   routing.json's `profile`/`setup` keys, which this renderer ignores.

2. MAX_TURNS IS TOO LOW. At 3, many runs are truncated before any conclusive
   final message, so the judge grades a fragment. `route-metrics` is ungated
   and still scored 0.50 for this reason alone, while `route-usage` — ungated
   AND short enough to finish — is the one positive that scored 1.00.

Negative probes are unaffected by both defects and look sound: all five scored
1.00, and a gate refusal is a legitimate PASS for "this must not route here".

Do not re-record a baseline from this run.

WHY THE POSITIVE PROBES CANNOT BE GRADED AT ALL (proven 2026-09-23)
-------------------------------------------------------------------
Chasing those two defects ran into a harder wall, and the wall is the tool, not
the sandbox: NO GRADER TYPE CAN OBSERVE WHICH SKILL WAS INVOKED.

  regex       `target` enum is `last_message` only. And the evidence is not
              reliably there: on a run whose trace.jsonl plainly contains
              {"skill": "acs:code"} and whose final assistant text says "the
              acs:code skill requires .acs/settings.json", a free regex grader
              for `acs:code` against last_message reported PATTERN NOT FOUND.
              What graders receive as last_message is narrower than the final
              text.
  tool_used   proves the Skill tool fired, never with which argument
  tool_order  before/after sequencing
  llm         reads the response, not the tool calls. Its criteria plumbing is
              fine - a grader saying "always pass" returns PASS PASS PASS and
              one saying "always fail" returns FAIL FAIL FAIL - so the FAILs on
              positive probes are a visibility limit, not a wording problem.
              Rewording a grader to accept a gate refusal as proof of routing
              did not change the verdict.

So tier 2 can deterministically answer "did SOME skill fire" and "did NO skill
fire", and cannot answer "did acs:code fire". Positive routing probes are not
gradeable here today, at any wording, with or without a seeded sandbox.

This is what tier 3 already does correctly and why it exists: measure_skills.py
reads the Skill tool_use out of the `claude -p` stream directly and kills the
run at the first one. Keep routing measurement there. Tier 2 remains useful for
its ablation support and for assertions about whether a skill fired at all.
"""

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_SUITE = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(EVAL_SUITE)
ROUTING = os.path.join(EVAL_SUITE, "dataset", "routing.json")
CASES = os.path.join(REPO_ROOT, "plugins", "acs", "evals", "routing")

#: Goes in the BODY, never above the frontmatter: the opening `---` must be the
#: file's first line, and a comment before it makes the loader see no
#: frontmatter at all — which surfaces as `graders: Required`, not as a
#: complaint about the comment.
HEADER = ("<!-- GENERATED by evals/runner/gen_plugin_eval.py from\n"
          "     evals/dataset/routing.json. Edit the JSON, not this file. -->\n\n")

#: Routing is decided in the first turn or two. A higher ceiling only pays for
#: the skill body to run, which no probe here asserts on.
MAX_TURNS = 3


def renderable(probe):
    """Controls test the instrument, not the plugin; they have no tier-2 case.

    `claude plugin eval` grades whether a skill fired, and a control's answer
    is known in advance (a canary registers, a missing command does not, a
    poem routes nowhere) — rendering one would only test the grader.
    """
    return probe.get("kind") != "control"


def files_for(probe):
    """Every file one probe renders, as {relative path: content}."""
    skill = probe["skill"]
    positive = probe["must_route"]
    slug = skill.replace(":", "-")
    out = {}

    out["prompt.md"] = (
        "---\nmax_turns: %d\nallowed_tools: [Skill]\n---\n\n%s%s\n"
        % (MAX_TURNS, HEADER, probe["prompt"].strip()))

    if positive:
        # Free, deterministic floor: SOMETHING routed. Cannot name the skill —
        # see the module docstring on why no free grader can.
        out["graders/a-skill-fired.md"] = (
            "---\ntype: tool_used\nweight: 1\ntool: Skill\nmin: 1\n---\n\n%s"
            "Some skill must be invoked. This does not check WHICH skill; the\n"
            "judge below does that. It exists so a run that routed nowhere at\n"
            "all fails on a free grader rather than on a paid verdict.\n" % HEADER)
        out["graders/routes-to-%s.md" % slug] = (
            "---\ntype: llm\nweight: 1\n---\n\n%s"
            "PASS only if the assistant invoked the `%s` skill.\n\n"
            "FAIL if it invoked a different skill, or answered without invoking one.\n"
            "Judge only which skill was invoked — not whether the skill's own work\n"
            "was correct, and not the quality of any prose.\n\n"
            "Why this probe exists: %s\n" % (HEADER, skill, probe["why"].strip()))
    else:
        # A negative probe asserts one skill stayed silent; another skill firing
        # is not a failure, so there is no tool_used floor here.
        out["graders/does-not-route-to-%s.md" % slug] = (
            "---\ntype: llm\nweight: 1\n---\n\n%s"
            "PASS unless the assistant invoked the `%s` skill.\n\n"
            "Invoking a DIFFERENT skill is a PASS — this probe asserts only that\n"
            "`%s` did not fire. Answering without invoking anything is a PASS.\n\n"
            "Why this probe exists: %s\n"
            % (HEADER, skill, skill, probe["why"].strip()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any generated file is missing or stale")
    args = ap.parse_args()

    with open(ROUTING) as fh:
        routing = json.load(fh)

    stale, written, expected = [], 0, set()
    for probe in routing["probes"]:
        if not renderable(probe):
            continue
        case = probe["id"].lower()
        expected.add(case)
        for rel, body in files_for(probe).items():
            path = os.path.join(CASES, case, rel)
            current = None
            if os.path.isfile(path):
                with open(path) as fh:
                    current = fh.read()
            if current == body:
                continue
            if args.check:
                stale.append(os.path.relpath(path, REPO_ROOT))
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(body)
            written += 1

    orphans = []
    if os.path.isdir(CASES):
        for name in sorted(os.listdir(CASES)):
            if name not in expected and os.path.isdir(os.path.join(CASES, name)):
                orphans.append(name)
                if not args.check:
                    shutil.rmtree(os.path.join(CASES, name))

    rel_cases = os.path.relpath(CASES, REPO_ROOT)
    if args.check:
        problems = stale + ["%s (orphan)" % o for o in orphans]
        if problems:
            sys.stderr.write("%s is out of date with dataset/routing.json:\n  %s\n"
                             % (rel_cases, "\n  ".join(problems)))
            return 1
        print("%s is up to date with dataset/routing.json (%d probes)"
              % (rel_cases, len(routing["probes"])))
        return 0

    print("rendered %d probe(s), %d file(s) changed, %d orphan(s) removed, into %s"
          % (len(expected), written, len(orphans), rel_cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
