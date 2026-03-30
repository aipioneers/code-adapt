# code-adapt

Never miss an upstream change again.

[![PyPI](https://img.shields.io/pypi/v/code-adapt)](https://pypi.org/project/code-adapt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

Track upstream repositories, classify changes automatically, assess relevance against your project, generate adaptation plans, and contribute improvements back — all from the terminal.

## Quick Start

```bash
pip install code-adapt
```

```bash
# Observe upstream changes from the last 7 days
cadp observe my-upstream --since 7d

# Analyze a specific pull request
cadp analyze pr-451

# Assess relevance against your project
cadp assess pr-451 --against my-project

# Generate an adaptation plan
cadp plan adaptation-001

# Create implementation branch and open a draft PR
cadp implement adaptation-001 --branch --open-pr
```

Requires a GitHub token: `gh auth login` or `export GITHUB_TOKEN="..."`.

## The Adaptation Lifecycle

code-adapt enforces a structured lifecycle — each stage has a clear purpose, and the CLI guides you through every transition:

```
observed → analyzed → assessed → planned → implemented → validated → contributed → merged
```

Any stage can transition to `rejected`. The state machine is enforced in code — you can't skip stages or make invalid transitions.

## Features

- **Multi-provider** — GitHub, GitLab, Gitea, gitcode.com, Codeberg, and self-hosted instances
- **Auto-classification** — security fixes, bugfixes, refactors, and features sorted by regex + heuristics
- **Relevance scoring** — risk assessment against your project's modules and policies
- **Adaptation plans** — concrete strategies with implementation branches and draft PRs
- **Git-tracked state** — all data lives in `.adapt/` as YAML and JSON, no database
- **Dual output** — rich terminal tables for humans, `--json` for scripts and CI
- **Policy management** — define and validate adaptation policies
- **Learning loop** — track outcomes, improve future assessments

## Development

```bash
git clone https://github.com/aipioneers/code-adapt.git
cd code-adapt
pip install -e ".[dev]"
pytest tests/ -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[MIT](LICENSE)

---

Part of the [AI Pioneers](https://pioneers.ai) ecosystem · [code-explore](https://github.com/aipioneers/code-explore) · [spec-intelligence](https://github.com/aipioneers/spec-intelligence)
