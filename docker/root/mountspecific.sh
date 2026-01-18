#!/bin/sh
set -eu

SRC_BASE="/mounts"
DST_BASE="/localremounts"   # configurable via env
LIST_FILE="/run/bind-mounts.list"

mkdir -p "$DST_BASE" /run
: > "$LIST_FILE"

# Rien à faire si le glob ne matche rien
set +e
CANDIDATES=$(ls -1d "$SRC_BASE"/local* 2>/dev/null)
set -e

if [ -z "${CANDIDATES:-}" ]; then
  echo "[bind-mounts] no candidates in $SRC_BASE"
  exit 0
fi

for src in $CANDIDATES; do
  name="$(basename "$src")"

  # ignore local_import
  if [ "$name" = "local_import" ]; then
    echo "[bind-mounts] skip $src"
    continue
  fi

  # seulement les dossiers
  if [ ! -d "$src" ]; then
    echo "[bind-mounts] skip non-dir: $src"
    continue
  fi

  dst="$DST_BASE/$name"
  mkdir -p "$dst"

  if mountpoint -q "$dst"; then
    echo "[bind-mounts] already mounted: $dst"
    continue
  fi

  mount --bind "$src" "$dst"

  # Optionnel : rendre RO si tu veux (ex: export readonly)
  if [ "${BIND_RO:-0}" = "1" ]; then
    mount -o remount,bind,ro "$dst" || true
  fi

  echo "$dst" >> "$LIST_FILE"
  echo "[bind-mounts] mounted $src -> $dst"
done

exit 0