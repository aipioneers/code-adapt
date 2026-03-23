import * as path from 'node:path';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeJson } from '../services/storage.js';
import { output, outputSuccess, withSpinner } from '../services/output.js';
import { NotInitializedError, ValidationError, RepoNotFoundError } from '../lib/errors.js';
import { getGitHubToken } from '../services/auth.js';
import { createOctokit, parseRepoUrl, fetchPRDiff, fetchCommitDiff } from '../services/github.js';
import { generateId } from '../services/id-generator.js';
import { classifyChange, extractModules, generateSummary, extractIntent } from '../services/classifier.js';
import type { Repository } from '../models/repository.js';
import type { Analysis } from '../models/analysis.js';

interface AnalyzeOptions {
  repo?: string;
}

/**
 * Parse a reference string into its type and identifier.
 *
 * Supported formats:
 *   - pr-<number>     → { type: 'pr', id: '<number>' }
 *   - commit-<sha>    → { type: 'commit', id: '<sha>' }
 *   - release-<tag>   → { type: 'release', id: '<tag>' }
 */
function parseReference(ref: string): { type: 'pr' | 'commit' | 'release'; id: string } {
  if (ref.startsWith('pr-')) {
    const num = ref.slice(3);
    if (!/^\d+$/.test(num)) {
      throw new ValidationError(`Invalid PR reference: "${ref}". Expected format: pr-<number>`);
    }
    return { type: 'pr', id: num };
  }

  if (ref.startsWith('commit-')) {
    const sha = ref.slice(7);
    if (sha.length < 4) {
      throw new ValidationError(`Invalid commit reference: "${ref}". SHA is too short.`);
    }
    return { type: 'commit', id: sha };
  }

  if (ref.startsWith('release-')) {
    const tag = ref.slice(8);
    if (tag.length === 0) {
      throw new ValidationError(`Invalid release reference: "${ref}". Tag cannot be empty.`);
    }
    return { type: 'release', id: tag };
  }

  throw new ValidationError(
    `Invalid reference format: "${ref}". Use pr-<number>, commit-<sha>, or release-<tag>.`,
  );
}

/**
 * Resolve the target repository:
 *   1. If --repo is given, use that
 *   2. If only one upstream repo exists, use it
 *   3. Otherwise, error
 */
function resolveRepo(repos: Repository[], repoOption?: string): Repository {
  if (repoOption) {
    const repo = repos.find((r) => r.name === repoOption);
    if (!repo) {
      throw new RepoNotFoundError(repoOption);
    }
    return repo;
  }

  const upstreams = repos.filter((r) => r.type === 'upstream');
  if (upstreams.length === 1) {
    return upstreams[0];
  }

  if (upstreams.length === 0) {
    throw new ValidationError('No upstream repositories registered. Add one with "adapt repo add upstream <name> <url>".');
  }

  throw new ValidationError(
    'Multiple upstream repositories found. Use --repo <name> to specify which one.',
  );
}

/**
 * `adapt analyze <reference>` — analyze a specific upstream change.
 */
export async function analyzeCommand(
  reference: string,
  options: AnalyzeOptions,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const { type, id } = parseReference(reference);

  // Load repos and resolve target
  const reposPath = path.join(getAdaptDir(), 'repos.yaml');
  const repos = readYaml<Repository[] | null>(reposPath) ?? [];
  const repo = resolveRepo(repos, options.repo);

  // Authenticate and create client
  const token = getGitHubToken();
  const octokit = createOctokit(token);
  const { owner, repo: repoSlug } = parseRepoUrl(repo.url);

  // Fetch diff data
  let files: string[];
  let additions: number;
  let deletions: number;
  let message: string;

  if (type === 'pr') {
    const diff = await withSpinner(`Fetching PR #${id}...`, () =>
      fetchPRDiff(octokit, owner, repoSlug, parseInt(id, 10)),
    );
    files = diff.files;
    additions = diff.additions;
    deletions = diff.deletions;

    // Also fetch PR title for message
    const prResponse = await octokit.pulls.get({
      owner,
      repo: repoSlug,
      pull_number: parseInt(id, 10),
    });
    message = prResponse.data.title;
  } else if (type === 'commit') {
    const diff = await withSpinner(`Fetching commit ${id.slice(0, 7)}...`, () =>
      fetchCommitDiff(octokit, owner, repoSlug, id),
    );
    files = diff.files;
    additions = diff.additions;
    deletions = diff.deletions;
    message = diff.message;
  } else {
    // release — fetch release info as a simplified analysis
    const releaseResponse = await withSpinner(`Fetching release ${id}...`, async () => {
      const resp = await octokit.repos.getReleaseByTag({ owner, repo: repoSlug, tag: id });
      return resp;
    });

    message = releaseResponse.data.name ?? id;
    files = [];
    additions = 0;
    deletions = 0;
  }

  // Classify the change
  const classification = classifyChange({ message, files, additions, deletions });
  const modules = extractModules(files);
  const diffStats = { additions, deletions, filesChanged: files.length };
  const summary = generateSummary(message, classification, diffStats);
  const intent = extractIntent(message);

  // Build Analysis entity
  const analysis: Analysis = {
    id: generateId('ana'),
    observationId: null,
    sourceRef: reference,
    sourceRefType: type,
    repoName: repo.name,
    summary,
    classification,
    intent,
    affectedFiles: files,
    affectedModules: modules,
    diffStats,
    createdAt: new Date().toISOString(),
  };

  // Save
  const analysisPath = path.join(getAdaptDir(), 'analyses', `${analysis.id}.json`);
  writeJson(analysisPath, analysis);

  // Display
  if (json) {
    output(analysis, { json: true });
  } else {
    outputSuccess(`Analysis ${analysis.id} saved.`);
    output(`  Reference:      ${reference}`);
    output(`  Repository:     ${repo.name}`);
    output(`  Classification: ${classification}`);
    output(`  Summary:        ${summary}`);
    output(`  Intent:         ${intent}`);
    output(`  Files changed:  ${diffStats.filesChanged}`);
    output(`  Additions:      +${diffStats.additions}`);
    output(`  Deletions:      -${diffStats.deletions}`);

    if (modules.length > 0) {
      output(`  Modules:        ${modules.join(', ')}`);
    }

    if (files.length > 0) {
      output('');
      output('Affected files:');
      for (const f of files.slice(0, 20)) {
        output(`  ${f}`);
      }
      if (files.length > 20) {
        output(`  ... and ${files.length - 20} more`);
      }
    }
  }
}
