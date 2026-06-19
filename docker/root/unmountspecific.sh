#!/bin/sh
set -eu

LIST_FILE="/run/bind-mounts.list"
DUMPS_DST="/localremounts/dumps"

unmount_one() {
  dst="$1"
  [ -n "$dst" ] || return 0
  if mountpoint -q "$dst"; then
    umount "$dst" || umount -l "$dst" || true
    echo "[bind-mounts] unmounted $dst"
  fi
}

# Umount en ordre inverse (plus safe)
if [ -f "$LIST_FILE" ]; then
  tac "$LIST_FILE" 2>/dev/null | while IFS= read -r dst; do
    unmount_one "$dst"
  done
fi

unmount_one "$DUMPS_DST"

exit 0
