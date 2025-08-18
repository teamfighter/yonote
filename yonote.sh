#!/usr/bin/env bash
# Yonote CLI wrapper for Docker
# Usage: source ./yonote.sh; yonote <args>

# Function to run Yonote CLI in Docker with proper mounts
yonote() {
  docker run --rm -it \
    -v "$HOME/.yonote.json:/root/.yonote.json" \
    -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
    -v "$(pwd):/work" \
    -w /work \
    ghcr.io/teamfighter/yonote:${YONOTE_VERSION:-latest} "$@"
}
