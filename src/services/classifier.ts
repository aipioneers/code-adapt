import type { DiffStats } from '../models/analysis.js';

export type Classification = 'feature' | 'bugfix' | 'refactor' | 'security' | 'unknown';

interface ClassifyInput {
  message: string;
  files: string[];
  additions: number;
  deletions: number;
}

/**
 * Classify a change based on its commit message, affected files, and diff stats.
 *
 * Rules (checked in order, first match wins):
 *   1. Security — message or files mention CVE/security/vulnerability/exploit
 *   2. Bugfix   — message mentions fix/bug/patch/hotfix/resolve
 *   3. Refactor — message mentions refactor/cleanup/rename/reorganize/restructure
 *   4. Feature  — message mentions feat/add/new/implement/introduce OR many new lines
 *   5. Default  — unknown
 */
export function classifyChange(data: ClassifyInput): Classification {
  const { message, files, additions, deletions } = data;

  // 1. Security
  if (
    /\b(cve|security|vulnerab|exploit)\b/i.test(message) ||
    files.some((f) => /^(security|auth|cve)/i.test(f))
  ) {
    return 'security';
  }

  // 2. Bugfix
  if (/\b(fix|bug|patch|hotfix|resolve)\b/i.test(message)) {
    return 'bugfix';
  }

  // 3. Refactor
  if (/\b(refactor|cleanup|rename|reorganize|restructure)\b/i.test(message)) {
    return 'refactor';
  }

  // 4. Feature
  if (
    /\b(feat|add|new|implement|introduce)\b/i.test(message) ||
    (additions > deletions * 3 && additions > 50)
  ) {
    return 'feature';
  }

  // 5. Default
  return 'unknown';
}

/**
 * Extract logical module names from file paths.
 * Groups by top-level directory (e.g. "src/models/user.ts" → "models").
 * Files at the root level are grouped under "root".
 */
export function extractModules(files: string[]): string[] {
  const modules = new Set<string>();

  for (const file of files) {
    const parts = file.split('/');
    if (parts.length <= 1) {
      modules.add('root');
    } else if (parts[0] === 'src' && parts.length > 2) {
      // For src/X/... use X as the module name
      modules.add(parts[1]);
    } else {
      modules.add(parts[0]);
    }
  }

  return Array.from(modules).sort();
}

/**
 * Generate a human-readable one-line summary.
 */
export function generateSummary(
  message: string,
  classification: string,
  stats: DiffStats,
): string {
  const label = classification.charAt(0).toUpperCase() + classification.slice(1);
  return `${label}: ${message} (+${stats.additions}/-${stats.deletions} in ${stats.filesChanged} file${stats.filesChanged !== 1 ? 's' : ''})`;
}

/**
 * Extract the intent from a commit message or PR title.
 * Returns the first sentence (up to the first period, newline, or end of string).
 */
export function extractIntent(message: string): string {
  const firstLine = message.split('\n')[0].trim();
  const match = firstLine.match(/^(.+?[.!])\s/);
  return match ? match[1] : firstLine;
}
