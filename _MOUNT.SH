#!/bin/bash
cd "$(dirname "$0")"
. ./jellygrail/config/settings.env # load settings
mkdir -p ./jellygrail/jellyfin/config
mkdir -p ./jellygrail/jellyfin/cache
mkdir -p ./fallbackdata
fusermount -uz ./Video_Library 2> /dev/null
fusermount -uz ./Video_Library 2> /dev/null
umount ./Video_Library 2> /dev/null
umount ./Video_Library 2> /dev/null
rmdir ./Video_Library

if [ ! -z "$ADD_HOST_MOUNT" ]; then
    fusermount -uz $ADD_HOST_MOUNT
    fusermount -uz $ADD_HOST_MOUNT
    umount $ADD_HOST_MOUNT
    umount $ADD_HOST_MOUNT
    rmdir $ADD_HOST_MOUNT

if [ "$1" = "mount" ];then
    mkdir -p ./Video_Library
    mount -o bind ./Video_Library ./Video_Library
    mount --make-shared ./Video_Library

    if [ ! -z "$ADD_HOST_MOUNT" ]; then
        mkdir -p $ADD_HOST_MOUNT
        mount --bind ./Video_Library $ADD_HOST_MOUNT
