# Makefile - One Task Runner Vocabulary for Agents and Humans
#
# Every language stack this template supports answers to the same seven verbs, so an
# agent never has to work out which ecosystem's commands this project uses:
#
#   make setup   make lint   make test   make docs   make verify   make push   make help
#
# `make verify` is exactly what .github/workflows/ci.yml runs. "Did I break CI?" is
# therefore one local command rather than a careful reading of the workflow file, and
# the two cannot drift apart because CI invokes this target rather than restating it.
#
# The block between the BOOTSTRAP LANGUAGE PROFILE markers is rewritten by
# `scripts/bootstrap_template.py --lang <stack>`. Everything outside the markers is
# language agnostic and is never touched by the bootstrapper. Once bootstrap has run,
# the block is yours to edit: it is your project's profile, not generated code.
#
# Requires GNU Make, which is not present on a default Windows install. See the
# "Windows" note in README.md -- Make is the accepted lowest common denominator here.

SHELL := /bin/sh
.DEFAULT_GOAL := help

PYTHON ?= python3

# pre-commit is a Python package whose console script is not always on PATH -- pip
# --user installs, a venv that is active for python but not for the shell, a CI image
# with a different bin directory. Falling back to the module invocation means `make
# lint` runs the gate instead of failing with "No such file or directory", which
# reads like a broken Makefile rather than a PATH problem. Override with
# `make lint PRE_COMMIT=/path/to/pre-commit`.
ifeq ($(origin PRE_COMMIT), undefined)
PRE_COMMIT := $(shell command -v pre-commit >/dev/null 2>&1 && echo pre-commit || echo "$(PYTHON) -m pre_commit")
endif

# Matches the check_docs_review.py thresholds used by the pre-commit hook and CI, so
# `make docs` cannot pass locally and fail in the pipeline.
DOCS_MAX_AGE_DAYS ?= 180

# Commit subject for `make push`. A make variable rather than a positional argument,
# so a forgotten message can never be filled in by the next flag on the line.
MESSAGE ?=
PUSH_ARGS ?=

.PHONY: help setup lint test docs verify push setup-tooling lint-tooling

help:
	@echo "Task runner. 'make verify' is exactly what CI runs."
	@echo ""
	@echo "  make setup   - install dev dependencies and the pre-commit git hooks"
	@echo "  make lint    - pre-commit run --all-files, plus this stack's linters"
	@echo "  make test    - this stack's non-interactive test command"
	@echo "  make docs    - refresh and verify documentation timestamp footers"
	@echo "  make verify  - lint + test + docs; the full local quality gate"
	@echo "  make push    - guarded commit-and-push (scripts/agent_push.py)"
	@echo "  make help    - this message"
	@echo ""
	@echo "Examples:"
	@echo "  make push MESSAGE=\"feat(scope): what changed\""
	@echo "  make verify DOCS_MAX_AGE_DAYS=365"

setup: setup-tooling setup-lang

setup-tooling:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PRE_COMMIT) install

lint: lint-tooling lint-lang

lint-tooling:
	$(PRE_COMMIT) run --all-files

test: test-lang

docs:
	$(PYTHON) scripts/append_timestamps.py
	$(PYTHON) scripts/check_docs_review.py --max-review-days $(DOCS_MAX_AGE_DAYS) --max-update-days $(DOCS_MAX_AGE_DAYS)

verify: lint test docs

# Guarded commit-and-push. The guards live in scripts/agent_push.py so they are
# unit-testable and work on a Windows checkout: it refuses a no-op push, refuses to
# commit while tracked files are still unstaged, rejects a flag-shaped commit message,
# and runs the pre-commit gate rather than bypassing it.
# --message=$(MESSAGE), not --message $(MESSAGE): with the separate form, a MESSAGE of
# "-m" reaches argparse as its own token and is read as another option, so the failure is
# a usage error about -m rather than the guard's explanation. The = form keeps the value
# attached whatever it looks like, so validate_commit_message() gets to reject it.
push:
	@$(PYTHON) scripts/agent_push.py --message="$(MESSAGE)" $(PUSH_ARGS)

# >>> BOOTSTRAP LANGUAGE PROFILE >>>
# --- python -------------------------------------------------------------------
PYTEST ?= $(PYTHON) -m pytest
PYTEST_ARGS ?= -v --tb=short

.PHONY: setup-lang lint-lang test-lang

setup-lang:
	@if [ -f requirements-python.txt ]; then $(PYTHON) -m pip install -r requirements-python.txt; fi

lint-lang:
	@echo "No extra Python linters configured. Add ruff / mypy to .pre-commit-config.yaml."

test-lang:
	$(PYTEST) $(PYTEST_ARGS)
# <<< BOOTSTRAP LANGUAGE PROFILE <<<
