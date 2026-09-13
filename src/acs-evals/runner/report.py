#!/usr/bin/env python3
"""Render a release-gate report from a golden-dataset run result.

    python3 runner/report.py                              # read results/latest.json
    python3 runner/report.py --json results/latest.json \
                            --out results/report          # -> report.md + report.html

Input is the JSON `run_golden.py --json` writes. Output is two files that say
the same thing to two audiences: `report.md` for review in the repo and in a
pull request, `report.html` as the shareable artifact.

The report states a verdict first and shows the evidence under it. It never
computes a verdict of its own — it reads `totals` and reports it — so the
report and the runner's exit status can never disagree.

Design plan for the HTML (kept here so the next person changing it has the
reasoning, not just the values):

  Color   Cool slate ground with a blue-biased neutral ramp; ONE accent,
          deep teal (#0E6B70 / #3FB6AE), which belongs to instrumentation
          rather than marketing. Semantic pass/divergence/fail are a separate
          scale from the accent, so "green" always means passed and never
          means "branded".
  Type    The IBM Plex trio, chosen because Plex was drawn for technical
          documentation: Sans for headings, labels and UI; Serif for the
          running prose a reviewer actually reads; Mono for case ids, exit
          codes, refusal strings and every column of digits.
  Layout  Verdict first, then evidence. A banner carrying the one fact that
          decides the release; a KPI row (justified here — in a QA report the
          figures ARE the content); coverage bars drawn to a real scale;
          divergences lifted out because they need a human decision; then the
          full case index, scrollable, for auditing.
"""

import argparse
import html
import json
import os
import string
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

GROUP_TITLES = {
    "01-derivation": "Derivation",
    "02-readiness": "Merge readiness",
    "03-verdict": "Verifier verdict",
    "04-filemap": "Executor file map",
    "05-lock": "Ticket locks",
    "06-gates": "Pipeline gates",
    "07-spine": "Pipeline spine",
    "08-schemas": "Shipped JSON schemas",
    "09-internals": "Internals",
    "10-skills": "Skill inventory",
    "11-schema-constraints": "Schema constraints (generated)",
}


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def aggregate(doc):
    """Group and ticket rollups, in the dataset's own file order."""
    groups, tickets = {}, {}
    for case in doc["cases"]:
        g = groups.setdefault(case["group"], {
            "name": case["group"],
            "title": GROUP_TITLES.get(case["group"], case["group"]),
            "surface": case["surface"], "total": 0, "passed": 0,
            "failed": 0, "divergences": 0, "seconds": 0.0})
        g["total"] += 1
        g["seconds"] += case["seconds"]
        g["passed" if case["status"] == "pass" else "failed"] += 1
        if case["known_divergence"]:
            g["divergences"] += 1
        for ticket in case["covers"]:
            t = tickets.setdefault(ticket, {"ticket": ticket, "total": 0,
                                            "passed": 0, "failed": 0})
            t["total"] += 1
            t["passed" if case["status"] == "pass" else "failed"] += 1
    return ([groups[k] for k in sorted(groups)],
            [tickets[k] for k in sorted(tickets, key=_ticket_key)])


def _ticket_key(ticket):
    head, _, num = ticket.partition("-")
    return (head, int(num) if num.isdigit() else 0)


