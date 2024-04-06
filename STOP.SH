#!/bin/bash
cd "$(dirname "$0")"
docker stop jellygrail
./_MOUNT.SH unmount
