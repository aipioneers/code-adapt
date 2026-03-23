#!/usr/bin/env node

import { Command } from 'commander';
import { AdaptError } from './lib/errors.js';
import { outputError } from './services/output.js';
import { initCommand } from './commands/init.js';
import { repoAddCommand, repoListCommand, repoShowCommand } from './commands/repo.js';
import { observeCommand } from './commands/observe.js';
import { analyzeCommand } from './commands/analyze.js';
import { assessCommand } from './commands/assess.js';
import { planCommand } from './commands/plan.js';
import { implementCommand } from './commands/implement.js';
import { validateCommand } from './commands/validate.js';
import { contributeCommand } from './commands/contribute.js';
import { statusCommand } from './commands/status.js';
import { syncCommand } from './commands/sync.js';
import { reportWeeklyCommand, reportReleaseCommand, reportUpstreamCommand } from './commands/report.js';
import { learnRecordCommand, learnStatsCommand } from './commands/learn.js';
import { policyInitCommand, policyListCommand, policyEditCommand, policyValidateCommand } from './commands/policy.js';
import { profileCreateCommand, profileInspectCommand, profileImportCommand } from './commands/profile.js';

const program = new Command();

program
  .name('code-adapt')
  .description('Observe. Adapt. Contribute. - CLI for the Adaptation Lifecycle')
  .version('0.1.0')
  .option('--json', 'Output results as JSON');

// ---- init -----------------------------------------------------------------

program
  .command('init')
  .description('Initialize a new code-adapt project')
  .option('--profile <name>', 'Use profile template')
  .action(async (options: { profile?: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await initCommand(options, parentOpts);
  });

// ---- repo -----------------------------------------------------------------

const repo = program
  .command('repo')
  .description('Manage upstream and downstream repositories');

repo
  .command('add <type> <name> <url>')
  .description('Add an upstream or downstream repository')
  .action(async (type: string, name: string, url: string, options: Record<string, unknown>) => {
    const parentOpts = program.opts() as { json?: boolean };
    await repoAddCommand(type, name, url, options, parentOpts);
  });

repo
  .command('list')
  .description('List all registered repositories')
  .action(async (options: Record<string, unknown>) => {
    const parentOpts = program.opts() as { json?: boolean };
    await repoListCommand(options, parentOpts);
  });

repo
  .command('show <name>')
  .description('Show details for a single repository')
  .action(async (name: string, options: Record<string, unknown>) => {
    const parentOpts = program.opts() as { json?: boolean };
    await repoShowCommand(name, options, parentOpts);
  });

// ---- observe ---------------------------------------------------------------

program
  .command('observe <repo-name>')
  .description('Observe upstream changes for a tracked repository')
  .option('--since <duration>', 'Only show changes since duration (e.g. 7d, 2w, 1m)')
  .option('--prs', 'Only observe pull requests')
  .option('--commits', 'Only observe commits')
  .option('--releases', 'Only observe releases')
  .action(async (repoName: string, options: { since?: string; prs?: boolean; commits?: boolean; releases?: boolean }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await observeCommand(repoName, options, parentOpts);
  });

// ---- analyze ---------------------------------------------------------------

program
  .command('analyze <reference>')
  .description('Analyze a specific upstream change (pr-<n>, commit-<sha>, release-<tag>)')
  .option('--repo <name>', 'Specify which upstream repository')
  .action(async (reference: string, options: { repo?: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await analyzeCommand(reference, options, parentOpts);
  });

// ---- assess ----------------------------------------------------------------

program
  .command('assess <reference>')
  .description('Assess relevance of an analyzed change')
  .requiredOption('--against <downstream-name>', 'Downstream project to assess against')
  .action(async (reference: string, options: { against: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await assessCommand(reference, options, parentOpts);
  });

// ---- plan ------------------------------------------------------------------

program
  .command('plan <adaptation-id>')
  .description('Generate an adaptation plan')
  .option('--strategy <strategy>', 'Override strategy (direct-adoption, partial-reimplementation, improved-implementation)')
  .action(async (adaptationId: string, options: { strategy?: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await planCommand(adaptationId, options, parentOpts);
  });

// ---- implement -------------------------------------------------------------

program
  .command('implement <adaptation-id>')
  .description('Implement the adaptation')
  .option('--branch', 'Create a git branch')
  .option('--dry-run', 'Show changes without applying')
  .option('--open-pr', 'Create an internal draft PR')
  .action(async (adaptationId: string, options: { branch?: boolean; dryRun?: boolean; openPr?: boolean }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await implementCommand(adaptationId, options, parentOpts);
  });

// ---- validate --------------------------------------------------------------

program
  .command('validate <adaptation-id>')
  .description('Validate an implemented adaptation')
  .option('--branch <branch-name>', 'Branch to validate against')
  .action(async (adaptationId: string, options: { branch?: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await validateCommand(adaptationId, options, parentOpts);
  });

// ---- contribute ------------------------------------------------------------

program
  .command('contribute <adaptation-id>')
  .description('Prepare upstream contribution')
  .option('--split', 'Split into multiple smaller PRs')
  .option('--draft-pr', 'Create draft PR against upstream')
  .action(async (adaptationId: string, options: { split?: boolean; draftPr?: boolean }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await contributeCommand(adaptationId, options, parentOpts);
  });

// ---- status ----------------------------------------------------------------

program
  .command('status')
  .description('Show adaptation dashboard')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await statusCommand(parentOpts);
  });

// ---- sync ------------------------------------------------------------------

program
  .command('sync [repo-name]')
  .description('Show synchronization status')
  .action(async (repoName: string | undefined) => {
    const parentOpts = program.opts() as { json?: boolean };
    await syncCommand(repoName, parentOpts);
  });

// ---- report ----------------------------------------------------------------

const report = program
  .command('report')
  .description('Generate adaptation reports');

report
  .command('weekly')
  .description('Weekly activity report')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await reportWeeklyCommand(parentOpts);
  });

report
  .command('release')
  .description('Activity since last release')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await reportReleaseCommand(parentOpts);
  });

