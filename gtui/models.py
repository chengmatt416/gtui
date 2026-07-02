from dataclasses import dataclass


@dataclass
class GitInfo:
    """Structured representation of repository status information."""

    is_repo: bool
    branch: str
    staged: int
    unstaged: int
    remote_url: str
