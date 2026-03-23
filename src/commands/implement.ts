import * as fs from 'node:fs';
import * as path from 'node:path';
import { execSync } from 'node:child_process';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeYaml, exists } from '../services/storage.js';
import { output, outputSuccess, outputWarning, outputTable } from '../services/output.js';
import { NotInitializedError, AdaptationNotFoundError, ValidationError } from '../lib/errors.js';
import { transitionStatus } from '../models/adaptation.js';
import type { Adaptation } from '../models/adaptation.js';
import type { Plan, PlanStep } from '../models/plan.js';

/**
 * Create an empty file stub with a TODO comment indicating the adaptation.
 */
function createFileStub(filePath: string, adaptationId: string): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const ext = path.extname(filePath);
  const comment = ext === '.ts' || ext === '.js' || ext === '.tsx' || ext === '.jsx'
    ? `// TODO: Implement adaptation ${adaptationId}\n`
    : ext === '.py'
      ? `# TODO: Implement adaptation ${adaptationId}\n`
      : `# TODO: Implement adaptation ${adaptationId}\n`;
  fs.writeFileSync(filePath, comment, 'utf-8');
}

/**
 * Add a TODO comment at the top of an existing file noting the adaptation.
 */
function addTodoComment(filePath: string, adaptationId: string): void {
  const existing = fs.readFileSync(filePath, 'utf-8');
  const ext = path.extname(filePath);
  const comment = ext === '.ts' || ext === '.js' || ext === '.tsx' || ext === '.jsx'
    ? `// TODO: Apply adaptation ${adaptationId}\n`
    : `# TODO: Apply adaptation ${adaptationId}\n`;
  fs.writeFileSync(filePath, comment + existing, 'utf-8');
}

/**
 * Create a test file stub for the adaptation.
 */
function createTestStub(filePath: string, adaptationId: string): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const content = [
    `// TODO: Add tests for adaptation ${adaptationId}`,
    `describe('Adaptation ${adaptationId}', () => {`,
    `  it.todo('should pass');`,
    `});`,
    '',
  ].join('\n');
  fs.writeFileSync(filePath, content, 'utf-8');
}

/**
 * Execute a plan step and return a description of what was done.
 */
function executeStep(step: PlanStep, adaptationId: string, dryRun: boolean): string {
  const resolvedPath = path.resolve(process.cwd(), step.targetFile);

  switch (step.type) {
    case 'create': {
      if (dryRun) {
        return `Would create file: ${step.targetFile}`;
      }
      createFileStub(resolvedPath, adaptationId);
      return `Created file stub: ${step.targetFile}`;
    }
    case 'modify': {
      if (dryRun) {
        return fs.existsSync(resolvedPath)
          ? `Would add TODO comment to: ${step.targetFile}`
          : `Would create file (missing): ${step.targetFile}`;
      }
      if (fs.existsSync(resolvedPath)) {
        addTodoComment(resolvedPath, adaptationId);
        return `Added TODO comment to: ${step.targetFile}`;
      }
      createFileStub(resolvedPath, adaptationId);
      return `Created file stub (original missing): ${step.targetFile}`;
    }
    case 'delete': {
      if (dryRun) {
        return `Would mark for deletion: ${step.targetFile}`;
      }
      return `Marked for deletion (manual review required): ${step.targetFile}`;
    }
    case 'test': {
      if (dryRun) {
        return `Would create test stub: ${step.targetFile}`;
      }
      createTestStub(resolvedPath, adaptationId);
      return `Created test stub: ${step.targetFile}`;
    }
    default:
      return `Unknown step type: ${(step as PlanStep).type}`;
  }
}

/**
 * `adapt implement <adaptation-id> [--branch] [--dry-run] [--open-pr] [--json]`
 *
 * Implement an adaptation plan by creating file stubs, TODO markers,
 * and optionally creating a git branch and draft PR.
 */
export async function implementCommand(
  adaptationId: string,
  options: { branch?: boolean; dryRun?: boolean; openPr?: boolean },
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;
  const dryRun = options.dryRun ?? false;

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

  // 4. Dry-run mode: display plan steps and exit
  if (dryRun) {
    const results = plan.steps.map((step) => executeStep(step, adaptationId, true));

    if (json) {
      output({
        adaptationId,
        dryRun: true,
        branch: options.branch ? `adapt/${adaptationId}` : null,
        steps: plan.steps.map((step, i) => ({
          order: step.order,
          type: step.type,
          targetFile: step.targetFile,
          action: results[i],
        })),
      }, { json: true });
    } else {
      outputWarning('Dry run — no changes will be made.');
      output(`  Adaptation: ${adaptationId}`);
      output(`  Strategy:   ${plan.strategy}`);
      if (options.branch) {
        output(`  Branch:     adapt/${adaptationId}`);
      }
      output('');
      outputTable(
        ['#', 'Type', 'Target File', 'Action'],
        plan.steps.map((step, i) => [
          String(step.order),
          step.type,
          step.targetFile,
          results[i],
        ]),
      );
    }
    return;
  }

  // 5. Create git branch if requested
  let branchName: string | null = null;

  if (options.branch) {
    branchName = `adapt/${adaptationId}`;
    try {
      execSync(`git checkout -b ${branchName}`, {
        stdio: 'pipe',
        encoding: 'utf-8',
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new ValidationError(
        `Failed to create branch "${branchName}": ${message}`,
      );
    }
  }

  // 6. Execute each plan step
  const results: string[] = [];
  for (const step of plan.steps) {
    const result = executeStep(step, adaptationId, false);
    results.push(result);
  }

  // 7. Update adaptation status to 'implemented'
  let updated = transitionStatus(adaptation, 'implemented');
  updated = {
    ...updated,
    branch: branchName ?? adaptation.branch,
  };

  // 8. Save adaptation
  writeYaml(adpPath, updated);

  // 9. Open draft PR if requested
  let prUrl: string | null = null;

  if (options.openPr) {
    try {
      const result = execSync(
        `gh pr create --draft --title "adapt: ${adaptationId}" --body "Adaptation ${adaptationId}"`,
        { stdio: 'pipe', encoding: 'utf-8' },
      );
      prUrl = result.trim();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      outputWarning(`Failed to create PR: ${message}`);
    }
  }

  // 10. Display summary
  if (json) {
    output({
      adaptationId,
      status: 'implemented',
      branch: branchName,
      stepsExecuted: results.length,
      steps: plan.steps.map((step, i) => ({
        order: step.order,
        type: step.type,
        targetFile: step.targetFile,
        result: results[i],
      })),
      prUrl,
    }, { json: true });
  } else {
    outputSuccess(`Adaptation ${adaptationId} implemented.`);
    output(`  Status:  implemented`);
    output(`  Steps:   ${results.length} executed`);
    if (branchName) {
      output(`  Branch:  ${branchName}`);
    }
    if (prUrl) {
      output(`  PR:      ${prUrl}`);
    }
    output('');
    outputTable(
      ['#', 'Type', 'Target File', 'Result'],
      plan.steps.map((step, i) => [
        String(step.order),
        step.type,
        step.targetFile,
        results[i],
      ]),
    );
  }
}
