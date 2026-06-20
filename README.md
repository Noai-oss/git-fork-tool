# git-fork-tool

A lightweight CLI for working with Git fork repositories.

Currently supports GitCode and GitHub.

## Usage

Set an access token:

```sh
export GC_TOKEN=your_token
# or
export GH_TOKEN=your_token
```

Add the parent repository as `upstream`:

```sh
gft setup
```

Check fork sync status:

```sh
gft sync --branch main --status
```

Trigger a fork sync:

```sh
gft sync --branch main
```

## Notes

- `GITCODE_TOKEN` can be used instead of `GC_TOKEN`.
- `GITHUB_TOKEN` can be used instead of `GH_TOKEN`.
- For GitHub, `--status` uses the compare API.
- Triggering GitHub sync requires contents write permission.
