import * as path from 'node:path';
import { execSync } from 'node:child_process';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeYaml } from '../services/storage.js';
import {
  output,
  outputSuccess,
  outputError,
  outputTable,
} from '../services/output.js';
import { NotInitializedError, AdaptError } from '../lib/errors.js';
import { Repository, validateRepository } from '../models/repository.js';

function reposPath(): string {
  return path.join(getAdaptDir(), 'repos.yaml');
}

function loadRepos(): Repository[] {
  const data = readYaml<Repository[] | null>(reposPath());
  return data ?? [];
}

function saveRepos(repos: Repository[]): void {
  writeYaml(reposPath(), repos);
}

/**
 * Try to detect the default branch of a remote repository via `git ls-remote`.
 * Returns "main" if detection fails.
 */
function detectRemoteBranch(url: string): string {
  try {
    const result = execSync(`git ls-remote --symref ${url} HEAD`, {
      encoding: 'utf-8',
      timeout: 15_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    // Output looks like: ref: refs/heads/main\tHEAD
    const match = result.match(/ref:\s+refs\/heads\/(\S+)\s+HEAD/);
    if (match) {
      return match[1];
    }
  } catch {
    // Detection failed — fall back to "main"
  }
  return 'main';
}

/**
 * Try to detect the current branch of the local git repository.
 * Returns "main" if detection fails.
 */
function detectLocalBranch(): string {
  try {
    const result = execSync('git rev-parse --abbrev-ref HEAD', {
      encoding: 'utf-8',
      timeout: 5_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return result.trim() || 'main';
  } catch {
    return 'main';
  }
}

/**
 * Try to detect the license of a remote repository.
 * This is a best-effort check using git ls-remote — returns null if
 * unable to determine.
 */
function detectRemoteLicense(_url: string): string | null {
  // License detection from a bare remote is unreliable without cloning or
  // using the GitHub API.  Return null for now; the user can set it later.
  return null;
}

// ---------------------------------------------------------------------------
// Command handlers
// ---------------------------------------------------------------------------

/**
 * `adapt repo add <type> <name> <url>`
 */
export async function repoAddCommand(
  type: string,
  name: string,
  url: string,
  _options: Record<string, unknown>,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  if (type !== 'upstream' && type !== 'downstream') {
    throw new AdaptError('Type must be "upstream" or "downstream".', 1);
  }

  const repos = loadRepos();

  // Duplicate check
  if (repos.some((r) => r.name === name)) {
    outputError(`Repository "${name}" is already registered.`);
    process.exit(1);
  }

  let defaultBranch: string;
  let resolvedUrl = url;

  if (type === 'downstream' && url === '.') {
    resolvedUrl = process.cwd();
    defaultBranch = detectLocalBranch();
  } else {
    defaultBranch = detectRemoteBranch(url);
  }

  const license = type === 'upstream' ? detectRemoteLicense(url) : null;

  const repo = validateRepository({
    name,
    url: resolvedUrl,
    type: type as 'upstream' | 'downstream',
    defaultBranch,
    license,
    techStack: [],
  });

  repos.push(repo);
  saveRepos(repos);

  if (json) {
    output(repo, { json: true });
  } else {
    outputSuccess(`Added ${type} repository "${name}" (${resolvedUrl})`);
  }
}

/**
 * `adapt repo list`
 */
export async function repoListCommand(
  _options: Record<string, unknown>,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const repos = loadRepos();

  if (json) {
    output(repos, { json: true });
    return;
  }

  if (repos.length === 0) {
    output('No repositories registered. Use "adapt repo add" to add one.');
    return;
  }

  outputTable(
    ['Name', 'Type', 'URL', 'Branch'],
    repos.map((r) => [r.name, r.type, r.url, r.defaultBranch]),
  );
}

/**
 * `adapt repo show <name>`
 */
export async function repoShowCommand(
  name: string,
  _options: Record<string, unknown>,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const repos = loadRepos();
  const repo = repos.find((r) => r.name === name);

  if (!repo) {
    outputError(`Repository "${name}" not found.`);
    process.exit(1);
  }

  if (json) {
    output(repo, { json: true });
  } else {
    output(`Name:           ${repo.name}`);
    output(`Type:           ${repo.type}`);
    output(`URL:            ${repo.url}`);
    output(`Default Branch: ${repo.defaultBranch}`);
    output(`License:        ${repo.license ?? 'unknown'}`);
    output(`Tech Stack:     ${repo.techStack.length > 0 ? repo.techStack.join(', ') : 'none'}`);
    output(`Added At:       ${repo.addedAt}`);
  }
}
