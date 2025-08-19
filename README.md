# yonote-tools — CLI for Yonote

[![CI](https://github.com/teamfighter/yonote/actions/workflows/ci.yml/badge.svg)](https://github.com/teamfighter/yonote/actions/workflows/ci.yml)
[![Release](https://github.com/teamfighter/yonote/actions/workflows/release.yml/badge.svg)](https://github.com/teamfighter/yonote/actions/workflows/release.yml)

Command line tool for exporting and importing documents from [Yonote](https://yonote.ru). The CLI can browse collections and documents interactively, refresh the cache selectively and work with nested folders.

## Run with Docker

Images are published to the [GitHub Container Registry](https://github.com/orgs/teamfighter/packages). To use the CLI pull the image and source the helper script:

```bash
export YONOTE_VERSION=<latest tag>
docker pull ghcr.io/teamfighter/yonote:$YONOTE_VERSION
curl -O https://raw.githubusercontent.com/teamfighter/yonote/main/yonote.sh
chmod +x yonote.sh
source yonote.sh
yonote --help
```

The wrapper mounts `~/.yonote.json` and `~/.yonote-cache.json` along with the current directory into `/app/work`, allowing relative paths. The examples below assume the `yonote` function is already available.

## Run through Python venv

Alternatively install the CLI into a local virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e yonote_cli
yonote --help
```

## Access configuration

Obtain a JWT token in the Yonote UI and save the connection parameters:

```bash
yonote auth set --base-url https://app.yonote.ru --token <JWT>
```

The configuration is stored in `~/.yonote.json`; document structure cache is stored in `~/.yonote-cache.json`.

## Export

```bash
yonote export --out-dir ./dump --workers 20 --format md
```

The command opens an interactive browser to pick collections and documents. Selected items are written to the target directory preserving hierarchy. Useful flags:

- `--refresh-cache` – refresh metadata cache;
- `--format md|json` – output file format;
- `--use-ids` – use identifiers in file names.

## Import

```bash
yonote import --src-dir ./dump
```

The CLI prompts for a collection and parent document, then reproduces the local folder structure inside Yonote and publishes created documents. Options:

- `--refresh-cache` – refresh cache before selection;
- `--workers N` – maximum number of threads for document creation (default 20).

## Interactive browser

Export and import dialogs rely on an interactive browser. It is based on [InquirerPy](https://github.com/kazhala/InquirerPy) which is included in the latest images. If you see `Interactive mode requires InquirerPy`, update `YONOTE_VERSION` to the latest tag. Available keys:

- `↑`/`↓` – move through the list;
- `PgUp`/`PgDn` – scroll by 10 items;
- `Enter` – open a section or confirm action;
- `Space` – mark/unmark documents during export;
- `Ctrl+S` – search; press again to exit search, `Enter` jumps to the next match;
- `Ctrl+R` – refresh the current list from the server (selective cache reset);
- `..` – go one level up.

## Working with cache

Collection and document metadata is stored in `~/.yonote-cache.json`. Use the following commands to manage the cache:

```bash
yonote cache info   # show cache information
yonote cache clear  # delete cache
```

The `--refresh-cache` flag or `Ctrl+R` shortcut let you refresh only required branches, reducing request time.

## Examples

### Export a collection to Markdown

```bash
yonote export --out-dir ./dump --format md --workers 20
```

### Import prepared files

```bash
yonote import --src-dir ./dump
```

Commands for pulling images with specific versions are published in release notes.

## Local development

Follow the instructions from [Run through Python venv](#run-through-python-venv), then run tests and build the image if needed.

### Run tests

```bash
pytest
```

### Build the Docker image

```bash
docker build -f docker/Dockerfile -t yonote:dev .
```
