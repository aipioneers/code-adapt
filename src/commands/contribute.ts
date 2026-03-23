import * as path from 'node:path';
import { execSync } from 'node:child_process';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeYaml, exists } from '../services/storage.js';
import { output, outputSuccess, outputWarning, outputTable } from '../services/output.js';
import { NotInitializedError, AdaptationNotFoundError, ValidationError } from '../lib/errors.js';
import { transitionStatus } from '../models/adaptation.js';
import type { Adaptation } from '../models/adaptation.js';
import type { Plan } from '../models/plan.js';
import type { Policy } from '../models/policy.js';
import type { Repository } from '../models/repository.js';

/**
 * Filter files against policy contribution exclude patterns.
 * Uses simple glob-like matching (startsWith for path prefixes,
 * regex for wildcard patterns).
 */
function filterExcludedFiles(files: string[], excludePatterns: string[]): string[] {
  if (excludePatterns.length === 0) {
    return files;
  }

  return files.filter((file) => {
    const isExcluded = excludePatterns.some((pattern) => {
      const regex = new RegExp(
        '^' +
          pattern
            .replace(/\./g, '\\.')
            .replace(/\*\*/g, '{{GLOBSTAR}}')
            .replace(/\*/g, '[^/]*')
            .replace(/\{\{GLOBSTAR\}\}/g, '.*') +
          '$',
      );
      return regex.test(file);
    });
    return !isExcluded;
  });
}

/**
 * Group files by their top-level module directory.
 */
function groupByModule(files: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};

  for (const file of files) {
    const parts = file.split('/');
    const module = parts.length > 1 ? parts[0] : '(root)';
    if (!groups[module]) {
      groups[module] = [];
    }
    groups[module].push(file);
  }

  return groups;
}

/**
 * `adapt contribute <adaptation-id> [--split] [--draft-pr] [--json]`
 *
 * Prepare and optionally submit upstream contributions from a
 * validated adaptation.
 */
export async function contributeCommand(
  adaptationId: string,
  options: { split?: boolean; draftPr?: boolean },
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  // 1. Check initialization
  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const adaptDir = getAdaptDir();

  // 2. Load adaptation
  const adpDir = path.join(adaptDir, 'adaptations', adaptationId);
  const adpPath = path.join(adpDir, 'adaptation.yaml');

  if (!exists(adpPath)) {
    throw new AdaptationNotFoundError(adaptationId);
  }

  const adaptation = readYaml<Adaptation>(adpPath);

  // 3. Load plan
  const planPath = path.join(adpDir, 'plan.yaml');

  if (!exists(planPath)) {
    throw new ValidationError(
      `No plan found for adaptation "${adaptationId}". Run 'adapt plan' first.`,
    );
  }

  const plan = readYaml<Plan>(planPath);

  // 4. Determine upstream-suitable files from contribution split
  let upstreamFiles: string[];

  if (plan.contributionSplit) {
    upstreamFiles = [...plan.contributionSplit.upstream];
  } else {
    // If no contribution split, all plan step files go to upstream
    upstreamFiles = plan.steps.map((s) => s.targetFile);
  }

  // 5. Load policy and filter out excluded files
  const policyPath = path.join(adaptDir, 'policies.yaml');
  const policy: Policy = exists(policyPath)
    ? readYaml<Policy>(policyPath)
    : {
        relevantModules: [],
        ignoredModules: [],
        criticalLicenses: [],
        protectedPaths: [],
        contributionRules: { enabled: false, requireReview: true, excludePatterns: [] },
        autoAssessThreshold: null,
      };

  const excludePatterns = policy.contributionRules?.excludePatterns ?? [];
  upstreamFiles = filterExcludedFiles(upstreamFiles, excludePatterns);

  // 6. Check if there are files to contribute
  if (upstreamFiles.length === 0) {
    outputWarning('Nothing to contribute upstream.');
    if (json) {
      output({
        adaptationId,
        upstreamFiles: [],
        status: adaptation.status,
      }, { json: true });
    }
    return;
  }

  // 7. Group by module if --split is requested
  const moduleGroups = options.split ? groupByModule(upstreamFiles) : null;

  // 8. Open draft PR if requested
  let prUrl: string | null = null;

  if (options.draftPr) {
    // Load repos.yaml to find the upstream repo URL
    const reposPath = path.join(adaptDir, 'repos.yaml');
    let upstreamUrl: string | null = null;

    if (exists(reposPath)) {
      const repos = readYaml<Repository[] | null>(reposPath) ?? [];
      const upstreamRepo = repos.find(
        (r) => r.type === 'upstream' && r.name === adaptation.sourceRepo,
      );
      if (upstreamRepo) {
        upstreamUrl = upstreamRepo.url;
      }
    }

    if (!upstreamUrl) {
      outputWarning(
        `Could not find upstream repo URL for "${adaptation.sourceRepo}" in repos.yaml. Skipping PR creation.`,
      );
    } else {
      const title = `adapt: ${adaptationId} contribution`;
      const body = `Adaptation ${adaptationId} — contributing ${upstreamFiles.length} file(s) upstream.`;
      try {
        const result = execSync(
          `gh pr create --draft --repo ${upstreamUrl} --title "${title}" --body "${body}"`,
          { stdio: 'pipe', encoding: 'utf-8' },
        );
        prUrl = result.trim();
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        outputWarning(`Failed to create upstream PR: ${message}`);
      }
    }
  }

  // 9. Transition adaptation to 'contributed'
  const updated = transitionStatus(adaptation, 'contributed');
  writeYaml(adpPath, updated);

  // 10. Display contribution summary
  if (json) {
    output({
      adaptationId,
      status: 'contributed',
      upstreamFiles,
      moduleGroups: moduleGroups ?? undefined,
      excludedPatterns: excludePatterns,
      prUrl,
    }, { json: true });
  } else {
    outputSuccess(`Contribution prepared for ${adaptationId}.`);
    output(`  Status:         contributed`);
    output(`  Upstream files: ${upstreamFiles.length}`);
    if (prUrl) {
      output(`  PR:             ${prUrl}`);
    }
    output('');

    if (moduleGroups) {
      output('Changesets by module:');
      for (const [mod, files] of Object.entries(moduleGroups)) {
        output(`\n  Module: ${mod} (${files.length} file(s))`);
        outputTable(
          ['File'],
          files.map((f) => [f]),
        );
      }
    } else {
      outputTable(
        ['Upstream Files'],
        upstreamFiles.map((f) => [f]),
      );
    }

    if (plan.contributionSplit && plan.contributionSplit.internal.length > 0) {
      output(`\n  Internal-only files (${plan.contributionSplit.internal.length}):`);
      for (const f of plan.contributionSplit.internal) {
        output(`    ${f}`);
      }
    }
  }
}
