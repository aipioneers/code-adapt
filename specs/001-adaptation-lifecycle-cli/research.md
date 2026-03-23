# Research: Adaptation Lifecycle CLI

**Date**: 2026-03-23
**Feature**: 001-adaptation-lifecycle-cli

## R1: Language & Runtime

**Decision**: TypeScript on Node.js

**Rationale**: CLI tools in the developer tooling space benefit from npm/npx distribution, rich GitHub ecosystem (`@octokit/rest`), native JSON/YAML handling, and fast prototyping. TypeScript adds type safety for the domain model (adaptations, observations, analyses). Node.js satisfies the <5s command execution target (SC-007) for local operations.

**Alternatives considered**:
- **Go**: Single binary distribution is appealing, but slower iteration speed and smaller YAML/GitHub library ecosystem for this domain.
- **Rust**: Best performance, but over-engineered for a tool that primarily orchestrates API calls and file operations. Higher contributor barrier.
- **Python**: Excellent prototyping speed, but distribution pain (requires Python runtime) and slower startup time conflict with SC-007.

## R2: CLI Framework

**Decision**: Commander.js

**Rationale**: Lightweight, well-documented, supports nested subcommands (`adapt repo add`, `adapt contribute split`), auto-generated help, and has the largest adoption for Node.js CLIs. Oclif is more opinionated but heavier; yargs has a less intuitive API for deeply nested commands.

**Alternatives considered**:
- **Oclif**: Plugin architecture is nice but adds complexity for MVP. Could migrate to later if plugin system becomes priority.
- **Yargs**: Good but less ergonomic for the nested command structure this CLI requires.
- **Clipanion**: Type-safe but smaller community.

## R3: GitHub API Client

**Decision**: @octokit/rest

**Rationale**: Official GitHub SDK for JavaScript/TypeScript. Handles authentication (token-based), pagination, rate limiting, and all required endpoints (repos, pulls, commits, releases, security advisories). Supports both `GITHUB_TOKEN` and `gh` CLI auth token extraction.

**Alternatives considered**:
- **Raw fetch/axios**: More control but must handle pagination, rate limits, auth manually.
- **gh CLI subprocess**: Works for simple cases but poor for structured data extraction and error handling.

## R4: State Persistence Format

**Decision**: YAML files for config/human-editable state, JSON files for machine-generated state (analyses, adaptations)

**Rationale**: Per clarification, all state is git-tracked and must support merge conflict resolution. YAML is more readable for config (`config.yaml`, `repos.yaml`, `policies.yaml`). JSON is faster to parse and more precise for machine-generated state (analyses, adaptation objects). Both are text-based and git-merge-friendly.

**Alternatives considered**:
- **All YAML**: More readable but slower parsing for large state files.
- **All JSON**: Faster but less readable for human-editable config.
- **SQLite**: Binary format prevents git merging; rejected per clarification.

## R5: TTY Output Rendering

**Decision**: chalk for colors, cli-table3 for tables, ora for spinners

**Rationale**: chalk is the standard for terminal coloring (supports color detection). cli-table3 handles the tabular status/report outputs. ora provides progress indication during network operations. All are lightweight and well-maintained.

**Alternatives considered**:
- **Ink (React for CLI)**: Powerful but over-engineered for this CLI's output needs.
- **Blessed/blessed-contrib**: Terminal UI framework, too heavy for a command-oriented CLI.

## R6: Testing Framework

**Decision**: Vitest

**Rationale**: Fast, TypeScript-native, compatible with Jest API, supports both unit and integration tests. Good CLI testing patterns with stdout/stderr capture.

**Alternatives considered**:
- **Jest**: Heavier, slower TypeScript support.
- **Node.js test runner**: Built-in but less mature assertion/mocking ecosystem.
- **AVA**: Good but smaller community for CLI testing patterns.

## R7: Change Classification (Rule-Based MVP)

**Decision**: Heuristic classification using file paths, commit message patterns, and diff characteristics

**Rationale**: For MVP, rule-based classification avoids AI dependency while providing useful categorization:
- **Security**: files matching `security*`, `auth*`, `cve*`, `vulnerability*`; commit messages with `CVE-`, `security`, `vulnerability`
- **Bugfix**: commit messages with `fix`, `bug`, `patch`, `hotfix`; small diff size
- **Refactor**: commit messages with `refactor`, `cleanup`, `rename`; file moves/renames
- **Feature**: commit messages with `feat`, `add`, `new`, `implement`; new files added
- Fallback: `unknown` classification with manual override

**Alternatives considered**:
- **AI-first**: More accurate but adds API dependency, cost, and latency for MVP.
- **Conventional commits only**: Too restrictive; many repos don't follow this convention.

## R8: Adaptation ID Generation

**Decision**: Format `adp_{year}_{sequential_number}` (e.g., `adp_2026_001`), sequential per project, stored in `.adapt/state/counter.json`

**Rationale**: Human-readable, sortable, and unique within a project. The year prefix provides temporal context. Sequential numbering is simple and avoids UUID collision complexity. Counter file is JSON (one line, easy merge).

**Alternatives considered**:
- **UUID**: Universally unique but not human-readable or sortable.
- **Hash-based**: Deterministic but cryptic.
- **Timestamp-based**: Risk of collision in concurrent team use.

## R9: Package Distribution

**Decision**: npm package (`adapt-cli`) with `npx adapt-cli` support and global install via `npm install -g adapt-cli`

**Rationale**: npm is the standard distribution channel for Node.js CLI tools. Supports `npx` for zero-install usage and global install for regular users. The binary name `adapt` is registered via package.json `bin` field.

**Alternatives considered**:
- **Homebrew**: macOS-only, additional maintenance burden. Can be added later.
- **Binary releases**: Requires bundling Node.js (e.g., pkg, bun compile). Can be added later.
