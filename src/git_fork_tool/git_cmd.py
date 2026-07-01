import subprocess

import click


UPSTREAM_REMOTE = "upstream"


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command and optionally raise a ClickException on failure."""
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        detail = res.stderr.strip() or res.stdout.strip()
        raise click.ClickException(f"git {' '.join(args)} failed: {detail}")
    return res


def is_git_repo() -> bool:
    """Return whether the current directory is inside a git work tree."""
    res = run_git(["rev-parse", "--is-inside-work-tree"], check=False)
    return res.returncode == 0 and res.stdout.strip() == "true"


def ensure_git_repo() -> None:
    """Raise if the current directory is not inside a git work tree."""
    if not is_git_repo():
        raise click.ClickException("not a git repository")


def find_remote_url(remote: str) -> str | None:
    """Return a configured remote URL, or None if the remote does not exist."""
    res = run_git(["remote", "get-url", remote], check=False)
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def get_remote_url(remote: str) -> str:
    """Return a configured remote URL."""
    remote_url = find_remote_url(remote)
    if remote_url is None:
        raise click.ClickException(f"remote {remote!r} does not exist")
    return remote_url


def get_origin_remote() -> str:
    """Return the origin remote URL for the current repository."""
    return get_remote_url("origin")


def set_upstream(owner: str, repo: str, prefix: str, suffix: str) -> None:
    """Add the parent repository as the upstream remote."""
    upstream_url = f"{prefix}{owner}/{repo}{suffix}"
    current_url = find_remote_url(UPSTREAM_REMOTE)
    if current_url is not None:
        if current_url == upstream_url:
            click.echo(f"Upstream remote already configured: {owner}/{repo}")
            return
        raise click.ClickException(
            f"upstream remote already exists with a different URL: {current_url}"
        )
    run_git(["remote", "add", UPSTREAM_REMOTE, upstream_url])
    click.echo(f"Upstream remote added: {owner}/{repo}")
