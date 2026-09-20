"""acs_lib — the deterministic kernel behind every acs hook and helper CLI.

MAR-522 split the 2,989-line module into eight domain modules; this facade
re-exports their public surface, so `import acs_lib as lib` resolves every name
it always did. In dependency order:

  _common        json/time/path primitives, the skill registry, GateError
  settings       .acs settings load/validate/merge, model and format resolution
  repo           git and checkout identity, workspace layout, ticket-id resolution
  hostgates      whether this runtime fires acs's hooks at all, and what to do if not
  planrules      the plan-approval predicate and the additive-diff classifier
  run / step     the two state machines (§4.3, §4.4)
  lock           the run lock and its audit ledger
  tickets        ticket.json, the id counter and tickets-index.json
  metrics        token/cost apportionment and the metrics ledger
  setup_helpers  CLAUDE.md managed block, toolchain probing, exempt-PR classifier
  forge          PR-metadata fill and tracker sync against gh (MAR-525)
  gate_inputs    the ticket-artifact input checks the Build/Test gates share
  gates          context resolution, the input/brake gates, post-hook persistence
  advisory       the out-of-order advisory line the pre-hook prints (never a refusal)
  verdict        the verifier's verdict document and its derived-pass rule
  derive         the result-document fields the kernel computes from artifacts
  lifecycle      the SubagentStart/SubagentStop/Stop/PreCompact hook bodies
  yamlsubset     the strict YAML subset the workflow files and front matter use
  workflow       phases registry, ship.yaml resolution/validation, predicates, `workflow next`
  artifacts      the ticket documents in the repo docs tree: ticket.md, derived status, migrate

PATCHING: a name imported into a sibling binds at import time, so patching it on
this facade does NOT reach a caller that already imported it. Patch the module
that USES it -- `mock.patch.object(lib.step, "write_json")` -- or, for a stdlib
module (`lib.subprocess`), patch the shared module object as before.
"""

from . import (_common, settings, repo, hostgates, planrules, lock, tickets, metrics,  # noqa: F401
               setup_helpers, forge, verdict, derive, gate_inputs, gates, lifecycle,  # noqa: F401
               advisory)  # noqa: F401

from ._common import (ATTRIBUTION_SKILL_MAP, DELIVERY_TICKET_SKILLS,
    DELIVERY_TICKET_TITLES, DOC_BOOTSTRAP_DEPENDENCIES, DOC_BOOTSTRAP_FANOUT_V1,
    DOC_BOOTSTRAP_SENTINEL, DOC_BOOTSTRAP_SETTINGS_KEY, DOC_SET_TITLES, DOC_SETS,
    CODE_PATH_LEGS, GateError, HOOKED_SKILLS, LEG_ENTRY_POINTS,
    PIPELINE_STEP_ORDER, PLANNING_SKILLS, PRIORITIES, PRODUCT_SKILLS,
    PRODUCT_TICKET_TITLES, PROJECT_MODE_LEG, PROJECT_MODE_SENTINEL,
    PROJECT_MODE_SETTINGS_KEY, PROJECT_MODES, RUN_STATUSES, ReconciliationRequired, TICKET_ID_RE,
    TICKET_STATUSES, TICKET_TYPES, UNHOOKED_SKILLS, WORKFLOW_SKILLS, _ISO_INSTANT,
    _git, deep_merge, now_iso, parse_iso, plugin_root, read_json, slugify, write_json)  # noqa: F401

from .settings import (BUILTIN_TEMPLATES, DEFAULT_SETTINGS, ENFORCEMENT_DEFAULTS,
    FORMAT_PLACEHOLDERS, MODEL_EFFORTS, MODEL_OVERRIDE_SKILLS, MODEL_ROLES,
    RECOMMENDED_MODELS, _model_override_skills, _normalize_e2e_into_suites,
    enforcement_value, load_settings, render_format, resolve_role_model,
    resolve_template, settings_files, validate_formats, validate_models,
    validate_settings)  # noqa: F401

from .repo import (GH_ACCESS_DENIED_MARKER, GH_ACCESS_HINT, GH_GENERIC_HINT,
    GUARD_ATTEMPTS, GUARD_ATTEMPTS_ENV, GUARD_ATTEMPTS_MAX, GUARD_INTERVAL,
    GUARD_STALE_SECONDS, GuardTimeout, guard_attempts, guard_stale_seconds,
    _EVIDENCE_RANKS, _evidence_source_commands, _guarded_repo_write, archive_dir,
    checkout_id, checkout_root, current_branch, default_state_root,
    find_ticket_partition, gh_failure_hint, gh_read_is_unevaluable,
    gh_pr_required_checks_ok, gh_pr_view, index_path, lock_path, main_repo_root,
    pointer_path, record_session_marker, repo_dir, repo_guard, repo_partition_id,
    resolve_active_partition, resolve_ticket_id, scan_local_ticket_evidence,
    session_marker_path, sessions_dir, ticket_dir,
    ticket_id_from_text)  # noqa: F401)  # noqa: F401

