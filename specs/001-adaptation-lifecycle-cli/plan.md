# Implementation Plan: Adaptation Lifecycle CLI

**Branch**: `001-adaptation-lifecycle-cli` | **Date**: 2026-03-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-adaptation-lifecycle-cli/spec.md`

## Summary

Build `adapt`, a TypeScript CLI tool that manages the full adaptation lifecycle for upstream-to-downstream development. The CLI tracks upstream repository changes, analyzes them semantically, assesses relevance, generates adaptation plans, and manages the implementation/contribution workflow. All state is git-tracked in `.adapt/` for team collaboration. MVP targets GitHub as the primary source platform with rule-based (non-AI) analysis.

## Technical Context

**Language/Version**: TypeScript 5.x on Node.js 20+
**Primary Dependencies**: commander (CLI framework), @octokit/rest (GitHub API), js-yaml (YAML), chalk (TTY colors), cli-table3 (tables), ora (spinners)
**Storage**: Text-based files - YAML for config/human-editable, JSON for machine-generated state. All git-tracked in `.adapt/`.
**Testing**: Vitest (unit + integration)
**Target Platform**: macOS, Linux (Node.js runtime)
**Project Type**: CLI tool
**Performance Goals**: All local commands < 5s (SC-007), observe < 30s for 1000 changes (SC-002)
**Constraints**: No binary databases (git-merge friendly), no stored credentials, offline-capable for non-observe commands
**Scale/Scope**: Single project tracking 1-10 upstream repos, up to hundreds of adaptations

## Constitution Check

*GATE: No constitution file found. Proceeding with standard best practices.*

No `.specify/memory/constitution.md` exists. No constitution gates to evaluate.

## Project Structure

### Documentation (this feature)

```text
specs/001-adaptation-lifecycle-cli/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: technology decisions
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: getting started guide
├── contracts/
│   └── cli-commands.md  # Phase 1: CLI command interface contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── index.ts                 # Entry point, commander setup
├── commands/
│   ├── init.ts              # adapt init
│   ├── repo.ts              # adapt repo add/list/show
│   ├── observe.ts           # adapt observe
│   ├── analyze.ts           # adapt analyze
│   ├── assess.ts            # adapt assess
│   ├── plan.ts              # adapt plan
│   ├── implement.ts         # adapt implement
│   ├── validate.ts          # adapt validate
│   ├── contribute.ts        # adapt contribute
│   ├── status.ts            # adapt status
│   ├── sync.ts              # adapt sync
│   ├── report.ts            # adapt report
│   ├── learn.ts             # adapt learn
│   ├── policy.ts            # adapt policy
│   └── profile.ts           # adapt profile
├── models/
│   ├── repository.ts        # Repository entity
│   ├── observation.ts       # Observation entity
│   ├── analysis.ts          # Analysis entity
│   ├── adaptation.ts        # Adaptation entity + state machine
│   ├── plan.ts              # Plan entity
│   ├── policy.ts            # Policy entity
│   ├── profile.ts           # Profile entity
│   └── learning.ts          # LearningRecord entity
├── services/
│   ├── github.ts            # GitHub API client (octokit wrapper)
│   ├── auth.ts              # Authentication (gh CLI + GITHUB_TOKEN)
│   ├── storage.ts           # YAML/JSON read/write for .adapt/
│   ├── classifier.ts        # Rule-based change classification
│   ├── assessor.ts          # Relevance scoring engine
│   ├── id-generator.ts      # Adaptation ID generation
│   └── output.ts            # TTY + JSON output formatting
└── lib/
    ├── config.ts            # .adapt/ config loading
    ├── errors.ts            # Custom error types
    └── utils.ts             # Shared utilities

tests/
├── unit/
│   ├── services/
│   │   ├── classifier.test.ts
│   │   ├── assessor.test.ts
│   │   ├── storage.test.ts
│   │   └── id-generator.test.ts
│   └── models/
│       └── adaptation.test.ts   # State machine transitions
├── integration/
│   ├── commands/
│   │   ├── init.test.ts
│   │   ├── repo.test.ts
│   │   ├── observe.test.ts
│   │   └── status.test.ts
│   └── workflows/
│       └── full-lifecycle.test.ts
└── fixtures/
    ├── github-responses/     # Mocked GitHub API responses
    └── sample-adapt/         # Sample .adapt/ directory state
```

**Structure Decision**: Single-project CLI layout. Commands map 1:1 to files in `src/commands/`. Domain logic lives in `src/services/` (stateless) and `src/models/` (entity definitions + validation). Storage abstracted behind `src/services/storage.ts` for consistent YAML/JSON handling.

## Complexity Tracking

No constitution violations to justify. Project follows a straightforward single-project CLI architecture.
