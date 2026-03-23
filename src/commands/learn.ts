import * as path from 'node:path';
import * as fs from 'node:fs';
import { isInitialized, getAdaptDir, ensureDir } from '../lib/utils.js';
import { readYaml, writeYaml, exists } from '../services/storage.js';
import { output, outputSuccess, outputTable } from '../services/output.js';
import { NotInitializedError, AdaptationNotFoundError, ValidationError } from '../lib/errors.js';
import { transitionStatus } from '../models/adaptation.js';
import type { Adaptation } from '../models/adaptation.js';
import type { LearningRecord } from '../models/learning.js';

/**
 * Resolve the path to the learnings file.
 */
function getLearningsPath(): string {
  return path.join(getAdaptDir(), 'reports', 'learnings.yaml');
}

/**
 * Load all existing learning records from disk.
 * Returns an empty array if the file does not exist.
 */
function loadLearnings(): LearningRecord[] {
  const learningsPath = getLearningsPath();
  if (!exists(learningsPath)) {
    return [];
  }
  return readYaml<LearningRecord[]>(learningsPath) ?? [];
}

/**
 * Save learning records to disk.
 */
function saveLearnings(records: LearningRecord[]): void {
  const learningsPath = getLearningsPath();
  ensureDir(path.dirname(learningsPath));
  writeYaml(learningsPath, records);
}

/**
 * Load an adaptation by ID from .adapt/adaptations/{id}/adaptation.yaml.
 * Throws AdaptationNotFoundError if it does not exist.
 */
function loadAdaptation(adaptationId: string): Adaptation {
  const adaptationPath = path.join(
    getAdaptDir(),
    'adaptations',
    adaptationId,
    'adaptation.yaml',
  );
  if (!exists(adaptationPath)) {
    throw new AdaptationNotFoundError(adaptationId);
  }
  return readYaml<Adaptation>(adaptationPath);
}

/**
 * Save an adaptation back to its directory.
 */
function saveAdaptation(adaptation: Adaptation): void {
  const adaptationPath = path.join(
    getAdaptDir(),
    'adaptations',
    adaptation.id,
    'adaptation.yaml',
  );
  writeYaml(adaptationPath, adaptation);
}

/**
 * `adapt learn record <adaptation-id> --accepted|--rejected [--reason <reason>]`
 *
 * Record the outcome of an adaptation (accepted or rejected),
 * update the adaptation status accordingly, and persist the learning record.
 */
export async function learnRecordCommand(
  adaptationId: string,
  options: { accepted?: boolean; rejected?: boolean; reason?: string },
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  // Validate that exactly one outcome flag is provided
  if (!options.accepted && !options.rejected) {
    throw new ValidationError('You must specify --accepted or --rejected.');
  }
  if (options.accepted && options.rejected) {
    throw new ValidationError('Cannot specify both --accepted and --rejected.');
  }

  // Load the adaptation
  const adaptation = loadAdaptation(adaptationId);

  // Determine outcome
  const outcome: 'accepted' | 'rejected' = options.accepted ? 'accepted' : 'rejected';

  // Create learning record
  const record: LearningRecord = {
    adaptationId,
    outcome,
    reason: options.reason ?? null,
    recordedAt: new Date().toISOString(),
  };

  // Load existing learnings, append, and save
  const learnings = loadLearnings();
  learnings.push(record);
  saveLearnings(learnings);

  // Transition adaptation status
  const targetStatus = outcome === 'accepted' ? 'merged' : 'rejected';
  const updated = transitionStatus(adaptation, targetStatus);
  saveAdaptation(updated);

  // Display result
  if (json) {
    output({ record, adaptation: updated }, { json: true });
  } else {
    outputSuccess(
      `Learning recorded: ${adaptationId} → ${outcome}` +
        (record.reason ? ` (reason: ${record.reason})` : ''),
    );
    output(`  Status updated: ${adaptation.status} → ${updated.status}`);
  }
}

/**
 * Scan all adaptation directories and return all adaptations.
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
 * `adapt learn stats [--json]`
 *
 * Display aggregate learning statistics: totals, acceptance rate,
 * top rejection reasons, and strategy correlations.
 */
export async function learnStatsCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const learnings = loadLearnings();

  if (learnings.length === 0) {
    if (json) {
      output(
        {
          total: 0,
          accepted: 0,
          rejected: 0,
          acceptanceRate: 0,
          rejectionReasons: [],
          strategies: [],
        },
        { json: true },
      );
    } else {
      output('No learning records found.');
    }
    return;
  }

  // Basic counts
  const total = learnings.length;
  const accepted = learnings.filter((l) => l.outcome === 'accepted').length;
  const rejected = learnings.filter((l) => l.outcome === 'rejected').length;
  const acceptanceRate = total > 0 ? (accepted / total) * 100 : 0;

  // Top rejection reasons
  const reasonCounts: Record<string, number> = {};
  for (const l of learnings) {
    if (l.outcome === 'rejected' && l.reason) {
      reasonCounts[l.reason] = (reasonCounts[l.reason] || 0) + 1;
    }
  }
  const rejectionReasons = Object.entries(reasonCounts)
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count);

  // Strategy correlations — load adaptations to map adaptationId → strategy
  const allAdaptations = loadAllAdaptations();
  const adaptationMap = new Map<string, Adaptation>();
  for (const a of allAdaptations) {
    adaptationMap.set(a.id, a);
  }

  const strategyCounts: Record<string, { accepted: number; rejected: number }> = {};
  for (const l of learnings) {
    const adaptation = adaptationMap.get(l.adaptationId);
    const strategy = adaptation?.strategy ?? 'unknown';
    if (!strategyCounts[strategy]) {
      strategyCounts[strategy] = { accepted: 0, rejected: 0 };
    }
    if (l.outcome === 'accepted') {
      strategyCounts[strategy].accepted += 1;
    } else {
      strategyCounts[strategy].rejected += 1;
    }
  }

  const strategies = Object.entries(strategyCounts).map(
    ([strategy, counts]) => ({
      strategy,
      accepted: counts.accepted,
      rejected: counts.rejected,
      total: counts.accepted + counts.rejected,
    }),
  );

  if (json) {
    output(
      {
        total,
        accepted,
        rejected,
        acceptanceRate: Math.round(acceptanceRate * 100) / 100,
        rejectionReasons,
        strategies,
      },
      { json: true },
    );
  } else {
    output('Learning Statistics');
    output('==================');
    outputTable(
      ['Metric', 'Value'],
      [
        ['Total records', String(total)],
        ['Accepted', String(accepted)],
        ['Rejected', String(rejected)],
        ['Acceptance rate', `${acceptanceRate.toFixed(1)}%`],
      ],
    );

    if (rejectionReasons.length > 0) {
      output('');
      output('Top Rejection Reasons');
      output('---------------------');
      outputTable(
        ['Reason', 'Count'],
        rejectionReasons.map((r) => [r.reason, String(r.count)]),
      );
    }

    if (strategies.length > 0) {
      output('');
      output('Strategies Used');
      output('---------------');
      outputTable(
        ['Strategy', 'Accepted', 'Rejected', 'Total'],
        strategies.map((s) => [
          s.strategy,
          String(s.accepted),
          String(s.rejected),
          String(s.total),
        ]),
      );
    }
  }
}
