import json
from typing import Any
from urllib.parse import quote

import click

from .api import github_api_request, gitcode_api_request
from .git_cmd import ensure_git_repo, get_origin_remote, set_upstream
from .platforms import GitPlatform, get_access_token, parse_git_remote_url


def parse_parent_repo(text: str) -> tuple[str, str, bool]:
    """Parse a parent repository from an API response."""
    data: dict[str, Any] = json.loads(text or "{}")
    parent = data.get("parent")
    if not parent:
        return ("", "", False)
    parent_owner, parent_repo = parent["full_name"].split("/")
    return (parent_owner, parent_repo, True)


def get_gitcode_parent_repo(
    owner: str, repo: str, access_token: str
) -> tuple[str, str, bool]:
    """Return the GitCode parent repository."""
    path = f"/api/v5/repos/{owner}/{repo}"
    status, text = gitcode_api_request("GET", path, {"access_token": access_token})
    if status != 200:
        raise click.ClickException(f"get parent repo failed: HTTP {status}: {text}")
    return parse_parent_repo(text)


def get_github_parent_repo(
    owner: str, repo: str, access_token: str
) -> tuple[str, str, bool]:
    """Return the GitHub parent repository."""
    status, text = github_api_request("GET", f"/repos/{owner}/{repo}", access_token)
    if status != 200:
        raise click.ClickException(f"get parent repo failed: HTTP {status}: {text}")
    return parse_parent_repo(text)


def get_parent_repo(
    git_platform: GitPlatform, owner: str, repo: str, access_token: str
) -> tuple[str, str, bool]:
    """Return the parent repository if the current repository is a fork."""
    if git_platform == GitPlatform.GITCODE:
        return get_gitcode_parent_repo(owner, repo, access_token)
    if git_platform == GitPlatform.GITHUB:
        return get_github_parent_repo(owner, repo, access_token)
    raise click.ClickException(f"unsupported git platform: {git_platform.name}")


def get_gitcode_sync_status(
    owner: str, repo: str, access_token: str, branch: str
) -> dict[str, Any]:
    """Return the GitCode fork sync status for a branch."""
    path = f"/api/v5/repos/{owner}/{repo}/sync_repo"
    status, text = gitcode_api_request(
        "GET", path, {"access_token": access_token, "branch": branch}
    )
    if status != 200:
        raise click.ClickException(f"get sync status failed: HTTP {status}: {text}")
    return json.loads(text or "{}")


def get_github_sync_status(
    owner: str, repo: str, access_token: str, branch: str
) -> dict[str, Any]:
    """Return the GitHub fork sync status for a branch."""
    parent_owner, parent_repo, is_fork = get_github_parent_repo(
        owner, repo, access_token
    )
    if not is_fork:
        raise click.ClickException("not a fork repository")

    basehead = f"{parent_owner}:{branch}...{owner}:{branch}"
    status, text = github_api_request(
        "GET",
        f"/repos/{parent_owner}/{parent_repo}/compare/{quote(basehead, safe=':')}",
        access_token,
    )
    if status != 200:
        raise click.ClickException(f"get sync status failed: HTTP {status}: {text}")

    data: dict[str, Any] = json.loads(text or "{}")
    return {
        "status": data.get("status"),
        "ahead_by": data.get("ahead_by"),
        "behind_by": data.get("behind_by"),
    }


def get_sync_status(
    git_platform: GitPlatform,
    owner: str,
    repo: str,
    access_token: str,
    branch: str,
) -> dict[str, Any]:
    """Return the fork sync status for a branch."""
    if git_platform == GitPlatform.GITCODE:
        return get_gitcode_sync_status(owner, repo, access_token, branch)
    if git_platform == GitPlatform.GITHUB:
        return get_github_sync_status(owner, repo, access_token, branch)
    raise click.ClickException(f"unsupported git platform: {git_platform.name}")


def trigger_gitcode_sync(
    owner: str, repo: str, access_token: str, branch: str
) -> dict[str, Any]:
    """Trigger a GitCode fork sync for a branch."""
    path = f"/api/v5/repos/{owner}/{repo}/sync_repo"
    status, text = gitcode_api_request(
        "PUT", path, {"access_token": access_token}, {"branch": branch}
    )
    if status != 200:
        raise click.ClickException(f"trigger sync failed: HTTP {status}: {text}")
    return json.loads(text or "{}")


def trigger_github_sync(
    owner: str, repo: str, access_token: str, branch: str
) -> dict[str, Any]:
    """Trigger a GitHub fork sync for a branch."""
    status, text = github_api_request(
        "POST",
        f"/repos/{owner}/{repo}/merge-upstream",
        access_token,
        {"branch": branch},
    )
    if status != 200:
        raise click.ClickException(f"trigger sync failed: HTTP {status}: {text}")
    return json.loads(text or "{}")


def trigger_sync(
    git_platform: GitPlatform,
    owner: str,
    repo: str,
    access_token: str,
    branch: str,
) -> dict[str, Any]:
    """Trigger a fork sync for a branch."""
    if git_platform == GitPlatform.GITCODE:
        return trigger_gitcode_sync(owner, repo, access_token, branch)
    if git_platform == GitPlatform.GITHUB:
        return trigger_github_sync(owner, repo, access_token, branch)
    raise click.ClickException(f"unsupported git platform: {git_platform.name}")


def setup_upstream_for_current_repo() -> None:
    """Setup upstream remote for the current fork repository."""
    ensure_git_repo()
    origin_remote = parse_git_remote_url(get_origin_remote())
    token = get_access_token(origin_remote.git_platform)
    click.echo(f"Origin: {origin_remote.owner}/{origin_remote.repo}")

    parent_owner, parent_repo, is_fork = get_parent_repo(
        origin_remote.git_platform, origin_remote.owner, origin_remote.repo, token
    )
    if not is_fork:
        raise click.ClickException("not a fork repository")
    click.echo(f"Parent: {parent_owner}/{parent_repo}")
    set_upstream(parent_owner, parent_repo, origin_remote.prefix, origin_remote.suffix)


def sync_fork_branch(branch: str, status: bool) -> None:
    """Sync a fork branch with its upstream source repository."""
    ensure_git_repo()
    origin_remote = parse_git_remote_url(get_origin_remote())
    click.echo(f"Fork: {origin_remote.owner}/{origin_remote.repo}", err=True)

    token = get_access_token(origin_remote.git_platform)
    if status:
        result = get_sync_status(
            origin_remote.git_platform,
            origin_remote.owner,
            origin_remote.repo,
            token,
            branch,
        )
        click.echo(json.dumps(result, ensure_ascii=False))
        return

    parent_owner, parent_repo, is_fork = get_parent_repo(
        origin_remote.git_platform, origin_remote.owner, origin_remote.repo, token
    )
    if not is_fork:
        raise click.ClickException("not a fork repository")
    click.echo(f"Upstream: {parent_owner}/{parent_repo}", err=True)

    click.echo(f"Syncing fork with upstream (branch: {branch})...", err=True)
    result = trigger_sync(
        origin_remote.git_platform,
        origin_remote.owner,
        origin_remote.repo,
        token,
        branch,
    )
    click.echo(json.dumps(result, ensure_ascii=False))
