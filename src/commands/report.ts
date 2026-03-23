import * as path from 'node:path';
import * as fs from 'node:fs';
import { isInitialized, getAdaptDir, ensureDir, parseDuration } from '../lib/utils.js';
import { readYaml, writeYaml, exists } from '../services/storage.js';
import { output, outputSuccess } from '../services/output.js';
import { NotInitializedError, ValidationError } from '../lib/errors.js';
import type { Observation } from '../models/observation.js';
import type { Adaptation } from '../models/adaptation.js';
import type { LearningRecord } from '../models/learning.js';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/**
 * Load all observation files from .adapt/analyses/obs_*.json.
 */
function loadAllObservations(): Observation[] {
  const analysesDir = path.join(getAdaptDir(), 'analyses');
  if (!fs.existsSync(analysesDir)) {
    return [];
  }

  const files = fs.readdirSync(analysesDir).filter(
    (f) => f.startsWith('obs_') && f.endsWith('.json'),
  );

  const observations: Observation[] = [];
  for (const file of files) {
    try {
      const content = fs.readFileSync(path.join(analysesDir, file), 'utf-8');
      observations.push(JSON.parse(content) as Observation);
    } catch {
      // Skip malformed files
    }
  }
  return observations;
}

/**
 * Load all adaptations from .adapt/adaptations/{id}/adaptation.yaml.
 */
function loadAllAdaptations(): Adaptation[] {
  const adaptationsDir = path.join(getAdaptDir(), 'adaptations');
  if (!fs.existsSync(adaptationsDir)) {
    return [];
  }

  const entries = fs.readdirSync(adaptationsDir, { withFileTypes: true });
  const adaptations: Adaptation[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const yamlPath = path.join(adaptationsDir, entry.name, 'adaptation.yaml');
    if (fs.existsSync(yamlPath)) {
      try {
        adaptations.push(readYaml<Adaptation>(yamlPath));
      } catch {
        // Skip malformed files
      }
    }
  }
  return adaptations;
}

/**
 * Load all learning records from .adapt/reports/learnings.yaml.
 */
function loadLearnings(): LearningRecord[] {
  const learningsPath = path.join(getAdaptDir(), 'reports', 'learnings.yaml');
  if (!exists(learningsPath)) {
    return [];
  }
  return readYaml<LearningRecord[]>(learningsPath) ?? [];
}

/**
 * Check whether a timestamp (ISO 8601) falls on or after the given cutoff date.
 */
function isAfter(timestamp: string, cutoff: Date): boolean {
  return new Date(timestamp).getTime() >= cutoff.getTime();
}

/**
 * Get ISO week number for a date.
 */
function getISOWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

// ---------------------------------------------------------------------------
// Report data structures
// ---------------------------------------------------------------------------

interface ReportData {
  period: string;
  generatedAt: string;
  observations: {
    total: number;
    repos: string[];
    totalCommits: number;
    totalPRs: number;
    totalReleases: number;
  };
  adaptations: {
    total: number;
    created: number;
    completed: number;
    rejected: number;
    inProgress: number;
    byStatus: Record<string, number>;
  };
  contributions: {
    submitted: number;
    merged: number;
    rejected: number;
  };
}

/**
 * Build report data for a given time window.
 */
