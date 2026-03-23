export class AdaptError extends Error {
  constructor(
    message: string,
    public code: number = 1,
  ) {
    super(message);
    this.name = 'AdaptError';
  }
}

export class NotInitializedError extends AdaptError {
  constructor() {
    super("Project not initialized. Run 'adapt init' first.", 2);
    this.name = 'NotInitializedError';
  }
}

export class RepoNotFoundError extends AdaptError {
  constructor(repo: string) {
    super(`Repository not found: ${repo}`, 3);
    this.name = 'RepoNotFoundError';
  }
}

export class AuthError extends AdaptError {
  constructor(message = 'Authentication failed. Check your GITHUB_TOKEN.') {
    super(message, 4);
    this.name = 'AuthError';
  }
}

export class ValidationError extends AdaptError {
  constructor(message: string) {
    super(message, 5);
    this.name = 'ValidationError';
  }
}

export class AdaptationNotFoundError extends AdaptError {
  constructor(id: string) {
    super(`Adaptation not found: ${id}`, 6);
    this.name = 'AdaptationNotFoundError';
  }
}
