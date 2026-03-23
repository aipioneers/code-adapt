# Tasks: Adaptation Lifecycle CLI

**Input**: Design documents from `/specs/001-adaptation-lifecycle-cli/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure: `src/commands/`, `src/models/`, `src/services/`, `src/lib/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`
- [ ] T002 Initialize Node.js project with package.json including name `adapt-cli`, bin field mapping `adapt` to `src/index.ts`, and dependencies: commander, @octokit/rest, js-yaml, chalk, cli-table3, ora
- [ ] T003 [P] Configure TypeScript with tsconfig.json targeting ES2022, strict mode, outDir `dist/`
- [ ] T004 [P] Configure Vitest in vitest.config.ts with TypeScript support
- [ ] T005 [P] Add .gitignore for node_modules/, dist/, and configure ESLint + Prettier

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [ ] T006 Implement custom error types (AdaptError, NotInitializedError, RepoNotFoundError, AuthError, ValidationError) in src/lib/errors.ts
- [ ] T007 [P] Implement shared utility functions (date parsing for `--since` durations like "7d"/"2w"/"1m", path resolution for `.adapt/`) in src/lib/utils.ts
- [ ] T008 [P] Implement config loader that reads `.adapt/config.yaml` and detects initialization state in src/lib/config.ts
- [ ] T009 Implement storage service with YAML read/write (for config files) and JSON read/write (for analyses/adaptations) in src/services/storage.ts. Must handle file creation, atomic writes, and directory scaffolding.
- [ ] T010 Implement output service supporting both TTY (chalk + cli-table3 formatting) and JSON (`--json` flag) output modes in src/services/output.ts
- [ ] T011 [P] Implement ID generator service for observations (`obs_{year}_{seq}`), analyses (`ana_{year}_{seq}`), and adaptations (`adp_{year}_{seq}`) using `.adapt/state/counter.json` in src/services/id-generator.ts
- [ ] T012 Create CLI entry point with commander program setup, global `--json` flag, version from package.json, and command registration skeleton in src/index.ts

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Initialize Adaptation Project (Priority: P1)

**Goal**: Developer can run `adapt init` to create `.adapt/` workspace and register upstream/downstream repos.

**Independent Test**: Run `adapt init` in empty dir, then `adapt repo add upstream mylib https://github.com/org/mylib`, verify `.adapt/` structure and `adapt repo list` output.

### Implementation for User Story 1

- [ ] T013 [P] [US1] Create Repository model with TypeScript interface and validation (name, url, type, defaultBranch, license, techStack, addedAt) in src/models/repository.ts
- [ ] T014 [P] [US1] Create Policy model with default template values (empty relevantModules, ignoredModules, contributionRules) in src/models/policy.ts
- [ ] T015 [P] [US1] Create Profile model with TypeScript interface (name, stack, architecture, conventions, criticalModules, priorities) in src/models/profile.ts
- [ ] T016 [US1] Implement `adapt init` command: create `.adapt/` directory structure with default config.yaml, empty repos.yaml, default policies.yaml, empty profile.yaml, state/counter.json, and subdirectories (cache/, context/, analyses/, adaptations/, reports/, logs/). Warn if already initialized. Support `--profile` flag. Output TTY/JSON per contract. Exit codes: 0 success, 1 already initialized. In src/commands/init.ts
- [ ] T017 [US1] Implement `adapt repo add` subcommand: register upstream/downstream repo in repos.yaml with auto-detected defaultBranch (via git ls-remote), license detection (check LICENSE file via GitHub API), and addedAt timestamp. Validate URL reachability. Exit codes: 0 success, 1 already registered, 2 unreachable. In src/commands/repo.ts
- [ ] T018 [US1] Implement `adapt repo list` and `adapt repo show <name>` subcommands: read repos.yaml and display registered repositories with name, type, URL, defaultBranch. Support `--json` output. In src/commands/repo.ts
- [ ] T019 [US1] Wire init and repo commands into commander program in src/index.ts

**Checkpoint**: `adapt init` and `adapt repo add/list` are fully functional. User can initialize a project and register repos.

---

## Phase 4: User Story 2 - Observe Upstream Changes (Priority: P1)

