# Contributing to rw_blueprint

Thank you for your interest in contributing. This document describes how to
set up a development environment and the standards we hold contributions to.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (the project's package and environment manager)

## Development setup

```bash
git clone <repo-url>
cd rw_blueprint
uv sync --group dev
```

`uv sync` creates the virtual environment, installs the pinned dependencies
from `uv.lock`, and installs the package in editable mode. No manual
`venv`/`pip` steps are required.

## Quality gates

Before opening a pull request, ensure the following pass:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

To auto-fix lint and formatting issues:

```bash
uv run ruff check . --fix
uv run ruff format .
```

## Commit conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Prefix your commit subject with one of: `feat`, `fix`, `docs`, `refactor`,
`test`, `chore`, `ci`.

## Pull request process

1. Open an issue describing the change (unless it is a trivial fix).
2. Branch from `main` with a descriptive name.
3. Add or update tests for any behavior change.
4. Run the quality gates above.
5. Open a PR referencing the issue.

## Code of conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).