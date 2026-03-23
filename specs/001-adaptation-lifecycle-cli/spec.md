# Feature Specification: Adaptation Lifecycle CLI

**Feature Branch**: `001-adaptation-lifecycle-cli`
**Created**: 2026-03-23
**Status**: Draft
**Input**: User description: "Implement the adapt CLI suite - a complete Adaptation Lifecycle tool covering observe, analyze, assess, plan, implement, validate, contribute, and learn phases for upstream-to-downstream adaptive development."

## Clarifications

### Session 2026-03-23

- Q: Should `.adapt/` state be git-tracked (shared with team) or gitignored (per-developer local)? → A: Fully git-tracked. The entire `.adapt/` directory is committed to version control so the team shares all adaptation state.
- Q: What is the cardinality between an adaptation and upstream changes? → A: 1:1 with upstream reference. One adaptation maps to exactly one upstream reference (PR, commit, or release tag). A release tag inherently bundles its constituent changes as a single unit.
- Q: How should the CLI authenticate with GitHub APIs? → A: Both: try `gh` CLI auth first, fall back to GITHUB_TOKEN environment variable. The CLI never stores credentials itself.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initialize Adaptation Project (Priority: P1)

A developer wants to set up their existing project for adaptation tracking against an upstream repository. They run `adapt init` to create the `.adapt/` workspace with default configuration, then register their upstream and downstream repos so the system knows what to track.

**Why this priority**: Without initialization and repo registration, no other command can function. This is the foundation for the entire lifecycle.

**Independent Test**: Can be fully tested by running `adapt init` in an empty directory and `adapt repo add` with a public GitHub URL, then verifying `.adapt/` structure and `adapt repo list` output.

**Acceptance Scenarios**:

1. **Given** a project directory without `.adapt/`, **When** the user runs `adapt init`, **Then** a `.adapt/` directory is created containing `config.yaml`, `repos.yaml`, `policies.yaml`, and subdirectories (`cache/`, `context/`, `analyses/`, `adaptations/`, `reports/`, `logs/`).
2. **Given** an initialized project, **When** the user runs `adapt repo add upstream mylib https://github.com/org/mylib`, **Then** the upstream repo is registered in `repos.yaml` with its URL, detected default branch, and license info.
3. **Given** an initialized project, **When** the user runs `adapt repo add downstream myproduct .`, **Then** the current project is registered as the downstream target.
4. **Given** an already-initialized project, **When** the user runs `adapt init` again, **Then** the system warns that the project is already initialized and does not overwrite existing config.

---

### User Story 2 - Observe Upstream Changes (Priority: P1)

A developer wants to check what has changed in their tracked upstream repository since their last observation. They run `adapt observe` to get a summary of new commits, PRs, releases, and security-relevant changes.

**Why this priority**: Observation is the entry point of the adaptation lifecycle. Without it, there is nothing to analyze or adapt.

**Independent Test**: Can be fully tested by running `adapt observe <repo-name> --since 7d` against a public repo and verifying it returns a structured list of changes.

**Acceptance Scenarios**:

1. **Given** a registered upstream repo, **When** the user runs `adapt observe mylib`, **Then** the system displays new commits, PRs, tags/releases since the last observation, grouped by type.
2. **Given** a registered upstream repo, **When** the user runs `adapt observe mylib --since 7d`, **Then** only changes from the last 7 days are shown.
3. **Given** a registered upstream repo, **When** the user runs `adapt observe mylib --prs`, **Then** only pull request activity is shown.
4. **Given** a registered upstream repo with no new changes, **When** the user runs `adapt observe mylib`, **Then** the system reports "No new changes since last observation."
5. **Given** any observe output, **When** the user adds `--json`, **Then** the output is formatted as machine-readable JSON.

---

### User Story 3 - Analyze Upstream Changes (Priority: P1)

