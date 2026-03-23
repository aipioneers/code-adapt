# code-adapt CLI

Observe. Adapt. Contribute.

A command-line tool for managing the adaptation lifecycle: observing upstream changes, analyzing and assessing them, planning adaptations, implementing changes, and contributing back upstream.

## Features

- **Observe**: Track upstream repository changes (commits, PRs, releases)
- **Analyze**: Deep analysis of specific changes with classification and intent extraction
- **Assess**: Evaluate relevance against downstream projects
- **Plan**: Generate detailed adaptation plans with strategies
- **Implement**: Create file stubs and TODO markers for adaptations
- **Validate**: Verify implemented adaptations
- **Contribute**: Prepare upstream contributions with draft PRs
- **Reporting**: Generate weekly and release activity reports
- **Learning**: Track adaptation outcomes and maintain statistics
- **Policy Management**: Define and validate adaptation policies
- **Profile Management**: Create and manage project profiles

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/aipioneers/adapt.git
cd adapt

# Install dependencies
npm install
```

### Authentication

Configure GitHub authentication:

```bash
# Option 1: Use GitHub CLI
gh auth login

# Option 2: Set environment variable
export GITHUB_TOKEN="your_token_here"
```

### Initialize a Project

```bash
code-adapt init
```

### Add Repositories

```bash
# Add upstream repository
code-adapt repo add upstream myrepo https://github.com/owner/myrepo.git

# Add downstream repository
code-adapt repo add downstream myproject https://github.com/owner/myproject.git
```

### Observe Changes

```bash
# Observe all changes since last time
code-adapt observe myrepo

# Observe changes in the last 7 days
code-adapt observe myrepo --since 7d

# Observe only pull requests
code-adapt observe myrepo --prs
```

### Analyze Changes

```bash
code-adapt analyze pr-123
code-adapt analyze commit-a1b2c3d
code-adapt analyze release-v1.0.0
```

### Assess Relevance

```bash
code-adapt assess pr-123 --against downstream-project
```

### Plan and Implement

```bash
# Generate adaptation plan
code-adapt plan adaptation-id

# Implement with dry-run first
code-adapt implement adaptation-id --dry-run

# Create implementation branch and open PR
code-adapt implement adaptation-id --branch --open-pr
```

## Project Structure

```
adapt/
├── src/
│   ├── commands/     # CLI command handlers
│   ├── services/     # Domain services (github, auth, storage)
│   ├── models/       # TypeScript interfaces and types
│   └── lib/          # Utilities and shared functions
├── tests/            # Test files
├── specs/            # Specification documents
└── .adapt/           # Runtime data directory
```

## Development

```bash
# Build TypeScript
npm run build

# Run tests
npm test

# Run tests with coverage
vitest --coverage

# Run linter
npm run lint
```

## Architecture

The code-adapt CLI follows the adaptation lifecycle pattern:

1. **Observe**: Track upstream changes through observations
2. **Analyze**: Classify and understand each change
3. **Assess**: Evaluate relevance and risk
4. **Plan**: Design implementation strategy
5. **Implement**: Apply changes to downstream project
6. **Validate**: Verify correctness
7. **Contribute**: Push changes upstream
8. **Learn**: Record outcomes and maintain statistics

## License

MIT
