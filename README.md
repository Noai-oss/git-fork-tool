# git-fork-tool

A lightweight CLI for working with Git fork repositories.

Currently supports GitCode.

## Usage

Set a GitCode token:

```sh
export GC_TOKEN=your_token
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

`GITCODE_TOKEN` can be used instead of `GC_TOKEN`.
