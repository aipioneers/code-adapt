import * as path from 'node:path';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeYaml, readJson, exists } from '../services/storage.js';
import { output, outputSuccess, outputTable } from '../services/output.js';
import { NotInitializedError, AdaptationNotFoundError, ValidationError } from '../lib/errors.js';
import { canTransition, transitionStatus } from '../models/adaptation.js';
import type { Adaptation, Strategy } from '../models/adaptation.js';
import type { Analysis } from '../models/analysis.js';
import type { Policy } from '../models/policy.js';
import type { Plan, PlanStep, ContributionSplit } from '../models/plan.js';

const VALID_STRATEGIES: Strategy[] = [
  'direct-adoption',
  'partial-reimplementation',
  'improved-implementation',
];

/**
 * Auto-select a strategy based on the analysis classification and diff size.
 *
 * Rules:
 *   - security classification -> direct-adoption (fast path)
 *   - large diffs (>200 additions) -> partial-reimplementation
 *   - refactor classification -> improved-implementation
 *   - small diffs / everything else -> direct-adoption
 */
function autoSelectStrategy(analysis: Analysis): Strategy {
  if (analysis.classification === 'security') {
    return 'direct-adoption';
  }

  if (analysis.diffStats.additions > 200) {
    return 'partial-reimplementation';
  }

  if (analysis.classification === 'refactor') {
    return 'improved-implementation';
  }

  return 'direct-adoption';
}

/**
 * Generate PlanSteps from the analysis's affected files.
 * Each affected file becomes a 'modify' step.
 * Each affected module gets a 'test' step appended at the end.
 */
function generateSteps(analysis: Analysis): PlanStep[] {
  const steps: PlanStep[] = [];
  let order = 1;

  for (const file of analysis.affectedFiles) {
    steps.push({
      order,
      description: `Apply upstream changes to ${file}`,
      targetFile: file,
      type: 'modify',
    });
    order++;
  }

  for (const mod of analysis.affectedModules) {
    steps.push({
      order,
      description: `Add/update tests for module ${mod}`,
      targetFile: `tests/${mod}.test.ts`,
      type: 'test',
    });
    order++;
  }

  return steps;
}

/**
 * Generate suggested test descriptions from affected modules.
 */
function generateSuggestedTests(analysis: Analysis): string[] {
  return analysis.affectedModules.map(
    (mod) => `Verify ${mod} module after adaptation`,
  );
}

/**
 * Determine the contribution split based on policy exclude patterns.
 * Files matching any excludePattern go to "internal"; the rest go to "upstream".
 */
