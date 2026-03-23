# Quickstart: adapt CLI

## Install

```bash
npm install -g adapt-cli
```

Or use without installing:

```bash
npx adapt-cli <command>
```

## Prerequisites

- Node.js 20+
- Git
- GitHub CLI (`gh`) authenticated, **or** `GITHUB_TOKEN` environment variable set

## First Adaptation in 5 Minutes

### 1. Initialize your project

```bash
cd your-project
adapt init
```

### 2. Register repositories

```bash
# Add the upstream repo you want to track
adapt repo add upstream mylib https://github.com/org/mylib

# Register your project as downstream
adapt repo add downstream myproduct .
```

### 3. Observe upstream changes

```bash
adapt observe mylib --since 7d
```

### 4. Analyze an interesting change

```bash
adapt analyze pr-1842
```

### 5. Assess relevance

```bash
adapt assess pr-1842 --against myproduct
```

### 6. Check status

```bash
adapt status
```

## What's Next

- `adapt plan <adaptation-id>` to create an implementation plan
- `adapt implement <adaptation-id> --branch` to generate code changes
- `adapt validate <adaptation-id>` to run quality checks
- `adapt contribute <adaptation-id> --draft-pr` to give back to upstream

## Configuration

All state lives in `.adapt/` (git-tracked, shared with your team):

```
.adapt/
├── config.yaml       # CLI settings
├── repos.yaml        # Tracked repositories
├── policies.yaml     # Governance rules
├── profile.yaml      # Your product profile
├── analyses/         # Observations & analyses
├── adaptations/      # Adaptation lifecycle state
└── reports/          # Generated reports & learnings
```

## CI/CD Integration

All commands support `--json` for machine-readable output:

```bash
adapt observe mylib --since 1d --json | jq '.pullRequests | length'
adapt status --json
```
