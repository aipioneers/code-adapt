import * as path from 'node:path';
import { readJson, writeJson, exists } from './storage.js';
import { getAdaptDir, ensureDir } from '../lib/utils.js';

type IdPrefix = 'obs' | 'ana' | 'adp' | 'plan';

interface CounterState {
  obs: number;
  ana: number;
  adp: number;
  plan: number;
}

function getCounterPath(): string {
  return path.join(getAdaptDir(), 'state', 'counter.json');
}

function loadCounter(): CounterState {
  const counterPath = getCounterPath();
  if (!exists(counterPath)) {
    return { obs: 0, ana: 0, adp: 0, plan: 0 };
  }
  return readJson<CounterState>(counterPath);
}

function saveCounter(counter: CounterState): void {
  const counterPath = getCounterPath();
  ensureDir(path.dirname(counterPath));
  writeJson(counterPath, counter);
}

/**
 * Generate a unique ID with the given prefix.
 *
 * Format: `{prefix}_{year}_{sequence}` where sequence is zero-padded to 3 digits.
 * Example: `obs_2026_001`
 *
 * Reads the current counter from `.adapt/state/counter.json`, increments it,
 * writes it back, and returns the formatted ID.
 */
export function generateId(prefix: IdPrefix): string {
  const counter = loadCounter();
  counter[prefix] += 1;
  saveCounter(counter);

  const year = new Date().getFullYear();
  const sequence = String(counter[prefix]).padStart(3, '0');

  return `${prefix}_${year}_${sequence}`;
}
