import * as path from 'node:path';
import { readYaml } from '../services/storage.js';
import { getAdaptDir, isInitialized } from './utils.js';
import { NotInitializedError } from './errors.js';

export interface AdaptConfig {
  version: string;
  defaultModel?: string;
  lintCommand?: string;
  testCommand?: string;
}

/**
 * Load the project configuration from `.adapt/config.yaml`.
 * Throws NotInitializedError if the project has not been initialized.
 */
export function loadConfig(): AdaptConfig {
  if (!isInitialized()) {
    throw new NotInitializedError();
  }

  const configPath = path.join(getAdaptDir(), 'config.yaml');
  return readYaml<AdaptConfig>(configPath);
}
