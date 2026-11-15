"""acs_lib.design_types — the design documents a repo produces (ADR-0118, ADR-0120).

A fixed catalog of high-level (HLD) and low-level (LLD) document types. A repo
picks which ones it wants at /acs:setup, stored as `design.hld_types` and
`design.lld_types`; the Design skills write exactly the enabled ones. This
module is the catalog's only declaration: the settings schema's enums and
defaults are tested against it, not the other way round.

The three HLD documents in HLD_ALWAYS are not a choice -- every architecture
set has an overview, a tech stack and the cross-cutting conventions -- so they
are named for the setup question but never stored.
"""

from ._common import GateError

#: HLD documents every architecture set carries; not selectable.
HLD_ALWAYS = ("overview", "tech-stack", "cross-cutting")

#: {id: (label, on by default)}, in the order docs list them.
HLD_TYPES = {
    "c4-context": ("C4 L1 system context: the system, its users, external systems", True),
    "c4-container": ("C4 L2 containers, relations labelled with protocol", True),
    "c4-component": ("C4 L3 components per container", True),
    "data-model": ("Conceptual ERD: entities and relationships, no attributes", True),
    "integration-map": ("API landscape: who exposes and consumes which API, sync or async", True),
    "deployment": ("Runtime and infrastructure topology", True),
    "project-structure": ("Intended repository layout", True),
    "data-flow": ("Data-flow diagram with trust boundaries (threat model)", False),
    "capability-map": ("Business capabilities mapped to containers", False),
}

LLD_TYPES = {
    "api-contract": ("Per operation or event: request/response or payload, errors, examples", True),
    "logical-erd": ("Logical ERD: attributes, keys, cardinalities", True),
    "physical-schema": ("Tables, types, indexes, constraints, migration outline", True),
    "sequence": ("Sequence diagrams: interaction over time", True),
    "activity": ("Activity diagrams: algorithm or business-rule flow", True),
    "state": ("State machines: an entity's lifecycle", True),
    "component-detail": ("Internals of one component", False),
    "class": ("Class diagrams: types and relationships", False),
}

#: settings key -> its catalog.
KINDS = {"hld_types": HLD_TYPES, "lld_types": LLD_TYPES}


def defaults():
    """The `design` block a repo gets when it sets none (fresh lists)."""
    return {key: [tid for tid, (_label, on) in catalog.items() if on]
            for key, catalog in KINDS.items()}


def normalise(ids, key):
    """`ids` deduplicated and in catalog order, so equal choices compare equal
    (/acs:setup writes only a choice that differs from the default). Unknown ids
    are kept, at the end, for validate_design to name."""
    catalog = KINDS[key]
    ids = list(dict.fromkeys(ids or []))
    return [t for t in catalog if t in ids] + [t for t in ids if t not in catalog]


def normalise_block(design):
    """A `design` answer with each known list normalised; anything else as given."""
    if not isinstance(design, dict):
        return design
    return {key: normalise(ids, key) if key in KINDS and isinstance(ids, list) else ids
            for key, ids in design.items()}


def validate_design(design):
    """`design` is {hld_types?: [id], lld_types?: [id]}, each id from its catalog."""
    if not isinstance(design, dict):
        raise GateError("design must be an object: {hld_types?: [...], lld_types?: [...]}.")
    for key, ids in design.items():
        if key not in KINDS:
            raise GateError("design.%s is not a setting (allowed: %s)." % (key, ", ".join(KINDS)))
        if not isinstance(ids, list) or not all(isinstance(t, str) for t in ids):
            raise GateError("design.%s must be a list of type ids." % key)
        unknown = [t for t in ids if t not in KINDS[key]]
        if unknown:
            raise GateError("design.%s: unknown type %s (allowed: %s)."
                            % (key, ", ".join(unknown), ", ".join(KINDS[key])))


def detect(settings):
    """What /acs:setup shows: each catalog with labels and defaults, the always-on
    HLD documents, and the repo's current choice."""
    current = (settings or {}).get("design") or {}
    defaults_now = defaults()
    return {
        "hld_always": list(HLD_ALWAYS),
        "catalog": {key: [{"id": tid, "label": label, "default": on}
                          for tid, (label, on) in catalog.items()]
                    for key, catalog in KINDS.items()},
        "current": {key: normalise(current.get(key, defaults_now[key]), key) for key in KINDS},
    }
