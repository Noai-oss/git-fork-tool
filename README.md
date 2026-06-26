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
gft repo init
```

Check fork sync status:

```sh
gft repo sync main --status
```

Trigger a fork sync:

```sh
gft repo sync main
```

Fetch an upstream pull request into a stable local ref and print that ref:

```sh
gft pr fetch 123
```

Create local branches with git:

```sh
git switch -c pr-123-original "$(gft pr fetch 123)"
git switch -c pr-123-experiment "$(gft pr fetch 123)"
```

Update an existing local branch with git:

```sh
ref="$(gft pr fetch 123)"
git switch pr-123-original
git merge --ff-only "$ref"
```

Rebase local experiment commits onto the latest PR:

```sh
ref="$(gft pr fetch 123)"
git switch pr-123-experiment
git rebase "$ref"
```

Reset a local branch to the latest PR:

```sh
ref="$(gft pr fetch 123)"
git switch pr-123-original
git reset --hard "$ref"
```

Print the ref or refspec without fetching:

```sh
gft pr ref 123
gft pr refspec 123
```

## Notes

- `GITCODE_TOKEN` can be used instead of `GC_TOKEN`.
- `GITHUB_TOKEN` can be used instead of `GH_TOKEN`.
- For GitHub, `--status` uses the compare API.
- Triggering GitHub sync requires contents write permission.