function buildReportData(
  period: string,
  cutoff: Date,
  filterRepo?: string,
): ReportData {
  const allObs = loadAllObservations();
  const allAdapt = loadAllAdaptations();
  const learnings = loadLearnings();

  // Filter observations
  let observations = allObs.filter((o) => isAfter(o.timestamp, cutoff));
  if (filterRepo) {
    observations = observations.filter((o) => o.repoName === filterRepo);
  }

  // Filter adaptations
  let adaptations = allAdapt.filter((a) => isAfter(a.createdAt, cutoff));
  if (filterRepo) {
    adaptations = adaptations.filter((a) => a.sourceRepo === filterRepo);
  }

  // Filter learnings
  let filteredLearnings = learnings.filter((l) => isAfter(l.recordedAt, cutoff));
  if (filterRepo) {
    const adaptationIds = new Set(adaptations.map((a) => a.id));
    filteredLearnings = filteredLearnings.filter((l) =>
      adaptationIds.has(l.adaptationId),
    );
  }

  // Observation stats
  const repos = [...new Set(observations.map((o) => o.repoName))];
  const totalCommits = observations.reduce(
    (sum, o) => sum + o.commits.length,
    0,
  );
  const totalPRs = observations.reduce(
    (sum, o) => sum + o.pullRequests.length,
    0,
  );
  const totalReleases = observations.reduce(
    (sum, o) => sum + o.releases.length,
    0,
  );

  // Adaptation stats
  const completedStatuses = new Set(['merged', 'contributed']);
  const rejectedStatuses = new Set(['rejected']);
  const inProgressStatuses = new Set([
    'observed',
    'analyzed',
    'assessed',
    'planned',
    'implemented',
    'validated',
  ]);

  const byStatus: Record<string, number> = {};
  for (const a of adaptations) {
    byStatus[a.status] = (byStatus[a.status] || 0) + 1;
  }

  const completed = adaptations.filter((a) =>
    completedStatuses.has(a.status),
  ).length;
  const rejected = adaptations.filter((a) =>
    rejectedStatuses.has(a.status),
  ).length;
  const inProgress = adaptations.filter((a) =>
    inProgressStatuses.has(a.status),
  ).length;

  // Contribution stats
  const submitted = adaptations.filter(
    (a) =>
      a.status === 'contributed' ||
      a.status === 'merged' ||
      a.status === 'rejected',
  ).length;
  const merged = adaptations.filter((a) => a.status === 'merged').length;
  const contributionRejected = adaptations.filter(
    (a) => a.status === 'rejected',
  ).length;

  return {
    period,
    generatedAt: new Date().toISOString(),
    observations: {
      total: observations.length,
      repos,
      totalCommits,
      totalPRs,
      totalReleases,
    },
    adaptations: {
      total: adaptations.length,
      created: adaptations.length,
      completed,
      rejected,
      inProgress,
      byStatus,
    },
    contributions: {
      submitted,
      merged,
      rejected: contributionRejected,
    },
  };
}

/**
 * Generate a markdown report string from report data.
 */
function generateMarkdown(data: ReportData): string {
  const lines: string[] = [];

  lines.push(`# Adapt Report — ${data.period}`);
  lines.push('');
  lines.push(`Generated: ${data.generatedAt}`);
  lines.push('');

  lines.push('## Observations');
  lines.push('');
  lines.push(`- Total observations: ${data.observations.total}`);
  lines.push(
    `- Repositories observed: ${data.observations.repos.length > 0 ? data.observations.repos.join(', ') : 'none'}`,
  );
  lines.push(`- Commits observed: ${data.observations.totalCommits}`);
  lines.push(`- Pull requests observed: ${data.observations.totalPRs}`);
  lines.push(`- Releases observed: ${data.observations.totalReleases}`);
  lines.push('');

  lines.push('## Adaptations');
  lines.push('');
  lines.push(`- Total: ${data.adaptations.total}`);
  lines.push(`- Completed: ${data.adaptations.completed}`);
  lines.push(`- Rejected: ${data.adaptations.rejected}`);
  lines.push(`- In progress: ${data.adaptations.inProgress}`);
  lines.push('');

  if (Object.keys(data.adaptations.byStatus).length > 0) {
    lines.push('### By Status');
    lines.push('');
    for (const [status, count] of Object.entries(data.adaptations.byStatus)) {
      lines.push(`- ${status}: ${count}`);
    }
    lines.push('');
  }

  lines.push('## Contributions');
  lines.push('');
  lines.push(`- Submitted: ${data.contributions.submitted}`);
  lines.push(`- Merged: ${data.contributions.merged}`);
  lines.push(`- Rejected: ${data.contributions.rejected}`);
  lines.push('');

  return lines.join('\n');
}

/**
 * Render the report to the terminal (human-readable).
 */