A developer has observed an interesting upstream PR and wants to understand what it does semantically. They run `adapt analyze` to get a structured breakdown of the change: what files are affected, what the intent is, and how it classifies (feature, bugfix, refactor, security).

**Why this priority**: Analysis transforms raw diffs into meaningful information. It is the foundation for all downstream decisions.

**Independent Test**: Can be fully tested by running `adapt analyze <change-ref>` against an observed change and verifying the output contains classification, affected modules, and intent summary.

**Acceptance Scenarios**:

1. **Given** an observed upstream change (e.g., PR), **When** the user runs `adapt analyze pr-1842`, **Then** the system returns: summary, change classification (feature/bugfix/refactor/security), affected files/modules, and extracted intent.
2. **Given** a commit reference, **When** the user runs `adapt analyze commit abc123`, **Then** the system produces the same structured analysis for that commit.
3. **Given** a release tag, **When** the user runs `adapt analyze release v2.4.0`, **Then** the system analyzes the aggregate changes in that release.
4. **Given** an analysis result, **When** the user adds `--json`, **Then** the output is structured JSON suitable for pipelines.

---

### User Story 4 - Assess Relevance for Downstream Product (Priority: P1)

A developer has analyzed an upstream change and now needs to decide if it matters for their product. They run `adapt assess` to get a relevance score, risk assessment, and suggested action.

**Why this priority**: Assessment is where upstream intelligence becomes a product decision. Without it, developers are back to manual judgment.

**Independent Test**: Can be fully tested by running `adapt assess <change-ref> --against <downstream>` and verifying it returns relevance score, risk score, and suggested action.

**Acceptance Scenarios**:

1. **Given** an analyzed upstream change, **When** the user runs `adapt assess pr-1842 --against myproduct`, **Then** the system returns: relevance score (high/medium/low), strategic value, risk score, and a suggested action (adopt, ignore, monitor, adapt-partially).
2. **Given** a downstream product with a configured profile, **When** assessment runs, **Then** the relevance scoring takes into account the product's architecture profile and module priorities.
3. **Given** an assessment result, **When** the suggested action is "adopt", **Then** an adaptation object is created with status "assessed" and a unique ID (e.g., `adp_2026_001`).

---

### User Story 5 - Plan an Adaptation (Priority: P2)

A developer has assessed an upstream change as relevant and needs a concrete plan for adapting it. They run `adapt plan` to generate a step-by-step adaptation plan including target modules, strategy, dependencies, and estimated scope.

**Why this priority**: Planning bridges assessment and implementation. It prevents ad-hoc adaptations and enables team review.

**Independent Test**: Can be fully tested by running `adapt plan <adaptation-id>` and verifying it produces a structured plan with target modules, steps, and strategy.

**Acceptance Scenarios**:

1. **Given** an assessed adaptation, **When** the user runs `adapt plan adp_2026_001`, **Then** the system generates: target modules, step-by-step actions, dependencies, suggested tests, and a recommended strategy (direct-adoption, partial-reimplementation, improved-implementation).
2. **Given** a plan request, **When** the user specifies `--strategy partial-reimplementation`, **Then** the plan is generated using that specific strategy.
3. **Given** a generated plan, **When** the user views it, **Then** it shows a contribution split indicating which parts could be contributed upstream.

---

### User Story 6 - View Adaptation Status Dashboard (Priority: P2)

A developer or team lead wants a quick overview of all tracked upstream repos, pending adaptations, and the overall health of their adaptation workflow. They run `adapt status` or `adapt sync`.

**Why this priority**: Status visibility is essential for teams to coordinate and not lose track of pending work.

**Independent Test**: Can be fully tested by running `adapt status` after creating several adaptations in various states and verifying the dashboard output.

**Acceptance Scenarios**:

1. **Given** an initialized project with tracked repos, **When** the user runs `adapt status`, **Then** they see: watched repos with last observation time, count of open adaptations by status, high-priority changes awaiting action, and contribution backlog.
2. **Given** an initialized project, **When** the user runs `adapt sync mylib`, **Then** they see: new upstream changes not yet observed, open adaptations, blocked items, and pending validations.
3. **Given** any status output, **When** the user adds `--json`, **Then** the output is machine-readable JSON.

