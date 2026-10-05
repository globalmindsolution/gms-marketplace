"""acs_lib.doc_sets — which doc set a repo document belongs to, and their order.

Shared by `commit_plan` (one commit per doc set, ADR-0127) and the
`acs.py design list` lister (ADR-0130), so the two always group a document the
same way. Paths are repo-relative POSIX paths; nothing here touches the disk.
"""

from .artifacts import TICKETS_PATH


#: The living LLD subfolders a feature keeps (edited in place, ADR-0126); any
#: other folder under lld/<feature>/ is one change's design records.
LLD_LIVING = {"api", "data", "flows", "components"}


def doc_set(path):
    """(key, label) of the doc set a document belongs to."""
    if path.startswith(TICKETS_PATH + "/") and path.count("/") >= 3:
        ticket_id = path.split("/")[2]
        return "tickets/%s" % ticket_id, "ticket %s docs" % ticket_id
    parts = [p.lower() for p in path.split("/")]
    dirs, name = parts[:-1], parts[-1]
    if "lld" in dirs:
        rest = parts[dirs.index("lld") + 1:-1]
        feature = rest[0] if rest else None
        if len(rest) >= 2 and rest[1] not in LLD_LIVING:
            # One change's design records (ADR-0128): lld/<feature>/<id>/.
            raw = path.split("/")[:-1][dirs.index("lld") + 2]
            return "lld/%s/%s" % (feature, raw), "%s design records" % raw
        return ("lld/%s" % feature, "LLD %s" % feature) if feature else ("lld", "LLD")
    if "features" in dirs and name == "analysis.md":
        feature = parts[dirs.index("features") + 1] if dirs.index("features") + 1 < len(dirs) \
            else None
        if feature and dirs.index("features") + 2 == len(dirs):
            return "prd/features/%s" % feature, "feature %s analysis" % feature
    if "hld" in dirs:
        return "hld", "HLD"
    if "development" in dirs:
        # A run's Development folder (ADR-0128): <development_dir>/<feature>/<id>/.
        # One change's documents group together, as docs/tickets/<ID>/ did.
        rest = [p for p in path.split("/")[:-1]][dirs.index("development") + 1:]
        if len(rest) >= 2:
            return "development/%s/%s" % (rest[0], rest[1]), "%s docs" % rest[1]
        return (("development/%s" % rest[0], "development %s docs" % rest[0]) if rest
                else ("development", "development docs"))
    if {"adr", "adrs", "decisions"}.intersection(dirs):
        return "adr", "ADRs"
    if "product" in dirs or "prd" in name or "roadmap" in name:
        return "prd", "PRD"
    if "requirements" in dirs:
        return "requirements", "requirements"
    return "other", "docs"


def doc_order(key):
    """The sort key of a doc set: PRD, requirements, HLD, LLD, development,
    ADRs, legacy ticket folders, then anything else."""
    order = ["prd", "requirements", "hld", "lld", "development", "adr", "tickets", "other"]
    head = key.split("/", 1)[0]
    return (order.index(head) if head in order else len(order), key)
