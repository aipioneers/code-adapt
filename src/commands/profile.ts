import * as path from 'node:path';
import chalk from 'chalk';
import { isInitialized, getAdaptDir } from '../lib/utils.js';
import { readYaml, writeYaml, exists } from '../services/storage.js';
import { output, outputTable, outputSuccess, outputWarning } from '../services/output.js';
import { NotInitializedError, ValidationError } from '../lib/errors.js';
import { defaultProfile } from '../models/profile.js';
import type { Profile } from '../models/profile.js';

/**
 * `adapt profile create <name> [--json]`
 *
 * Create a new project profile with default settings and write it
 * to .adapt/profile.yaml.
 */
export async function profileCreateCommand(
  name: string,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const profilePath = path.join(getAdaptDir(), 'profile.yaml');
  const profile = defaultProfile(name);
  writeYaml(profilePath, profile);

  if (json) {
    output({ created: true, path: profilePath, profile }, { json: true });
  } else {
    outputSuccess(`Profile "${name}" created at ${profilePath}`);
  }
}

/**
 * `adapt profile inspect [--json]`
 *
 * Read and display the current project profile from .adapt/profile.yaml.
 */
export async function profileInspectCommand(
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const profilePath = path.join(getAdaptDir(), 'profile.yaml');

  if (!exists(profilePath)) {
    if (json) {
      output({ error: 'No profile found. Run "adapt profile create <name>" first.' }, { json: true });
    } else {
      outputWarning('No profile found. Run "adapt profile create <name>" first.');
    }
    return;
  }

  const profile = readYaml<Profile>(profilePath);

  if (json) {
    output(profile, { json: true });
    return;
  }

  output(chalk.bold('\nProject Profile'));

  const rows: string[][] = [
    ['Name', profile.name],
    ['Stack', formatList(profile.stack)],
    ['Architecture', profile.architecture || chalk.dim('(not set)')],
    ['Conventions', formatList(profile.conventions)],
    ['Critical Modules', formatList(profile.criticalModules)],
    ['Priorities', formatList(profile.priorities)],
  ];

  outputTable(['Field', 'Value'], rows);
  output('');
}

/**
 * `adapt profile import <file> [--json]`
 *
 * Import a profile from an external YAML file and write it
 * to .adapt/profile.yaml. The file must contain at minimum a 'name' field.
 */
export async function profileImportCommand(
  file: string,
  parentOptions: { json?: boolean },
): Promise<void> {
  const json = parentOptions.json ?? false;

  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const sourcePath = path.resolve(file);

  if (!exists(sourcePath)) {
    throw new ValidationError(`File not found: ${sourcePath}`);
  }

  const imported = readYaml<Record<string, unknown>>(sourcePath);

  if (!imported || typeof imported !== 'object') {
    throw new ValidationError('Invalid profile file: expected a YAML object.');
  }

  if (!imported.name || typeof imported.name !== 'string') {
    throw new ValidationError('Invalid profile: missing required "name" field.');
  }

  const profilePath = path.join(getAdaptDir(), 'profile.yaml');
  writeYaml(profilePath, imported);

  if (json) {
    output({ imported: true, source: sourcePath, path: profilePath, profile: imported }, { json: true });
  } else {
    outputSuccess(`Profile imported from ${sourcePath} to ${profilePath}`);
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatList(items: string[] | undefined): string {
  if (!items || items.length === 0) {
    return chalk.dim('(none)');
  }
  return items.join(', ');
}