def verdict(doc):
    """(state, headline, detail) — the rubric's verdict, never recomputed.

    Severity decides, not the failure count: docs/RUBRIC.md says one critical
    failure blocks a release outright and no number of passes offsets it, while
    minor drift is triage rather than a hold.
    """
    totals = doc["totals"]
    sev = totals.get("by_severity") or {}
    crit = sev.get("critical", {}).get("failed", 0)
    major = sev.get("major", {}).get("failed", 0)
    minor = sev.get("minor", {}).get("failed", 0)
    if crit:
        return ("fail", "Release gate: BLOCKED (critical)",
                "%d critical case(s) failed. A critical assertion is one whose "
                "failure lets acs produce a wrong or unauditable outcome in a "
                "consumer repo — a gate opening that should have stayed shut, a "
                "fail-closed path failing open, or evidence that is no longer "
                "evidence. Do not cut a release from this build." % crit)
    if major:
        return ("fail", "Release gate: BLOCKED",
                "%d major case(s) failed: a documented contract moved. Fix the "
                "regression, or re-record the golden deliberately in its own "
                "reviewed commit and name the change in the changelog."
                % major)
    if minor:
        return ("warn", "Release gate: PASSED (minor drift)",
                "%d minor case(s) failed. Minor drift does not block a release, "
                "but each one needs a decision before the next cut — "
                "unexplained drift is often the first symptom of something "
                "larger." % minor)
    if totals["failed"]:
        return ("fail", "Release gate: BLOCKED",
                "%d of %d cases do not match the recorded behaviour."
                % (totals["failed"], totals["total"]))
    if not doc.get("baseline_match", True):
        return ("warn", "Release gate: PASSED (off-baseline)",
                "All %d cases match, but the build under test is acs %s while "
                "the goldens were recorded against acs %s. Confirm the version "
                "bump is intended, then re-record the baseline."
                % (totals["total"], doc["build"]["version"],
                   doc["dataset"]["recorded_against"]))
    return ("pass", "Release gate: PASSED",
            "All %d cases match the behaviour recorded for acs %s. No "
            "regression in the surfaces this dataset covers."
            % (totals["total"], doc["dataset"]["recorded_against"]))


DIVERGENCE_FIELDS = (
    ("observed", "What the build does"),
    ("expected_by_contract", "What its contract says"),
    ("cause", "Cause"),
    ("blast_radius", "Blast radius"),
    ("status", "Status"),
)


def divergences(doc):
    return [c for c in doc["cases"] if c["known_divergence"]]


def failures(doc):
    return [c for c in doc["cases"] if c["status"] == "fail"]


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

def md_cell(text):
    """A table cell: `|` is the column separator, so surfaces like
    `acs lane|stakes|slug` must escape it or they split the row."""
    return str(text).replace("|", "\\|")


def _pre_commit_clean(text):
    """Normalise what this repo's pre-commit hooks would otherwise rewrite.

    A reviewed report is committed under ``reports/``, so it passes through
    ``trailing-whitespace`` and ``end-of-file-fixer`` like any other file.
    Emitting what they want means a regenerated report never arrives with a
    diff nobody wrote: no per-line trailing whitespace, and exactly one
    newline at the end.
    """
    body = "\n".join(line.rstrip() for line in text.split("\n"))
    return body.rstrip("\n") + "\n"