from .hostgates import (DEFAULT_GATE_RESPONSE, GATE_EVIDENCE_MAX_AGE_SECONDS,
    GATE_RESPONSES, HOOK_ENFORCEMENTS, SESSION_MARKER_MAX_AGE_SECONDS,
    accepted_gate_evidence, accepted_session_marker, consume_gate_evidence,
    gate_evidence, gate_evidence_path, gate_notice, gate_response,
    record_gate_evidence)  # noqa: F401

from .planrules import (PLAN_FOLD_CLAUSES, PLAN_FOLD_SECTIONS,
    PLAN_REQUIRED_SECTIONS, _PLAN_HEADING_RE, _coverage_target_stated,
    _plan_headings, classify_additive_diff, plan_approval_eligible)  # noqa: F401

from .readiness import (DECISION_FIELDS, NO_REQUIRED_CHECKS_MARKERS,
    DIMENSIONS, PASSING_CONCLUSIONS, PENDING_STATES,
    PENDING_STATUSES, PR_VIEW_FIELDS, VERDICTS, check_name, check_state,
    classify_checks, merge_readiness)  # noqa: F401

from . import lock as lock_module  # noqa: F401
from .lock import (LOCK_MAX_AGE_HOURS, LOCK_STALENESS_REASONS,  # noqa: F401
    acquire_lock, append_lock_event, check_lock, force_release_lock,
    lock_audit_path, lock_is_stale, lock_staleness, read_lock, release_lock)

from . import tickets as tickets_module  # noqa: F401
from .tickets import (allocate_ticket_id, load_ticket, new_ticket_doc,  # noqa: F401
    save_ticket, update_index)

from .metrics import (_EMPTY_MEASURED_TOKENS, _TOKEN_TOTAL_FIELDS, _measure_run_usage,
    _sum_role_tokens, _update_metrics_body, backfill_distinct_pr_count,
    compute_ticket_totals, elapsed_seconds, metrics_path, run_seconds, update_metrics)  # noqa: F401

from .setup_helpers import (ACS_BLOCK_BEGIN, ACS_BLOCK_END, DOC_SET_ALL, DocSetRequest,
    TOOLCHAIN, _BARE_INT_RE,
    _FANOUT_FOR_RE, _LEGACY_FOR_NOTE, _PR_FLAG_RE, _PR_HASH_RE, _PR_URL_RE,
    _managed_body, _pr_labels, _short_doc_set, _unknown_doc_set_note,
    _sentinel_present, _soft_peers, _strip_stray_markers, _tool_version,
    canonical_doc_set, check_toolchain,
    classify_merge_pr_arg, doc_set_present_on_disk, doc_set_spellings, fanout_batches,
    managed_block_is_malformed, managed_body_from_template, missing_tools,
    parse_doc_set_arg, parse_fanout_for_arg, project_mode, render_managed_block,
    tracker_cli_warning,
    upsert_managed_block, validate_exempt_pr)  # noqa: F401

from .gate_inputs import e2e_case_count  # noqa: F401
from .gates import (ARCHITECTURE_GATED, BRAKES, NothingOwed,  # noqa: F401
    _archive_partition, _clear_pointers_for_ticket, _epic_auto_done,
    _merge_pr_arg_text,
    _read_result_from_argv, _require_architecture_doc_set, build_context,
    design_requirement, gate_step, parent_epic_dir, resolve_run_for, run_post,
    run_post_exempt_pr, run_pre, run_pre_payload, session_end,
    subject_from_payload)
 # noqa: F401
from .advisory import ADVISORY_MARK, render_advisory, workflow_advisory  # noqa: F401

# Re-exported so `lib.subprocess` / `lib.os` keep resolving: patching
# `acs_lib.subprocess.run` patches the shared module object every submodule sees.
from ._common import (cc, datetime, fnmatch, hashlib, json, os, re, shutil, socket,
    subprocess, sys, tempfile, timedelta, timezone)  # noqa: F401

from .forge import (GROUP_B_FIELDS, PR_STATUS_OPTIONS, TICKET_STATUS_OPTIONS,
    TYPE_OPTIONS, Gh, fill_group_b, find_item_for_url, finding, first_matching_option,
    match_field, match_option, pr_metadata_fill, project_fields, project_fill,
    project_items, reviewers_for, sync_candidates, tracker_sync,
    tracker_sync_one)  # noqa: F401
from .lifecycle import (ACTIVE_AGENTS_DIRNAME, BLOCK_LIMIT,
    HANDOFF_CONTEXT_FILENAME,
    ROLE_PHASES, active_agents, active_agents_dir, agent_record_path, clear_agent,
    clear_stop_blocks, count_agent_stop_attempt, count_stop_block, extract_message,
    in_flight_skill, open_clarifications, parse_agent_type, phase_artifact_path,
    pre_compact, read_agent, record_agent_start, render_handoff_context, resolve_partition,
    result_document, stop, stop_counter_key, subagent_start, subagent_stop,
    write_handoff_context, write_phase_snapshot)  # noqa: F401