**Goal**: Developer can observe what changed in an upstream repo since last check.

**Independent Test**: Run `adapt observe mylib --since 7d` against a registered public repo, verify structured output of commits/PRs/releases.

### Implementation for User Story 2

- [ ] T020 [P] [US2] Implement auth service: try `gh auth token` subprocess first, fall back to `GITHUB_TOKEN` env var. Throw AuthError if neither available. In src/services/auth.ts
- [ ] T021 [P] [US2] Create Observation model with TypeScript interfaces for Observation, CommitSummary, PRSummary, ReleaseSummary, SecurityAlert in src/models/observation.ts
- [ ] T022 [US2] Implement GitHub API client wrapping @octokit/rest: fetch commits (GET /repos/{owner}/{repo}/commits), PRs (GET /repos/{owner}/{repo}/pulls), releases (GET /repos/{owner}/{repo}/releases), with pagination support, rate limit handling (respect X-RateLimit headers, report remaining quota), and since-date filtering. In src/services/github.ts
- [ ] T023 [US2] Implement `adapt observe` command: accept repo-name positional arg, parse `--since` duration (default: last observation timestamp from most recent obs_*.json, or 30 days), `--prs`/`--commits`/`--releases` filters. Call GitHub service, build Observation entity, save to `.adapt/analyses/obs_{id}.json` via storage service. Display TTY summary grouped by type or JSON output. Exit codes per contract. In src/commands/observe.ts
- [ ] T024 [US2] Wire observe command into commander program in src/index.ts

**Checkpoint**: `adapt observe` fetches and persists upstream changes. Full observe pipeline works end-to-end.

---

## Phase 5: User Story 3 - Analyze Upstream Changes (Priority: P1)

**Goal**: Developer can analyze an observed change to get semantic classification, affected modules, and intent.

**Independent Test**: Run `adapt analyze pr-<number>` against an observed PR, verify output contains classification, affected files/modules, summary, and intent.

### Implementation for User Story 3

- [ ] T025 [P] [US3] Create Analysis model with TypeScript interfaces for Analysis, DiffStats in src/models/analysis.ts
- [ ] T026 [P] [US3] Implement classifier service with rule-based heuristics: classify by commit message patterns (fix/bug→bugfix, feat/add→feature, refactor/cleanup→refactor, CVE/security→security), file path patterns (auth*/security*→security), diff characteristics (new files→feature, renames→refactor), fallback to "unknown". In src/services/classifier.ts
- [ ] T027 [US3] Implement `adapt analyze` command: parse reference format (`pr-<number>`, `commit-<sha>`, `release-<tag>`), fetch diff/details from GitHub API for the specific reference, run classifier, extract affected files and module groupings (directory-level grouping), generate summary and intent from commit messages/PR description. Save Analysis to `.adapt/analyses/ana_{id}.json`. Support `--json`. In src/commands/analyze.ts
- [ ] T028 [US3] Wire analyze command into commander program in src/index.ts

**Checkpoint**: `adapt analyze` produces structured semantic analysis from upstream references.

---

## Phase 6: User Story 4 - Assess Relevance for Downstream Product (Priority: P1)

**Goal**: Developer can assess if an analyzed change is relevant to their product, getting a relevance score, risk score, and suggested action. Creates an adaptation object.

**Independent Test**: Run `adapt assess pr-<number> --against myproduct`, verify relevance/risk scores and suggested action. Verify adaptation object created in `.adapt/adaptations/`.

### Implementation for User Story 4

- [ ] T029 [P] [US4] Create Adaptation model with TypeScript interface, status enum (observed/analyzed/assessed/planned/implemented/validated/contributed/merged/rejected), and state transition validation (forward-only + rejected from any state, with skip support) in src/models/adaptation.ts
- [ ] T030 [P] [US4] Implement assessor service: score relevance (high/medium/low) by comparing analysis.affectedModules against profile.criticalModules and policy.relevantModules, score risk based on diff size and classification (security→high risk), determine strategic value from profile.priorities overlap, suggest action (adopt if high relevance + low risk, ignore if low relevance, monitor if medium, adapt-partially otherwise). In src/services/assessor.ts
- [ ] T031 [US4] Implement `adapt assess` command: accept reference arg and `--against` required flag, load analysis from `.adapt/analyses/`, load profile from `.adapt/profile.yaml`, run assessor service, create Adaptation entity with status "assessed" and unique ID, save to `.adapt/adaptations/{id}/adaptation.yaml`. Display assessment results TTY/JSON. In src/commands/assess.ts
- [ ] T032 [US4] Wire assess command into commander program in src/index.ts

