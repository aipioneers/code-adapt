"""Custom error hierarchy for code-adapt."""


class AdaptError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class NotInitializedError(AdaptError):
    def __init__(self):
        super().__init__("Project not initialized. Run 'code-adapt init' first.", 2)


class RepoNotFoundError(AdaptError):
    def __init__(self, repo: str):
        super().__init__(f"Repository not found: {repo}", 3)


class AuthError(AdaptError):
    def __init__(self, message: str = "Authentication failed. Check your GITHUB_TOKEN."):
        super().__init__(message, 4)


class ValidationError(AdaptError):
    def __init__(self, message: str):
        super().__init__(message, 5)


class AdaptationNotFoundError(AdaptError):
    def __init__(self, adaptation_id: str):
        super().__init__(f"Adaptation not found: {adaptation_id}", 6)
