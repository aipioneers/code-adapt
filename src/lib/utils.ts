import * as fs from 'node:fs';
import * as path from 'node:path';

/**
 * Parse a duration string like "7d", "2w", "1m", "3M" into a Date (now minus duration).
 *
 * Supported units:
 *   d = days
 *   w = weeks
 *   m = months
 *   M = months (alias)
 */
export function parseDuration(input: string): Date {
  const match = input.match(/^(\d+)([dwmM])$/);
  if (!match) {
    throw new Error(`Invalid duration format: "${input}". Use formats like 7d, 2w, 1m, 3M.`);
  }

  const amount = parseInt(match[1], 10);
  const unit = match[2];
  const now = new Date();

  switch (unit) {
    case 'd':
      now.setDate(now.getDate() - amount);
      break;
    case 'w':
      now.setDate(now.getDate() - amount * 7);
      break;
    case 'm':
    case 'M':
      now.setMonth(now.getMonth() - amount);
      break;
  }

  return now;
}

/**
 * Resolve the `.adapt/` directory path from the current working directory.
 */
export function getAdaptDir(): string {
  return path.resolve(process.cwd(), '.adapt');
}

/**
 * Create a directory and all parent directories if they don't exist (mkdir -p).
 */
export function ensureDir(dirPath: string): void {
  fs.mkdirSync(dirPath, { recursive: true });
}

/**
 * Check if the project is initialized (`.adapt/` exists with `config.yaml`).
 */
export function isInitialized(): boolean {
  const adaptDir = getAdaptDir();
  const configPath = path.join(adaptDir, 'config.yaml');
  return fs.existsSync(adaptDir) && fs.existsSync(configPath);
}