**Checkpoint**: Full P1 pipeline works: init → repo add → observe → analyze → assess. Adaptation objects are created and persisted.

---

## Phase 7: User Story 5 - Plan an Adaptation (Priority: P2)

**Goal**: Developer can generate a structured adaptation plan with target modules, steps, strategy, and contribution split.

**Independent Test**: Run `adapt plan adp_2026_001`, verify plan output with target modules, steps, and strategy.

### Implementation for User Story 5

- [ ] T033 [P] [US5] Create Plan model with TypeScript interfaces for Plan, PlanStep, ContributionSplit in src/models/plan.ts
- [ ] T034 [US5] Implement `adapt plan` command: load adaptation and its analysis from `.adapt/`, determine strategy (auto-select based on diff size and classification, or use `--strategy` override), generate ordered PlanSteps mapping affected files to target downstream modules, identify contribution split (generic changes → upstream, product-specific → internal), save Plan to `.adapt/adaptations/{id}/plan.yaml`, update adaptation status to "planned". Display plan TTY/JSON. In src/commands/plan.ts
- [ ] T035 [US5] Wire plan command into commander program in src/index.ts

**Checkpoint**: `adapt plan` generates actionable plans from assessed adaptations.

---

## Phase 8: User Story 6 - View Adaptation Status Dashboard (Priority: P2)

**Goal**: Developer or team lead can see a complete overview of all tracked repos, adaptations, and pending work.

**Independent Test**: Run `adapt status` with several adaptations in various states, verify dashboard shows repos, adaptation counts by state, high-priority items.

### Implementation for User Story 6

- [ ] T036 [US6] Implement `adapt status` command: scan `.adapt/repos.yaml` for tracked repos with last observation timestamps, scan `.adapt/adaptations/` for all adaptations grouped by status, identify high-priority items (high relevance, assessed but not planned), count contribution backlog. Render TTY dashboard using cli-table3 with color-coded status. Support `--json`. In src/commands/status.ts
- [ ] T037 [US6] Implement `adapt sync` command: accept optional repo-name, compare last observation timestamp against current time to identify stale repos, list open adaptations and their statuses, flag blocked items (e.g., adaptations waiting for upstream data that's been force-pushed). Support `--json`. In src/commands/sync.ts
- [ ] T038 [US6] Wire status and sync commands into commander program in src/index.ts

**Checkpoint**: `adapt status` and `adapt sync` provide full project visibility.

---

## Phase 9: User Story 7 - Implement an Adaptation (Priority: P2)

**Goal**: Developer can create a git branch with proposed code changes from a planned adaptation.

**Independent Test**: Run `adapt implement adp_2026_001 --branch`, verify git branch created. Run with `--dry-run` to verify no changes applied.

### Implementation for User Story 7

- [ ] T039 [US7] Implement `adapt implement` command: load adaptation and plan from `.adapt/`, create git branch (`adapt/{adaptation-id}`), apply plan steps as file operations (create/modify stubs based on plan), support `--dry-run` (show planned changes without writing), support `--branch` (create branch), support `--open-pr` (create draft PR via GitHub API using gh CLI). Update adaptation status to "implemented" and record branch name. In src/commands/implement.ts
- [ ] T040 [US7] Wire implement command into commander program in src/index.ts

**Checkpoint**: `adapt implement` creates branches with proposed changes.

---

## Phase 10: User Story 8 - Validate an Adaptation (Priority: P2)

**Goal**: Developer can validate an implemented adaptation against quality checks.

**Independent Test**: Run `adapt validate adp_2026_001`, verify pass/fail results with issue details.

### Implementation for User Story 8

- [ ] T041 [US8] Implement `adapt validate` command: load adaptation, determine branch (from adaptation.branch or `--branch` override), run validation checks in sequence: 1) policy compliance (check adapted files against policy.protectedPaths), 2) architecture conformance (check target modules exist), 3) lint check (run project linter if configured in config.yaml), 4) test check (run project test command if configured). Aggregate results as pass/fail per check with severity and suggested fixes. Update adaptation status to "validated" if all pass. Support `--json`. In src/commands/validate.ts
- [ ] T042 [US8] Wire validate command into commander program in src/index.ts

