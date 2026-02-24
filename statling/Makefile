# Makefile for Statling development

.PHONY: help install dev-install format format-ruff format-trad lint lint-ruff lint-trad type-check test clean build all check

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package
	pip install .

dev-install:  ## Install package with development dependencies
	pip install -e '.[dev]'

format-ruff:  ## Format code with Ruff (fast)
	ruff format .
	ruff check --fix .

format-trad:  ## Format code with Black and isort
	black .
	isort .

format: format-ruff  ## Format code (uses Ruff by default)

lint-ruff:  ## Lint with Ruff (fast)
	ruff check .

lint-trad:  ## Lint with Flake8
	flake8 .

lint: lint-ruff  ## Lint code (uses Ruff by default)

type-check:  ## Run type checking with mypy
	mypy .

test:  ## Run tests with pytest
	pytest -v

check-ruff:  ## Run all checks with Ruff and mypy (fast)
	ruff format --check .
	ruff check .
	mypy .

check-trad:  ## Run all checks with traditional tools
	black --check .
	isort --check-only .
	flake8 .
	mypy .

check: check-ruff  ## Run all checks (uses Ruff by default)

all: format lint type-check test  ## Format, lint, type-check, and test

clean:  ## Clean build artifacts and caches
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete

build:  ## Build distribution packages
	python -m build

render-test:  ## Render test character sheet
	statling ../characters/2014_elowen_turnerleaf.yaml -o output/test.md
	@echo "Character sheet rendered to output/test.md"
