# acs-evals — the evaluation process, as commands.
#
# `make gate` is the whole thing: run the suite, check the generated eval tree,
# write the report. Everything else is a step of it, or a tool for working on
# the dataset.
#
# This suite lives at src/acs-evals/ inside the gms-marketplace repo, so the
# plugin source it grades is a sibling: ../../plugins/acs.
#
# ACS_PLUGIN_ROOT selects the build under test. Leave it unset and the runner
# resolves the newest INSTALLED acs build, which is what a consumer actually
# runs; set it to point at a working tree instead. `make eval-source` is that
# second form, pre-spelled for the sibling source.
#
#   make gate ACS_PLUGIN_ROOT=$(CURDIR)/../../plugins/acs

PYTHON  ?= python3
MUTANTS ?= 40
CATCH_RUNS ?= 1
WORKSPACE ?= ../../.acs/state-machine/globalmindsolution-gms-marketplace
#: The plugin source this checkout carries, as `eval-source` points at it.
SOURCE  := $(CURDIR)/../../plugins/acs
RESULTS ?= results
JSON    ?= $(RESULTS)/latest.json
REPORT  ?= $(RESULTS)/report
MEASURE ?= $(RESULTS)/measurements.json

.DEFAULT_GOAL := help
.PHONY: help gate eval eval-source report check generate mutation list record clean verify-self

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

eval: ## Run the deterministic tier (502 cases, zero cost, no model)
	$(PYTHON) runner/run_golden.py --json $(JSON)

# Point the suite at the sibling plugin source. This does NOT change
# resolution: runner/harness.py still prefers the INSTALLED build by default,
# on purpose — packaging drift between source and installed is a defect this
# dataset exists to catch, and a source-only gate would never see it.
eval-source: ## Run the deterministic tier against this checkout's plugins/acs
	ACS_PLUGIN_ROOT=$(CURDIR)/../../plugins/acs $(PYTHON) runner/run_golden.py --json $(JSON)

measure: ## TIER 3 — run the controlled scenario set (SPENDS MONEY; needs `claude`)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/measure_skills.py --out $(MEASURE)

measure-plan: ## What `make measure` would run, and how many sessions, spending nothing
	$(PYTHON) runner/measure_skills.py --dry-run

measure-routing: ## TIER 3, cheap half — routing reliability + controls (43 probes)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/measure_skills.py --routing-only --out $(MEASURE)

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
	$(PYTHON) runner/test_baseline_identity.py

report: ## Render report.md + report.html from the last run
	$(PYTHON) runner/report.py --json $(JSON) --out $(REPORT)

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
# --plugin-dir`, so the run exercises the build it names. Before that wiring
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

mutation-cli: ## Measure CLI-tier coverage by mutating the plugin's decision code (slow: ~10s per mutant)
	$(PYTHON) runner/mutation_cli.py --max-mutants $(MUTANTS)

verifier-rates: ## Per-dimension verifier finding rates from an acs workspace (WORKSPACE=<workspace>/<repo_id>)
	$(PYTHON) runner/verifier_rates.py --workspace $(WORKSPACE) --json results/verifier-rates.json

#: Pass --holes (constraints nothing pins) or --inert (occurrences that
#: restrict nothing, so are not in the denominator) through to the sweep.
MUTATION_ARGS ?=

mutation: ## Measure schema coverage by deleting each constraint (must stay >= 90%)
	ACS_PLUGIN_ROOT=$(ACS_PLUGIN_ROOT) $(PYTHON) runner/mutation_sweep.py --threshold 0.9 $(MUTATION_ARGS)

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
	$(PYTHON) runner/test_baseline_identity.py
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
