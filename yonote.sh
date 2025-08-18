#!/usr/bin/env bash
# Yonote CLI wrapper for Docker
# Usage: source ./yonote.sh; yonote <args>

# Function to run Yonote CLI in Docker with proper mounts
yonote() {
  # Ensure config and cache files exist so Docker mounts them as files rather than
  # creating directories. Without these placeholders Docker would create
  # directories which leads to IsADirectoryError inside the container when the
  # CLI tries to write to the JSON files.
  if [ -d "$HOME/.yonote.json" ]; then
    echo "Error: $HOME/.yonote.json is a directory. Remove or rename it." >&2
    return 1
  fi
  if [ -d "$HOME/.yonote-cache.json" ]; then
    echo "Error: $HOME/.yonote-cache.json is a directory. Remove or rename it." >&2
    return 1
  fi
  if [ ! -e "$HOME/.yonote.json" ]; then
    touch "$HOME/.yonote.json"
  fi
  if [ ! -e "$HOME/.yonote-cache.json" ]; then
    touch "$HOME/.yonote-cache.json"
  fi

  docker run --rm -it \
    -v "$HOME/.yonote.json:/root/.yonote.json" \
    -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
    -v "$(pwd):/app/work" \
    -w /app/work \
    ghcr.io/teamfighter/yonote:${YONOTE_VERSION:-latest} "$@"
}