def render_markdown(doc):
    groups, tickets = aggregate(doc)
    state, headline, detail = verdict(doc)
    t = doc["totals"]
    badge = {"pass": "PASS", "warn": "PASS (off-baseline)", "fail": "FAIL"}[state]
    out = []
    w = out.append

    w("# acs plugin — evaluation report")
    w("")
    w("**%s**" % headline)
    w("")
    w(detail)
    w("")
    w("| | |")
    w("|---|---|")
    w("| Result | **%s** |" % badge)
    w("| Build under test | acs `%s` |" % doc["build"]["version"])
    w("| Target release | `%s` |" % doc["dataset"]["target_release"])
    w("| Dataset | `%s`, recorded against acs `%s` |"
      % (doc["dataset"]["version"], doc["dataset"]["recorded_against"]))
    w("| Cases | %d passed, %d failed, %d total |"
      % (t["passed"], t["failed"], t["total"]))
    w("| Known divergences | %d |" % t["known_divergences"])
    w("| Wall clock | %.1fs |" % t["seconds"])
    w("| Generated | %s |" % doc["generated_at"])
    w("")
    w("Scope: the deterministic tier only. No model, no network, no cost. This "
      "report pins **contracts** — that the surfaces still emit what they were "
      "recorded emitting. It says nothing about whether skills got less "
      "reliable, worse, more expensive or slower: those are tier 3's subject "
      "(`make measure && make perf`, see `docs/PERFORMANCE.md`), and a green "
      "report here is not evidence about any of them. Routing at runtime is "
      "likewise unmeasured here — tier 3 measures it; the tier-2 tree "
      "(`evals/`, `claude plugin eval`) remains authored and never executed.")
    w("")

    w("## Coverage by surface")
    w("")
    w("| Group | Surface | Cases | Passed | Failed | Divergences |")
    w("|---|---|---:|---:|---:|---:|")
    for g in groups:
        w("| %s | `%s` | %d | %d | %d | %d |"
          % (md_cell(g["title"]), md_cell(g["surface"]), g["total"],
             g["passed"], g["failed"], g["divergences"]))
    w("| **Total** | | **%d** | **%d** | **%d** | **%d** |"
      % (t["total"], t["passed"], t["failed"], t["known_divergences"]))
    w("")

    w("## Coverage by ticket")
    w("")
    w("Cases are tagged with the ticket whose behaviour they pin. A ticket "
      "with no cases is not covered by this dataset.")
    w("")
    w("| Ticket | Cases | Passed | Failed |")
    w("|---|---:|---:|---:|")
    for tk in tickets:
        w("| %s | %d | %d | %d |"
          % (tk["ticket"], tk["total"], tk["passed"], tk["failed"]))
    w("")

    if failures(doc):
        w("## Failures")
        w("")
        w("Every failure is a behaviour change. Decide, per case, whether the "
          "build regressed or the golden is stale — never re-record to clear "
          "a red run.")
        w("")
        for c in failures(doc):
            w("### `%s` — %s" % (c["id"], c["title"]))
            w("")
            w("- Group: %s (`%s`)"
              % (md_cell(GROUP_TITLES.get(c["group"], c["group"])),
                 md_cell(c["surface"])))
            w("- Profile: `%s`" % c["profile"])
            if c["note"]:
                w("- Note: %s" % c["note"])
            w("")
            w("```")
            for d in c["diffs"]:
                w(d)
            w("```")
            w("")
            w("Reproduce: `python3 runner/run_golden.py -v --case %s`" % c["id"])
            w("")

    if divergences(doc):
        w("## Known divergences")
        w("")
        w("These cases pass because they pin what the build **actually does**, "
          "which differs from what its own contract states. They are recorded "
          "deliberately so that closing the gap fails loudly instead of "
          "passing unnoticed. Each needs a decision before release.")
        w("")
        for c in divergences(doc):
            w("### `%s` — %s" % (c["id"], c["title"]))
            w("")
            block = c["known_divergence"]
            for key, label in DIVERGENCE_FIELDS:
                if block.get(key):
                    w("- **%s:** %s" % (label, md_cell(block[key])))
            w("")

    w("## Reproducing this run")
    w("")
    w("```bash")
    w("export ACS_PLUGIN_ROOT=%s" % doc["build"]["root"])
    w("make eval          # or: python3 runner/run_golden.py --json results/latest.json")
    w("make report        # regenerates this file")
    w("```")
    w("")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def e(text):
    return html.escape(str(text), quote=True)


def bar(passed, failed, total, width=100):
    """One coverage bar, drawn to scale. Widths are percentages of `total`."""
    if not total:
        return ""
    pw = passed / total * width
    fw = failed / total * width
    parts = []
    if pw:
        parts.append('<span class="seg seg-pass" style="width:%.4f%%"></span>' % pw)
    if fw:
        parts.append('<span class="seg seg-fail" style="width:%.4f%%"></span>' % fw)
    return '<span class="bar">%s</span>' % "".join(parts)


