#!/bin/bash
cd "$(dirname "$0")"
docker stop jellygrail3
fusermount -uz ./Video_Library
fusermount -uz ./Video_Library
umount ./Video_Library
umount ./Video_Library
mkdir -p ./Video_Library
mount -o bind ./Video_Library ./Video_Library
mount --make-shared ./Video_Library
docker start jellygrail3
# call to additonal host mount
./CUSTOM_HOST_MOUNT.SH
