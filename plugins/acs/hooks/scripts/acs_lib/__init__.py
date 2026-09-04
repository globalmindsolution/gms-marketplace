"""acs_lib — the deterministic kernel behind every acs hook and helper CLI.

MAR-522 split the 2,989-line module into eight domain modules; this facade
re-exports their public surface, so `import acs_lib as lib` resolves every name
it always did. In dependency order:

  _common        json/time/path primitives, the skill registry, GateError
  settings       .acs settings load/validate/merge, model and format resolution
  repo           git and checkout identity, workspace layout, ticket-id resolution
  lanes          lane/axis derivation and the plan-approval predicate
  state          run ledgers, pipeline state, tickets, index, counters, locking
  metrics        token/cost apportionment and the metrics ledger
  setup_helpers  CLAUDE.md managed block, toolchain probing, exempt-PR classifier
  gates          context resolution, the pre-hook gates, post-hook persistence
  verdict        the verifier's verdict document and its derived-pass rule
  derive         the result-document fields the kernel computes from artifacts
  lifecycle      the SubagentStart/SubagentStop/Stop/PreCompact hook bodies

PATCHING: a name imported into a sibling binds at import time, so patching it on
this facade does NOT reach a caller that already imported it. Patch the module
that USES it -- `mock.patch.object(lib.state, "write_json")` -- or, for a stdlib
module (`lib.subprocess`), patch the shared module object as before.
"""

from . import (_common, settings, repo, lanes, state, metrics, setup_helpers,  # noqa: F401
               verdict, derive, gates, lifecycle)  # noqa: F401

from ._common import (ATTRIBUTION_SKILL_MAP, DELIVERY_TICKET_SKILLS,
    DELIVERY_TICKET_TITLES, DOC_BOOTSTRAP_DEPENDENCIES, DOC_BOOTSTRAP_FANOUT_V1,
    DOC_BOOTSTRAP_SENTINEL, DOC_BOOTSTRAP_SETTINGS_KEY, GateError, HOOKED_SKILLS,
    PIPELINE_STEP_ORDER, PLANNING_SKILLS, PRIORITIES, PRODUCT_SKILLS,
    PRODUCT_TICKET_TITLES, RUN_STATUSES, ReconciliationRequired, TICKET_ID_RE,
    TICKET_STATUSES, TICKET_TYPES, UNHOOKED_SKILLS, WORKFLOW_SKILLS, _ISO_INSTANT,
    _git, deep_merge, now_iso, parse_iso, plugin_root, read_json, slugify, write_json)  # noqa: F401

from .settings import (BUILTIN_TEMPLATES, DEFAULT_SETTINGS, ENFORCEMENT_DEFAULTS,
    FORMAT_PLACEHOLDERS, MODEL_EFFORTS, MODEL_OVERRIDE_SKILLS, MODEL_ROLES,
    RECOMMENDED_MODELS, _model_override_skills, _normalize_e2e_into_suites,
    enforcement_value, load_settings, render_format, resolve_role_model,
    resolve_template, settings_files, validate_formats, validate_models,
    validate_settings)  # noqa: F401

from .repo import (GH_ACCESS_DENIED_MARKER, GH_ACCESS_HINT, GH_GENERIC_HINT,
    _EVIDENCE_RANKS, _evidence_source_commands, _guarded_repo_write, archive_dir,
    checkout_id, checkout_root, current_branch, default_state_root,
    find_ticket_partition, gh_failure_hint, index_path, lock_path, main_repo_root,
    pointer_path, record_session_marker, repo_dir, repo_partition_id,
    resolve_ticket_id, scan_local_ticket_evidence, session_marker_path, sessions_dir,
    state_path, ticket_dir, ticket_id_from_text)  # noqa: F401

from .lanes import (LANE_ORDER, PLAN_FOLD_CLAUSES, PLAN_FOLD_SECTIONS,
    PLAN_REQUIRED_SECTIONS, VERIFY_ITERATION_CAP, _PLAN_HEADING_RE, _SIZE_ORDER,
    _STAKES_ORDER, _coverage_target_stated, _plan_headings, classify_additive_diff,
    derive_lane, escalate_lane, guard_axes, lane_rank, plan_approval_eligible,
    recommend_stakes, verify_depth)  # noqa: F401

