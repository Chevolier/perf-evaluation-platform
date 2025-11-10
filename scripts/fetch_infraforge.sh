#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR=${1:-../InfraForge}
REPO_URL=${INFRAFORGE_REPO_URL:-https://github.com/awslabs/InfraForge.git}
REFERENCE=${INFRAFORGE_REF:-main}

mkdir -p "$(dirname "$TARGET_DIR")"

if [ -d "$TARGET_DIR/.git" ]; then
  echo "[HyperPod] Updating InfraForge in $TARGET_DIR" >&2
  git -C "$TARGET_DIR" fetch --quiet --tags "$REPO_URL"
  git -C "$TARGET_DIR" checkout --quiet "$REFERENCE"
  git -C "$TARGET_DIR" pull --quiet --ff-only "$REPO_URL" "$REFERENCE"
else
  echo "[HyperPod] Cloning InfraForge into $TARGET_DIR" >&2
  git clone --quiet "$REPO_URL" "$TARGET_DIR"
  git -C "$TARGET_DIR" checkout --quiet "$REFERENCE"
fi

echo "[HyperPod] InfraForge ready at $TARGET_DIR (ref: $(git -C "$TARGET_DIR" rev-parse --short HEAD))" >&2
