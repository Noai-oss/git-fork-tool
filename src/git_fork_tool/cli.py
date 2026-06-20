import http.client
import json
import os
import subprocess
from contextlib import closing
from enum import Enum
from typing import Any
from urllib.parse import quote, urlencode

import click


GITCODE_API_HOST = "api.gitcode.com"
GITHUB_API_HOST = "api.github.com"


class GitPlatform(Enum):
    GITCODE = 0
    GITHUB = 1


def api_request(
    host: str,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Send a JSON HTTP request and return the status code and response text."""
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    payload: bytes | None = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    url = path
    if query:
        url = f"{path}?{urlencode(query)}"

    with closing(http.client.HTTPSConnection(host, timeout=30)) as conn:
        conn.request(method, url, body=payload, headers=request_headers)
        res = conn.getresponse()
        text = res.read().decode("utf-8")

    return res.status, text


def gitcode_api_request(
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Call the GitCode API."""
    return api_request(GITCODE_API_HOST, method, path, query, body)


def github_api_request(
    method: str,
    path: str,
    access_token: str,
    body: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Call the GitHub API."""
    return api_request(
        GITHUB_API_HOST,
        method,
        path,
        body=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "git-fork-tool",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )


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


def get_parent_repo(
    git_platform: GitPlatform, owner: str, repo: str, access_token: str
) -> tuple[str, str, bool]:
    """Return the parent repository if the current repository is a fork."""
    if git_platform == GitPlatform.GITCODE:
        return get_gitcode_parent_repo(owner, repo, access_token)
    if git_platform == GitPlatform.GITHUB:
        return get_github_parent_repo(owner, repo, access_token)
    raise click.ClickException(f"unsupported git platform: {git_platform.name}")


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


def get_owner_repo_from_origin_remote(
    remote_url: str,
) -> tuple[str, str, str, str, GitPlatform]:
    """Parse owner, repository, URL pieces, and platform from an origin remote."""
    suffix = ".git"
    if remote_url.startswith("https://gitcode.com/"):
        prefix = "https://gitcode.com/"
        git_platform = GitPlatform.GITCODE
    elif remote_url.startswith("git@gitcode.com:"):
        prefix = "git@gitcode.com:"
        git_platform = GitPlatform.GITCODE
    elif remote_url.startswith("https://github.com/"):
        prefix = "https://github.com/"
        git_platform = GitPlatform.GITHUB
    elif remote_url.startswith("git@github.com:"):
        prefix = "git@github.com:"
        git_platform = GitPlatform.GITHUB
    else:
        raise click.ClickException(f"unsupported origin remote: {remote_url}")

    path = remote_url.removeprefix(prefix).removesuffix(suffix)
    owner, repo = path.split("/")
    return owner, repo, prefix, suffix, git_platform


def get_origin_remote() -> str:
    """Return the origin remote URL for the current repository."""
    cmds = ["git", "remote", "get-url", "origin"]
    res = subprocess.run(cmds, capture_output=True, text=True)
    if res.returncode != 0:
        raise click.ClickException(f"failed to get origin remote: {res.stderr.strip()}")
    return res.stdout.strip()


def is_git_repo() -> bool:
    """Return whether the current directory is inside a git work tree."""
    cmds = ["git", "rev-parse", "--is-inside-work-tree"]
    res = subprocess.run(cmds, capture_output=True, text=True)
    return res.returncode == 0 and res.stdout.strip() == "true"


def set_upstream(owner: str, repo: str, prefix: str, suffix: str) -> None:
    """Add the parent repository as the upstream remote."""
    upstream_url = f"{prefix}{owner}/{repo}{suffix}"
    cmds = ["git", "remote", "add", "upstream", upstream_url]
    res = subprocess.run(cmds, capture_output=True, text=True)
    if res.returncode != 0:
        raise click.ClickException(
            f"failed to add upstream remote: {res.stderr.strip()}"
        )
    click.echo(f"Upstream remote added: {owner}/{repo}")


@click.group()
def cli() -> None:
    """Git Fork Tool - Manage fork relationships"""
    pass


@cli.command()
def setup() -> None:
    """Setup upstream remote for fork repository"""
    if not is_git_repo():
        raise click.ClickException("not a git repository")
    origin_url = get_origin_remote()
    owner, repo, prefix, suffix, git_platform = get_owner_repo_from_origin_remote(
        origin_url
    )
    token = get_access_token(git_platform)
    click.echo(f"Origin: {owner}/{repo}")

    parent_owner, parent_repo, is_fork = get_parent_repo(
        git_platform, owner, repo, token
    )
    if not is_fork:
        raise click.ClickException("not a fork repository")
    click.echo(f"Parent: {parent_owner}/{parent_repo}")
    set_upstream(parent_owner, parent_repo, prefix, suffix)


@cli.command()
@click.option("--branch", "-b", required=True, help="Branch to sync from upstream")
@click.option(
    "--status",
    "-s",
    is_flag=True,
    default=False,
    help="Only show sync status without triggering sync",
)
def sync(branch: str, status: bool) -> None:
    """Sync fork repository with upstream source repository"""
    if not is_git_repo():
        raise click.ClickException("not a git repository")
    origin_url = get_origin_remote()
    owner, repo, _, _, git_platform = get_owner_repo_from_origin_remote(origin_url)
    click.echo(f"Fork: {owner}/{repo}", err=True)

    if status:
        token = get_access_token(git_platform)
        result = get_sync_status(git_platform, owner, repo, token, branch)
        click.echo(json.dumps(result, ensure_ascii=False))
        return

    token = get_access_token(git_platform)
    parent_owner, parent_repo, is_fork = get_parent_repo(
        git_platform, owner, repo, token
    )
    if not is_fork:
        raise click.ClickException("not a fork repository")
    click.echo(f"Upstream: {parent_owner}/{parent_repo}", err=True)

    click.echo(f"Syncing fork with upstream (branch: {branch})...", err=True)
    result = trigger_sync(git_platform, owner, repo, token, branch)
    click.echo(json.dumps(result, ensure_ascii=False))
