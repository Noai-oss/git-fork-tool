import unittest
from unittest.mock import patch

import click

from git_fork_tool.platforms import GitPlatform
from git_fork_tool.pr import pr_refspec, pr_source_ref, resolve_pr_platform


class PrRefspecTests(unittest.TestCase):
    def test_github_source_ref(self) -> None:
        self.assertEqual(pr_source_ref(GitPlatform.GITHUB, 123), "refs/pull/123/head")

    def test_gitcode_source_ref(self) -> None:
        self.assertEqual(
            pr_source_ref(GitPlatform.GITCODE, 123),
            "refs/merge-requests/123/head",
        )

    def test_fetch_refspec_uses_stable_local_ref(self) -> None:
        self.assertEqual(
            pr_refspec("upstream", 123, GitPlatform.GITCODE),
            "+refs/merge-requests/123/head:refs/remotes/upstream/pr/123",
        )


class ResolvePrPlatformTests(unittest.TestCase):
    def test_resolves_platform_from_remote_url(self) -> None:
        with patch(
            "git_fork_tool.pr.find_remote_url",
            return_value="https://gitcode.com/owner/repo.git",
        ):
            self.assertEqual(resolve_pr_platform("upstream"), GitPlatform.GITCODE)

    def test_missing_remote_mentions_repo_init(self) -> None:
        with patch("git_fork_tool.pr.find_remote_url", return_value=None):
            with self.assertRaisesRegex(click.ClickException, "gft repo init"):
                resolve_pr_platform("upstream")

    def test_unsupported_remote_mentions_remote_name(self) -> None:
        with patch(
            "git_fork_tool.pr.find_remote_url",
            return_value="https://example.com/owner/repo.git",
        ):
            with self.assertRaisesRegex(click.ClickException, "unsupported remote"):
                resolve_pr_platform("upstream")


if __name__ == "__main__":
    unittest.main()
