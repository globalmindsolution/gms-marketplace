#!/usr/bin/env python3
"""pr-conventions.py — pre-open convention self-check for a PR body.

Gives /acs:create-pr -- since ADR-0127 the only skill that opens a PR -- a
deterministic way to:

  check         Self-check a filled PR body BEFORE the PR is opened against
                exactly what CI will check -- that it names its ticket
                (ADR-0106) -- by driving check-conventions.py's evaluate()
                (single source of truth); this module never re-implements the
                rule. Two producer-only hygiene scans (unrendered {placeholder}
                tokens, leftover <!-- --> template comments) run on top of,
                never instead of, evaluate().

Stdlib-only, runtime-agnostic. Shape mirrors clarify.py / new-ticket.py:
argparse with subparsers, JSON to stdout, sys.exit non-zero on failure.

A PR's title is free text the author writes, like any contributor, so there is
nothing to render.

Usage:
  pr-conventions.py check --body-file pr-body.md --ticket-prefix MAR
"""

import argparse
import importlib.util
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ---------------------------------------------------------------------------
# Load check-conventions.py by file path — the SAME in-plugin template path
# tests/acs/test_conventions_check.py loads, never a consumer-repo copy at
# <checkout_root>/.acs/ci/check-conventions.py (which may be stale). This is
# the single source of truth for convention evaluation (AC-3): this module
# calls ONLY cc.evaluate, never re-implements it.
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join(_PLUGIN_ROOT, "templates", "ci", "check-conventions.py")
_cc_spec = importlib.util.spec_from_file_location("acs_check_conventions", CHECKER)
cc = importlib.util.module_from_spec(_cc_spec)
_cc_spec.loader.exec_module(cc)

# Producer-only body-fill hygiene scans — NOT convention rules, distinct
# headings, run in addition to (never instead of) cc.evaluate().
_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _hygiene_errors(body):
    """The two producer-only hygiene scans, distinct from evaluate()'s headings."""
    errors = []
    if _PLACEHOLDER_RE.search(body or ""):
        errors.append({
            "heading": "unrendered_placeholder",
            "detail": "PR body contains an unrendered {token} placeholder — "
                      "fill every template placeholder before opening the PR.",
        })
    if _HTML_COMMENT_RE.search(body or ""):
        errors.append({
            "heading": "leftover_template_comment",
            "detail": "PR body contains a leftover <!-- --> template guidance "
                      "comment — delete it when filling the section.",
        })
    return errors


def run_check(body, ticket_prefix):
    """Drive cc.evaluate(settings, ctx, "pr") -- the CI check, which is now only
    the ticket link (ADR-0106) -- plus the two hygiene scans.

    No branch, labels or commit history are passed: CI no longer reads them for
    anything but an exemption, and a PR about to be opened is never exempt."""
    settings = {"ticket_prefix": ticket_prefix}
    ctx = {"body": body, "branch": "", "labels": []}
    res = cc.evaluate(settings, ctx, "pr")
    errors = [{"heading": heading, "detail": detail} for heading, detail in res.errors]
    errors.extend(_hygiene_errors(body))
    return {"passed": not errors, "errors": errors, "skipped": list(res.skipped)}


# ---------------------------------------------------------------------------
# argparse plumbing — testable core above is callable without it.
# ---------------------------------------------------------------------------

def _add_check_parser(sub):
    p = sub.add_parser("check")
    p.add_argument("--body-file", required=True)
    p.add_argument("--ticket-prefix", required=True)
    # Accepted and ignored, so an older skill invocation still runs: CI no
    # longer checks the title, a label or the description's sections (ADR-0106).
    for legacy in ("--title", "--require-label", "--pr-title-format"):
        p.add_argument(legacy, default=None, help=argparse.SUPPRESS)
    p.add_argument("--sections", default=None, action="append", help=argparse.SUPPRESS)
    return p


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_check_parser(sub)
    args = parser.parse_args(argv)

    if args.cmd == "check":
        try:
            with open(args.body_file, "r", encoding="utf-8") as fh:
                body = fh.read()
        except OSError as exc:
            print(json.dumps({"passed": False,
                               "errors": [{"heading": "body_file",
                                           "detail": "could not read --body-file: %s" % exc}],
                               "skipped": []}))
            sys.exit(1)
        result = run_check(body=body, ticket_prefix=args.ticket_prefix)
        print(json.dumps(result))
        sys.exit(0 if result["passed"] else 1)

    sys.exit(2)  # pragma: no cover - unreachable, argparse `required=True` gates cmd


if __name__ == "__main__":
    main()
