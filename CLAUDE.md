# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
pip install -e ".[dev]"              # Install in editable mode with dev deps
pytest tests/ -v                     # Run all tests
pytest tests/test_models.py -v       # Run single test file
pytest -k "test_security" -v         # Run tests matching pattern
code-adapt --help                    # CLI help (or: cadp --help)
```

GitHub auth is required for most commands: `gh auth login` or `export GITHUB_TOKEN="..."`.

## Architecture

**code-adapt** is a Python CLI (Typer + Rich) that manages an "adaptation lifecycle" — tracking upstream repo changes, assessing their relevance to a downstream project, and planning/implementing adaptations. Follows the same patterns as the sibling project [code-explore](https://github.com/aipioneers/code-explore).

### Lifecycle State Machine

```
observed → analyzed → assessed → planned → implemented → validated → contributed → merged
                                                                                    ↓
          ←─────────────────── rejected (from any stage) ──────────────────────────
```

### Layer Structure

- **`code_adapt/cli/main.py`** — Typer app. All 15 commands defined here. Global `--json` flag on each command.
- **`code_adapt/models.py`** — Pydantic models with validation. Key: `Adaptation.transition()` enforces the state machine. Enums for status, relevance, risk, strategy, classification.
- **`code_adapt/services/`** — Stateless domain services:
  - `github.py` — httpx-based GitHub REST API client (commits, PRs, releases, diffs, rate limits)
  - `auth.py` — Token resolution (`gh auth token` → `GITHUB_TOKEN` env → error)
  - `classifier.py` — Regex-based change classification (feature/bugfix/refactor/security)
  - `assessor.py` — Relevance/risk scoring, suggested action computation
  - `id_generator.py` — Sequential IDs (`obs_2026_001`) with counter in `.adapt/state/counter.json`
- **`code_adapt/storage.py`** — YAML/JSON file I/O with atomic writes (temp + rename), duration parsing, `.adapt/` directory helpers.
- **`code_adapt/errors.py`** — Custom error hierarchy with exit codes.

### Data Storage

All state lives in the `.adapt/` directory as YAML/JSON files (git-tracked, no database):
- `.adapt/repos.yaml` — registered upstream/downstream repos
- `.adapt/analyses/{id}.json` — observations and analyses
- `.adapt/adaptations/{id}/adaptation.yaml` — adaptation records
- `.adapt/adaptations/{id}/plan.yaml` — adaptation plans
- `.adapt/policies.yaml` — project policies
- `.adapt/profile.yaml` — project profile
- `.adapt/state/counter.json` — ID generation counters

## Key Conventions

- **Python 3.11+** — Hatchling build, `pyproject.toml` config
- **Pydantic v2** — All models are Pydantic `BaseModel` subclasses with validation
- **Typer + Rich** — CLI framework with rich terminal output (tables, colors, spinners)
- **httpx** — GitHub API client (no PyGithub dependency)
- **Custom error hierarchy** — `AdaptError` base with `NotInitializedError` (2), `RepoNotFoundError` (3), `AuthError` (4), `ValidationError` (5), `AdaptationNotFoundError` (6)
- **Atomic file writes** — Storage writes to temp file then renames
- **Output dual mode** — All commands support `--json` for machine-readable output
- **Tests** — pytest in `tests/`. Fixtures in `conftest.py`.
- **Entry points** — `code-adapt` (full) and `cadp` (short alias)
