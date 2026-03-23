import * as path from 'node:path';
import * as fs from 'node:fs';
import { isInitialized, getAdaptDir, ensureDir } from '../lib/utils.js';
import { readYaml, writeYaml } from '../services/storage.js';
import { output, outputSuccess, outputWarning } from '../services/output.js';
import { NotInitializedError, ValidationError } from '../lib/errors.js';
import { generateId } from '../services/id-generator.js';
import { assessRelevance } from '../services/assessor.js';
import type { Analysis } from '../models/analysis.js';
import type { Profile } from '../models/profile.js';
import type { Policy } from '../models/policy.js';
import type { Adaptation } from '../models/adaptation.js';

interface AssessOptions {
  against: string;
}

/**
 * Parse a reference string to match against stored analyses.
 * Accepted formats: pr-<number>, commit-<sha>, release-<tag>
 */
function normalizeReference(ref: string): string {
  if (ref.startsWith('pr-') || ref.startsWith('commit-') || ref.startsWith('release-')) {
    return ref;
  }
  throw new ValidationError(
    `Invalid reference format: "${ref}". Use pr-<number>, commit-<sha>, or release-<tag>.`,
  );
}

/**
 * Scan the analyses directory for an Analysis matching the given sourceRef.
 */
function findAnalysis(sourceRef: string): Analysis | null {
  const analysesDir = path.join(getAdaptDir(), 'analyses');
  if (!fs.existsSync(analysesDir)) {
    return null;
  }

  const files = fs.readdirSync(analysesDir)
    .filter((f) => f.startsWith('ana_') && f.endsWith('.json'));

  for (const file of files) {
    try {
      const filePath = path.join(analysesDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const analysis = JSON.parse(content) as Analysis;
      if (analysis.sourceRef === sourceRef) {
        return analysis;
      }
    } catch {
      // Skip malformed files
    }
  }

  return null;
}

/**
 * `adapt assess <reference> --against <downstream-name>`
 *
 * Assess the relevance and risk of an analyzed upstream change
 * against a downstream project's profile and policy.
 */
export async function assessCommand(
  reference: string,
  options: AssessOptions,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const sourceRef = normalizeReference(reference);

  // Find the analysis for this reference
  const analysis = findAnalysis(sourceRef);
  if (!analysis) {
    throw new ValidationError(
      `No analysis found for reference "${sourceRef}". Run "adapt analyze ${sourceRef}" first.`,
    );
  }

  // Load profile and policy
  const adaptDir = getAdaptDir();
  const profile = readYaml<Profile>(path.join(adaptDir, 'profile.yaml'));
  const policy = readYaml<Policy>(path.join(adaptDir, 'policies.yaml'));

  // Verify the downstream repo exists (--against)
  const repos = readYaml<Array<{ name: string; type: string }> | null>(
    path.join(adaptDir, 'repos.yaml'),
  ) ?? [];
  const downstream = repos.find((r) => r.name === options.against);
  if (!downstream) {
    outputWarning(
      `Downstream repository "${options.against}" not found in repos.yaml. ` +
        'Proceeding with assessment using current profile and policy.',
    );
  }

  // Run the assessment
  const result = assessRelevance(analysis, profile, policy);

  // Determine source ref type from the reference prefix
  let sourceRefType: 'pr' | 'commit' | 'release';
  if (sourceRef.startsWith('pr-')) {
    sourceRefType = 'pr';
  } else if (sourceRef.startsWith('commit-')) {
    sourceRefType = 'commit';
  } else {
    sourceRefType = 'release';
  }

  // Create Adaptation entity
  const now = new Date().toISOString();
  const adaptation: Adaptation = {
    id: generateId('adp'),
    sourceRepo: analysis.repoName,
    sourceRef,
    sourceRefType,
    analysisId: analysis.id,
    status: 'assessed',
    relevance: result.relevance,
    riskScore: result.riskScore,
    suggestedAction: result.suggestedAction,
    strategy: null,
    targetModules: analysis.affectedModules,
    planId: null,
    branch: null,
    createdAt: now,
    updatedAt: now,
  };

  // Save adaptation
  const adpDir = path.join(adaptDir, 'adaptations', adaptation.id);
  ensureDir(adpDir);
  writeYaml(path.join(adpDir, 'adaptation.yaml'), adaptation);

  // Display results
  if (json) {
    output({ ...adaptation, strategicValue: result.strategicValue }, { json: true });
  } else {
    outputSuccess(`Assessment ${adaptation.id} saved.`);
    output(`  Reference:       ${sourceRef}`);
    output(`  Repository:      ${analysis.repoName}`);
    output(`  Against:         ${options.against}`);
    output(`  Relevance:       ${result.relevance}`);
    output(`  Risk:            ${result.riskScore}`);
    output(`  Suggested Action: ${result.suggestedAction}`);
    output(`  Strategic Value: ${result.strategicValue}`);
    output(`  Classification:  ${analysis.classification}`);
    output(`  Affected Modules: ${analysis.affectedModules.join(', ') || 'none'}`);
  }
}
