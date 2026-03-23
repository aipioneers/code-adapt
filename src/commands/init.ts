import * as path from 'node:path';
import { isInitialized, getAdaptDir, ensureDir } from '../lib/utils.js';
import { writeYaml, writeJson } from '../services/storage.js';
import { output, outputSuccess, outputWarning } from '../services/output.js';
import { defaultPolicy } from '../models/policy.js';
import { defaultProfile } from '../models/profile.js';

interface InitOptions {
  profile?: string;
}

/**
 * `adapt init` — initialise a new adaptation workspace.
 *
 * Creates the `.adapt/` directory tree with default configuration,
 * policies, profile, and counter state.
 */
export async function initCommand(options: InitOptions, parentOptions: { json?: boolean }): Promise<void> {
  const json = parentOptions.json ?? false;

  if (isInitialized()) {
    outputWarning('Project is already initialized.');
    process.exit(1);
  }

  const adaptDir = getAdaptDir();
  const projectName = path.basename(process.cwd());

  // Create subdirectories
  const subdirs = [
    'cache',
    'context',
    'analyses',
    'adaptations',
    'reports',
    'logs',
    'state',
  ];

  for (const sub of subdirs) {
    ensureDir(path.join(adaptDir, sub));
  }

  // config.yaml
  const configPath = path.join(adaptDir, 'config.yaml');
  writeYaml(configPath, { version: '1.0' });

  // repos.yaml — empty array
  const reposPath = path.join(adaptDir, 'repos.yaml');
  writeYaml(reposPath, []);

  // policies.yaml
  const policiesPath = path.join(adaptDir, 'policies.yaml');
  writeYaml(policiesPath, defaultPolicy());

  // profile.yaml
  const profilePath = path.join(adaptDir, 'profile.yaml');
  const profile = defaultProfile(options.profile ?? projectName);
  writeYaml(profilePath, profile);

  // state/counter.json
  const counterPath = path.join(adaptDir, 'state', 'counter.json');
  writeJson(counterPath, { obs: 0, ana: 0, adp: 0, plan: 0 });

  const createdFiles = [
    configPath,
    reposPath,
    policiesPath,
    profilePath,
    counterPath,
  ];

  if (json) {
    output({ initialized: true, directory: adaptDir, files: createdFiles }, { json: true });
  } else {
    outputSuccess(`Initialized adapt project in ${adaptDir}`);
  }
}