**Checkpoint**: `adapt validate` runs quality checks on implemented adaptations.

---

## Phase 11: User Story 9 - Contribute Back to Upstream (Priority: P3)

**Goal**: Developer can extract generic improvements from an adaptation and prepare an upstream PR.

**Independent Test**: Run `adapt contribute adp_2026_001 --draft-pr`, verify generated PR contains only generic non-proprietary code.

### Implementation for User Story 9

- [ ] T043 [US9] Implement `adapt contribute` command: load adaptation and plan, use plan.contributionSplit to identify upstream-suitable files, filter out files matching policy.contributionRules.excludePatterns, generate a clean changeset with only upstream-relevant changes. Support `--split` (create separate changesets per module). Support `--draft-pr` (create draft PR against upstream repo via GitHub API). Update adaptation status to "contributed". In src/commands/contribute.ts
- [ ] T044 [US9] Wire contribute command into commander program in src/index.ts

**Checkpoint**: `adapt contribute` prepares clean upstream contributions.

---

## Phase 12: User Story 10 - Record Learning Feedback (Priority: P3)

**Goal**: Developer can record adaptation outcomes to improve future scoring.

**Independent Test**: Run `adapt learn record adp_2026_001 --accepted`, verify learning stored. Run `adapt learn stats`, verify aggregate statistics.

### Implementation for User Story 10

- [ ] T045 [P] [US10] Create LearningRecord model with TypeScript interface (adaptationId, outcome, reason, recordedAt) in src/models/learning.ts
- [ ] T046 [US10] Implement `adapt learn record` command: accept adaptation-id, `--accepted` or `--rejected` flag, optional `--reason`. Validate adaptation exists. Append LearningRecord to `.adapt/reports/learnings.yaml`. Update adaptation status to "merged" (if accepted) or "rejected" (if rejected). In src/commands/learn.ts
- [ ] T047 [US10] Implement `adapt learn stats` subcommand: read `.adapt/reports/learnings.yaml`, compute aggregate stats (total count, acceptance rate, rejection rate, top rejection reasons, most successful strategies from linked adaptations). Display TTY/JSON. In src/commands/learn.ts
- [ ] T048 [US10] Wire learn command into commander program in src/index.ts

**Checkpoint**: `adapt learn` records outcomes and shows aggregate learning stats.

---

## Phase 13: User Story 11 - Generate Reports (Priority: P3)

**Goal**: Team lead can generate summary reports of adaptation activity over a period.

**Independent Test**: Run `adapt report weekly`, verify output summarizes observations, adaptations, and contributions.

### Implementation for User Story 11

- [ ] T049 [US11] Implement `adapt report` command with subcommands: `weekly` (last 7 days activity), `release` (since last tagged release), `upstream <repo> --since <duration>` (specific repo focus). Aggregate data from observations, adaptations, and learnings. Generate report showing: changes observed, adaptations started/completed/rejected, contributions submitted, key decisions. Save markdown report to `.adapt/reports/`. Display TTY summary and support `--json`. In src/commands/report.ts
- [ ] T050 [US11] Wire report command into commander program in src/index.ts

**Checkpoint**: `adapt report` generates management-ready activity summaries.

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: Configuration commands and final polish

