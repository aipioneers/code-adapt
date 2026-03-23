import * as path from 'node:path';
import * as fs from 'node:fs';
import chalk from 'chalk';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml } from '../services/storage.js';
import { output, outputTable, outputWarning } from '../services/output.js';
import { NotInitializedError, RepoNotFoundError } from '../lib/errors.js';
import type { Repository } from '../models/repository.js';
import type { Observation } from '../models/observation.js';
import type { Adaptation } from '../models/adaptation.js';

/**
 * Find the latest observation timestamp for a given repo.
 */
function findLastObservationTimestamp(repoName: string): string | null {
  const analysesDir = path.join(getAdaptDir(), 'analyses');
  if (!fs.existsSync(analysesDir)) {
    return null;
  }

  const files = fs.readdirSync(analysesDir)
    .filter((f) => f.startsWith('obs_') && f.endsWith('.json'));

  let latestTimestamp: string | null = null;

  for (const file of files) {
    try {
      const filePath = path.join(analysesDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const obs = JSON.parse(content) as Observation;
      if (obs.repoName === repoName) {
        if (!latestTimestamp || obs.timestamp > latestTimestamp) {
          latestTimestamp = obs.timestamp;
        }
      }
    } catch {
      // Skip malformed files
    }
  }

  return latestTimestamp;
}

/**
 * Load all adaptations from .adapt/adaptations/<id>/adaptation.yaml.
 */
function loadAllAdaptations(): Adaptation[] {
  const adaptationsDir = path.join(getAdaptDir(), 'adaptations');
  if (!fs.existsSync(adaptationsDir)) {
    return [];
  }

  const entries = fs.readdirSync(adaptationsDir, { withFileTypes: true });
  const adaptations: Adaptation[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const yamlPath = path.join(adaptationsDir, entry.name, 'adaptation.yaml');
    try {
      if (fs.existsSync(yamlPath)) {
        const adaptation = readYaml<Adaptation>(yamlPath);
        adaptations.push(adaptation);
      }
    } catch {
      // Skip malformed files
    }
  }

  return adaptations;
}

/**
 * Calculate staleness in days between now and a given ISO timestamp.
 */
function staleDays(timestamp: string): number {
  const then = new Date(timestamp).getTime();
  const now = Date.now();
  return Math.floor((now - then) / (1000 * 60 * 60 * 24));
}

/**
 * Format staleness with color: green < 3d, yellow < 7d, red >= 7d.
 */
function formatStaleness(days: number): string {
  const label = `${days}d ago`;
  if (days < 3) {
    return chalk.green(label);
  }
  if (days < 7) {
    return chalk.yellow(label);
  }
  return chalk.red(label);
}

/**
 * Terminal (non-merged, non-rejected) statuses indicate open adaptations.
 */
function isOpenAdaptation(adp: Adaptation): boolean {
  return adp.status !== 'merged' && adp.status !== 'rejected';
}

/**
 * `adapt sync [repo-name] [--json]`
 *
 * Show synchronization status for upstream repositories: staleness,
 * open adaptations, pending validations, and contribution candidates.
 */
export async function syncCommand(
  repoName: string | undefined,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  // Load repos
  const reposPath = path.join(getAdaptDir(), 'repos.yaml');
  const allRepos = readYaml<Repository[] | null>(reposPath) ?? [];

  // Filter to upstream repos (or a specific repo)
  let repos: Repository[];
  if (repoName) {
    const found = allRepos.find((r) => r.name === repoName);
    if (!found) {
      throw new RepoNotFoundError(repoName);
    }
    repos = [found];
  } else {
    repos = allRepos.filter((r) => r.type === 'upstream');
  }

  if (repos.length === 0) {
    if (json) {
      output({ repos: [] }, { json: true });
    } else {
      outputWarning('No upstream repositories to sync. Use "adapt repo add upstream <name> <url>" to add one.');
    }
    return;
  }

  // Load all adaptations once
  const adaptations = loadAllAdaptations();

  // Build sync data per repo
  const syncData = repos.map((repo) => {
    const lastObserved = findLastObservationTimestamp(repo.name);
    const days = lastObserved ? staleDays(lastObserved) : null;

    // Filter adaptations for this repo
    const repoAdaptations = adaptations.filter((adp) => adp.sourceRepo === repo.name);
    const openAdaptations = repoAdaptations.filter(isOpenAdaptation).length;
    const pendingValidations = repoAdaptations.filter((adp) => adp.status === 'implemented').length;
    const contributionCandidates = repoAdaptations.filter((adp) => adp.status === 'validated').length;

    return {
      name: repo.name,
      lastObserved,
      staleDays: days,
      openAdaptations,
      pendingValidations,
      contributionCandidates,
    };
  });

  // JSON output
  if (json) {
    output({ repos: syncData }, { json: true });
    return;
  }

  // TTY output
  output(chalk.bold('\nSync Status'));
  outputTable(
    ['Repository', 'Last Observed', 'Staleness', 'Open Adaptations', 'Pending Validations', 'Contribution Candidates'],
    syncData.map((r) => [
      r.name,
      r.lastObserved ?? chalk.dim('never'),
      r.staleDays !== null ? formatStaleness(r.staleDays) : chalk.dim('n/a'),
      String(r.openAdaptations),
      String(r.pendingValidations),
      String(r.contributionCandidates),
    ]),
  );
  output('');
}