---

### User Story 7 - Implement an Adaptation (Priority: P2)

A developer has a planned adaptation and wants to create the actual code changes in their downstream project. They run `adapt implement` to generate a branch with the proposed changes.

**Why this priority**: Implementation is the core value delivery, but depends on the observe-analyze-assess-plan pipeline being in place first.

**Independent Test**: Can be fully tested by running `adapt implement <adaptation-id> --branch` and verifying a new git branch is created with the proposed changes.

**Acceptance Scenarios**:

1. **Given** a planned adaptation, **When** the user runs `adapt implement adp_2026_001 --branch`, **Then** a new git branch is created (e.g., `adapt/adp-2026-001`) with the proposed file changes.
2. **Given** an implementation request, **When** the user adds `--dry-run`, **Then** the system shows what would be changed without creating files or branches.
3. **Given** an implementation, **When** the user runs `adapt implement adp_2026_001 --open-pr`, **Then** an internal draft PR is created from the adaptation branch.

---

### User Story 8 - Validate an Adaptation (Priority: P2)

After implementing an adaptation, a developer wants to verify it meets quality standards. They run `adapt validate` to check lint, tests, policy compliance, and architecture conformance.

**Why this priority**: Validation prevents broken adaptations from being merged and ensures policy compliance.

**Independent Test**: Can be fully tested by running `adapt validate <adaptation-id>` against an implemented adaptation and verifying pass/fail results with issue details.

**Acceptance Scenarios**:

1. **Given** an implemented adaptation, **When** the user runs `adapt validate adp_2026_001`, **Then** the system runs: lint checks, test suite, policy compliance, and architecture conformance, returning a pass/fail result with details.
2. **Given** a failing validation, **When** issues are found, **Then** the system lists each issue with severity and suggested fix.
3. **Given** a validation, **When** the user specifies `--branch adapt/adp-2026-001`, **Then** validation runs against that specific branch.

---

### User Story 9 - Contribute Back to Upstream (Priority: P3)

A developer has an adaptation that contains improvements valuable to the upstream community. They run `adapt contribute` to extract the generic parts, remove proprietary elements, apply upstream coding style, and prepare a PR.

**Why this priority**: Contribution is strategically valuable but not required for the core adaptation workflow.

**Independent Test**: Can be fully tested by running `adapt contribute <adaptation-id> --draft-pr` and verifying the generated PR contains only generic, non-proprietary code in upstream style.

**Acceptance Scenarios**:

1. **Given** a validated adaptation, **When** the user runs `adapt contribute adp_2026_001`, **Then** the system extracts the generic contribution core, removes proprietary references, and generates a PR-ready changeset.
2. **Given** a contribution, **When** the user adds `--split`, **Then** the contribution is split into multiple smaller PRs for easier upstream review.
3. **Given** a contribution, **When** the user adds `--draft-pr`, **Then** a draft PR is created against the upstream repository.

---

### User Story 10 - Record Learning Feedback (Priority: P3)

After an adaptation is complete (accepted or rejected), a developer records the outcome so the system can improve its future relevance scoring and strategy recommendations.

**Why this priority**: Learning improves the system over time but is not required for basic functionality.

**Independent Test**: Can be fully tested by running `adapt learn record <adaptation-id> --accepted` and verifying the feedback is stored and `adapt learn stats` reflects it.

**Acceptance Scenarios**:

1. **Given** a completed adaptation, **When** the user runs `adapt learn record adp_2026_001 --accepted`, **Then** the outcome is stored in the learning database.
2. **Given** a rejected adaptation, **When** the user runs `adapt learn record adp_2026_001 --rejected --reason "too coupled"`, **Then** the rejection reason is recorded for future reference.
3. **Given** recorded learnings, **When** the user runs `adapt learn stats`, **Then** aggregate statistics are shown: acceptance rate, common rejection reasons, most successful strategies.