- [ ] T051 [P] Implement `adapt policy` subcommands (init, list, edit, validate) for managing `.adapt/policies.yaml` in src/commands/policy.ts
- [ ] T052 [P] Implement `adapt profile` subcommands (create, inspect, import) for managing `.adapt/profile.yaml` in src/commands/profile.ts
- [ ] T053 Wire policy and profile commands into commander program in src/index.ts
- [ ] T054 Add global error handling wrapper: catch all AdaptError subtypes, display user-friendly messages in TTY mode, structured errors in JSON mode, exit with appropriate codes. In src/index.ts
- [ ] T055 Run quickstart.md validation: execute the full quickstart flow (init → repo add → observe → analyze → assess → status) against a real public GitHub repo to verify end-to-end functionality
- [ ] T056 Add `--version` flag support and npm `bin` field verification for global install in package.json and src/index.ts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - No dependencies on other stories
- **US2 (Phase 4)**: Depends on Foundational + US1 (needs repo registration)
- **US3 (Phase 5)**: Depends on US2 (needs observation data)
- **US4 (Phase 6)**: Depends on US3 (needs analysis data)
- **US5 (Phase 7)**: Depends on US4 (needs adaptation object)
- **US6 (Phase 8)**: Depends on US4 (needs adaptations to display) - can run parallel with US5
- **US7 (Phase 9)**: Depends on US5 (needs plan)
- **US8 (Phase 10)**: Depends on US7 (needs implementation)
- **US9 (Phase 11)**: Depends on US8 (needs validated adaptation)
- **US10 (Phase 12)**: Depends on US4 (needs adaptation object) - can run parallel with US5-US9
- **US11 (Phase 13)**: Depends on US4 (needs adaptation data) - can run parallel with US5-US10
- **Polish (Phase 14)**: Depends on all user stories being complete

### User Story Dependencies (Graph)

```
US1 → US2 → US3 → US4 ──┬──→ US5 → US7 → US8 → US9
                          ├──→ US6 (parallel with US5+)
                          ├──→ US10 (parallel with US5+)
                          └──→ US11 (parallel with US5+)
```

### Within Each User Story

- Models before services
- Services before commands
- Core implementation before integration
- Wire into commander after command implementation

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 can run in parallel
- **Phase 2**: T007, T008, T011 can run in parallel (after T006). T010 parallel with T009.
- **Phase 3**: T013, T014, T015 can run in parallel (models)
- **Phase 4**: T020, T021 can run in parallel
- **Phase 5**: T025, T026 can run in parallel
- **Phase 6**: T029, T030 can run in parallel
- **Phase 8**: US6 can start as soon as US4 is done (parallel with US5)
- **Phase 12-13**: US10 and US11 can start as soon as US4 is done (parallel with US5-US9)
- **Phase 14**: T051, T052 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all models for US1 together:
Task: "Create Repository model in src/models/repository.ts"
Task: "Create Policy model in src/models/policy.ts"
Task: "Create Profile model in src/models/profile.ts"

# Then implement commands sequentially (shared file src/commands/repo.ts):
Task: "Implement adapt init in src/commands/init.ts"
Task: "Implement adapt repo add/list/show in src/commands/repo.ts"
```

## Parallel Example: After US4 Completes

```bash
# These can all start simultaneously after US4:
Task: "US5 - Implement adapt plan in src/commands/plan.ts"
Task: "US6 - Implement adapt status in src/commands/status.ts"
Task: "US10 - Implement adapt learn in src/commands/learn.ts"
Task: "US11 - Implement adapt report in src/commands/report.ts"
```

---

## Implementation Strategy

### MVP First (User Stories 1-4 = P1 scope)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (init + repo)
4. Complete Phase 4: US2 (observe)
5. Complete Phase 5: US3 (analyze)
6. Complete Phase 6: US4 (assess)
7. **STOP and VALIDATE**: Test full P1 pipeline: init → repo add → observe → analyze → assess
8. Deploy/demo if ready (v0.1)

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1-US4 → P1 pipeline (v0.1 MVP)
3. US5-US8 → P2 features (v0.2: plan, status, implement, validate)
4. US9-US11 → P3 features (v0.3: contribute, learn, report)
5. Polish → Production-ready release

### Parallel Team Strategy

With multiple developers after US4 completes:
- Developer A: US5 (plan) → US7 (implement) → US8 (validate) → US9 (contribute)
- Developer B: US6 (status/sync) + US10 (learn) + US11 (report)
- Both paths can proceed independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The P1 stories (US1-US4) are sequential (each depends on the previous)
- After US4, multiple P2/P3 stories can proceed in parallel
