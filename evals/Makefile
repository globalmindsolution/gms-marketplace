# acs evals — the evaluation process, as commands.
#
# The suite that grades the plugin is `claude plugin eval` cases living INSIDE
# the plugin, at ../plugins/acs/evals/, laid out the way
# https://code.claude.com/docs/en/plugin-evals specifies. This directory holds
# what renders and drives them.
#
# What used to be here and is not any more: a 355-case deterministic tier and
# its golden runner, a schema-constraint generator, mutation sweeps, a tier-3
# session measurer and its performance gate. They ran no model (the
# deterministic tier) or reimplemented what the CLI now does (routing), and
# were removed in favour of the documented format. Git history has them.
#
# `make behavioural` is the other half, and the next thing to migrate: the
# real-session scenarios under behavioural/. They are NOT part of any gate here
# — the free tier runs on every commit via the acs-free-evals pre-commit hook,
# and the paid tier spends money.

PYTHON  ?= python3
RESULTS ?= results

#: Runs per case per arm. The CLI default, and the right one: a single run of a
#: non-deterministic agent is a smoke test, not a rate.
ROUTING_RUNS ?= 3
#: Empty by default ON PURPOSE. --json makes the run QUIET -- no progress
#: lines, no summary table -- and aggregate-result.json is written to the
#: results directory either way, so passing it buys nothing interactively and
#: costs the operator every signal. Set it for an archived, scriptable copy.
ROUTING_JSON ?=
#: 1.0 is the CLI default: a case passes only if EVERY run routed as asserted,
#: and anything less exits 1. That is the right bar for a routing assertion --
#: "it routes two times in three" is a finding, not a pass.
ROUTING_THRESHOLD ?= 1.0
#: Unset uses whatever the CLI defaults to. PIN IT before recording any number
#: you intend to compare against a later run: the reference is explicit that an
#: unpinned model makes a rollout indistinguishable from a plugin regression,
#: which is exactly what this suite exists to tell apart.
ROUTING_MODEL ?=
#: Each job is a full `claude` child on one credential, so they share a rate
#: limit. The ceiling is a guard, not a budget: at ~$0.12 a run, 40 cases x 3
#: runs lands near $15. The reference is explicit that --max-cost-usd is the
#: right lever for cost, and a tight max_turns is not.
ROUTING_JOBS ?= 4
ROUTING_MAX_USD ?= 20
ROUTING_ABLATION ?= none

.DEFAULT_GOAL := help
.PHONY: help check generate routing-cases routing-cases-installed behavioural behavioural-paid verify-self clean

help: ## Show this help
	@printf '\nacs evals — evaluation process\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' '{printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'
	@printf '\n'

check: ## Fail if the generated case tree is stale against the dataset (free; runs in CI)
	$(PYTHON) runner/gen_plugin_eval.py --check

generate: ## Re-render the routing case tree from dataset/routing.json
	$(PYTHON) runner/gen_plugin_eval.py

#: --ablation none runs the with-arm only and halves the spend. It is a cost
#: choice, NOT a correctness one -- an earlier revision claimed the default
#: two-arm mode would drop every grader here out of the score, because
#: `tool_used: Skill` graders are auto-excluded from it. They are, but the rule
#: ends "if every grader in a case is one of these, they are scored normally
#: instead", and every case here has exactly one. Set ROUTING_ABLATION=with-without
#: to buy the baseline arm; for "did acs:code fire" its answer is structurally
#: zero, which is why it is not bought by default.
#:
#: --trust-plugin is the CI answer to the first-run trust prompt. It grants
#: nothing -- no --scaffold, no --allow-tools -- and these cases need nothing:
#: `allowed_tools: [Skill]` is the whole tool surface, and the routing verdict is
#: read off the tool call before any skill body or gate runs. The eval dir is not
#: passed: plugin.json sets no experimental.evals, so the default evals/ applies.
routing-cases: ## Run the generated routing cases against the plugin (~$0.12/run)
	cd .. && claude plugin eval plugins/acs \
	  --case 'route-*' --runs $(ROUTING_RUNS) --ablation $(ROUTING_ABLATION) \
	  --threshold $(ROUTING_THRESHOLD) $(if $(ROUTING_MODEL),--model $(ROUTING_MODEL)) \
	  -j $(ROUTING_JOBS) --max-cost-usd $(ROUTING_MAX_USD) \
	  --trust-plugin --no-publish $(if $(ROUTING_JSON),--json evals/$(ROUTING_JSON))

#: The SOURCE-vs-INSTALLED distinction, which the guide expresses directly: a
#: named target runs the cases in the INSTALLED copy's eval directory with the
#: installed copy loaded -- what a consumer actually executes. Until a release
#: ships plugins/acs/evals/, this correctly reports "No eval cases found":
#: that IS the packaging answer, not a failure of the command.
routing-cases-installed: ## Run the suite against the newest INSTALLED build, not this checkout
	claude plugin eval acs@gms-marketplace \
	  --case 'route-*' --runs $(ROUTING_RUNS) --ablation $(ROUTING_ABLATION) \
	  --threshold $(ROUTING_THRESHOLD) $(if $(ROUTING_MODEL),--model $(ROUTING_MODEL)) \
	  -j $(ROUTING_JOBS) --max-cost-usd $(ROUTING_MAX_USD) \
	  --trust-plugin --no-publish

behavioural: ## Run the behavioural FREE tier (deterministic, $0, no model) against this checkout
	ACS_EVAL_SOURCE=1 $(PYTHON) behavioural/run_evals.py --plugin acs

behavioural-paid: ## The behavioural PAID tier — SPENDS MONEY; needs an authenticated `claude`
	ACS_EVAL_SOURCE=1 $(PYTHON) behavioural/run_evals.py --plugin acs --paid

verify-self: ## Byte-compile the renderer and prove the case tree is current
	$(PYTHON) -m compileall -q runner/gen_plugin_eval.py
	$(PYTHON) runner/gen_plugin_eval.py --check

clean: ## Remove generated results and caches
	rm -rf $(RESULTS) ../plugins/acs/evals/results
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
