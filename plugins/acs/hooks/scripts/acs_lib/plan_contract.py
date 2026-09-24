"""acs_lib.plan_contract — the plan's machine-readable minimum.

`/acs:create-impl-plan` now works the way Claude Code's plan mode works
(§3.2): read-only until approved, and a plan written for a human to approve in
one read rather than a template with a section per heading whether or not that
heading has content.

"Not a template" is not "no structure", though: three things downstream code
reads must be findable without parsing prose. So the plan ends with ONE
section of fixed shape, and everything above it is free-form:

    ## Contract
    delivery_path: standard
    owes:
      api_contract: true
      test_cases:   true
      e2e:          false
      reason: "CLI-only change; no HTTP surface, no browser flow"

    ### Executor tasks & file map
    - task 1: plugins/acs/hooks/scripts/acs_lib/run.py, tests/acs/test_run.py
    - task 2: plugins/acs/skills/ship/SKILL.md

`### Executor tasks & file map` keeps its exact heading because the file-map
guard and `plan-approval.py` already key on it.

Three readers, three reasons:

  * the **delivery path** -- `/acs:code` dispatches to its leg from it (§3.5).
    Judged ONCE, here, from the plan's own scope; this is the only place it is
    judged, and recording it on the plan rather than in `ship.yaml` is what
    let the `delivery:` block leave the workflow.
  * the **owes** flags -- the four always-run steps read them and record an
    evidenced no-op when nothing is owed (§2.2), which is what replaced the
    `when:` predicates the workflow used to carry.
  * the **file map** -- the executor partition, and the contract the file-map
    guard enforces on every Write.

`plan_sha256` hashes the whole file, prose and contract alike, so editing
either invalidates the approval.
"""

import os
import re

from . import yamlsubset
from .yamlsubset import YamlSubsetError

CONTRACT_HEADING = "## Contract"
FILE_MAP_HEADING = "### Executor tasks & file map"

#: The three predicates the plan states and the always-run steps read.
OWES_KEYS = ("api_contract", "test_cases", "e2e")

#: The delivery paths, cheapest first. `/acs:code` dispatches to `code-<path>`.
DELIVERY_PATHS = ("trivial", "small", "standard", "complex")

_HEADING_RE = re.compile(r"^#{1,6}\s")


def contract_text(text):
    """The `## Contract` section's body, or None when the plan has none. Ends
    at the next heading of the same or higher level -- `### Executor tasks &
    file map` is INSIDE the contract, not after it."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == CONTRACT_HEADING:
            start = index + 1
            break
    if start is None:
        return None
    out = []
    for line in lines[start:]:
        stripped = line.strip()
        if _HEADING_RE.match(stripped) and not stripped.startswith("###"):
            break
        out.append(line)
    return "\n".join(out)


def parse(text):
    """The contract as a dict, `{}` when the plan declares none.

    Only the YAML-ish head of the section is parsed -- up to the file-map
    subheading -- because the file map is a markdown list the guard reads, not
    a mapping.
    """
    body = contract_text(text)
    if body is None:
        return {}
    head = body.split(FILE_MAP_HEADING)[0]
    head = "\n".join(line for line in head.splitlines() if line.strip())
    if not head.strip():
        return {}
    try:
        doc = yamlsubset.loads(head)
    except YamlSubsetError:
        return {}
    return doc if isinstance(doc, dict) else {}


def read(path):
    """`parse` over a plan on disk; `{}` when it is missing or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return parse(fh.read())
    except OSError:
        return {}


def delivery_path(contract):
    """The judged path, or None. `/acs:code` dispatches to `code-<path>`."""
    value = (contract or {}).get("delivery_path")
    return value if value in DELIVERY_PATHS else None


def owes(contract, key):
    """True / False / None -- whether the plan says this artifact is owed.
    None means the plan did not say, and silence is not permission to skip:
    the step does its work and decides for itself."""
    table = (contract or {}).get("owes") or {}
    value = table.get(key)
    return value if isinstance(value, bool) else None


def errors(contract):
    """[message, ...] for a contract block that cannot be acted on. Empty when
    it is admissible -- including when it is absent, which is a plan written
    before this section existed rather than a broken one."""
    if not contract:
        return []
    out = []
    path = contract.get("delivery_path")
    if path is not None and path not in DELIVERY_PATHS:
        out.append("delivery_path: %r is not one of %s"
                   % (path, " | ".join(DELIVERY_PATHS)))
    table = contract.get("owes")
    if table is not None and not isinstance(table, dict):
        out.append("owes: expected a mapping of %s" % ", ".join(OWES_KEYS))
    elif isinstance(table, dict):
        for key, value in table.items():
            if key == "reason":
                continue
            if key not in OWES_KEYS:
                out.append("owes.%s: not one of %s" % (key, ", ".join(OWES_KEYS)))
            elif not isinstance(value, bool):
                out.append("owes.%s: expected true or false, got %r" % (key, value))
    return out
