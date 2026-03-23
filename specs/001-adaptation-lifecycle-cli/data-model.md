# Data Model: Adaptation Lifecycle CLI

**Date**: 2026-03-23
**Feature**: 001-adaptation-lifecycle-cli

## Entities

### Repository

Tracked upstream or downstream git repository.

| Field         | Type                       | Required | Description                                |
|---------------|----------------------------|----------|--------------------------------------------|
| name          | string                     | yes      | Short alias (e.g., "mylib")                |
| url           | string                     | yes      | Git remote URL                             |
| type          | "upstream" \| "downstream" | yes      | Role in adaptation relationship            |
| defaultBranch | string                     | yes      | Auto-detected (e.g., "main")              |
| license       | string \| null             | no       | Detected license identifier (SPDX)        |
| techStack     | string[]                   | no       | Detected languages/frameworks              |
| addedAt       | ISO 8601 datetime          | yes      | When the repo was registered               |

**Identity**: Unique by `name` within a project.
**Storage**: `.adapt/repos.yaml`

---

### Observation

Snapshot of upstream changes at a point in time.

| Field       | Type                  | Required | Description                                  |
|-------------|-----------------------|----------|----------------------------------------------|
| id          | string                | yes      | Auto-generated (e.g., "obs_2026_001")        |
| repoName    | string                | yes      | Reference to Repository.name                 |
| timestamp   | ISO 8601 datetime     | yes      | When observation was performed               |
| since       | ISO 8601 datetime     | no       | Start of observation window                  |
| commits     | CommitSummary[]       | yes      | New commits found                            |
| pullRequests| PRSummary[]           | yes      | New/updated PRs found                        |
| releases    | ReleaseSummary[]      | yes      | New tags/releases found                      |
| securityAlerts | SecurityAlert[]    | no       | Security-relevant changes                    |

**Identity**: Unique by `id`.
**Storage**: `.adapt/analyses/{id}.json`

#### CommitSummary

| Field   | Type   | Description              |
|---------|--------|--------------------------|
| sha     | string | Commit hash              |
| message | string | First line of commit msg |
| author  | string | Author name              |
| date    | string | Commit date (ISO 8601)   |

#### PRSummary

| Field  | Type   | Description            |
|--------|--------|------------------------|
| number | number | PR number              |
| title  | string | PR title               |
| state  | string | open/closed/merged     |
| author | string | PR author              |
| url    | string | PR URL                 |

#### ReleaseSummary

| Field   | Type   | Description            |
|---------|--------|------------------------|
| tag     | string | Release tag name       |
| name    | string | Release title          |
| date    | string | Publish date           |
| url     | string | Release URL            |

#### SecurityAlert

| Field    | Type   | Description              |
|----------|--------|--------------------------|
| id       | string | Alert identifier         |
| severity | string | critical/high/medium/low |
| summary  | string | Brief description        |

---

### Analysis

Semantic breakdown of an upstream change.

| Field           | Type                                            | Required | Description                                   |
|-----------------|-------------------------------------------------|----------|-----------------------------------------------|
| id              | string                                          | yes      | Auto-generated (e.g., "ana_2026_001")         |
| observationId   | string                                          | no       | Link to source Observation                    |
| sourceRef       | string                                          | yes      | Upstream reference (e.g., "pr-1842")          |
| sourceRefType   | "pr" \| "commit" \| "release"                   | yes      | Type of upstream reference                    |
| repoName        | string                                          | yes      | Source repository name                        |
| summary         | string                                          | yes      | Human-readable summary of the change          |
| classification  | "feature" \| "bugfix" \| "refactor" \| "security" \| "unknown" | yes | Change type classification      |
| intent          | string                                          | yes      | Extracted purpose/goal of the change          |
| affectedFiles   | string[]                                        | yes      | List of changed file paths                    |
| affectedModules | string[]                                        | no       | Higher-level module grouping                  |
| diffStats       | DiffStats                                       | yes      | Quantitative diff metrics                     |
| createdAt       | ISO 8601 datetime                               | yes      | When analysis was performed                   |

**Identity**: Unique by `id`.
**Storage**: `.adapt/analyses/{id}.json`

#### DiffStats

| Field     | Type   | Description           |
|-----------|--------|-----------------------|
| additions | number | Lines added           |
| deletions | number | Lines removed         |
| filesChanged | number | Number of files changed |

---

### Adaptation

Core lifecycle entity. One per upstream reference.

| Field          | Type                                                                                                       | Required | Description                                    |
|----------------|------------------------------------------------------------------------------------------------------------|----------|------------------------------------------------|
| id             | string                                                                                                     | yes      | Format: "adp_{year}_{seq}" (e.g., "adp_2026_001") |
| sourceRepo     | string                                                                                                     | yes      | Upstream repository name                       |
| sourceRef      | string                                                                                                     | yes      | Upstream reference (e.g., "pr-1842")           |
| sourceRefType  | "pr" \| "commit" \| "release"                                                                              | yes      | Type of upstream reference                     |
| analysisId     | string                                                                                                     | no       | Link to Analysis                               |
| status         | "observed" \| "analyzed" \| "assessed" \| "planned" \| "implemented" \| "validated" \| "contributed" \| "merged" \| "rejected" | yes | Current lifecycle state                        |
| relevance      | "high" \| "medium" \| "low" \| null                                                                       | no       | Assessment result                              |
| riskScore      | "high" \| "medium" \| "low" \| null                                                                       | no       | Risk assessment                                |
| suggestedAction| "adopt" \| "ignore" \| "monitor" \| "adapt-partially" \| null                                              | no       | Recommended action from assessment             |
| strategy       | "direct-adoption" \| "partial-reimplementation" \| "improved-implementation" \| null                       | no       | Chosen adaptation strategy                     |
| targetModules  | string[]                                                                                                   | no       | Downstream modules affected                    |
| planId         | string \| null                                                                                             | no       | Link to Plan                                   |
| branch         | string \| null                                                                                             | no       | Implementation git branch name                 |
| createdAt      | ISO 8601 datetime                                                                                          | yes      | When adaptation was created                    |
| updatedAt      | ISO 8601 datetime                                                                                          | yes      | Last status change                             |

