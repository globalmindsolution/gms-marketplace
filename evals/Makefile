# acs-evals — the evaluation process, as commands.
#
# `make gate` is the whole thing: run the suite, check the generated eval tree,
# write the report. Everything else is a step of it, or a tool for working on
# the dataset.
#
# This suite lives at evals/ at the root of the gms-marketplace repo, and the
# plugin source it grades lives beside it at ../plugins/acs.
#
# `make behavioural` is the other half: the real-session scenarios under
# behavioural/, which were their own top-level tree before they were folded in
# here. They are not part of `gate` — the free tier already runs on every commit
# via the acs-free-evals pre-commit hook, and the paid tier spends money.
#
# ACS_PLUGIN_ROOT selects the build under test. Leave it unset and the runner
# resolves the newest INSTALLED acs build, which is what a consumer actually
# runs; set it to point at a working tree instead. `make eval-source` is that
# second form, pre-spelled for this checkout's plugin source.
#
#   make gate ACS_PLUGIN_ROOT=$(CURDIR)/../plugins/acs

PYTHON  ?= python3
MUTANTS ?= 40
CATCH_RUNS ?= 1
WORKSPACE ?= ../.acs/state-machine/globalmindsolution-gms-marketplace
#: The plugin source this checkout carries, as `eval-source` points at it.
SOURCE  := $(CURDIR)/../plugins/acs
RESULTS ?= results
JSON    ?= $(RESULTS)/latest.json
REPORT  ?= $(RESULTS)/report
MEASURE ?= $(RESULTS)/measurements.json
#: Routing is stochastic; one run per case is a smoke test, not a rate.
ROUTING_RUNS ?= 3
ROUTING_JSON ?= $(RESULTS)/routing-cases.json
#: Each job is a full `claude` child on one credential, so they share a rate
#: limit; 4 is the point where wall-clock stops improving here. The ceiling is
#: a guard, not a budget -- at ~$0.08 a run, 40 cases x 3 runs lands near $10.
ROUTING_JOBS ?= 4
ROUTING_MAX_USD ?= 15

.DEFAULT_GOAL := help
.PHONY: help gate eval eval-source report check generate mutation list record clean verify-self \
        behavioural behavioural-paid routing-cases

help: ## Show this help
	@printf '\nacs-evals — evaluation process\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' '{printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\nBuild under test: %s\n\n' "$${ACS_PLUGIN_ROOT:-<newest installed acs>}"

gate: eval check mutation report perf ## Full local sweep against the INSTALLED build (the release gate itself is release.pre_release_gate in .acs/settings.json)
	@printf '\nRelease gate complete. Report: $(REPORT).md / $(REPORT).html\n'

gate-deterministic: eval check mutation report ## The deterministic tier only — what `gate` was before tier 3
	@printf '\nDeterministic tier complete. This says NOTHING about skill\n'
	@printf 'quality, reliability, cost or time — see docs/PERFORMANCE.md.\n'

eval: ## Run the deterministic tier (502 cases, zero cost, no model)
	$(PYTHON) runner/run_golden.py --json $(JSON)

# Point the suite at this checkout's plugin source. This does NOT change
# resolution: runner/harness.py still prefers the INSTALLED build by default,
# on purpose — packaging drift between source and installed is a defect this
# dataset exists to catch, and a source-only gate would never see it.
eval-source: ## Run the deterministic tier against this checkout's plugins/acs
	ACS_PLUGIN_ROOT=$(CURDIR)/../plugins/acs $(PYTHON) runner/run_golden.py --json $(JSON)

#: Extra flags for `measure` (e.g. MEASURE_ARGS=--force to re-measure a build
#: that already has a complete measurement on disk).
MEASURE_ARGS ?=

measure: ## TIER 3 — run the controlled scenario set (SPENDS MONEY; needs `claude`; no-op when this exact build is already measured)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/measure_skills.py --out $(MEASURE) $(MEASURE_ARGS)

measure-plan: ## What `make measure` would run, and how many sessions, spending nothing
	$(PYTHON) runner/measure_skills.py --dry-run

measure-routing: ## TIER 3, cheap half — routing reliability + controls (35 probes)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/measure_skills.py --routing-only --out $(MEASURE)

perf: ## Judge the last measurement against the baseline (pure; no model, no cost; refuses a measurement of any other build)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/perf_gate.py --measurement $(MEASURE) --json $(RESULTS)/perf.json

perf-test: ## Self-test the tier-3 comparator's decision rules
	$(PYTHON) runner/test_perf_gate.py
	$(PYTHON) runner/test_measure_skills.py
	$(PYTHON) runner/test_mutation_cli.py
	$(PYTHON) runner/test_verifier_rates.py
	$(PYTHON) runner/test_fixture_app.py
	$(PYTHON) runner/test_defects.py
	$(PYTHON) runner/test_verifier_catch_rate.py
	$(PYTHON) runner/test_baseline_identity.py
	$(PYTHON) runner/test_dataset_integrity.py
	$(PYTHON) runner/test_routing_metrics.py

REPORT_ARGS ?=

report: ## Render report.md + report.html from the last run (add REPORT_ARGS='--measurement results/measurements.json' for the per-skill section)
	$(PYTHON) runner/report.py --json $(JSON) --out $(REPORT) $(REPORT_ARGS)

fixture-selftest: ## Build the fixture app in a temp dir and run its own tests
	$(PYTHON) runner/fixture_app.py selftest

defects-selftest: ## Every seeded defect applies to a fresh fixture and leaves its suite green
	$(PYTHON) runner/defects.py selftest

catch-rate-plan: ## What `make catch-rate` would run, spending nothing
	$(PYTHON) runner/verifier_catch_rate.py --dry-run