function determineContributionSplit(
  files: string[],
  policy: Policy,
): ContributionSplit | null {
  if (!policy.contributionRules.enabled) {
    return null;
  }

  const excludePatterns = policy.contributionRules.excludePatterns;

  const upstream: string[] = [];
  const internal: string[] = [];

  for (const file of files) {
    const isExcluded = excludePatterns.some((pattern) => {
      // Simple glob matching: support * and ** wildcards
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

    if (isExcluded) {
      internal.push(file);
    } else {
      upstream.push(file);
    }
  }

  return { upstream, internal };
}

/**
 * Infer module-level dependencies from affected modules.
 * Returns a de-duplicated list of module names that the plan depends on.
 */
function inferDependencies(analysis: Analysis): string[] {
  // Use affected modules as the dependency set; the caller's modules
  // are the ones that need to exist and be compatible.
  return [...analysis.affectedModules];
}

/**
 * `adapt plan <adaptation-id> [--strategy <strategy>] [--json]`
 *
 * Generate an adaptation plan for an assessed adaptation.
 */
export async function planCommand(
  adaptationId: string,
  options: { strategy?: string },
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

  // 3. Validate that adaptation can transition to 'planned'
  if (!canTransition(adaptation.status, 'planned')) {
    throw new ValidationError(
      `Adaptation "${adaptationId}" is in status "${adaptation.status}" and cannot be planned. ` +
        `Only adaptations in 'assessed' (or earlier eligible) status can be planned.`,
    );
  }

  // 4. Load the associated analysis
  if (!adaptation.analysisId) {
    throw new ValidationError(
      `Adaptation "${adaptationId}" has no associated analysis. Run "adapt analyze" first.`,
    );
  }

  const analysisPath = path.join(adaptDir, 'analyses', `${adaptation.analysisId}.json`);
  if (!exists(analysisPath)) {
    throw new ValidationError(
      `Analysis "${adaptation.analysisId}" not found for adaptation "${adaptationId}".`,
    );
  }

  const analysis = readJson<Analysis>(analysisPath);

  // 5. Load policy
  const policyPath = path.join(adaptDir, 'policies.yaml');
  const policy = exists(policyPath)
    ? readYaml<Policy>(policyPath)
    : {
        relevantModules: [],
        ignoredModules: [],
        criticalLicenses: [],
        protectedPaths: [],
        contributionRules: { enabled: false, requireReview: true, excludePatterns: [] },
        autoAssessThreshold: null,
      };

  // 6. Determine strategy
  let strategy: Strategy;

  if (options.strategy) {
    if (!VALID_STRATEGIES.includes(options.strategy as Strategy)) {
      throw new ValidationError(
        `Invalid strategy: "${options.strategy}". ` +
          `Valid strategies: ${VALID_STRATEGIES.join(', ')}.`,
      );
    }
    strategy = options.strategy as Strategy;
  } else {
    strategy = autoSelectStrategy(analysis);
  }

  // 7. Generate plan steps
  const steps = generateSteps(analysis);

  // 8. Determine contribution split
  const contributionSplit = determineContributionSplit(
    analysis.affectedFiles,
    policy,
  );

  // 9. Create Plan entity
  const planId = `plan_${adaptationId}`;
  const plan: Plan = {
    id: planId,
    adaptationId,
    strategy,
    targetModules: analysis.affectedModules,
    steps,
    dependencies: inferDependencies(analysis),
    suggestedTests: generateSuggestedTests(analysis),
    contributionSplit,
    createdAt: new Date().toISOString(),
  };

  // 9a. Save plan
  writeYaml(path.join(adpDir, 'plan.yaml'), plan);

  // 10. Update adaptation status to 'planned'
  let updated = transitionStatus(adaptation, 'planned');
  updated = {
    ...updated,
    strategy,
    planId,
  };

  // 11. Save updated adaptation
  writeYaml(adpPath, updated);

  // 12. Display results
  if (json) {
    output(plan, { json: true });
  } else {
    outputSuccess(`Plan ${planId} created.`);
    output(`  Adaptation: ${adaptationId}`);
    output(`  Strategy:   ${strategy}`);
    output(`  Steps:      ${steps.length}`);
    output(`  Modules:    ${plan.targetModules.join(', ') || 'none'}`);

    if (plan.dependencies.length > 0) {
      output(`  Dependencies: ${plan.dependencies.join(', ')}`);
    }

    if (plan.suggestedTests.length > 0) {
      output('');
      output('Suggested tests:');
      for (const test of plan.suggestedTests) {
        output(`  - ${test}`);
      }
    }

    if (steps.length > 0) {
      output('');
      outputTable(
        ['#', 'Type', 'Target File', 'Description'],
        steps.map((s) => [
          String(s.order),
          s.type,
          s.targetFile,
          s.description,
        ]),
      );
    }

    if (contributionSplit) {
      output('');
      output('Contribution split:');
      output(`  Upstream (${contributionSplit.upstream.length} files):`);
      for (const f of contributionSplit.upstream) {
        output(`    ${f}`);
      }
      if (contributionSplit.internal.length > 0) {
        output(`  Internal (${contributionSplit.internal.length} files):`);
        for (const f of contributionSplit.internal) {
          output(`    ${f}`);
        }
      }
    }
  }
}
