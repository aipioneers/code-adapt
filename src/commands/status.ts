import * as path from 'node:path';
import * as fs from 'node:fs';
import chalk from 'chalk';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml } from '../services/storage.js';
import { output, outputTable, outputWarning } from '../services/output.js';
import { NotInitializedError } from '../lib/errors.js';
import type { Repository } from '../models/repository.js';
import type { Observation } from '../models/observation.js';
import type { Adaptation, AdaptationStatus } from '../models/adaptation.js';

/**
 * Find the latest observation for a given repo by scanning .adapt/analyses/obs_*.json.
 * Returns the observation with the latest timestamp, or null if none found.
 */
function findLatestObservation(repoName: string): Observation | null {
  const analysesDir = path.join(getAdaptDir(), 'analyses');
  if (!fs.existsSync(analysesDir)) {
    return null;
  }

  const files = fs.readdirSync(analysesDir)
    .filter((f) => f.startsWith('obs_') && f.endsWith('.json'));

  let latest: Observation | null = null;

  for (const file of files) {
    try {
      const filePath = path.join(analysesDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const obs = JSON.parse(content) as Observation;
      if (obs.repoName === repoName) {
        if (!latest || obs.timestamp > latest.timestamp) {
          latest = obs;
        }
      }
    } catch {
      // Skip malformed files
    }
  }

  return latest;
}

/**
 * Scan all adaptation subdirectories and load every adaptation.yaml.
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
 * Count changes found in an observation (commits + PRs + releases).
 */
function countChanges(obs: Observation): number {
  return obs.commits.length + obs.pullRequests.length + obs.releases.length;
}

/**
 * `adapt status [--json]`
 *
 * Display a dashboard of tracked repositories, adaptation statuses,
 * high-priority items, and the contribution backlog.
 */
export async function statusCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  // 1. Load tracked repos
  const reposPath = path.join(getAdaptDir(), 'repos.yaml');
  const repos = readYaml<Repository[] | null>(reposPath) ?? [];

  // 2. For each repo, find its latest observation
  const repoData = repos.map((repo) => {
    const latestObs = findLatestObservation(repo.name);
    return {
      name: repo.name,
      type: repo.type,
      lastObserved: latestObs ? latestObs.timestamp : null,
      changesFound: latestObs ? countChanges(latestObs) : 0,
    };
  });

  // 3. Load all adaptations
  const adaptations = loadAllAdaptations();

  // 4. Group adaptations by status
  const byStatus: Record<string, number> = {};
  for (const adp of adaptations) {
    byStatus[adp.status] = (byStatus[adp.status] ?? 0) + 1;
  }

  // 5. High-priority: relevance='high' AND status in ['assessed', 'analyzed']
  const highPriority = adaptations.filter(
    (adp) => adp.relevance === 'high' && (adp.status === 'assessed' || adp.status === 'analyzed'),
  );

  // 6. Contribution backlog: status='validated'
  const contributionBacklog = adaptations.filter((adp) => adp.status === 'validated');

  // JSON output
  if (json) {
    output(
      {
        repositories: repoData,
        adaptations: {
          byStatus,
          total: adaptations.length,
        },
        highPriority: highPriority.map((adp) => ({
          id: adp.id,
          sourceRef: adp.sourceRef,
          sourceRepo: adp.sourceRepo,
          relevance: adp.relevance,
          status: adp.status,
        })),
        contributionBacklog: contributionBacklog.length,
      },
      { json: true },
    );
    return;
  }

  // TTY output - dashboard

  // Section: Tracked Repositories
  output(chalk.bold('\nTracked Repositories'));
  if (repoData.length === 0) {
    outputWarning('  No repositories tracked. Use "adapt repo add" to add one.');
  } else {
    outputTable(
      ['Name', 'Type', 'Last Observed', 'Changes Found'],
      repoData.map((r) => [
        r.name,
        r.type,
        r.lastObserved ?? chalk.dim('never'),
        String(r.changesFound),
      ]),
    );
  }

  // Section: Adaptations by Status
  output(chalk.bold('\nAdaptations by Status'));
  if (adaptations.length === 0) {
    outputWarning('  No adaptations found.');
  } else {
    const allStatuses: AdaptationStatus[] = [
      'observed', 'analyzed', 'assessed', 'planned',
      'implemented', 'validated', 'contributed', 'merged', 'rejected',
    ];
    const statusRows = allStatuses
      .filter((s) => (byStatus[s] ?? 0) > 0)
      .map((s) => [s, String(byStatus[s])]);

    if (statusRows.length > 0) {
      outputTable(['Status', 'Count'], statusRows);
    }
    output(`  Total: ${adaptations.length}`);
  }

  // Section: High Priority
  output(chalk.bold('\nHigh Priority'));
  if (highPriority.length === 0) {
    output('  None');
  } else {
    for (const adp of highPriority) {
      output(`  ${chalk.red('!')} ${adp.id} — ${adp.sourceRef} (${adp.sourceRepo})`);
    }
  }

  // Section: Contribution Backlog
  output(chalk.bold('\nContribution Backlog'));
  if (contributionBacklog.length === 0) {
    output('  No validated adaptations ready for contribution.');
  } else {
    output(`  ${contributionBacklog.length} adaptation(s) ready for contribution.`);
    for (const adp of contributionBacklog) {
      output(`    ${adp.id} — ${adp.sourceRef} (${adp.sourceRepo})`);
    }
  }

  output('');
}
