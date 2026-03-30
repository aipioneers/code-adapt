# Contributing to code-adapt

Contributions are welcome. Whether it's a bug report, feature suggestion, or pull request — thank you for helping improve code-adapt.

## Reporting Bugs

Open an issue using the **Bug Report** template. Include steps to reproduce, expected behavior, and your environment (OS, Python version, code-adapt version).

## Suggesting Features

Open an issue using the **Feature Request** template. Describe the use case and why it matters.

## Development Setup

```bash
git clone https://github.com/aipioneers/code-adapt.git
cd code-adapt
pip install -e ".[dev]"
pytest tests/ -v
```

Requires Python 3.11+ and a GitHub token (`gh auth login` or `GITHUB_TOKEN` env var).

## Pull Requests

1. Fork the repo and create a branch from `main`
2. Write tests for new functionality
3. Run `pytest tests/ -v` and make sure everything passes
4. Open a PR with a clear description of what and why

## Code Style

- **Linter**: ruff (line length 100, target Python 3.11)
- **Types**: Pydantic v2 models for all data structures
- **Tests**: pytest with fixtures in `conftest.py`

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be kind.
