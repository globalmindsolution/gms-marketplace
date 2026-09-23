#!/usr/bin/env python3
"""Post-hook for /acs:merge-pr — finalizes the step's invocation and updates
run.json and tickets-index.json.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-merge-pr.py --result-file <result.json>     # or JSON on stdin

The exempt non-ticket path (/acs:merge-pr --pr) has no post step: with no
ticket there is nothing to record (ADR-0104).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


def main():
    lib.run_post("merge-pr")


if __name__ == "__main__":
    main()
