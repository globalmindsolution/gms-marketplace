PYTHON ?= python3

test: ## Run the unit tests
	$(PYTHON) -m unittest discover -s tests -v

coverage: ## Run the tests under coverage and enforce the floor in .coveragerc
	$(PYTHON) -m coverage run -m unittest discover -s tests
	$(PYTHON) -m coverage report

.PHONY: test coverage
