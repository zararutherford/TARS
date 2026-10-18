# TARS entry points. Everything here runs locally; nothing leaves the machine.
SHELL := /bin/bash
ENGINE := engine
SWIFT := swift
DATA_DIR ?= $(or $(TARS_DATA_DIR),$(HOME)/Library/Application Support/TARS)

.PHONY: setup build run check models app sign clean

setup: ## Install Python deps, pre-commit hook, and seed tars.toml if absent
	cd $(ENGINE) && uv sync
	uvx pre-commit install
	@if [ ! -f "$(DATA_DIR)/tars.toml" ]; then \
		mkdir -p "$(DATA_DIR)"; \
		cd $(ENGINE) && uv run python -c 'from pathlib import Path; from tars import config; p=Path("$(DATA_DIR)")/"tars.toml"; config.write_example(p, config.detect_profile()); print("wrote", p)'; \
	fi

build: app sign ## Build and sign dist/TARS.app

app:
	scripts/bundle_app.sh release

sign:
	scripts/dev_sign.sh dist/TARS.app

run: build ## Launch the signed app
	open dist/TARS.app

check: ## ruff, mypy, pytest (not needs_models), swift build, endpoint check
	cd $(ENGINE) && uv run ruff format --check . && uv run ruff check .
	cd $(ENGINE) && uv run mypy
	cd $(ENGINE) && uv run pytest -q
	cd $(SWIFT) && swift build
	cd $(SWIFT) && swift test
	scripts/check_no_ai_endpoints.sh

models: ## Download local models (M0)
	@echo "scripts/download_models.sh arrives in M0"

clean:
	rm -rf dist $(SWIFT)/.build
