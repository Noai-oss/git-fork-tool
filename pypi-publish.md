# PyPI Publishing

This project uses `uv` and `uv-dynamic-versioning` for packaging. The package
version comes from git tags, not from a hard-coded version in `pyproject.toml`.

## Before Publishing

Make sure the release commit is on `main` and the working tree is clean:

```sh
git switch main
git pull --ff-only origin main
git status --short
```

Run the checks:

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

## Version Tag

Create and push a version tag. For example:

```sh
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Because the version is dynamic, this tag is what makes the built package version
become `0.1.0`.

## Build

Build the source distribution and wheel:

```sh
rm -rf dist
uv build --no-sources
```

The generated files should appear under `dist/`.

## Check

Check the package metadata and README rendering before uploading:

```sh
uvx twine check dist/*
```

## Publish

Create a PyPI API token, then publish:

```sh
UV_PUBLISH_TOKEN="pypi-..." uv publish
```

For a dry run:

```sh
UV_PUBLISH_TOKEN="pypi-..." uv publish --dry-run
```

For TestPyPI:

```sh
UV_PUBLISH_TOKEN="pypi-..." \
UV_PUBLISH_URL="https://test.pypi.org/legacy/" \
uv publish
```

## Verify

After publishing, install and run the command from PyPI:

```sh
uvx --from git-fork-tool gft --help
```
