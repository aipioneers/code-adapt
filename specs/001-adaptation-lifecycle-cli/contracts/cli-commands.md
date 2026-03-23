# CLI Command Contracts: adapt

**Date**: 2026-03-23
**Feature**: 001-adaptation-lifecycle-cli

All commands support `--json` for machine-readable output and `--help` for usage info.

---

## Core Lifecycle Commands

### `adapt init`

Initialize adaptation workspace in current project.

```
adapt init [--profile <profile-name>]
```

| Flag       | Type   | Default | Description                        |
|------------|--------|---------|------------------------------------|
| --profile  | string | none    | Use a named profile template       |

**Exit codes**: 0 success, 1 already initialized (with warning), 2 error

**JSON output**:
```json
{
  "created": true,
  "path": ".adapt/",
  "files": ["config.yaml", "repos.yaml", "policies.yaml"]
}
```

---

### `adapt repo add <type> <name> <url>`

Register an upstream or downstream repository.

```
adapt repo add upstream <name> <url>
adapt repo add downstream <name> <path-or-url>
```

| Positional | Type                       | Description                    |
|------------|----------------------------|--------------------------------|
| type       | "upstream" \| "downstream" | Repository role                |
| name       | string                     | Short alias                    |
| url        | string                     | Git URL or local path          |

**Exit codes**: 0 success, 1 repo already registered, 2 URL unreachable

---

### `adapt repo list`

List all registered repositories.

```
adapt repo list [--json]
```

**JSON output**:
```json
{
  "repositories": [
    { "name": "mylib", "type": "upstream", "url": "https://...", "defaultBranch": "main" }
  ]
}
```

---

### `adapt observe <repo-name>`

Observe upstream changes.

```
adapt observe <repo-name> [--since <duration>] [--prs] [--commits] [--releases] [--json]
```

| Flag       | Type   | Default   | Description                          |
|------------|--------|-----------|--------------------------------------|
| --since    | string | last obs  | Time window (e.g., "7d", "2w", "1m") |
| --prs      | bool   | false     | Filter to PRs only                   |
| --commits  | bool   | false     | Filter to commits only               |
| --releases | bool   | false     | Filter to releases only              |

**Exit codes**: 0 changes found, 0 no changes (with message), 1 auth failure, 2 repo not found

**JSON output**:
```json
{
  "observationId": "obs_2026_001",
  "repo": "mylib",
  "since": "2026-03-16T00:00:00Z",
  "commits": [...],
  "pullRequests": [...],
  "releases": [...],
  "securityAlerts": [...]
}
```

---

### `adapt analyze <reference>`

Analyze an upstream change semantically.

```
adapt analyze <type>-<id>    # e.g., pr-1842, commit-abc123, release-v2.4.0
adapt analyze <reference> [--json]
```

| Positional | Type   | Description                                      |
|------------|--------|--------------------------------------------------|
| reference  | string | Format: `pr-<number>`, `commit-<sha>`, `release-<tag>` |

**Exit codes**: 0 success, 1 reference not found, 2 analysis failure

**JSON output**:
```json
{
  "analysisId": "ana_2026_001",
  "sourceRef": "pr-1842",
  "classification": "feature",
  "summary": "Adds request caching layer to reduce API latency",
  "intent": "Improve performance for repeated upstream requests",
  "affectedFiles": ["src/cache.ts", "src/fetch.ts"],
  "affectedModules": ["cache", "fetch"],
  "diffStats": { "additions": 142, "deletions": 23, "filesChanged": 4 }
}
```

---

### `adapt assess <reference> --against <downstream>`

Assess relevance of a change for the downstream product.

```
adapt assess <reference> --against <downstream-name> [--json]
```

| Flag      | Type   | Required | Description                    |
|-----------|--------|----------|--------------------------------|
| --against | string | yes      | Downstream repo name to assess |

**Exit codes**: 0 success, 1 no analysis found, 2 assessment failure

**JSON output**:
```json
{
  "adaptationId": "adp_2026_001",
  "sourceRef": "pr-1842",
  "relevance": "high",
  "strategicValue": "Improves caching aligned with performance priority",
  "riskScore": "low",
  "suggestedAction": "adopt"
}
```

---

### `adapt plan <adaptation-id>`

Generate an adaptation plan.

```
adapt plan <adaptation-id> [--strategy <strategy>] [--json]
```

| Flag       | Type   | Default         | Description                      |
|------------|--------|-----------------|----------------------------------|
| --strategy | string | auto-determined | direct-adoption, partial-reimplementation, improved-implementation |

**Exit codes**: 0 success, 1 adaptation not found, 2 planning failure

---

### `adapt implement <adaptation-id>`

Implement the adaptation.

```
adapt implement <adaptation-id> [--branch] [--dry-run] [--open-pr] [--json]
```

| Flag      | Type | Default | Description                        |
|-----------|------|---------|------------------------------------|
| --branch  | bool | false   | Create a git branch                |
| --dry-run | bool | false   | Show changes without applying      |
| --open-pr | bool | false   | Create internal draft PR           |

**Exit codes**: 0 success, 1 no plan found, 2 implementation failure

---

### `adapt validate <adaptation-id>`

Validate an implemented adaptation.

```
adapt validate <adaptation-id> [--branch <branch-name>] [--json]
```

| Flag     | Type   | Default        | Description                     |
|----------|--------|----------------|---------------------------------|
| --branch | string | auto-detected  | Branch to validate against      |

**Exit codes**: 0 all checks pass, 1 validation failures found, 2 error

---

### `adapt contribute <adaptation-id>`

Prepare upstream contribution.

```
adapt contribute <adaptation-id> [--split] [--draft-pr] [--json]
```

| Flag       | Type | Default | Description                         |
|------------|------|---------|-------------------------------------|
| --split    | bool | false   | Split into multiple smaller PRs     |
| --draft-pr | bool | false   | Create draft PR against upstream    |

**Exit codes**: 0 success, 1 nothing to contribute, 2 error

---

## Status & Reporting Commands

### `adapt status`

Show adaptation dashboard.

```
adapt status [--json]
```

**TTY output**: Human-readable dashboard with repos, adaptation counts by state, high-priority items.

---

### `adapt sync <repo-name>`

Show synchronization status for a specific repo.

```
adapt sync [<repo-name>] [--json]
```

---

### `adapt report <type>`

Generate reports.

```
adapt report weekly [--json]
adapt report release [--json]
adapt report upstream <repo-name> --since <duration> [--json]
```

---

## Learning Commands

### `adapt learn record <adaptation-id>`

Record adaptation outcome.

```
adapt learn record <adaptation-id> --accepted
adapt learn record <adaptation-id> --rejected [--reason <reason>]
```

### `adapt learn stats`

Show learning statistics.

```
adapt learn stats [--json]
```

---

## Configuration Commands

### `adapt policy`

```
adapt policy init
adapt policy list [--json]
adapt policy edit
adapt policy validate [--json]
```

### `adapt profile`

```
adapt profile create <name>
adapt profile inspect [--json]
adapt profile import <file>
```
