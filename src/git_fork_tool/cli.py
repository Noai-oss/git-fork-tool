import http.client
import json
import os
import subprocess
from contextlib import closing
from enum import Enum
from typing import Any
from urllib.parse import urlencode

import click


GITCODE_API_HOST = "api.gitcode.com"


class GIT_PLATFORM(Enum):
    GITCODE = 0
    GITHUB = 1


def gitcode_api_request(
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, str] | None = None,
) -> tuple[int, str]:
    headers = {"Accept": "application/json"}
    payload: bytes | None = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    url = path
    if query:
        url = f"{path}?{urlencode(query)}"

    with closing(http.client.HTTPSConnection(GITCODE_API_HOST, timeout=30)) as conn:
        conn.request(method, url, body=payload, headers=headers)
        res = conn.getresponse()
        text = res.read().decode("utf-8")

    return res.status, text


def get_gc_token() -> str:
    token = os.environ.get("GC_TOKEN") or os.environ.get("GITCODE_TOKEN")
    if not token:
        raise click.ClickException(
            "missing GitCode token: set GC_TOKEN or GITCODE_TOKEN"
        )
    return token


def get_parent_repo(
    git_platform: GIT_PLATFORM, owner: str, repo: str, access_token: str
) -> tuple[str, str, bool]:
    if git_platform != GIT_PLATFORM.GITCODE:
        raise click.ClickException(f"unsupported git platform: {git_platform.name}")

    path = f"/api/v5/repos/{owner}/{repo}"
    status, text = gitcode_api_request("GET", path, {"access_token": access_token})
    if status != 200:
        raise click.ClickException(f"get parent repo failed: HTTP {status}: {text}")

    data: dict[str, Any] = json.loads(text or "{}")
    parent = data.get("parent")
    if not parent:
        return ("", "", False)
    parent_owner, parent_repo = parent["full_name"].split("/")
    return (parent_owner, parent_repo, True)


def get_sync_status(
    git_platform: GIT_PLATFORM,
    owner: str,
    repo: str,
    access_token: str,
    branch: str,
) -> dict[str, Any]:
    if git_platform != GIT_PLATFORM.GITCODE:
        raise click.ClickException(f"unsupported git platform: {git_platform.name}")

    path = f"/api/v5/repos/{owner}/{repo}/sync_repo"
    status, text = gitcode_api_request(
        "GET", path, {"access_token": access_token, "branch": branch}
    )
    if status != 200:
        raise click.ClickException(f"get sync status failed: HTTP {status}: {text}")
    return json.loads(text or "{}")


def trigger_sync(
    git_platform: GIT_PLATFORM,
    owner: str,
    repo: str,
    access_token: str,
    branch: str,
) -> dict[str, Any]:
    if git_platform != GIT_PLATFORM.GITCODE:
        raise click.ClickException(f"unsupported git platform: {git_platform.name}")

    path = f"/api/v5/repos/{owner}/{repo}/sync_repo"
    status, text = gitcode_api_request(
        "PUT", path, {"access_token": access_token}, {"branch": branch}
    )
    if status != 200:
        raise click.ClickException(f"trigger sync failed: HTTP {status}: {text}")
    return json.loads(text or "{}")


def get_owner_repo_from_origin_remote(
    remote_url: str,
) -> tuple[str, str, str, str, GIT_PLATFORM]:
    suffix = ".git"
    if remote_url.startswith("https://gitcode.com/"):
        prefix = "https://gitcode.com/"
        path = remote_url.removeprefix(prefix).removesuffix(suffix)
    elif remote_url.startswith("git@gitcode.com:"):
        prefix = "git@gitcode.com:"
        path = remote_url.removeprefix(prefix).removesuffix(suffix)
    else:
        raise click.ClickException(f"unsupported origin remote: {remote_url}")
    owner, repo = path.split("/")
    return owner, repo, prefix, suffix, GIT_PLATFORM.GITCODE


def get_origin_remote() -> str:
    cmds = ["git", "remote", "get-url", "origin"]
    res = subprocess.run(cmds, capture_output=True, text=True)
    if res.returncode != 0:
        raise click.ClickException(f"failed to get origin remote: {res.stderr.strip()}")
    return res.stdout.strip()


def is_git_repo() -> bool:
    cmds = ["git", "rev-parse", "--is-inside-work-tree"]
    res = subprocess.run(cmds, capture_output=True, text=True)
    return res.returncode == 0 and res.stdout.strip() == "true"


def set_upstream(owner: str, repo: str, prefix: str, suffix: str) -> None:
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
    token = get_gc_token()
    origin_url = get_origin_remote()
    owner, repo, prefix, suffix, git_platform = get_owner_repo_from_origin_remote(
        origin_url
    )
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
    token = get_gc_token()
    origin_url = get_origin_remote()
    owner, repo, prefix, suffix, git_platform = get_owner_repo_from_origin_remote(
        origin_url
    )
    click.echo(f"Fork: {owner}/{repo}")

    if status:
        result = get_sync_status(git_platform, owner, repo, token, branch)
        click.echo(f"Sync status: {result}")
        return

    parent_owner, parent_repo, is_fork = get_parent_repo(
        git_platform, owner, repo, token
    )
    if not is_fork:
        raise click.ClickException("not a fork repository")
    click.echo(f"Upstream: {parent_owner}/{parent_repo}")

    click.echo(f"Syncing fork with upstream (branch: {branch})...")
    result = trigger_sync(git_platform, owner, repo, token, branch)
    click.echo(f"Sync triggered: {result}")
