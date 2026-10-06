# Inputs — gather before the loop

Read before the first spawn — what you find decides how you scope the run,
never whether it runs.

Read (you and your designer; reference by path in XML, do not inline file bodies):

1. The requirements document (`requirements.path`, the run's
   `requirements.md`): title, description, acceptance criteria — plus a
   ticket's type, priority and children when the run has one. The run's
   analysis and the feature's living analysis (`feature_analysis`,
   `<prd_dir>/features/<feature>/analysis/`) when `acs.py artifacts show`
   reports them — the impact map and risks the
   design starts from. Each is a folder (ADR-0133): read its `README.md`
   first (`artifacts["analysis.md"]`), then the context files the design spans
   (`analysis_files`); a legacy single `analysis.md` is read whole.
2. **The HLD — PRIMARY input when it exists**:
   `<checkout_root>/<architecture_dir>/hld/` (`overview.md`, the C4 views,
   `data-model.md`, `integration-map.md`, `deployment.md`, `tech-stack.md`,
   `cross-cutting.md`, whichever exist). The design either CONFORMS to the HLD
   or names, view by view, the change it requires. Absent → say so in
   `## HLD views affected` and design against the codebase directly.
3. **The feature's living LLD** — every document under
   `<checkout_root>/<architecture_dir>/lld/<feature>/{api,data,flows,components}/`
   (written by `/acs:create-api-contract`, `/acs:create-data-design` and
   `/acs:create-flows`), with its version: `python3
   "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check <each document>`
   prints `{path, status, version}`. The tech design SNAPSHOTS them at those
   versions; it never redesigns them. A category with no document yet is
   reported "none yet" with the skill that writes it.
4. The PRD at `<checkout_root>/<prd>` when present —
   product-level NFRs and constraints bound the design.
5. The consumer repo's code and docs relevant to the change (the designer's
   survey identifies the exact files).

Any of 2-5 may be absent; the requirements are always there, and the design
is then grounded in them and the codebase as it is.