from .state import (acquire_lock, allocate_ticket_id, append_in_progress_run,
    check_lock, confirm_deescalation, empty_state, finalize_run, last_run,
    last_run_status, load_pipeline, load_state, load_ticket, lock_is_stale,
    new_ticket_doc, read_lock, record_escalation_event, release_lock, save_ticket,
    skill_completed, update_index, update_pipeline)  # noqa: F401

from .metrics import (_EMPTY_MEASURED_TOKENS, _TOKEN_TOTAL_FIELDS, _measure_run_usage,
    _sum_role_tokens, _update_metrics_body, backfill_distinct_pr_count,
    compute_ticket_totals, elapsed_seconds, metrics_path, run_seconds, update_metrics)  # noqa: F401

from .setup_helpers import (ACS_BLOCK_BEGIN, ACS_BLOCK_END, TOOLCHAIN, _BARE_INT_RE,
    _FANOUT_FOR_RE, _PR_FLAG_RE, _PR_HASH_RE, _PR_URL_RE, _managed_body, _pr_labels,
    _soft_peers, _strip_stray_markers, _tool_version, check_toolchain,
    classify_merge_pr_arg, doc_set_present_on_disk, fanout_batches,
    managed_block_is_malformed, managed_body_from_template, missing_tools,
    parse_fanout_for_arg, render_managed_block, tracker_cli_warning,
    upsert_managed_block, validate_exempt_pr)  # noqa: F401

from .gates import (ARCHITECTURE_DEPENDENT_SKILLS,GATES, _archive_partition, _clear_pointers_for_ticket,
    _epic_auto_done, _merge_pr_arg_text, _read_result_from_argv,
    _require_architecture_doc_set, _require_completed, _resolve_ticket_for_gate,
    build_context, design_requirement, gate_code, gate_create_architecture,
    gate_create_design, gate_create_operations, gate_create_pr, gate_create_prd,
    gate_create_principles, gate_create_project, gate_create_quality,
    gate_create_requirements, gate_create_standards, gate_create_ticket,
    gate_docs_sync, gate_merge_pr, gate_standardize_project, parent_epic_dir, run_post,
    run_post_exempt_pr, run_pre, run_pre_payload, session_end)  # noqa: F401

# Re-exported so `lib.subprocess` / `lib.os` keep resolving: patching
# `acs_lib.subprocess.run` patches the shared module object every submodule sees.
from ._common import (cc, datetime, fnmatch, hashlib, json, os, re, shutil, socket,
    subprocess, sys, tempfile, timedelta, timezone)  # noqa: F401

from .lifecycle import (ACTIVE_AGENTS_FILENAME, BLOCK_LIMIT, HANDOFF_CONTEXT_FILENAME,
    ROLE_PHASES, active_agents_path, clear_agent, clear_stop_blocks, count_agent_stop_attempt,
    count_stop_block, extract_message, in_flight_skill, parse_agent_type, phase_artifact_path,
    pre_compact, read_agent, record_agent_start, render_handoff_context, resolve_partition,
    result_document, subagent_start, subagent_stop, write_handoff_context,
    write_phase_snapshot)  # noqa: F401
from .lifecycle import stop as stop_hook  # noqa: F401

from .verdict import (DIMENSION_RESULTS, LENSES, SEVERITIES, VERDICT_DIMENSIONS,
    blocking_findings, derived_passed, load_verdict, merge_lens_verdicts,
    validate_verdict, verdict_filename, verdict_path, write_verdict)  # noqa: F401

from .derive import (DERIVED_KEYS, VERDICT_SKILLS, derive_states, derive_tests,
    derive_verifier_passed, disagreements, execute_reports, gh_pr_for_branch,
    latest_verdict, review_iterations)  # noqa: F401
