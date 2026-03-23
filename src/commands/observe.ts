import * as path from 'node:path';
import * as fs from 'node:fs';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeJson } from '../services/storage.js';
import { output, outputSuccess, outputWarning, withSpinner } from '../services/output.js';
import { NotInitializedError, RepoNotFoundError } from '../lib/errors.js';
import { getGitHubToken } from '../services/auth.js';
import { createOctokit, parseRepoUrl, fetchCommits, fetchPullRequests, fetchReleases } from '../services/github.js';
import { generateId } from '../services/id-generator.js';
import { parseDuration } from '../lib/utils.js';
import type { Repository } from '../models/repository.js';
import type { Observation } from '../models/observation.js';

interface ObserveOptions {
  since?: string;
  prs?: boolean;
  commits?: boolean;
  releases?: boolean;
}

/**
 * Find the timestamp of the most recent observation for a given repo.
 * Scans .adapt/analyses/ for obs_*.json files and returns the latest timestamp,
 * or null if no previous observation exists.
 */
function findLastObservationTimestamp(repoName: string): string | null {
  const analysesDir = path.join(getAdaptDir(), 'analyses');
  if (!fs.existsSync(analysesDir)) {
    return null;
  }

  const files = fs.readdirSync(analysesDir)
    .filter((f) => f.startsWith('obs_') && f.endsWith('.json'))
    .sort()
    .reverse();

  for (const file of files) {
    try {
      const filePath = path.join(analysesDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const obs = JSON.parse(content) as Observation;
      if (obs.repoName === repoName) {
        return obs.timestamp;
      }
    } catch {
      // Skip malformed files
    }
  }

  return null;
}

/**
 * `adapt observe <repo-name>` — observe upstream changes for a tracked repository.
 */
export async function observeCommand(
  repoName: string,
  options: ObserveOptions,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  // Load repos and find the target
  const reposPath = path.join(getAdaptDir(), 'repos.yaml');
  const repos = readYaml<Repository[] | null>(reposPath) ?? [];
  const repo = repos.find((r) => r.name === repoName);

  if (!repo) {
    throw new RepoNotFoundError(repoName);
  }

  // Determine the "since" date
  let sinceDate: Date | undefined;
  let sinceLabel: string | null = null;

  if (options.since) {
    sinceDate = parseDuration(options.since);
    sinceLabel = options.since;
  } else {
    const lastTs = findLastObservationTimestamp(repoName);
    if (lastTs) {
      sinceDate = new Date(lastTs);
      sinceLabel = lastTs;
    }
  }

  // Determine which categories to fetch (default: all)
  const fetchAll = !options.prs && !options.commits && !options.releases;
  const doCommits = fetchAll || !!options.commits;
  const doPrs = fetchAll || !!options.prs;
  const doReleases = fetchAll || !!options.releases;

  // Authenticate
  const token = getGitHubToken();
  const octokit = createOctokit(token);
  const { owner, repo: repoSlug } = parseRepoUrl(repo.url);

  // Fetch data with spinner
  const observation = await withSpinner(
    `Observing changes in ${repoName}...`,
    async () => {
      const [commits, pullRequests, releases] = await Promise.all([
        doCommits ? fetchCommits(octokit, owner, repoSlug, sinceDate) : Promise.resolve([]),
        doPrs ? fetchPullRequests(octokit, owner, repoSlug, sinceDate) : Promise.resolve([]),
        doReleases ? fetchReleases(octokit, owner, repoSlug, sinceDate) : Promise.resolve([]),
      ]);

      const obs: Observation = {
        id: generateId('obs'),
        repoName,
        timestamp: new Date().toISOString(),
        since: sinceLabel,
        commits,
        pullRequests,
        releases,
        securityAlerts: [],
      };

      return obs;
    },
  );

  // Save observation
  const obsPath = path.join(getAdaptDir(), 'analyses', `${observation.id}.json`);
  writeJson(obsPath, observation);

  // Check for "no changes"
  const totalChanges =
    observation.commits.length +
    observation.pullRequests.length +
    observation.releases.length;

  if (totalChanges === 0) {
    if (json) {
      output(observation, { json: true });
    } else {
      outputWarning('No changes observed' + (sinceLabel ? ` since ${sinceLabel}` : '') + '.');
      output(`Observation saved: ${observation.id}`);
    }
    return;
  }

  // Display results
  if (json) {
    output(observation, { json: true });
  } else {
    outputSuccess(`Observation ${observation.id} saved.`);
    if (sinceLabel) {
      output(`  Since: ${sinceLabel}`);
    }
    output(`  Commits:        ${observation.commits.length}`);
    output(`  Pull Requests:  ${observation.pullRequests.length}`);
    output(`  Releases:       ${observation.releases.length}`);

    if (observation.commits.length > 0) {
      output('');
      output('Recent commits:');
      for (const c of observation.commits.slice(0, 10)) {
        output(`  ${c.sha.slice(0, 7)} ${c.message}`);
      }
      if (observation.commits.length > 10) {
        output(`  ... and ${observation.commits.length - 10} more`);
      }
    }

    if (observation.pullRequests.length > 0) {
      output('');
      output('Pull requests:');
      for (const pr of observation.pullRequests.slice(0, 10)) {
        output(`  #${pr.number} ${pr.title} (${pr.state})`);
      }
      if (observation.pullRequests.length > 10) {
        output(`  ... and ${observation.pullRequests.length - 10} more`);
      }
    }

    if (observation.releases.length > 0) {
      output('');
      output('Releases:');
      for (const r of observation.releases.slice(0, 10)) {
        output(`  ${r.tag} — ${r.name}`);
      }
      if (observation.releases.length > 10) {
        output(`  ... and ${observation.releases.length - 10} more`);
      }
    }
  }
}