catch-rate: ## PAID — feed every seeded defect through /acs:code and read the verifier's verdicts
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/verifier_catch_rate.py --runs $(CATCH_RUNS)

# Everything that reads or exercises the plugin, EXCEPT `eval`, resolves the
# tree being edited rather than the newest installed build.
#
# For the authoring tools (generate / check / mutation) that is about pinning
# the right schemas: with source nine merged PRs ahead of 0.4.9, five schemas
# differed and two (phases, ship-workflow) did not exist there at all, so cases
# were generated for a schema set nobody was reviewing.
#
# For the tier-3 targets (measure / measure-routing / catch-rate) it decides
# which plugin the SESSIONS load -- measure_skills passes this root to `claude
# --plugin-dir`, so the run exercises the build it names -- and for `perf` it
# names the build the measurement must be OF: the gate refuses to judge a
# measurement whose content digest is any other tree's. Before that wiring
# existed the root was printed and then dropped, and every session loaded
# whatever the operator happened to have installed: on this checkout that
# invalidated a third of routing.json, because seven probed skills did not
# exist in 0.4.9 and six negative probes asserted a guarantee its legs did not
# carry.
#
# `eval` is deliberately NOT in this list: it is the gate, and which build it
# judges is the question, not a detail. Override with ACS_PLUGIN_ROOT=... to
# point any of these at something else.
ACS_PLUGIN_ROOT ?= $(SOURCE)

check: ## Fail if any generated tree is stale against the plugin source
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/gen_plugin_eval.py --check
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/gen_schema_cases.py --check
	$(PYTHON) runner/fixture_app.py --check

generate: ## Re-render both generated trees (routing cases, schema constraint cases)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/gen_plugin_eval.py
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/gen_schema_cases.py

#: --ablation none is load-bearing, not a preference. Every grader in the
#: routing tree is `tool_used: Skill`, which the CLI auto-marks with-only: under
#: the default --ablation with-without they all become a "the plugin fired"
#: indicator and drop OUT of the score, so the run reports no routing number.
#: The default is right in general -- baseline Claude has no acs skills, so its
#: arm trivially never fires one -- and wrong for a tree where that IS the
#: measurement. --trust-plugin is the CI answer to the first-run trust prompt;
#: it grants nothing (no --scaffold, no --allow-tools), and these cases need
#: nothing: `allowed_tools: [Skill]` is the whole tool surface, and the routing
#: verdict is read off the tool call before any skill body or gate runs.
routing-cases: ## TIER 2 -- run the generated routing cases against the plugin source (~$0.08/run)
	cd .. && claude plugin eval plugins/acs --eval-dir evals 	  --case 'route-*' --runs $(ROUTING_RUNS) --ablation none 	  --trust-plugin --no-publish --json evals/$(ROUTING_JSON)

mutation-cli: ## Measure CLI-tier coverage by mutating the plugin's decision code (slow: ~10s per mutant)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/mutation_cli.py --max-mutants $(MUTANTS)

verifier-rates: ## Per-dimension verifier finding rates from an acs workspace (WORKSPACE=<workspace>/<repo_id>)
	$(PYTHON) runner/verifier_rates.py --workspace $(WORKSPACE) --json results/verifier-rates.json

#: Pass --holes (constraints nothing pins) or --inert (occurrences that
#: restrict nothing, so are not in the denominator) through to the sweep.
MUTATION_ARGS ?=

mutation: ## Measure schema coverage by deleting each constraint (must stay >= 90%)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/mutation_sweep.py --threshold 0.9 $(MUTATION_ARGS)

list: ## List every case without running anything
	$(PYTHON) runner/run_golden.py --list

# The behavioural tree at behavioural/ is the other half of this suite: real
# `claude -p` sessions asserting on the artifacts a run leaves behind, rather
# than recorded CLI surfaces. Its dispatcher takes --plugin and resolves paths
# from the repo root, hence the `cd`.
behavioural: ## Run the behavioural FREE tier (deterministic, $0, no model) against this checkout
	cd .. && ACS_EVAL_SOURCE=1 $(PYTHON) evals/behavioural/run_evals.py --plugin acs

behavioural-paid: ## The behavioural PAID tier — SPENDS MONEY; needs an authenticated `claude`
	cd .. && $(PYTHON) evals/behavioural/run_evals.py --plugin acs --paid

verify-self: ## Byte-compile the runner, parse every dataset file, self-test the gate
	$(PYTHON) -m py_compile runner/*.py
	$(PYTHON) runner/test_perf_gate.py
	$(PYTHON) runner/test_measure_skills.py
	$(PYTHON) runner/test_mutation_cli.py
	$(PYTHON) runner/test_verifier_rates.py
	$(PYTHON) runner/test_fixture_app.py
	$(PYTHON) runner/test_defects.py
	$(PYTHON) runner/test_verifier_catch_rate.py
	$(PYTHON) runner/test_baseline_identity.py
	$(PYTHON) runner/test_dataset_integrity.py
	$(PYTHON) runner/test_routing_metrics.py
	@$(PYTHON) -c "import glob,json,sys; \
	  [json.load(open(f)) for f in glob.glob('dataset/**/*.json', recursive=True)]; \
	  print('dataset: all JSON parses')"

record: ## DANGER — rewrite goldens from this build. Read the diff before committing.
	@printf 'This rewrites recorded expectations from the CURRENT build.\n'
	@printf 'Only do this when you have decided a behaviour change is intended.\n\n'
	$(PYTHON) runner/run_golden.py --record
	@printf '\nNow review EVERY line:  git diff dataset/cases/\n'

clean: ## Remove generated results and caches
	rm -rf $(RESULTS) runner/__pycache__
	find behavioural -name __pycache__ -type d -prune -exec rm -rf {} +
