VENV_DIR := .venv
PYTHON ?= python
HATCH ?= hatch
ifeq ($(CI),)
RUN := $(HATCH) run python
else
RUN := $(PYTHON)
endif
DEMO_TAPE := demo/doctor-demo.tape
DEMO_IMAGE := azure-functions-doctor-demo-vhs
DEMO_GIF := docs/assets/doctor-demo.gif
DEMO_FINAL_PNG := docs/assets/doctor-demo-final.png
VERSIONED_DOCS := README.md llms.txt llms-full.txt docs/deployment.md

.PHONY: bootstrap
bootstrap:
	@command -v $(HATCH) >/dev/null || { echo "Install Hatch once in an isolated tool environment"; exit 1; }

.PHONY: ensure-hatch
ensure-hatch: bootstrap

.PHONY: install
install: ensure-hatch
	@$(HATCH) env create
	@if [ -n "$$CI" ]; then \
		echo "CI detected: skipping pre-commit hook installation"; \
	else \
		$(MAKE) precommit-install; \
	fi

.PHONY: install-ci
install-ci:
	@$(PYTHON) -m pip install -e ".[dev,docs]"

.PHONY: shell
shell: ensure-hatch
	@$(HATCH) shell

.PHONY: reset
reset: clean-all install
	@echo "Project reset complete."

.PHONY: hatch-clean
hatch-clean: ensure-hatch
	@$(HATCH) env remove || echo "No hatch environment to remove"

.PHONY: format
format:
	@$(RUN) -m ruff format src tests tools/verification*.py

.PHONY: format-check
format-check:
	@$(RUN) -m ruff format --check src tests tools/verification*.py

.PHONY: style
style: format-check
	@$(RUN) -m ruff check src tests tools/verification*.py

.PHONY: typecheck
typecheck:
	@$(RUN) -m mypy src tests tools/verification*.py

.PHONY: lint
lint: style typecheck

.PHONY: security
security:
	@$(RUN) -m bandit -r src

.PHONY: check
check: style typecheck security lint-workflows
	@$(RUN) scripts/lint_mermaid.py
	@$(RUN) scripts/gen_rule_inventory.py --check
	@$(RUN) scripts/check_docs_consistency.py

.PHONY: lint-workflows
lint-workflows:
	@$(RUN) tools/lint_release_workflows.py
	@$(RUN) tools/lint_workflow_pins.py
	@$(RUN) tools/lint_hatch_matrix.py

.PHONY: check-all
check-all: verify

.PHONY: integration verify report host-smoke cli-smoke wheel-smoke
integration verify report host-smoke:
	@$(RUN) -m tools.verification $@

cli-smoke:
	@$(RUN) -m tools.verification_cli

wheel-smoke:
	@$(RUN) -m tools.verification_wheel

.PHONY: precommit
precommit: ensure-hatch
	@$(HATCH) run precommit

.PHONY: precommit-install
precommit-install: ensure-hatch
	@$(HATCH) run precommit-install

.PHONY: test
test:
	@$(RUN) -m tools.verification test

.PHONY: cov
cov: ensure-hatch
	@$(HATCH) run cov
	@echo "Open htmlcov/index.html in your browser to view the coverage report."
	@echo "coverage.xml generated for Codecov upload."

.PHONY: e2e-local
e2e-local:
	@E2E_BASE_URL=http://localhost:7071 E2E_EXPECTED_VERSION=$${E2E_EXPECTED_VERSION:-$$($(HATCH) version)} $(RUN) -m tools.verification local-e2e

.PHONY: e2e-azure
e2e-azure:
	@$(RUN) -m tools.verification azure-e2e

.PHONY: build
build:
	@$(RUN) -m tools.verification focused build -m build --no-isolation

.PHONY: publish-test
publish-test: ensure-hatch
	@$(HATCH) publish --repo test

.PHONY: sync-docs-version
sync-docs-version: ensure-hatch
	@$(HATCH) run python scripts/sync_docs_version.py

.PHONY: version
version: ensure-hatch
	@echo "Current version:"
	@$(HATCH) version

.PHONY: docs
docs:
	@$(RUN) -m tools.verification focused docs -m mkdocs build --strict

.PHONY: docs-serve
docs-serve: ensure-hatch
	@$(HATCH) run docs

.PHONY: demo
demo: demo-image
	@mkdir -p docs/assets
	@docker run --rm -v "$(CURDIR):/workspace" -w /workspace $(DEMO_IMAGE) $(DEMO_TAPE)
	@TMP_DIR=$$(mktemp -d); \
	ffmpeg -y -i $(DEMO_GIF) $$TMP_DIR/frame%03d.png >/dev/null 2>&1; \
	cp "$$TMP_DIR/$$(ls $$TMP_DIR | sort | tail -n 1)" $(DEMO_FINAL_PNG); \
	rm -rf $$TMP_DIR

.PHONY: demo-image
demo-image:
	@docker build -t $(DEMO_IMAGE) -f demo/Dockerfile.vhs .

.PHONY: doctor
doctor:
	@if [ -n "$$CI" ]; then $(PYTHON) -m tools.verification doctor; \
	else environment=$$($(HATCH) env find) && test -x "$$environment/bin/python" && \
	PATH="$$environment/bin:$$PATH" "$$environment/bin/python" -m tools.verification doctor; fi

.PHONY: clean
clean:
	@$(RUN) -m tools.verification clean

.PHONY: clean-all
clean-all: clean
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	@rm -rf .DS_Store $(VENV_DIR)

.PHONY: help
help:
	@echo "Canonical: install install-ci doctor format format-check check test integration verify e2e-azure report clean"
	@echo "doctor: developer prerequisites only; product CLI: azure-functions-doctor doctor"
	@echo "check-all: exact alias of verify; requires func and Azurite"
	@echo "Focused/partial: lint style typecheck security lint-workflows cov cli-smoke wheel-smoke host-smoke build docs e2e-local"
	@echo "Maintenance: bootstrap ensure-hatch shell reset hatch-clean clean-all precommit precommit-install publish-test sync-docs-version version docs-serve demo demo-image"