function displayReport(data: ReportData): void {
  output(`Adapt Report — ${data.period}`);
  output('='.repeat(40));
  output('');

  output('Observations');
  output('------------');
  output(`  Total:          ${data.observations.total}`);
  output(
    `  Repositories:   ${data.observations.repos.length > 0 ? data.observations.repos.join(', ') : 'none'}`,
  );
  output(`  Commits:        ${data.observations.totalCommits}`);
  output(`  Pull Requests:  ${data.observations.totalPRs}`);
  output(`  Releases:       ${data.observations.totalReleases}`);
  output('');

  output('Adaptations');
  output('-----------');
  output(`  Total:          ${data.adaptations.total}`);
  output(`  Completed:      ${data.adaptations.completed}`);
  output(`  Rejected:       ${data.adaptations.rejected}`);
  output(`  In Progress:    ${data.adaptations.inProgress}`);

  if (Object.keys(data.adaptations.byStatus).length > 0) {
    output('');
    output('  By Status:');
    for (const [status, count] of Object.entries(data.adaptations.byStatus)) {
      output(`    ${status}: ${count}`);
    }
  }
  output('');

  output('Contributions');
  output('-------------');
  output(`  Submitted:      ${data.contributions.submitted}`);
  output(`  Merged:         ${data.contributions.merged}`);
  output(`  Rejected:       ${data.contributions.rejected}`);
}

/**
 * Save a markdown report to .adapt/reports/.
 */
function saveMarkdownReport(filename: string, data: ReportData): void {
  const reportsDir = path.join(getAdaptDir(), 'reports');
  ensureDir(reportsDir);
  const reportPath = path.join(reportsDir, filename);
  fs.writeFileSync(reportPath, generateMarkdown(data), 'utf-8');
  return;
}

// ---------------------------------------------------------------------------
// Subcommands
// ---------------------------------------------------------------------------

/**
 * `adapt report weekly [--json]`
 *
 * Aggregate the last 7 days of activity: observations created,
 * adaptations created/completed/rejected, and contributions submitted.
 */
export async function reportWeeklyCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const now = new Date();
  const cutoff = new Date(now);
  cutoff.setDate(cutoff.getDate() - 7);

  const week = getISOWeek(now);
  const year = now.getFullYear();
  const period = `Weekly — ${year}-W${String(week).padStart(2, '0')}`;

  const data = buildReportData(period, cutoff);

  // Save markdown report
  const filename = `weekly_${year}_${String(week).padStart(2, '0')}.md`;
  saveMarkdownReport(filename, data);

  if (json) {
    output(data, { json: true });
  } else {
    displayReport(data);
    output('');
    outputSuccess(`Report saved to .adapt/reports/${filename}`);
  }
}

/**
 * `adapt report release [--json]`
 *
 * Show activity since the last tagged release observation.
 * Finds the latest observation that contains at least one release,
 * then aggregates all activity from that observation's timestamp onward.
 */
export async function reportReleaseCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  // Find the latest observation that contains a release
  const allObs = loadAllObservations();
  const releaseObs = allObs
    .filter((o) => o.releases.length > 0)
    .sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );

  let cutoff: Date;
  let latestTag: string;

  if (releaseObs.length > 0) {
    const latest = releaseObs[0];
    cutoff = new Date(latest.timestamp);
    latestTag = latest.releases[0]?.tag ?? 'unknown';
  } else {
    // No release observations found — fall back to last 30 days
    cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    latestTag = 'none';
  }

  const period = `Since Release ${latestTag}`;
  const data = buildReportData(period, cutoff);

  // Save markdown report
  const safeTag = latestTag.replace(/[^a-zA-Z0-9._-]/g, '_');
  const filename = `release_${safeTag}.md`;
  saveMarkdownReport(filename, data);

  if (json) {
    output(data, { json: true });
  } else {
    displayReport(data);
    output('');
    outputSuccess(`Report saved to .adapt/reports/${filename}`);
  }
}

/**
 * `adapt report upstream <repo> --since <duration> [--json]`
 *
 * Focus on a specific upstream repository.
 * Filters observations and adaptations by repo name and time window.
 */
export async function reportUpstreamCommand(
  repoName: string,
  options: { since: string },
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  if (!options.since) {
    throw new ValidationError(
      'The --since option is required. Use formats like 7d, 2w, 1m.',
    );
  }

  const cutoff = parseDuration(options.since);
  const period = `Upstream: ${repoName} (since ${options.since})`;

  const data = buildReportData(period, cutoff, repoName);

  // Save markdown report
  const safeRepo = repoName.replace(/[^a-zA-Z0-9._-]/g, '_');
  const filename = `upstream_${safeRepo}_${options.since}.md`;
  saveMarkdownReport(filename, data);

  if (json) {
    output(data, { json: true });
  } else {
    displayReport(data);
    output('');
    outputSuccess(`Report saved to .adapt/reports/${filename}`);
  }
}
