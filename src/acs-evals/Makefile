# acs-evals — the evaluation process, as commands.
#
# `make gate` is the whole thing: run the suite, check the generated eval tree,
# write the report. Everything else is a step of it, or a tool for working on
# the dataset.
#
# ACS_PLUGIN_ROOT selects the build under test. Leave it unset and the runner
# resolves the newest INSTALLED acs build, which is what a consumer actually
# runs; set it to point at a working tree instead.
#
#   make gate ACS_PLUGIN_ROOT=~/src/gms-marketplace/plugins/acs

PYTHON  ?= python3
MUTANTS ?= 40
CATCH_RUNS ?= 1
WORKSPACE ?= ../gms-marketplace/.acs/state-machine/globalmindsolution-gms-marketplace
RESULTS ?= results
JSON    ?= $(RESULTS)/latest.json
REPORT  ?= $(RESULTS)/report
MEASURE ?= $(RESULTS)/measurements.json

.DEFAULT_GOAL := help
.PHONY: help gate eval report check generate mutation list record clean verify-self

help: ## Show this help
	@printf '\nacs-evals — evaluation process\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' '{printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\nBuild under test: %s\n\n' "$${ACS_PLUGIN_ROOT:-<newest installed acs>}"

gate: eval check mutation report perf ## THE RELEASE GATE — run everything, fail on any red
	@printf '\nRelease gate complete. Report: $(REPORT).md / $(REPORT).html\n'

gate-deterministic: eval check mutation report ## The deterministic tier only — what `gate` was before tier 3
	@printf '\nDeterministic tier complete. This says NOTHING about skill\n'
	@printf 'quality, reliability, cost or time — see docs/PERFORMANCE.md.\n'

eval: ## Run the deterministic tier (356 cases, zero cost, no model)
	$(PYTHON) runner/run_golden.py --json $(JSON)

measure: ## TIER 3 — run the controlled scenario set (SPENDS MONEY; needs `claude`)
	$(PYTHON) runner/measure_skills.py --out $(MEASURE)

measure-plan: ## What `make measure` would run, and how many sessions, spending nothing
	$(PYTHON) runner/measure_skills.py --dry-run

measure-routing: ## TIER 3, cheap half — routing reliability + controls (30 probes)
	$(PYTHON) runner/measure_skills.py --routing-only --out $(MEASURE)

perf: ## Judge the last measurement against the baseline (pure; no model, no cost)
	$(PYTHON) runner/perf_gate.py --measurement $(MEASURE) --json $(RESULTS)/perf.json

perf-test: ## Self-test the tier-3 comparator's decision rules
	$(PYTHON) runner/test_perf_gate.py
	$(PYTHON) runner/test_measure_skills.py
	$(PYTHON) runner/test_mutation_cli.py
	$(PYTHON) runner/test_verifier_rates.py
	$(PYTHON) runner/test_fixture_app.py
	$(PYTHON) runner/test_defects.py
	$(PYTHON) runner/test_verifier_catch_rate.py

report: ## Render report.md + report.html from the last run
	$(PYTHON) runner/report.py --json $(JSON) --out $(REPORT)

fixture-selftest: ## Build the fixture app in a temp dir and run its own tests
	$(PYTHON) runner/fixture_app.py selftest

defects-selftest: ## Every seeded defect applies to a fresh fixture and leaves its suite green
	$(PYTHON) runner/defects.py selftest

catch-rate-plan: ## What `make catch-rate` would run, spending nothing
	$(PYTHON) runner/verifier_catch_rate.py --dry-run

catch-rate: ## PAID — feed every seeded defect through /acs:code and read the verifier's verdicts
	$(PYTHON) runner/verifier_catch_rate.py --runs $(CATCH_RUNS)

check: ## Fail if any generated tree is stale against its source
	$(PYTHON) runner/gen_plugin_eval.py --check
	$(PYTHON) runner/gen_schema_cases.py --check
	$(PYTHON) runner/fixture_app.py --check

generate: ## Re-render both generated trees (routing cases, schema constraint cases)
	$(PYTHON) runner/gen_plugin_eval.py
	$(PYTHON) runner/gen_schema_cases.py

mutation-cli: ## Measure CLI-tier coverage by mutating the plugin's decision code (slow: ~10s per mutant)
	$(PYTHON) runner/mutation_cli.py --max-mutants $(MUTANTS)

verifier-rates: ## Per-dimension verifier finding rates from an acs workspace (WORKSPACE=<workspace>/<repo_id>)
	$(PYTHON) runner/verifier_rates.py --workspace $(WORKSPACE) --json results/verifier-rates.json

mutation: ## Measure schema coverage by deleting each constraint (must stay >= 50%)
	$(PYTHON) runner/mutation_sweep.py --threshold 0.5

list: ## List every case without running anything
	$(PYTHON) runner/run_golden.py --list

verify-self: ## Byte-compile the runner, parse every dataset file, self-test the gate
	$(PYTHON) -m py_compile runner/*.py
	$(PYTHON) runner/test_perf_gate.py
	$(PYTHON) runner/test_measure_skills.py
	$(PYTHON) runner/test_mutation_cli.py
	$(PYTHON) runner/test_verifier_rates.py
	$(PYTHON) runner/test_fixture_app.py
	$(PYTHON) runner/test_defects.py
	$(PYTHON) runner/test_verifier_catch_rate.py
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
