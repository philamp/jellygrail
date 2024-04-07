#!/bin/bash
cd "$(dirname "$0")"
sleep 120
./_MOUNT.SH mount
docker start jellygrail
