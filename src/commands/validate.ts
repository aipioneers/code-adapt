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
import type { AdaptConfig } from '../lib/config.js';

interface ValidationCheck {
  name: string;
  passed: boolean;
  issues: string[];
}

/**
 * Check plan steps against policy protected paths.
 * Uses a simple startsWith check for glob-like matching.
 */
function checkPolicyCompliance(plan: Plan, policy: Policy): ValidationCheck {
  const issues: string[] = [];

  for (const step of plan.steps) {
    for (const protectedPath of policy.protectedPaths) {
      if (step.targetFile.startsWith(protectedPath)) {
        issues.push(
          `Step ${step.order}: "${step.targetFile}" targets protected path "${protectedPath}"`,
        );
      }
    }
  }

  return {
    name: 'Policy compliance',
    passed: issues.length === 0,
    issues,
  };
}

/**
 * Check that the plan's target modules are accounted for in the plan steps.
 */
function checkArchitectureConformance(plan: Plan): ValidationCheck {
  const issues: string[] = [];
  const stepFiles = plan.steps.map((s) => s.targetFile);

  for (const mod of plan.targetModules) {
    const hasStep = stepFiles.some(
      (f) => f.includes(mod) || f.startsWith(`${mod}/`),
    );
    if (!hasStep) {
      issues.push(
        `Module "${mod}" is listed in targetModules but has no matching plan step`,
      );
    }
  }

  return {
    name: 'Architecture conformance',
    passed: issues.length === 0,
    issues,
  };
}

/**
 * Run a lint command and return a validation check result.
 * If no lint command is configured, the check passes with a skip note.
 */
function checkLint(config: AdaptConfig): ValidationCheck {
  if (!config.lintCommand) {
    return {
      name: 'Lint check',
      passed: true,
      issues: ['Skipped: no lintCommand configured'],
    };
  }

  try {
    execSync(config.lintCommand, {
      stdio: 'pipe',
      encoding: 'utf-8',
    });
    return {
      name: 'Lint check',
      passed: true,
      issues: [],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      name: 'Lint check',
      passed: false,
      issues: [`Lint failed: ${message}`],
    };
  }
}

/**
 * Run a test command and return a validation check result.
 * If no test command is configured, the check passes with a skip note.
 */
function checkTests(config: AdaptConfig): ValidationCheck {
  if (!config.testCommand) {
    return {
      name: 'Test check',
      passed: true,
      issues: ['Skipped: no testCommand configured'],
    };
  }

  try {
    execSync(config.testCommand, {
      stdio: 'pipe',
      encoding: 'utf-8',
    });
    return {
      name: 'Test check',
      passed: true,
      issues: [],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      name: 'Test check',
      passed: false,
      issues: [`Tests failed: ${message}`],
    };
  }
}

/**
 * `adapt validate <adaptation-id> [--branch <name>] [--json]`
 *
 * Validate an implemented adaptation against policy, architecture,
 * lint rules, and tests.
 */
export async function validateCommand(
  adaptationId: string,
  options: { branch?: string },
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

  // 3. Determine branch
  const branch = options.branch ?? adaptation.branch;

  // 4. Load policy (use defaults if missing)
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

  // 5. Load plan
  const planPath = path.join(adpDir, 'plan.yaml');

  if (!exists(planPath)) {
    throw new ValidationError(
      `No plan found for adaptation "${adaptationId}". Run 'adapt plan' first.`,
    );
  }

  const plan = readYaml<Plan>(planPath);

  // 6. Load config for lint/test commands
  const configPath = path.join(adaptDir, 'config.yaml');
  const config: AdaptConfig = exists(configPath)
    ? readYaml<AdaptConfig>(configPath)
    : { version: '1' };

  // 7. Run validation checks
  const checks: ValidationCheck[] = [
    checkPolicyCompliance(plan, policy),
    checkArchitectureConformance(plan),
    checkLint(config),
    checkTests(config),
  ];

  // 8. Aggregate results
  const allPassed = checks.every((c) => c.passed);

  // 9. If all pass, transition to 'validated'
  if (allPassed) {
    const updated = transitionStatus(adaptation, 'validated');
    writeYaml(adpPath, updated);
  }

  // 10. Display results
  if (json) {
    output({
      adaptationId,
      branch: branch ?? null,
      overall: allPassed ? 'pass' : 'fail',
      checks: checks.map((c) => ({
        name: c.name,
        passed: c.passed,
        issues: c.issues,
      })),
      status: allPassed ? 'validated' : adaptation.status,
    }, { json: true });
  } else {
    if (allPassed) {
      outputSuccess(`Validation passed for ${adaptationId}.`);
    } else {
      outputWarning(`Validation failed for ${adaptationId}.`);
    }

    output(`  Adaptation: ${adaptationId}`);
    if (branch) {
      output(`  Branch:     ${branch}`);
    }
    output(`  Overall:    ${allPassed ? 'PASS' : 'FAIL'}`);
    output('');

    outputTable(
      ['Check', 'Status', 'Issues'],
      checks.map((c) => [
        c.name,
        c.passed ? 'PASS' : 'FAIL',
        c.issues.length > 0 ? c.issues.join('; ') : '-',
      ]),
    );

    if (allPassed) {
      output(`\nAdaptation status updated to "validated".`);
    }
  }
}
