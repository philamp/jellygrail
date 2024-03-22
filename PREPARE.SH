#!/bin/bash

# Path to the rclone configuration file and its example

CONF_PATH="./mounts/remote_realdebrid/rclone.conf"
CONF_EXAMPLE_PATH="./mounts/remote_realdebrid/rclone.conf.example"

SETTINGS_PATH="./jellygrail/config/settings.env"
SETTINGS_EXAMPLE_PATH="./jellygrail/config/settings.env.example"

if [ ! -f "RESTART.SH"  ]; then
    cp -f "RESTART.SH.example" "RESTART.SH"
fi

if [ "$1" = "upgrade" ]; then
    read -p "Would you like to stop and remove the already running JellyGrail container ? (yes/no) (needed for running a new one): " upyesno
    if [ $upyesno = "yes" ]; then
        docker stop jellygrail
        docker rm jellygrail
    fi
fi 

# Check if the configuration file already exists
if [ ! -f "$CONF_PATH"  ] || [ ! -f "$SETTINGS_PATH"  ] || [ "$1" = "upgrade" ]; then

    # Copy the example configuration file to the new configuration file
    if [ -f "$SETTINGS_EXAMPLE_PATH" ]; then
        cp -f "$SETTINGS_EXAMPLE_PATH" "$SETTINGS_PATH"
    fi
        
    # Prompt the user for the API key
    echo "Upgrade or creation of config files: $CONF_PATH and $SETTINGS_PATH will be created"
    read -p "Please enter your Real-Debrid API key (leave empty to ignore): " api_key
    read -p "Please enter the remote JellyGrail instance location (ex: http://10.6.0.1:6502 ; leave empty to ignore): " remote_loc
    read -p $'Please enter the initial increment from which you want to synchronize remote torrents. \nIt does not apply if /jellygrail/data/rd_incr.txt already exists. \n(default: 0 ; leave empty to keep default): ' default_incr

    if [ ! -z "$remote_loc" ]; then
        read -p "From the remote JellyGrail instance, do you want to take the whole content of torrents, including folders ? yes/no (default: yes ; leave empty to keep default): " whole_content
    fi

    # Check if the user input is empty
    if [ ! -z "$api_key" ]; then
        # Make sure the example configuration file exists
        if [ -f "$CONF_EXAMPLE_PATH" ]; then
            # Copy the example configuration file to the new configuration file
            cp -f "$CONF_EXAMPLE_PATH" "$CONF_PATH"
    
            # Replace the placeholder with the user-provided API key
            sed -i "s/PASTE-YOUR-KEY-HERE/$api_key/" "$CONF_PATH"
    
            echo "The RD rclone configuration file has been created and the API key has been inserted."
        else
            echo "The RD rclone example configuration file does not exist. Please check the path."
        fi

        # Make sure the example configuration file exists
        if [ -f "$SETTINGS_EXAMPLE_PATH" ]; then

            # Replace the placeholder with the user-provided API key
            sed -i "s/PASTE-YOUR-KEY-HERE/$api_key/" "$SETTINGS_PATH"
            if [ ! -z "$remote_loc" ]; then
                sed -i "s|PASTE-REMOTE-ADDR-HERE|$remote_loc|" "$SETTINGS_PATH"
            fi
            if [ ! -z "$default_incr" ]; then
                sed -i 's/DEFAULT_INCR="0"/DEFAULT_INCR="$default_incr"/' "$SETTINGS_PATH"
            fi
            if [ ! -z "$whole_content" ]; then
                sed -i 's/ALL_FILES_INCLUDING_STRUCTURE="yes"/ALL_FILES_INCLUDING_STRUCTURE="$whole_content"/' "$SETTINGS_PATH"
            fi

        else
            echo "The jellygrail example settings file does not exist. Please check the path."
        fi

    else
        echo "No API key entered. The configuration file will not be created. Real-Debrid implementation will not work"
    fi

else
    echo "The configuration file already exists."
fi



echo "Proceeding with the script (creation of config folders and rshare mounting of Video_Library folder)"
echo "---------------------------------------------------------------------------------------------------"
mkdir -p ./jellygrail/jellyfin/config
mkdir -p ./jellygrail/jellyfin/cache
mkdir -p ./fallbackdata
fusermount -uz ./Video_Library 2> /dev/null
fusermount -uz ./Video_Library 2> /dev/null
umount ./Video_Library 2> /dev/null
umount ./Video_Library 2> /dev/null
mkdir -p ./Video_Library
mount -o bind ./Video_Library ./Video_Library
mount --make-shared ./Video_Library



# OLD STUFF TODO: to remove :
# fusermount -uz ./volumeG/rd_fuse_volume
# umount ./volumeG/rd_fuse_volume
# fusermount -uz ./volumeG/rar2fs_fuse_volume
# umount ./volumeG/rar2fs_fuse_volume
# mkdir -p ./volumeG/Symlinks_unrar_fullchk
# mkdir -p ./volumeG/bindfs_fuse_volume
# mkdir -p ./volumeG/rar2fs_fuse_volume
# mkdir -p ./volumeG/rd_fuse_volume
# fusermount -uz ./volumeG/bindfs_fuse_volume
# umount ./volumeG/bindfs_fuse_volume
# mount -o bind ./volumeG/bindfs_fuse_volume ./volumeG/bindfs_fuse_volume
# mount --make-shared ./volumeG/bindfs_fuse_volume
# mount -o bind ./volumeG/rd_fuse_volume ./volumeG/rd_fuse_volume
# mount --make-shared ./volumeG/rd_fuse_volume
# mount -o bind ./volumeG/rar2fs_fuse_volume ./volumeG/rar2fs_fuse_volume
# mount --make-shared ./volumeG/rar2fs_fuse_volume