def render_html(doc):
    groups, tickets = aggregate(doc)
    state, headline, detail = verdict(doc)
    t = doc["totals"]
    biggest = max((g["total"] for g in groups), default=1)

    sev = t.get("by_severity") or {}

    def sev_note(level, blocking):
        entry = sev.get(level, {})
        failed, total = entry.get("failed", 0), entry.get("total", 0)
        if failed:
            return "%d of %d failed — %s" % (failed, total, blocking)
        return "%d cases, all passing" % total

    kpis = [
        ("Critical", "%d" % sev.get("critical", {}).get("failed", 0),
         sev_note("critical", "blocks the release outright")),
        ("Major", "%d" % sev.get("major", {}).get("failed", 0),
         sev_note("major", "blocks unless re-recorded")),
        ("Minor", "%d" % sev.get("minor", {}).get("failed", 0),
         sev_note("minor", "triage, does not block")),
        ("Divergences", "%d" % t["known_divergences"],
         "pinned as observed, need a decision"),
    ]

    rows = []
    for g in groups:
        rows.append(
            '<tr><th scope="row">%s<span class="sub">%s</span></th>'
            '<td class="num">%d</td><td class="barcell">%s</td>'
            '<td class="num">%d</td><td class="num %s">%d</td></tr>'
            % (e(g["title"]), e(g["surface"]), g["total"],
               bar(g["passed"], g["failed"], biggest,
                   width=100.0 * g["total"] / biggest),
               g["passed"], "warnnum" if g["divergences"] else "zero",
               g["divergences"]))

    ticket_rows = "".join(
        '<li><code>%s</code><span class="tnum">%d</span>'
        '<span class="tbar">%s</span></li>'
        % (e(tk["ticket"]), tk["total"],
           bar(tk["passed"], tk["failed"], max(x["total"] for x in tickets),
               width=100.0 * tk["total"] / max(x["total"] for x in tickets)))
        for tk in tickets)

    fail_html = ""
    if failures(doc):
        blocks = []
        for c in failures(doc):
            diffs = "\n".join(e(d) for d in c["diffs"])
            blocks.append(
                '<article class="finding fail-finding">'
                '<h3><code>%s</code> %s</h3>'
                '<p class="meta">%s · profile <code>%s</code></p>'
                '<pre>%s</pre>'
                '<p class="repro">Reproduce: <code>python3 runner/run_golden.py '
                '-v --case %s</code></p></article>'
                % (e(c["id"]), e(c["title"]),
                   e(GROUP_TITLES.get(c["group"], c["group"])), e(c["profile"]),
                   diffs, e(c["id"])))
        fail_html = (
            '<section id="failures"><h2>Failures</h2>'
            '<p class="lede">Every failure is a behaviour change. Decide, per '
            'case, whether the build regressed or the golden is stale — never '
            're-record to clear a red run.</p>%s</section>' % "".join(blocks))

    div_html = ""
    if divergences(doc):
        blocks = []
        for c in divergences(doc):
            block = c["known_divergence"]
            # NOT `rows`: that name holds the coverage table's body further up,
            # and rebinding it here silently replaced the whole table with this
            # definition list.
            fields = "".join(
                "<div><dt>%s</dt><dd>%s</dd></div>" % (e(label), e(block[key]))
                for key, label in DIVERGENCE_FIELDS if block.get(key))
            blocks.append(
                '<article class="finding warn-finding">'
                '<h3><code>%s</code> %s</h3>'
                '<dl class="divergence">%s</dl></article>'
                % (e(c["id"]), e(c["title"]), fields))
        div_html = (
            '<section id="divergences"><h2>Known divergences</h2>'
            '<p class="lede">These cases pass because they pin what the build '
            '<em>actually does</em>, which differs from what its own contract '
            'states. They are recorded deliberately, so that closing the gap '
            'fails loudly instead of passing unnoticed. Each needs a decision '
            'before release.</p>%s</section>' % "".join(blocks))

    index_rows = "".join(
        '<tr class="%s"><td><code>%s</code></td><td>%s</td>'
        '<td class="dim">%s</td><td class="dim"><code>%s</code></td>'
        '<td class="status">%s</td></tr>'
        % ("row-fail" if c["status"] == "fail" else
           ("row-warn" if c["known_divergence"] else ""),
           e(c["id"]), e(c["title"]),
           e(GROUP_TITLES.get(c["group"], c["group"])),
           e(c.get("severity", "major")),
           ('<span class="pill pill-fail">fail</span>' if c["status"] == "fail"
            else ('<span class="pill pill-warn">divergence</span>'
                  if c["known_divergence"]
                  else '<span class="pill pill-pass">pass</span>')))
        for c in doc["cases"])

    kpi_html = "".join(
        '<div class="kpi"><span class="kpi-label">%s</span>'
        '<span class="kpi-value">%s</span><span class="kpi-note">%s</span></div>'
        % (e(label), e(value), e(note)) for label, value, note in kpis)

    badge = {"pass": "Passed", "warn": "Passed, off-baseline", "fail": "Blocked"}[state]

    return string.Template(TEMPLATE).substitute(
        state=state,
        badge=e(badge),
        headline=e(headline),
        detail=e(detail),
        build=e(doc["build"]["version"]),
        target=e(doc["dataset"]["target_release"]),
        dsver=e(doc["dataset"]["version"]),
        baseline=e(doc["dataset"]["recorded_against"]),
        generated=e(doc["generated_at"]),
        kpis=kpi_html,
        rows="".join(rows),
        total=t["total"],
        passed=t["passed"],
        failed=t["failed"],
        divergences=t["known_divergences"],
        ticket_rows=ticket_rows,
        ticket_count=len(tickets),
        failures=fail_html,
        divergence_section=div_html,
        index_rows=index_rows,
    )