---

### User Story 11 - Generate Reports (Priority: P3)

A team lead or engineering manager wants to understand the adaptation activity over a period. They run `adapt report` to get a summary of what was observed, adapted, ignored, and contributed.

**Why this priority**: Reporting provides visibility for stakeholders but is not required for the core developer workflow.

**Independent Test**: Can be fully tested by running `adapt report weekly` after completing several adaptations and verifying the output summarizes activity.

**Acceptance Scenarios**:

1. **Given** adaptation activity over a period, **When** the user runs `adapt report weekly`, **Then** a report is generated showing: observed changes, adaptations started/completed/rejected, contributions submitted, and key decisions.
2. **Given** a report request, **When** the user runs `adapt report upstream mylib --since 30d`, **Then** the report focuses on that specific upstream repo's activity.

---

### Edge Cases

- What happens when `adapt observe` is run against a repo that no longer exists or is inaccessible? System should report a clear error with the last known state.
- How does the system handle conflicting adaptations (two adaptations targeting the same downstream module)? System should warn and suggest manual review.
- What happens when an upstream change is force-pushed or rebased after observation? System should detect the discrepancy and mark the observation as stale.
- How does `adapt init` behave inside a monorepo with multiple downstream targets? System supports multiple downstream registrations via `adapt repo add downstream`.
- What happens when `adapt implement` is run on an adaptation whose upstream change has since been reverted? System should warn that the source change no longer exists upstream.
- How does the system handle rate-limiting from GitHub APIs during observation? System should respect rate limits, cache aggressively, and report remaining quota.
- What happens when `adapt validate` detects policy violations that cannot be auto-fixed? System should report violations with severity levels and block merge for critical violations.
- How does the system handle git merge conflicts on `.adapt/` state files when multiple team members modify adaptation state concurrently? System should use text-based formats (YAML/JSON) for all shared state to enable standard git merge resolution, and provide `adapt sync` conflict detection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST initialize a `.adapt/` workspace directory with config files (`config.yaml`, `repos.yaml`, `policies.yaml`) and subdirectories (`cache/`, `context/`, `analyses/`, `adaptations/`, `reports/`, `logs/`).
- **FR-002**: System MUST register upstream and downstream repositories with URL, type (upstream/downstream), and auto-detected metadata (default branch, license, tech stack).
- **FR-003**: System MUST observe upstream repositories for new commits, pull requests, tags/releases, and security-related changes, with time-range filtering (`--since`). Authentication uses `gh` CLI auth (preferred) with fallback to `GITHUB_TOKEN` environment variable; the CLI MUST NOT store credentials itself.
- **FR-004**: System MUST analyze upstream changes to produce: summary, change classification (feature/bugfix/refactor/security), affected files/modules, and extracted intent.
- **FR-005**: System MUST assess the relevance of analyzed changes against a downstream product profile, producing: relevance score, strategic value, risk score, and suggested action.
- **FR-006**: System MUST create and manage adaptation objects with unique IDs (1:1 with an upstream reference: PR, commit, or release tag), tracking their status through the lifecycle: observed, analyzed, assessed, planned, implemented, validated, contributed, merged, rejected.
- **FR-007**: System MUST generate adaptation plans containing: target modules, step-by-step actions, dependencies, recommended strategy, and contribution split.
- **FR-008**: System MUST implement adaptations by creating git branches with proposed file changes, supporting dry-run and PR creation modes.
- **FR-009**: System MUST validate implemented adaptations against configurable checks (lint, tests, policy compliance, architecture conformance).
- **FR-010**: System MUST prepare upstream contributions by extracting generic code, removing proprietary elements, and generating PR-ready changesets.
- **FR-011**: System MUST record learning feedback (accepted/rejected with reasons) and provide aggregate statistics.
- **FR-012**: System MUST generate periodic reports summarizing adaptation activity.
- **FR-013**: System MUST provide a status dashboard showing: watched repos, open adaptations by state, high-priority items, and contribution backlog.
- **FR-014**: Every command output MUST support both human-readable (TTY) and machine-readable (`--json`) formats.
- **FR-015**: System MUST persist all state using text-based formats (YAML/JSON) to enable git-tracked team collaboration and merge conflict resolution, alongside YAML config files for human-editable settings.
- **FR-016**: System MUST manage project profiles describing the downstream product's architecture, conventions, critical modules, and priorities.
- **FR-017**: System MUST manage policies defining: relevant modules, critical license types, protected areas, and contribution rules.

