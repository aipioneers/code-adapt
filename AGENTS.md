# code-adapt CLI Agent Guidelines

## Build, Test, and Lint Commands

### Development Commands
```bash
# Install dependencies
npm install

# Build TypeScript to dist/
npm run build

# Run tests (includes coverage)
npm test

# Run linter
npm run lint

# Run tests with coverage
vitest --coverage

# Run a single test file
vitest tests/observe.test.ts

# Run tests matching a pattern
vitest --run observe

# Run tests in watch mode
npm test -- --watch
```

### Environment Setup
```bash
# Authenticate with GitHub (required for most commands)
gh auth login

# Set token explicitly if needed
export GITHUB_TOKEN="your_token"
```

## Code Style Guidelines

### TypeScript Configuration
- **Target**: ES2022
- **Module**: Node16
- **Strict Mode**: Enabled (`"strict": true`)
- **Module Resolution**: Node16
- **Declaration Generation**: Enabled
- **Package Type**: ESM (`"type": "module"`)
- **Include**: `src/**/*`
- **Exclude**: `node_modules`, `dist`, `tests`

### Import Style
- Use `.js` extension for all imports (ESM style): `import { foo } from './bar.js'`
- Named exports only (no `export * from`)
- All imports must have extensions in `.ts` files

### Type Annotations
- Always use explicit parameter and return types
- Use `void` for functions that don't return values
- Type all functions: `async function name(args: Type): Promise<Type>`
- Validate types strictly with strict TypeScript

### Error Handling
- **Custom Error Hierarchy**: Extend `AdaptError` base class
- **Error Codes**: Include numeric error codes in error constructors
- **Error Classes**: `AdaptError`, `NotInitializedError`, `RepoNotFoundError`, `AuthError`, `ValidationError`, `AdaptationNotFoundError`
- **Error Messages**: Include context in messages, refer to data (e.g., repo name, adaptation ID)
- **Error Propagation**: Use `throw new Error()` for validation failures

### Naming Conventions
- **Classes**: PascalCase (e.g., `AdaptError`, `Repository`)
- **Functions & Variables**: camelCase (e.g., `getGitHubToken`, `repoName`)
- **Types & Interfaces**: PascalCase (e.g., `Adaptation`, `Repository`)
- **Enums**: PascalCase (e.g., `AdaptationStatus`, `RelevanceScore`)
- **Constants**: UPPER_SNAKE_CASE (if any)

### File Structure
```
src/
├── index.ts              # CLI entry point with command registration
├── commands/             # Command handlers (analyze, observe, implement, etc.)
├── services/             # Domain services (github, auth, storage, output)
├── models/               # TypeScript models, interfaces, and type definitions
├── lib/                  # Utilities and shared functions (utils, errors, config)
└── services/             # Application services (assessor, classifier, etc.)
```

### Code Organization Patterns
- **Command Pattern**: Each command in `src/commands/` exports a function
  ```typescript
  export async function commandName(
    arg: string,
    options: Options,
    parentOptions: { json?: boolean },
  ): Promise<void>
  ```
- **Service Pattern**: Services handle specific domain operations
  ```typescript
  export async function serviceFunction(...): Promise<ReturnType>
  ```
- **Model Pattern**: Use TypeScript interfaces for data models
- **Error Pattern**: Custom errors with numeric codes and context

### Function Documentation
- Use JSDoc comments for all public functions
- Document function purpose, parameters, and return values
- Include parameter types in JSDoc: `@param {string} name - Description`

### Async/Await Patterns
- Use `async/await` instead of callbacks
- Wrap potentially slow operations in `withSpinner` helper
- Promise.all for parallel async operations

### Output Format
- **Text Output**: Use `output()`, `outputSuccess()`, `outputWarning()`, `outputError()`
- **JSON Output**: Use `{ json: true }` flag to output structured data
- **Tables**: Use `outputTable()` for tabular data
- **Error Handling**: Errors go to stderr, all other output to stdout

### Git Operations
- Use `execSync()` for git commands
- Handle failures with try/catch and wrap in `ValidationError`
- For GitHub CLI: use `gh` commands via subprocess

### Storage Pattern
- Use `readYaml()`/`writeYaml()` for YAML files
- Use `readJson()`/`writeJson()` for JSON files
- Use `exists()` to check file presence
- Use `atomicWrite()` for safe file writes (temp file + rename)
- Store files in `.adapt/` directory

### Type Safety Examples
```typescript
// Good
function parseDuration(input: string): Date

// Bad
function parseDuration(input: string): any

// Good
export interface Adaptation {
  id: string;
  status: AdaptationStatus;
}

// Bad
interface Adaptation {
  id: string;
  status: string;
}
```

### Error Handling Examples
```typescript
// Good
if (!repo) {
  throw new RepoNotFoundError(repoName);
}

// Bad
if (!repo) {
  console.error(`Repo not found: ${repoName}`);
}

// Good
const result = await withSpinner('Fetching data...', () => fetch());
// ... use result
// Exception propagates automatically
```

### Command Flow Pattern
Every command should follow this pattern:
1. Initialize check: `if (!isInitialized()) throw new NotInitializedError()`
2. Load configuration: Read YAML/JSON files from `.adapt/`
3. Authenticate: Get GitHub token if needed
4. Process: Execute domain logic
5. Save: Write results to `.adapt/` directory
6. Output: Display results to user (text or JSON)

### Testing
- Write tests in `tests/` directory
- Test file names: `*.test.ts` or `*.spec.ts`
- Use Vitest test framework
- Mock external services if needed
- Test both happy paths and error cases

### Type Guards and Transitions
- Use type-safe state transitions in models (e.g., `transitionStatus()`)
- Validate state changes before applying
- Throw `ValidationError` if invalid transition attempted
