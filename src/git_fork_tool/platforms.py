import os
from dataclasses import dataclass
from enum import Enum

import click


class GitPlatform(Enum):
    GITCODE = 0
    GITHUB = 1


@dataclass(frozen=True)
class GitRemote:
    owner: str
    repo: str
    prefix: str
    suffix: str
    git_platform: GitPlatform


def parse_git_remote_url(remote_url: str) -> GitRemote:
    """Parse owner, repository, URL pieces, and platform from a remote URL."""
    normalized_url = remote_url.rstrip("/")
    suffix = ".git" if normalized_url.endswith(".git") else ""
    if normalized_url.startswith("https://gitcode.com/"):
        prefix = "https://gitcode.com/"
        git_platform = GitPlatform.GITCODE
    elif normalized_url.startswith("git@gitcode.com:"):
        prefix = "git@gitcode.com:"
        git_platform = GitPlatform.GITCODE
    elif normalized_url.startswith("https://github.com/"):
        prefix = "https://github.com/"
        git_platform = GitPlatform.GITHUB
    elif normalized_url.startswith("git@github.com:"):
        prefix = "git@github.com:"
        git_platform = GitPlatform.GITHUB
    else:
        raise click.ClickException(f"unsupported remote URL: {remote_url}")

    path = normalized_url.removeprefix(prefix).removesuffix(suffix)
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        raise click.ClickException(f"unsupported remote URL: {remote_url}")

    owner, repo = parts
    return GitRemote(owner, repo, prefix, suffix, git_platform)


def get_access_token(git_platform: GitPlatform) -> str:
    """Read the access token for the selected git platform."""
    if git_platform == GitPlatform.GITCODE:
        token = os.environ.get("GC_TOKEN") or os.environ.get("GITCODE_TOKEN")
        token_names = "GC_TOKEN or GITCODE_TOKEN"
    elif git_platform == GitPlatform.GITHUB:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        token_names = "GH_TOKEN or GITHUB_TOKEN"
    else:
        raise click.ClickException(f"unsupported git platform: {git_platform.name}")

    if not token:
        raise click.ClickException(
            f"missing {git_platform.name} token: set {token_names}"
        )
    return token