from .lifecycle import stop as stop_hook  # noqa: F401
from .filemap import (FILEMAP_FILENAME_FMT, WRITE_TOOL_PATH_KEYS, active_executor,
    file_map_guard, filemap_path, load_filemap, normalize_repo_path, path_in_filemap,
    save_filemap_task)  # noqa: F401

from .verdict import (BASE_DIMENSIONS, DIMENSION_RESULTS, LENS_DIMENSIONS, owed_dimensions, LENSES, SEVERITIES, VERDICT_DIMENSIONS,
    blocking_findings, derived_passed, load_verdict, merge_lens_verdicts,
    validate_verdict, verdict_filename, verdict_path, write_verdict)  # noqa: F401

from .derive import (DERIVED_KEYS, VERDICT_SKILLS, derive_states, derive_tests,
    derive_verifier_passed, disagreements, execute_reports,
    gh_pr_for_branch, guard_denials, latest_verdict, review_iterations)  # noqa: F401

from . import yamlsubset, workflow  # noqa: F401,E402
from .yamlsubset import YamlSubsetError, split_front_matter  # noqa: F401
from .workflow import (OVERRIDE_WORKFLOW_RELPATH, PHASE_GROUPS,  # noqa: F401
    RUN_LEVEL_ARTIFACTS, WORKFLOW_VERSION, WorkflowError,
    default_workflow_path, has_step, load_workflow, loop_for, loops_of,
    order_warnings, override_workflow_path, resolve_workflow, step_index,
    steps_of, validate_workflow, validate_workflow_file, workflow_name)

from . import skills as skills_registry  # noqa: F401,E402
from .skills import (AGENT_ROLES, SKILL_SCHEMA_FILENAME, SkillsError,  # noqa: F401
    agent_roles_of, agents_dir, entry_point_of, is_skill, is_step_candidate,
    legs_of, load_manifest, load_manifests, load_schema, manifest_path,
    phase_of, reads_of, registered_skills, schema_path, skill_agents,
    skill_dir, skill_legs, skills_dir, step_candidates, unreachable_agents,
    workflows_dir, writes_of)

from . import run as run_machine  # noqa: F401,E402
from .run import (RUN_STATUSES, STEP_STATUSES, STOP_REASONS,  # noqa: F401
    SUBJECT_KINDS, TERMINAL_RUN_STATUSES, abandon_run, create_run, cursor,
    derive_run_id, existing_run_ids, finish_step, in_progress_step,
    iteration_dir, iteration_of, latest_open_run, load_run, require_run,
    run_dir, run_path, save_run, start_step, step_completed, step_dir,
    step_entry, step_status, steps_dir, subject_dir)
from .run import check as check_run  # noqa: F401
from .run import load_index as load_runs_index  # noqa: F401

from . import sessions  # noqa: F401,E402
from .sessions import (checkout_dir, current_step, load_pointer,  # noqa: F401
    save_pointer, sessions_root)

from . import plan_contract  # noqa: F401,E402
from . import stepgate  # noqa: F401,E402
from .stepgate import check_inputs, check_invariants, noop_decision, settle_no_op  # noqa: F401

from . import step as step_machine  # noqa: F401,E402
from .step import (append_invocation, finalize_invocation, load_fragment,  # noqa: F401
    load_result, outcome_vocabulary, result_path, validate_result,
    write_noop_result)
from .step import empty_state, empty_state as empty_step_state  # noqa: F401
from .step import record_error, record_guard_event  # noqa: F401
from .step import load_state, save_state  # noqa: F401
from .step import last_invocation, last_status  # noqa: F401
from .step import load_state as load_step_state  # noqa: F401
from .step import save_state as save_step_state  # noqa: F401
from .step import state_path, state_path as step_state_path  # noqa: F401

from . import artifacts  # noqa: F401,E402
from .artifacts import (ARTIFACT_NAMES, MOVED_POINTER_FILENAME, TICKET_MD_FILENAME,  # noqa: F401
    artifact_path, derive_status, parse_ticket_md, render_ticket_md, ticket_docs_dir,
    ticket_docs_root, ticket_source)
from .artifacts import migrate as migrate_artifacts  # noqa: F401


def current_run_id(ctx):
    """The run this checkout is working on, from its pointer. None when it has
    none -- which is when `acs run new` is what should happen next."""
    return sessions.current_run_id(repo_dir(ctx["workspace"], ctx["repo_id"]),
                                   ctx["checkout_id"])


def point_checkout_at(ctx, run_id, step=None):
    """Record this checkout's current run (and step), so the next invocation
    resumes it without anyone typing an id."""
    return sessions.save_pointer(repo_dir(ctx["workspace"], ctx["repo_id"]),
                                 ctx["checkout_id"], run_id=run_id, step=step,
                                 checkout_path=ctx.get("checkout_root"))
