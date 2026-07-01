import click

from .git_cmd import find_remote_url, run_git
from .platforms import GitPlatform, parse_git_remote_url


def resolve_pr_platform(remote: str) -> GitPlatform:
    """Resolve the platform used for pull request or merge request refs."""
    remote_url = find_remote_url(remote)
    if remote_url is None:
        raise click.ClickException(
            f"remote {remote!r} does not exist; run `gft repo init` first"
        )

    try:
        return parse_git_remote_url(remote_url).git_platform
    except click.ClickException as exc:
        raise click.ClickException(
            f"unsupported remote {remote!r}: {remote_url}"
        ) from exc


def pr_remote_ref(remote: str, pr_number: int) -> str:
    """Return the local remote-tracking ref used for a PR."""
    return f"refs/remotes/{remote}/pr/{pr_number}"


def pr_source_ref(git_platform: GitPlatform, pr_number: int) -> str:
    """Return the remote source ref for a pull or merge request."""
    if git_platform == GitPlatform.GITCODE:
        return f"refs/merge-requests/{pr_number}/head"
    if git_platform == GitPlatform.GITHUB:
        return f"refs/pull/{pr_number}/head"
    raise click.ClickException(f"unsupported git platform: {git_platform.name}")


def pr_refspec(remote: str, pr_number: int, git_platform: GitPlatform) -> str:
    """Return the fetch refspec used for a PR."""
    return (
        f"+{pr_source_ref(git_platform, pr_number)}:{pr_remote_ref(remote, pr_number)}"
    )


def fetch_pr_ref(pr_number: int, remote: str, git_platform: GitPlatform) -> str:
    """Fetch an upstream PR into a stable local remote-tracking ref."""
    ref = pr_remote_ref(remote, pr_number)
    run_git(["fetch", remote, pr_refspec(remote, pr_number, git_platform)])
    return ref
