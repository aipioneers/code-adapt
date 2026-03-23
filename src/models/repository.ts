import { ValidationError } from '../lib/errors.js';

export interface Repository {
  name: string;
  url: string;
  type: 'upstream' | 'downstream';
  defaultBranch: string;
  license: string | null;
  techStack: string[];
  addedAt: string; // ISO 8601
}

/**
 * Validate and normalise a partial Repository object into a full Repository.
 * Throws ValidationError when required fields are missing or have invalid values.
 */
export function validateRepository(repo: Partial<Repository>): Repository {
  if (!repo.name || repo.name.trim().length === 0) {
    throw new ValidationError('Repository name is required.');
  }

  if (!repo.url || repo.url.trim().length === 0) {
    throw new ValidationError('Repository URL is required.');
  }

  if (repo.type !== 'upstream' && repo.type !== 'downstream') {
    throw new ValidationError('Repository type must be "upstream" or "downstream".');
  }

  return {
    name: repo.name.trim(),
    url: repo.url.trim(),
    type: repo.type,
    defaultBranch: repo.defaultBranch?.trim() || 'main',
    license: repo.license ?? null,
    techStack: repo.techStack ?? [],
    addedAt: repo.addedAt ?? new Date().toISOString(),
  };
}
