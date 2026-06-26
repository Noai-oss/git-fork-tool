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
UPSTREAM_REMOTE = "upstream"


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
    return git_output(["remote", "get-url", "origin"])


def is_git_repo() -> bool:
    """Return whether the current directory is inside a git work tree."""
    res = run_git(["rev-parse", "--is-inside-work-tree"], check=False)
    return res.returncode == 0 and res.stdout.strip() == "true"


def ensure_git_repo() -> None:
    """Raise if the current directory is not inside a git work tree."""
    if not is_git_repo():
        raise click.ClickException("not a git repository")


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command and optionally raise a ClickException on failure."""
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        detail = res.stderr.strip() or res.stdout.strip()
        raise click.ClickException(f"git {' '.join(args)} failed: {detail}")
    return res


def git_output(args: list[str]) -> str:
    """Run a git command and return stripped stdout."""
    return run_git(args).stdout.strip()


def remote_exists(remote: str) -> bool:
    """Return whether a git remote exists."""
    return run_git(["remote", "get-url", remote], check=False).returncode == 0


def pr_remote_ref(remote: str, pr_number: int) -> str:
    """Return the local remote-tracking ref used for a PR."""
    return f"refs/remotes/{remote}/pr/{pr_number}"


def pr_refspec(remote: str, pr_number: int) -> str:
    """Return the fetch refspec used for a PR."""
    return f"+refs/pull/{pr_number}/head:{pr_remote_ref(remote, pr_number)}"


def fetch_pr_ref(pr_number: int, remote: str) -> str:
    """Fetch an upstream PR into a stable local remote-tracking ref."""
    if not remote_exists(remote):
        raise click.ClickException(f"remote {remote!r} does not exist")

    ref = pr_remote_ref(remote, pr_number)
    run_git(["fetch", remote, pr_refspec(remote, pr_number)])
    return ref


def set_upstream(owner: str, repo: str, prefix: str, suffix: str) -> None:
    """Add the parent repository as the upstream remote."""
    upstream_url = f"{prefix}{owner}/{repo}{suffix}"
    if remote_exists(UPSTREAM_REMOTE):
        current_url = git_output(["remote", "get-url", UPSTREAM_REMOTE])
        if current_url == upstream_url:
            click.echo(f"Upstream remote already configured: {owner}/{repo}")
            return
        raise click.ClickException(
            f"upstream remote already exists with a different URL: {current_url}"
        )
    run_git(["remote", "add", UPSTREAM_REMOTE, upstream_url])
    click.echo(f"Upstream remote added: {owner}/{repo}")


def setup_upstream_for_current_repo() -> None:
    """Setup upstream remote for the current fork repository."""
    ensure_git_repo()
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


def sync_fork_branch(branch: str, status: bool) -> None:
    """Sync a fork branch with its upstream source repository."""
    ensure_git_repo()
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


def resolve_branch(branch_arg: str | None, branch_option: str | None) -> str:
    """Resolve a branch from positional and option forms."""
    if branch_arg and branch_option and branch_arg != branch_option:
        raise click.ClickException("pass the branch either as BRANCH or --branch")
    branch = branch_option or branch_arg
    if not branch:
        raise click.ClickException("missing branch: pass BRANCH or --branch")
    return branch


@click.group()
def cli() -> None:
    """Git Fork Tool - Manage fork relationships."""
    pass


@cli.group()
def repo() -> None:
    """Manage fork repository remotes and sync."""
    pass


@repo.command("init")
def repo_init() -> None:
    """Setup upstream remote for fork repository."""
    setup_upstream_for_current_repo()


@repo.command("sync")
@click.argument("branch_arg", required=False, metavar="BRANCH")
@click.option("--branch", "-b", "branch_option", help="Branch to sync")
@click.option(
    "--status",
    "-s",
    is_flag=True,
    default=False,
    help="Only show sync status without triggering sync",
)
def repo_sync(branch_arg: str | None, branch_option: str | None, status: bool) -> None:
    """Sync fork repository with upstream source repository."""
    sync_fork_branch(resolve_branch(branch_arg, branch_option), status)


@cli.group()
def pr() -> None:
    """Work with upstream pull requests."""
    pass


@pr.command("fetch")
@click.argument("pr_number", type=int, metavar="PR_NUMBER")
@click.option(
    "--remote",
    "-r",
    default=UPSTREAM_REMOTE,
    show_default=True,
    help="Remote that contains pull request refs",
)
def pr_fetch(pr_number: int, remote: str) -> None:
    """Fetch a pull request and print its local ref."""
    ensure_git_repo()
    ref = fetch_pr_ref(pr_number, remote)
    click.echo(ref)


@pr.command("ref")
@click.argument("pr_number", type=int, metavar="PR_NUMBER")
@click.option(
    "--remote",
    "-r",
    default=UPSTREAM_REMOTE,
    show_default=True,
    help="Remote name used for the local PR ref",
)
def pr_ref(pr_number: int, remote: str) -> None:
    """Print the local ref used for a pull request."""
    click.echo(pr_remote_ref(remote, pr_number))


@pr.command("refspec")
@click.argument("pr_number", type=int, metavar="PR_NUMBER")
@click.option(
    "--remote",
    "-r",
    default=UPSTREAM_REMOTE,
    show_default=True,
    help="Remote name used for the local PR ref",
)
def pr_refspec_command(pr_number: int, remote: str) -> None:
    """Print the refspec used to fetch a pull request."""
    click.echo(pr_refspec(remote, pr_number))
