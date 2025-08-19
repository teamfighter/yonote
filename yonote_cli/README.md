# yonote-tools — CLI for Yonote

This package contains the `yonote` utility. The main usage examples and instructions are described in the [root README](../README.md).

## Architecture

The package is split into two layers:

* **commands/** – individual subcommands (`auth`, `cache`, `export`, `import`). Each subcommand lives in its own file and relies on helpers from the core layer.
* **core/** – shared utilities: HTTP API access, caching, progress reporting and the interactive navigation through collections and documents.

The central module `yonote_cli/core/interactive.py` implements interactive workflows. It fetches collections and documents lazily from the API and lets the user browse the hierarchy with the keyboard.

## Command reference

### `yonote auth set`
Stores the base URL and API token in `~/.yonote.json`. Both values can also be supplied via environment variables.

### `yonote auth info`
Prints the current configuration including the resolved base URL and token location.

### `yonote cache info`
Shows where the cache file is located and basic statistics about stored collections and documents.

### `yonote cache clear`
Removes `~/.yonote-cache.json` so that subsequent commands fetch fresh metadata from the API.

### `yonote export`
Interactive export of collections and documents. The command uses the browser from `interactive.py` to select targets, then downloads document content concurrently and writes files to the output directory.

### `yonote import`
Imports local Markdown files into Yonote. The command prompts for a collection and optional parent document, mirrors the local folder structure, and creates documents in parallel workers.

This layered structure keeps network logic, caching and interactive UI reusable across all commands.
