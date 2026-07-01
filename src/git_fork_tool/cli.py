import click

from .git_cmd import UPSTREAM_REMOTE, ensure_git_repo
from .pr import fetch_pr_ref, pr_refspec, pr_remote_ref, resolve_pr_platform
from .repo import setup_upstream_for_current_repo, sync_fork_branch


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
@click.argument("branch", metavar="BRANCH")
@click.option(
    "--status",
    "-s",
    is_flag=True,
    default=False,
    help="Only show sync status without triggering sync",
)
def repo_sync(branch: str, status: bool) -> None:
    """Sync fork repository with upstream source repository."""
    sync_fork_branch(branch, status)


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
    git_platform = resolve_pr_platform(remote)
    ref = fetch_pr_ref(pr_number, remote, git_platform)
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
    git_platform = resolve_pr_platform(remote)
    click.echo(pr_refspec(remote, pr_number, git_platform))