report
  .command('upstream <repo-name>')
  .description('Upstream-specific report')
  .requiredOption('--since <duration>', 'Time window (e.g. 7d, 2w, 1m)')
  .action(async (repoName: string, options: { since: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await reportUpstreamCommand(repoName, options, parentOpts);
  });

// ---- learn -----------------------------------------------------------------

const learn = program
  .command('learn')
  .description('Record and review adaptation outcomes');

learn
  .command('record <adaptation-id>')
  .description('Record adaptation outcome')
  .option('--accepted', 'Mark adaptation as accepted')
  .option('--rejected', 'Mark adaptation as rejected')
  .option('--reason <reason>', 'Reason for outcome')
  .action(async (adaptationId: string, options: { accepted?: boolean; rejected?: boolean; reason?: string }) => {
    const parentOpts = program.opts() as { json?: boolean };
    await learnRecordCommand(adaptationId, options, parentOpts);
  });

learn
  .command('stats')
  .description('Show learning statistics')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await learnStatsCommand(parentOpts);
  });

// ---- policy ----------------------------------------------------------------

const policy = program
  .command('policy')
  .description('Manage adaptation policies');

policy
  .command('init')
  .description('Initialize default policies')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await policyInitCommand(parentOpts);
  });

policy
  .command('list')
  .description('List current policy settings')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await policyListCommand(parentOpts);
  });

policy
  .command('edit')
  .description('Edit policies file')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await policyEditCommand(parentOpts);
  });

policy
  .command('validate')
  .description('Validate policy configuration')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await policyValidateCommand(parentOpts);
  });

// ---- profile ---------------------------------------------------------------

const profile = program
  .command('profile')
  .description('Manage project profiles');

profile
  .command('create <name>')
  .description('Create a new project profile')
  .action(async (name: string) => {
    const parentOpts = program.opts() as { json?: boolean };
    await profileCreateCommand(name, parentOpts);
  });

profile
  .command('inspect')
  .description('Inspect current profile')
  .action(async () => {
    const parentOpts = program.opts() as { json?: boolean };
    await profileInspectCommand(parentOpts);
  });

profile
  .command('import <file>')
  .description('Import profile from YAML file')
  .action(async (file: string) => {
    const parentOpts = program.opts() as { json?: boolean };
    await profileImportCommand(file, parentOpts);
  });

// ---- run -------------------------------------------------------------------

program.parseAsync(process.argv).catch((err: unknown) => {
  if (err instanceof AdaptError) {
    outputError(err.message);
    process.exit(err.code);
  } else if (err instanceof Error) {
    outputError(err.message);
    process.exit(1);
  } else {
    outputError('An unexpected error occurred.');
    process.exit(1);
  }
});
