#!/bin/bash
cd "$(dirname "$0")"
. ./jellygrail/config/settings.env # load settings
mkdir -p ./fallbackdata
fusermount -uz ./Video_Library 2> /dev/null
fusermount -uz ./Video_Library 2> /dev/null
umount ./Video_Library 2> /dev/null
umount ./Video_Library 2> /dev/null
rmdir ./Video_Library 2> /dev/null

if [ ! -z "$ADD_HOST_MOUNT" ]; then
    fusermount -uz $ADD_HOST_MOUNT 2> /dev/null
    fusermount -uz $ADD_HOST_MOUNT 2> /dev/null
    umount $ADD_HOST_MOUNT 2> /dev/null
    umount $ADD_HOST_MOUNT 2> /dev/null
    rmdir $ADD_HOST_MOUNT 2> /dev/null
fi

if [ "$1" = "mount" ];then
    mkdir -p ./Video_Library
    mount -o bind ./Video_Library ./Video_Library
    mount --make-shared ./Video_Library
    if [ ! -z "$ADD_HOST_MOUNT" ]; then
        mkdir -p $ADD_HOST_MOUNT
        mount --bind ./Video_Library $ADD_HOST_MOUNT
    fi
fi


