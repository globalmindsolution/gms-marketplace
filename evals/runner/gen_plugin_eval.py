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

THE CASE FORMAT
---------------
    <case>/prompt.md            --- max_turns, runs, allowed_tools ---  prompt
    <case>/graders/<name>.md    --- type, tool, input_match, ... ---    docs

Grader types are `regex | tool_order | tool_used | file_exists | llm |
baseline`. The one that matters here is `tool_used`, whose `input_match` is a
regex tested against the JSON-encoded tool input — which is how a routing probe
is graded deterministically and for free:

    ---
    type: tool_used
    tool: Skill
    input_match: '"skill"\\s*:\\s*"(?:[\\w-]+:)?code"'
    min: 1
    ---

Every acs skill invocation goes through the same `Skill` tool, and the skill it
was asked for is in that tool's input as `{"skill": "acs:code", ...}`. The
optional `(?:[\\w-]+:)?` prefix accepts the bare and plugin-qualified spellings
alike, and the closing quote anchors the name so `code` cannot match
`code-small`. A negative probe is the same grader with `min: 0` and `max: 0` —
`min` defaults to 1, so a negative MUST set both bounds or it asserts the
opposite of what it means.

RETRACTION: THIS FILE PREVIOUSLY RECORDED A FALSE FINDING
---------------------------------------------------------
Between 2026-09-23 commits f6f658f and dff2341 this docstring asserted, as a
proven result, that NO grader type can observe which skill was invoked, and
therefore that positive routing probes are ungradeable in tier 2 at any
wording. That is wrong, and it was wrong when it was written.

It was reached by probing key names invented rather than looked up: the probe
tried `input_contains`, got "unrecognized key", and generalised a missing
feature from a misspelling. The real key is `input_match`, it is the documented
canonical routing grader, and it is accepted by the CLI shipped here
(2.1.280 — the feature needs 2.1.269+). Two smaller claims fell with it: the
`target`/`focus` enum is not `last_message` only (it also takes `trace`,
`files`, `{source: file, path: ...}` and `mock_calls`; the earlier probe tried
`transcript` and never tried `trace`), and `max_turns` defaults to 10, not 3.

The consequence for this tier is the opposite of what was recorded: routing is
graded deterministically, at $0 per grader, by a free `tool_used` grader — and
the two instrument defects that made the first full run (40 cases, $3.87)
unreadable are both retired by that same change, not worked around:

1. THE GATE-REFUSAL MIS-SCORE IS GONE. `route-code` had scored 0.50 with a
   trace plainly showing `{"skill": "acs:code"}`, because the skill's
   precondition gate refused for want of an `.acs/` workspace and the llm judge
   graded that refusal — it reads the final message, not the tool calls. A
   `tool_used` grader reads the tool call, which happens BEFORE any gate runs.
   No `scaffold_script`, no seeded sandbox, no `--scaffold` needed to measure
   routing.
2. TRUNCATION NO LONGER BIASES THE VERDICT. The old ceiling of 3 turns cut runs
   off before a conclusive final message, so the judge graded a fragment. A
   truncated run still carries every tool call it made, so the ceiling now
   costs coverage only if a probe routes late, never correctness.

Judge graders are gone from this tier as a result; it is free apart from the
agent runs themselves.

RUN IT WITH --ablation none
---------------------------
`tool_used: Skill` graders are auto-marked with-only, so under the default
`--ablation with-without` they become a "the plugin fired" indicator and drop
OUT of the score — the tier would report no routing number at all. That default
is right in general (baseline Claude has no acs skills, so it trivially never
fires one, and scoring the baseline arm would measure nothing) and wrong here,
where every grader is of that kind. `make -C evals` passes `--ablation none`.

Tier 3 (`measure_skills.py`, which reads the Skill tool_use out of the
`claude -p` stream and kills the run at the first one) still exists and still
measures routing; the two now agree by construction rather than by luck.
"""

import argparse
import json
import os
import re
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

#: Well below the CLI default of 10, and deliberately: the grader reads the
#: Skill tool call rather than the final message, so a run cut off here still
#: carries the evidence — `route-usage` scores 1.00 on a run that exits with
#: "Reached maximum number of turns". Every turn past the routing decision is
#: paid for and graded on nothing. With `allowed_tools: [Skill]` there is no
#: file to read first, so a probe that has not routed by turn 2 has not routed.
MAX_TURNS = 2


def skill_input_pattern(skill):
    """Regex matching the Skill tool's input for exactly `skill`.

    The tool input carries the skill as `{"skill": "acs:code", ...}`. The
    optional prefix group accepts the bare name too, and the closing quote
    anchors the end so `code` does not also match `code-small`.
    """
    bare = skill.split(":", 1)[-1]
    if not re.match(r"^[\w-]+$", bare):
        raise ValueError("skill name is not regex-safe verbatim: %r" % skill)
    return r'"skill"\s*:\s*"(?:[\w-]+:)?%s"' % bare


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
    why = probe["why"].strip()
    out = {}

    out["prompt.md"] = (
        "---\nmax_turns: %d\nallowed_tools: [Skill]\n---\n\n%s%s\n"
        % (MAX_TURNS, HEADER, probe["prompt"].strip()))

    # One grader per probe, so the case score IS the routing verdict: 1.00
    # routed as asserted, 0.00 did not. A second "some skill fired" grader
    # would read well in the report and turn every wrong route into a 0.50.
    if positive:
        out["graders/routes-to-%s.md" % slug] = (
            "---\ntype: tool_used\nweight: 1\ntool: Skill\n"
            "input_match: '%s'\nmin: 1\n---\n\n%s"
            "The `%s` skill must be invoked at least once.\n\n"
            "Deterministic and free: this reads the Skill tool call, not the\n"
            "assistant's prose, so a precondition gate refusing AFTER the skill\n"
            "routed still counts as a route — which is what this probe asserts.\n\n"
            "Why this probe exists: %s\n"
            % (skill_input_pattern(skill), HEADER, skill, why))
    else:
        out["graders/does-not-route-to-%s.md" % slug] = (
            "---\ntype: tool_used\nweight: 1\ntool: Skill\n"
            "input_match: '%s'\nmin: 0\nmax: 0\n---\n\n%s"
            "The `%s` skill must NOT be invoked.\n\n"
            "`input_match` narrows the count to that one skill, so invoking a\n"
            "DIFFERENT skill is a PASS — this probe asserts only that `%s` did\n"
            "not fire. Both bounds are set deliberately: `min` defaults to 1, and\n"
            "a `max: 0` alone would assert the impossible range 1..0.\n\n"
            "Why this probe exists: %s\n"
            % (skill_input_pattern(skill), HEADER, skill, skill, why))
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
        rendered = files_for(probe)
        for rel, body in rendered.items():
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
        # A grader renamed or retyped leaves its predecessor behind, and a
        # stale grader keeps scoring: the tree is the CLI's whole input.
        gdir = os.path.join(CASES, case, "graders")
        keep = {os.path.basename(r) for r in rendered if r.startswith("graders/")}
        if os.path.isdir(gdir):
            for name in sorted(os.listdir(gdir)):
                if name in keep:
                    continue
                rel = os.path.relpath(os.path.join(gdir, name), REPO_ROOT)
                if args.check:
                    stale.append("%s (orphan grader)" % rel)
                else:
                    os.remove(os.path.join(gdir, name))
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
        print("%s is up to date with dataset/routing.json (%d renderable probe(s))"
              % (rel_cases, len(expected)))
        return 0

    print("rendered %d probe(s), %d file(s) changed, %d orphan(s) removed, into %s"
          % (len(expected), written, len(orphans), rel_cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