### Key Entities

- **Repository**: A tracked upstream or downstream git repository with URL, type, default branch, license, and tech stack metadata.
- **Observation**: A snapshot of upstream changes at a point in time, containing commits, PRs, releases, and security alerts.
- **Analysis**: A semantic breakdown of an upstream change, including classification, intent, and affected modules.
- **Adaptation**: The core lifecycle entity tracking exactly one upstream reference (PR, commit, or release tag) through assessment, planning, implementation, validation, and contribution. Has a unique ID, status, strategy, and links to source reference and downstream target. A release tag is treated as a single unit encompassing its constituent changes.
- **Plan**: A structured adaptation plan with target modules, steps, dependencies, and contribution split.
- **Policy**: A set of governance rules controlling what gets adapted, how, and what can be contributed.
- **Profile**: A description of the downstream product's architecture, stack, conventions, and priorities.
- **Learning Record**: Feedback on a completed adaptation (accepted/rejected, reason, outcome metrics).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can go from `adapt init` to their first assessed adaptation in under 10 minutes with a public upstream repo.
- **SC-002**: `adapt observe` returns upstream changes within 30 seconds for repositories with up to 1000 recent changes.
- **SC-003**: `adapt status` provides a complete overview of all adaptations across all tracked repos in a single view.
- **SC-004**: 90% of adaptation assessments produce actionable recommendations (adopt, ignore, monitor, adapt-partially) without requiring manual override.
- **SC-005**: Every adaptation is traceable from observation through to completion or rejection, with full audit history.
- **SC-006**: Teams reduce the time spent manually reviewing upstream changes by at least 60% compared to manual git diff workflows.
- **SC-007**: All CLI commands complete within 5 seconds for typical operations (excluding network-dependent observation).
- **SC-008**: The `--json` output of every command can be consumed by CI/CD pipelines without additional parsing logic.
- **SC-009**: The learning system improves relevance scoring accuracy by at least 15% after 50 recorded outcomes.

## Assumptions

- The CLI is a project-level tool; all state is stored in `.adapt/` within the project directory and is fully git-tracked (committed to version control) so the entire team shares adaptation state, observations, and decisions.
- Git is available in the user's environment (required for branch creation and repo operations).
- Network access is required for `adapt observe` to fetch upstream changes (authenticated via `gh` CLI auth with fallback to `GITHUB_TOKEN` env var), but all other commands can work offline with cached data.
- The initial MVP (v0.1) targets GitHub as the primary source platform; GitLab and Bitbucket are deferred to plugin extensions.
- AI/model integration for semantic analysis and assessment is planned but not required for the core CLI skeleton. Commands should work with rule-based defaults and be enhanceable with AI models later.
- The adaptation status lifecycle (observed -> analyzed -> assessed -> planned -> implemented -> validated -> contributed/merged/rejected) is linear but allows skipping steps (e.g., direct plan from observation for known patterns).
- All state files use text-based formats (YAML/JSON) to support git-tracked team collaboration and standard merge conflict resolution. No binary database (e.g., SQLite) is used for shared state; no external database or service is required.
- The CLI binary is named `adapt`; daemon functionality (`adaptd`) is a future extension.
