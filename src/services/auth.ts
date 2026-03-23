import { execFileSync } from 'node:child_process';
import { AuthError } from '../lib/errors.js';

/**
 * Obtain a GitHub personal access token.
 *
 * Resolution order:
 *   1. `gh auth token` subprocess
 *   2. GITHUB_TOKEN environment variable
 *   3. Throw AuthError
 */
export function getGitHubToken(): string {
  // 1. Try `gh auth token`
  try {
    const result = execFileSync('gh', ['auth', 'token'], {
      encoding: 'utf-8',
      timeout: 10_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    const token = result.trim();
    if (token.length > 0) {
      return token;
    }
  } catch {
    // gh CLI not available or not authenticated — continue
  }

  // 2. Check GITHUB_TOKEN environment variable
  const envToken = process.env.GITHUB_TOKEN;
  if (envToken && envToken.trim().length > 0) {
    return envToken.trim();
  }

  // 3. No token available
  throw new AuthError(
    'No GitHub token found. Either run "gh auth login" or set the GITHUB_TOKEN environment variable.',
  );
}
