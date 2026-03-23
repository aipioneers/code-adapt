import { Octokit } from '@octokit/rest';
import { ValidationError } from '../lib/errors.js';
import { outputWarning } from './output.js';
import type { CommitSummary, PRSummary, ReleaseSummary } from '../models/observation.js';

/**
 * Create an authenticated Octokit instance.
 */
export function createOctokit(token: string): Octokit {
  return new Octokit({ auth: token });
}

/**
 * Extract owner and repo name from a GitHub URL.
 *
 * Supports:
 *   - https://github.com/owner/repo
 *   - https://github.com/owner/repo.git
 *   - git@github.com:owner/repo.git
 */
export function parseRepoUrl(url: string): { owner: string; repo: string } {
  // HTTPS format
  const httpsMatch = url.match(/github\.com\/([^/]+)\/([^/.]+)(?:\.git)?/);
  if (httpsMatch) {
    return { owner: httpsMatch[1], repo: httpsMatch[2] };
  }

  // SSH format
  const sshMatch = url.match(/github\.com:([^/]+)\/([^/.]+)(?:\.git)?/);
  if (sshMatch) {
    return { owner: sshMatch[1], repo: sshMatch[2] };
  }

  throw new ValidationError(`Cannot parse GitHub owner/repo from URL: ${url}`);
}

/**
 * Check rate-limit headers and warn if running low.
 */
function checkRateLimit(headers: Record<string, string | number | undefined>): void {
  const remaining = headers['x-ratelimit-remaining'];
  if (remaining !== undefined && Number(remaining) < 100) {
    outputWarning(`GitHub API rate limit low: ${remaining} requests remaining.`);
  }
}

/**
 * Fetch commits from a repository, optionally since a given date.
 */
export async function fetchCommits(
  octokit: Octokit,
  owner: string,
  repo: string,
  since?: Date,
): Promise<CommitSummary[]> {
  const params: Record<string, unknown> = {
    owner,
    repo,
    per_page: 100,
  };
  if (since) {
    params.since = since.toISOString();
  }

  const response = await octokit.repos.listCommits(params as Parameters<typeof octokit.repos.listCommits>[0]);
  checkRateLimit(response.headers as Record<string, string | number | undefined>);

  return response.data.map((c) => ({
    sha: c.sha,
    message: c.commit.message.split('\n')[0],
    author: c.commit.author?.name ?? c.author?.login ?? 'unknown',
    date: c.commit.author?.date ?? '',
  }));
}

/**
 * Fetch pull requests from a repository, optionally filtered by date.
 */
export async function fetchPullRequests(
  octokit: Octokit,
  owner: string,
  repo: string,
  since?: Date,
): Promise<PRSummary[]> {
  const response = await octokit.pulls.list({
    owner,
    repo,
    state: 'all',
    sort: 'updated',
    direction: 'desc',
    per_page: 100,
  });
  checkRateLimit(response.headers as Record<string, string | number | undefined>);

  let prs = response.data;
  if (since) {
    const sinceTime = since.getTime();
    prs = prs.filter((pr) => new Date(pr.updated_at).getTime() >= sinceTime);
  }

  return prs.map((pr) => ({
    number: pr.number,
    title: pr.title,
    state: pr.state,
    author: pr.user?.login ?? 'unknown',
    url: pr.html_url,
  }));
}

/**
 * Fetch releases from a repository, optionally filtered by date.
 */
export async function fetchReleases(
  octokit: Octokit,
  owner: string,
  repo: string,
  since?: Date,
): Promise<ReleaseSummary[]> {
  const response = await octokit.repos.listReleases({
    owner,
    repo,
    per_page: 100,
  });
  checkRateLimit(response.headers as Record<string, string | number | undefined>);

  let releases = response.data;
  if (since) {
    const sinceTime = since.getTime();
    releases = releases.filter(
      (r) => r.published_at && new Date(r.published_at).getTime() >= sinceTime,
    );
  }

  return releases.map((r) => ({
    tag: r.tag_name,
    name: r.name ?? r.tag_name,
    date: r.published_at ?? r.created_at,
    url: r.html_url,
  }));
}

/**
 * Fetch diff information for a specific pull request.
 */
export async function fetchPRDiff(
  octokit: Octokit,
  owner: string,
  repo: string,
  prNumber: number,
): Promise<{ files: string[]; additions: number; deletions: number; patch: string }> {
  const [prResponse, filesResponse] = await Promise.all([
    octokit.pulls.get({ owner, repo, pull_number: prNumber }),
    octokit.pulls.listFiles({ owner, repo, pull_number: prNumber, per_page: 100 }),
  ]);

  checkRateLimit(prResponse.headers as Record<string, string | number | undefined>);

  const files = filesResponse.data.map((f) => f.filename);
  const additions = filesResponse.data.reduce((sum, f) => sum + f.additions, 0);
  const deletions = filesResponse.data.reduce((sum, f) => sum + f.deletions, 0);
  const patch = filesResponse.data.map((f) => f.patch ?? '').join('\n');

  return { files, additions, deletions, patch };
}

/**
 * Fetch diff information for a specific commit.
 */
export async function fetchCommitDiff(
  octokit: Octokit,
  owner: string,
  repo: string,
  sha: string,
): Promise<{ files: string[]; additions: number; deletions: number; message: string }> {
  const response = await octokit.repos.getCommit({ owner, repo, ref: sha });
  checkRateLimit(response.headers as Record<string, string | number | undefined>);

  const commitFiles = response.data.files ?? [];
  const files = commitFiles.map((f) => f.filename);
  const additions = commitFiles.reduce((sum, f) => sum + f.additions, 0);
  const deletions = commitFiles.reduce((sum, f) => sum + f.deletions, 0);
  const message = response.data.commit.message;

  return { files, additions, deletions, message };
}
