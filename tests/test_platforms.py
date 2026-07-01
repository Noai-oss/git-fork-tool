import unittest

import click

from git_fork_tool.platforms import GitPlatform, parse_git_remote_url


class ParseGitRemoteUrlTests(unittest.TestCase):
    def test_parses_github_https_remote(self) -> None:
        remote = parse_git_remote_url("https://github.com/owner/repo.git")

        self.assertEqual(remote.owner, "owner")
        self.assertEqual(remote.repo, "repo")
        self.assertEqual(remote.prefix, "https://github.com/")
        self.assertEqual(remote.suffix, ".git")
        self.assertEqual(remote.git_platform, GitPlatform.GITHUB)

    def test_preserves_missing_git_suffix(self) -> None:
        remote = parse_git_remote_url("https://github.com/owner/repo")

        self.assertEqual(remote.owner, "owner")
        self.assertEqual(remote.repo, "repo")
        self.assertEqual(remote.suffix, "")

    def test_parses_gitcode_ssh_remote(self) -> None:
        remote = parse_git_remote_url("git@gitcode.com:owner/repo.git")

        self.assertEqual(remote.owner, "owner")
        self.assertEqual(remote.repo, "repo")
        self.assertEqual(remote.prefix, "git@gitcode.com:")
        self.assertEqual(remote.suffix, ".git")
        self.assertEqual(remote.git_platform, GitPlatform.GITCODE)

    def test_rejects_unsupported_remote_host(self) -> None:
        with self.assertRaises(click.ClickException):
            parse_git_remote_url("https://example.com/owner/repo.git")

    def test_rejects_malformed_supported_remote(self) -> None:
        with self.assertRaises(click.ClickException):
            parse_git_remote_url("https://github.com/owner-only.git")


if __name__ == "__main__":
    unittest.main()