TEMPLATE = """<title>acs v0.4.10 Release Gate</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:ital,wght@0,400;0,500;1,400&display=swap">
<style>
:root {
  --ground:#f5f7f9; --surface:#ffffff; --surface-2:#eef2f5;
  --ink:#0f1519; --ink-2:#3d4a55; --muted:#63727e; --line:#dce3e9;
  --accent:#0e6b70; --accent-soft:#d9ecec;
  --pass:#2f7a55; --pass-soft:#dcefe4;
  --warn:#8d5b0c; --warn-soft:#f6e9d2;
  --fail:#ab2b22; --fail-soft:#f7dedb;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --serif:"IBM Plex Serif",Georgia,"Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:#0d1317; --surface:#141c22; --surface-2:#1b252c;
    --ink:#e7eef4; --ink-2:#b6c4ce; --muted:#8496a3; --line:#26333c;
    --accent:#46b3ac; --accent-soft:#12312f;
    --pass:#5cbb8b; --pass-soft:#122a1f;
    --warn:#d3a049; --warn-soft:#2e2413;
    --fail:#e2726a; --fail-soft:#2f1a18;
  }
}
:root[data-theme="dark"] {
  --ground:#0d1317; --surface:#141c22; --surface-2:#1b252c;
  --ink:#e7eef4; --ink-2:#b6c4ce; --muted:#8496a3; --line:#26333c;
  --accent:#46b3ac; --accent-soft:#12312f;
  --pass:#5cbb8b; --pass-soft:#122a1f;
  --warn:#d3a049; --warn-soft:#2e2413;
  --fail:#e2726a; --fail-soft:#2f1a18;
}
* { box-sizing:border-box; }
body {
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--serif); font-size:16px; line-height:1.65;
  -webkit-font-smoothing:antialiased;
}
.wrap { max-width:60rem; margin:0 auto; padding:2.5rem 1.5rem 5rem; }
h1,h2,h3,.kpi,.eyebrow,th,.pill,.badge,nav { font-family:var(--sans); }
code,pre,.num,.tnum,.kpi-value { font-family:var(--mono); font-variant-numeric:tabular-nums; }

.eyebrow {
  font-size:.75rem; font-weight:600; letter-spacing:.12em;
  text-transform:uppercase; color:var(--accent); margin:0 0 .5rem;
}
h1 { font-size:2rem; line-height:1.2; margin:0 0 1.5rem; text-wrap:balance; font-weight:700; }

/* Verdict banner — the one fact that decides the release, so it is the one
   element that gets a fill and a heavy left rule. */
.verdict {
  display:flex; gap:1.25rem; align-items:flex-start;
  border-left:5px solid var(--edge); background:var(--fill);
  padding:1.25rem 1.5rem; border-radius:3px; margin:0 0 2rem;
}
.verdict.pass { --edge:var(--pass); --fill:var(--pass-soft); }
.verdict.warn { --edge:var(--warn); --fill:var(--warn-soft); }
.verdict.fail { --edge:var(--fail); --fill:var(--fail-soft); }
.badge {
  font-size:.7rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
  padding:.3rem .6rem; border-radius:2px; white-space:nowrap; color:var(--ground);
  background:var(--edge); margin-top:.2rem;
}
.verdict h2 { margin:0 0 .35rem; font-size:1.1rem; font-weight:600; }
.verdict p { margin:0; color:var(--ink-2); font-size:.95rem; }

dl.facts {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));
  gap:1rem 2rem; margin:0 0 2.5rem; padding:1.25rem 0;
  border-top:1px solid var(--line); border-bottom:1px solid var(--line);
}
dl.facts div { display:flex; flex-direction:column; gap:.15rem; }
dl.facts dt {
  font-family:var(--sans); font-size:.7rem; font-weight:600; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted);
}
dl.facts dd { margin:0; font-family:var(--mono); font-size:.9rem; color:var(--ink); }

.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(11rem,1fr)); gap:1px;
        background:var(--line); border:1px solid var(--line); margin:0 0 3rem; }
.kpi { background:var(--surface); padding:1.1rem 1.25rem; display:flex;
       flex-direction:column; gap:.2rem; }
.kpi-label { font-size:.7rem; font-weight:600; letter-spacing:.08em;
             text-transform:uppercase; color:var(--muted); }
.kpi-value { font-size:1.9rem; line-height:1.1; font-weight:500; color:var(--ink); }
.kpi-note { font-size:.78rem; color:var(--muted); font-family:var(--sans); }

section { margin:0 0 3rem; }
h2 { font-size:1.25rem; font-weight:600; margin:0 0 .5rem; letter-spacing:-.01em; }
.lede { color:var(--ink-2); margin:0 0 1.25rem; max-width:65ch; }

.tablewrap { overflow-x:auto; border:1px solid var(--line); background:var(--surface); }
table { width:100%; border-collapse:collapse; font-size:.9rem; }
thead th {
  font-size:.68rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
  color:var(--muted); text-align:left; padding:.7rem .9rem;
  border-bottom:1px solid var(--line); background:var(--surface-2); white-space:nowrap;
}
tbody th, tbody td { padding:.65rem .9rem; border-bottom:1px solid var(--line);
                     vertical-align:middle; }
tbody tr:last-child th, tbody tr:last-child td { border-bottom:none; }
tbody th { text-align:left; font-weight:600; font-size:.92rem; font-family:var(--sans); }
tbody th .sub { display:block; font-family:var(--mono); font-weight:400;
                font-size:.72rem; color:var(--muted); margin-top:.15rem; }
td.num, th.num { text-align:right; white-space:nowrap; }
td.zero { color:var(--muted); }
td.warnnum { color:var(--warn); font-weight:500; }
td.barcell { width:22%; min-width:6rem; }

.bar { display:flex; height:.55rem; background:var(--surface-2);
       border-radius:1px; overflow:hidden; }
.seg { display:block; height:100%; }
.seg-pass { background:var(--pass); }
.seg-fail { background:var(--fail); }

ul.tickets { list-style:none; margin:0; padding:0;
             display:grid; grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));
             gap:.5rem 2rem; }
ul.tickets li { display:grid; grid-template-columns:6.5rem 2.5rem 1fr;
                align-items:center; gap:.75rem; padding:.3rem 0;
                border-bottom:1px solid var(--line); }
ul.tickets code { font-size:.85rem; color:var(--ink); }
.tnum { font-size:.85rem; color:var(--muted); text-align:right; }

.finding { border:1px solid var(--line); border-left:4px solid var(--edge);
           background:var(--surface); padding:1.1rem 1.35rem; margin:0 0 1rem; }
.fail-finding { --edge:var(--fail); }
.warn-finding { --edge:var(--warn); }
.finding h3 { font-size:1rem; font-weight:600; margin:0 0 .35rem; }
.finding h3 code { font-size:.9rem; color:var(--accent); margin-right:.4rem; }
.finding p { margin:0 0 .6rem; color:var(--ink-2); font-size:.93rem; }
.finding p:last-child { margin-bottom:0; }
.finding .meta { font-family:var(--sans); font-size:.78rem; color:var(--muted); }
.finding pre { background:var(--surface-2); padding:.8rem 1rem; overflow-x:auto;
               font-size:.82rem; margin:0 0 .6rem; border-radius:2px; }
.repro { font-size:.82rem; }
dl.divergence { margin:0; display:grid; gap:.55rem; }
dl.divergence div { display:grid; grid-template-columns:11rem 1fr; gap:1rem; }
dl.divergence dt { font-family:var(--sans); font-size:.72rem; font-weight:600;
                   letter-spacing:.06em; text-transform:uppercase;
                   color:var(--muted); padding-top:.15rem; }
dl.divergence dd { margin:0; font-size:.9rem; color:var(--ink-2); }
@media (max-width:44rem) { dl.divergence div { grid-template-columns:1fr; gap:.15rem; } }

.pill { display:inline-block; font-size:.66rem; font-weight:600; letter-spacing:.06em;
        text-transform:uppercase; padding:.16rem .45rem; border-radius:2px; }
.pill-pass { background:var(--pass-soft); color:var(--pass); }
.pill-warn { background:var(--warn-soft); color:var(--warn); }
.pill-fail { background:var(--fail-soft); color:var(--fail); }
td.status { text-align:right; white-space:nowrap; }
td.dim { color:var(--muted); font-size:.83rem; }
.row-warn { background:color-mix(in srgb, var(--warn-soft) 45%, transparent); }
.row-fail { background:color-mix(in srgb, var(--fail-soft) 55%, transparent); }
.indexwrap { max-height:32rem; overflow:auto; border:1px solid var(--line);
             background:var(--surface); }
.indexwrap thead th { position:sticky; top:0; z-index:1; }

code { font-size:.88em; background:var(--surface-2); padding:.08em .34em;
       border-radius:2px; }
pre code { background:none; padding:0; }
.scope { border:1px solid var(--line); border-left:4px solid var(--accent);
         background:var(--surface); padding:1rem 1.3rem; margin:0 0 3rem;
         font-size:.92rem; color:var(--ink-2); }
.scope strong { color:var(--ink); }
footer { border-top:1px solid var(--line); padding-top:1.25rem; margin-top:3rem;
         font-family:var(--sans); font-size:.8rem; color:var(--muted); }
footer code { font-size:.85em; }
@media (max-width:34rem) {
  .verdict { flex-direction:column; gap:.75rem; }
  ul.tickets li { grid-template-columns:6rem 2.2rem 1fr; }
}
</style>

<div class="wrap">
  <p class="eyebrow">Golden dataset · deterministic tier</p>
  <h1>acs plugin evaluation — $target release gate</h1>

  <div class="verdict $state">
    <span class="badge">$badge</span>
    <div>
      <h2>$headline</h2>
      <p>$detail</p>
    </div>
  </div>

  <dl class="facts">
    <div><dt>Build under test</dt><dd>acs $build</dd></div>
    <div><dt>Target release</dt><dd>$target</dd></div>
    <div><dt>Dataset</dt><dd>$dsver</dd></div>
    <div><dt>Baseline</dt><dd>acs $baseline</dd></div>
    <div><dt>Generated</dt><dd>$generated</dd></div>
  </dl>

  <div class="kpis">$kpis</div>

  <p class="scope"><strong>Scope.</strong> This report covers the
  <strong>deterministic tier</strong> only — no model, no network, no cost. It
  pins <strong>contracts</strong>: that these surfaces still emit what they were
  recorded emitting. It says <strong>nothing</strong> about whether skills got
  less reliable, worse, more expensive or slower — those are tier 3's subject
  (<code>make measure &amp;&amp; make perf</code>, see
  <code>docs/PERFORMANCE.md</code>), and a green report here is not evidence
  about any of them. Routing at runtime is unmeasured here too; tier 3 measures
  it, while the tier-2 tree (<code>evals/</code>, run by
  <code>claude plugin eval</code>) remains authored and never executed.</p>

  <section>
    <h2>Coverage by surface</h2>
    <p class="lede">Bar length is the group's share of the largest group, so
    the widths compare case counts directly. $total cases, weighted by the
    severity rubric rather than counted flat.</p>
    <div class="tablewrap">
      <table>
        <thead><tr>
          <th scope="col">Group</th><th scope="col" class="num">Cases</th>
          <th scope="col">Result</th><th scope="col" class="num">Passed</th>
          <th scope="col" class="num">Divergences</th>
        </tr></thead>
        <tbody>$rows</tbody>
        <tfoot><tr>
          <th scope="row">Total</th><td class="num">$total</td><td></td>
          <td class="num">$passed</td><td class="num">$divergences</td>
        </tr></tfoot>
      </table>
    </div>
  </section>

  <section>
    <h2>Coverage by ticket</h2>
    <p class="lede">Cases carry the ticket whose behaviour they pin.
    $ticket_count tickets are covered; a ticket absent from this list has no
    cases and is not covered by this dataset.</p>
    <ul class="tickets">$ticket_rows</ul>
  </section>

  $failures
  $divergence_section

  <section>
    <h2>Case index</h2>
    <p class="lede">Every case in the run, in execution order.</p>
    <div class="indexwrap">
      <table>
        <thead><tr>
          <th scope="col">Case</th><th scope="col">Assertion</th>
          <th scope="col">Group</th><th scope="col">Severity</th>
          <th scope="col" class="status">Status</th>
        </tr></thead>
        <tbody>$index_rows</tbody>
      </table>
    </div>
  </section>

  <footer>
    Generated by <code>runner/report.py</code> from
    <code>results/latest.json</code>. Reproduce with <code>make eval &amp;&amp;
    make report</code>. A failing case is a behaviour change, not automatically
    a defect — read the diff before deciding whether the build regressed or the
    golden is stale.
  </footer>
</div>
"""


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=os.path.join(REPO_ROOT, "results", "latest.json"),
                    help="run result written by run_golden.py --json")
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "results", "report"),
                    help="output path WITHOUT extension; .md and .html are written")
    args = ap.parse_args()

    if not os.path.isfile(args.json):
        print("no run result at %s — run `make eval` first" % args.json,
              file=sys.stderr)
        return 2
    with open(args.json) as fh:
        doc = json.load(fh)

    directory = os.path.dirname(os.path.abspath(args.out))
    if directory:
        os.makedirs(directory, exist_ok=True)
    md_path, html_path = args.out + ".md", args.out + ".html"
    with open(md_path, "w") as fh:
        fh.write(_pre_commit_clean(render_markdown(doc)))
    with open(html_path, "w") as fh:
        fh.write(_pre_commit_clean(render_html(doc)))

    state, headline, _ = verdict(doc)
    print("%s\n  %s\n  %s" % (headline, md_path, html_path))
    return 0 if state != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
