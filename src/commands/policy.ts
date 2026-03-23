import * as path from 'node:path';
import chalk from 'chalk';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeYaml, exists } from '../services/storage.js';
import { output, outputTable, outputSuccess, outputWarning, outputError } from '../services/output.js';
import { NotInitializedError, ValidationError } from '../lib/errors.js';
import { defaultPolicy } from '../models/policy.js';
import type { Policy, ContributionRules } from '../models/policy.js';

/**
 * `adapt policy init`
 *
 * Initialize default policy settings in .adapt/policies.yaml.
 * Warns if the file already exists.
 */
export async function policyInitCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const policiesPath = path.join(getAdaptDir(), 'policies.yaml');

  if (exists(policiesPath)) {
    if (json) {
      output({ initialized: false, reason: 'Policy already initialized' }, { json: true });
    } else {
      outputWarning('Policy already initialized.');
    }
    return;
  }

  const policy = defaultPolicy();
  writeYaml(policiesPath, policy);

  if (json) {
    output({ initialized: true, path: policiesPath, policy }, { json: true });
  } else {
    outputSuccess(`Policy initialized at ${policiesPath}`);
  }
}

/**
 * `adapt policy list [--json]`
 *
 * Display the current policy settings from .adapt/policies.yaml.
 */
export async function policyListCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const policiesPath = path.join(getAdaptDir(), 'policies.yaml');

  if (!exists(policiesPath)) {
    if (json) {
      output({ error: 'No policies found. Run "adapt policy init" first.' }, { json: true });
    } else {
      outputWarning('No policies found. Run "adapt policy init" first.');
    }
    return;
  }

  const policy = readYaml<Policy>(policiesPath);

  if (json) {
    output(policy, { json: true });
    return;
  }

  // Human-readable output
  output(chalk.bold('\nPolicy Settings'));

  const rows: string[][] = [
    ['Relevant Modules', formatList(policy.relevantModules)],
    ['Ignored Modules', formatList(policy.ignoredModules)],
    ['Critical Licenses', formatList(policy.criticalLicenses)],
    ['Protected Paths', formatList(policy.protectedPaths)],
    ['Contribution Rules — Enabled', String(policy.contributionRules?.enabled ?? false)],
    ['Contribution Rules — Require Review', String(policy.contributionRules?.requireReview ?? false)],
    ['Contribution Rules — Exclude Patterns', formatList(policy.contributionRules?.excludePatterns)],
    ['Auto-Assess Threshold', policy.autoAssessThreshold ?? chalk.dim('none')],
  ];

  outputTable(['Setting', 'Value'], rows);
  output('');
}

/**
 * `adapt policy edit`
 *
 * Placeholder that tells the user to edit .adapt/policies.yaml directly.
 */
export async function policyEditCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  const policiesPath = path.join(getAdaptDir(), 'policies.yaml');

  if (json) {
    output({ path: policiesPath, message: 'Edit this file directly' }, { json: true });
  } else {
    output(`Edit your policy file directly at:\n  ${chalk.cyan(policiesPath)}`);
  }
}

/**
 * `adapt policy validate [--json]`
 *
 * Validate the structure and types in .adapt/policies.yaml.
 * Reports pass/fail for each section.
 */
export async function policyValidateCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const policiesPath = path.join(getAdaptDir(), 'policies.yaml');

  if (!exists(policiesPath)) {
    throw new ValidationError('No policies file found. Run "adapt policy init" first.');
  }

  const policy = readYaml<Record<string, unknown>>(policiesPath);
  const results: ValidationResult[] = [];

  // Validate each section
  results.push(validateStringArray('relevantModules', policy.relevantModules));
  results.push(validateStringArray('ignoredModules', policy.ignoredModules));
  results.push(validateStringArray('criticalLicenses', policy.criticalLicenses));
  results.push(validateStringArray('protectedPaths', policy.protectedPaths));
  results.push(validateContributionRules(policy.contributionRules));
  results.push(validateAutoAssessThreshold(policy.autoAssessThreshold));

  const allPassed = results.every((r) => r.pass);

  if (json) {
    output(
      {
        valid: allPassed,
        results: results.map((r) => ({
          section: r.section,
          pass: r.pass,
          message: r.message,
        })),
      },
      { json: true },
    );
    return;
  }

  output(chalk.bold('\nPolicy Validation'));

  const rows = results.map((r) => [
    r.section,
    r.pass ? chalk.green('PASS') : chalk.red('FAIL'),
    r.message,
  ]);

  outputTable(['Section', 'Status', 'Details'], rows);

  if (allPassed) {
    outputSuccess('\nAll policy sections are valid.');
  } else {
    outputError('\nSome policy sections have issues.');
  }

  output('');
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

interface ValidationResult {
  section: string;
  pass: boolean;
  message: string;
}

function formatList(items: string[] | undefined): string {
  if (!items || items.length === 0) {
    return chalk.dim('(none)');
  }
  return items.join(', ');
}

function validateStringArray(name: string, value: unknown): ValidationResult {
  if (value === undefined || value === null) {
    return { section: name, pass: true, message: 'Not set (defaults to empty)' };
  }
  if (!Array.isArray(value)) {
    return { section: name, pass: false, message: `Expected array, got ${typeof value}` };
  }
  for (let i = 0; i < value.length; i++) {
    if (typeof value[i] !== 'string') {
      return { section: name, pass: false, message: `Item at index ${i} is not a string` };
    }
  }
  return { section: name, pass: true, message: `${value.length} item(s)` };
}

function validateContributionRules(value: unknown): ValidationResult {
  const section = 'contributionRules';

  if (value === undefined || value === null) {
    return { section, pass: true, message: 'Not set (defaults apply)' };
  }

  if (typeof value !== 'object' || Array.isArray(value)) {
    return { section, pass: false, message: `Expected object, got ${typeof value}` };
  }

  const rules = value as Record<string, unknown>;

  if (rules.enabled !== undefined && typeof rules.enabled !== 'boolean') {
    return { section, pass: false, message: '"enabled" must be a boolean' };
  }

  if (rules.requireReview !== undefined && typeof rules.requireReview !== 'boolean') {
    return { section, pass: false, message: '"requireReview" must be a boolean' };
  }

  if (rules.excludePatterns !== undefined) {
    const patternResult = validateStringArray('contributionRules.excludePatterns', rules.excludePatterns);
    if (!patternResult.pass) {
      return { section, pass: false, message: patternResult.message };
    }
  }

  return { section, pass: true, message: 'Valid contribution rules' };
}

function validateAutoAssessThreshold(value: unknown): ValidationResult {
  const section = 'autoAssessThreshold';

  if (value === undefined || value === null) {
    return { section, pass: true, message: 'Not set' };
  }

  if (typeof value !== 'string') {
    return { section, pass: false, message: `Expected string or null, got ${typeof value}` };
  }

  // Validate threshold format (e.g., "7d", "2w", "1m")
  const validFormat = /^\d+[dwmM]$/.test(value);
  if (!validFormat) {
    return { section, pass: false, message: `Invalid format "${value}". Use formats like 7d, 2w, 1m.` };
  }

  return { section, pass: true, message: `Threshold: ${value}` };
}