**Identity**: Unique by `id`. Sequential counter stored in `.adapt/state/counter.json`.
**Storage**: `.adapt/adaptations/{id}.yaml`

**State Transitions**:

```
observed → analyzed → assessed → planned → implemented → validated → contributed → merged
                         ↓           ↓          ↓             ↓            ↓
                      rejected    rejected   rejected      rejected    rejected
```

Transitions are generally forward-only. `rejected` is a terminal state reachable from any active state. Steps can be skipped (e.g., observed → planned for known patterns).

---

### Plan

Structured adaptation plan.

| Field              | Type     | Required | Description                               |
|--------------------|----------|----------|-------------------------------------------|
| id                 | string   | yes      | Format: "plan_{adp_id}" (e.g., "plan_adp_2026_001") |
| adaptationId       | string   | yes      | Parent adaptation ID                      |
| strategy           | string   | yes      | Selected strategy                         |
| targetModules      | string[] | yes      | Downstream modules to modify              |
| steps              | PlanStep[] | yes    | Ordered implementation steps              |
| dependencies       | string[] | no       | External dependencies or prerequisites    |
| suggestedTests     | string[] | no       | Tests to add/modify                       |
| contributionSplit  | ContributionSplit | no | Upstream vs internal breakdown           |
| createdAt          | ISO 8601 datetime | yes | When plan was generated                 |

**Storage**: `.adapt/adaptations/{adaptation_id}/plan.yaml`

#### PlanStep

| Field       | Type   | Description                    |
|-------------|--------|--------------------------------|
| order       | number | Step sequence number           |
| description | string | What to do                     |
| targetFile  | string | File to modify (if applicable) |
| type        | string | create/modify/delete/test      |

#### ContributionSplit

| Field      | Type     | Description                         |
|------------|----------|-------------------------------------|
| upstream   | string[] | Files/changes suitable for upstream |
| internal   | string[] | Files/changes that stay internal    |

---

### Policy

Governance rules.

| Field              | Type     | Required | Description                                |
|--------------------|----------|----------|--------------------------------------------|
| relevantModules    | string[] | no       | Module patterns to prioritize              |
| ignoredModules     | string[] | no       | Module patterns to skip                    |
| criticalLicenses   | string[] | no       | License types requiring manual review      |
| protectedPaths     | string[] | no       | Paths that must not be auto-modified       |
| contributionRules  | ContributionRules | no | Rules for upstream contributions       |
| autoAssessThreshold| string   | no       | Minimum relevance for auto-adaptation      |

**Storage**: `.adapt/policies.yaml`

#### ContributionRules

| Field            | Type    | Description                             |
|------------------|---------|-----------------------------------------|
| enabled          | boolean | Whether contribution is allowed         |
| requireReview    | boolean | Require manual review before submitting |
| excludePatterns  | string[]| File patterns never to contribute       |

---

### Profile

Downstream product description.

| Field          | Type     | Required | Description                              |
|----------------|----------|----------|------------------------------------------|
| name           | string   | yes      | Product/project name                     |
| stack          | string[] | no       | Technology stack                         |
| architecture   | string   | no       | Architecture style description           |
| conventions    | string[] | no       | Coding conventions                       |
| criticalModules| string[] | no       | Modules with highest priority            |
| priorities     | string[] | no       | Product priorities (e.g., "performance") |

**Storage**: `.adapt/profile.yaml`

---

### LearningRecord

Feedback on completed adaptations.

| Field        | Type                        | Required | Description                        |
|--------------|-----------------------------|----------|------------------------------------|
| adaptationId | string                      | yes      | Reference to Adaptation.id         |
| outcome      | "accepted" \| "rejected"    | yes      | Final outcome                      |
| reason       | string \| null              | no       | Rejection reason or acceptance note|
| recordedAt   | ISO 8601 datetime           | yes      | When feedback was recorded         |

**Storage**: `.adapt/reports/learnings.yaml` (append-only list)

---

## Storage Layout

```
.adapt/
├── config.yaml              # Global CLI config
├── repos.yaml               # Repository (list)
├── policies.yaml            # Policy
├── profile.yaml             # Profile
├── state/
│   └── counter.json         # ID sequence counters
├── cache/                   # Temporary API response cache (gitignored optional)
├── context/                 # Imported architecture docs
├── analyses/
│   ├── obs_2026_001.json    # Observation
│   └── ana_2026_001.json    # Analysis
├── adaptations/
│   └── adp_2026_001/
│       ├── adaptation.yaml  # Adaptation entity
│       └── plan.yaml        # Plan (if generated)
├── reports/
│   ├── learnings.yaml       # LearningRecord (append-only)
│   └── weekly_2026_12.md    # Generated reports
└── logs/                    # CLI operation logs
```
