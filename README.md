<img src="jellygrail_logo.png">

# What is JellyGrail ?
JellyGrail is an **experimental** modified Jellyfin docker image to manage all your video storages (local and cloud/remote) in one merged virtual folder that you can manage as if it were a real one. It's optimized for [Real-Debrid](https://real-debrid.com/) service and provides on-the-fly RAR extraction.

- You can stream your Real-Debrid video files directly (thanks to https://github.com/itsToggle/rclone_RD)
- RAR archives extracted on the fly (thanks to rar2fs):
  - No need to extract your local RAR downloads. 
  - No need to download and extract Real-Debrid torrents having RARs, it's just streamed and extracted on-the-fly.
    - ✨ With an optimized cache to mitigate real-debrid issues with ISO and RAR files (thanks to https://github.com/philamp/rclone_jelly, is a fork of rclone_RD).
- Real-Debrid magnet hashes management:
  - Automatic backup of last 2500 Real-Debrid torrents (TODO: service to restore them if lost).
  - RD torrent-hashes sync from another instance of JellyGrail (but no secured proxy or VPN is provided here, so be careful).
- ✨ Auto-organized TV shows and movies in a virtual folder:
  - Subtitle files renamed following standards.
  - Same movie variants merged into same folder when possible
  - You can manage this virtual folder as if it were a real one (rename and move files the way you want)
  - ✨ Every storage is merged into this unique virtual folder (thanks to https://github.com/philamp/bindfs_jelly):
  - It can be shared on your local network through any protocol (There is a WebDAV server included but you can also share it through SMB, DLNA or NFS)
  - Smart deletion of actual assets behind virtual files, including rclone cache files.
  - ✨ Detects extras and put them in an /extras subfolder of the movie so it won't mess up your Jellyfin Library
- Preconfigured Jellyfin included if needed.
- Included Webdav/HTTP server (nginx) on port 8085.
  - TODO: include an additional share protocol like DLNA.

## ⚠️ Warnings 

> ⚠ This is experimental stuff.

- I'm not responsible of any data loss.
- Do not open ports 8085 and 6502 to the internet.
- I'm not responsible of any illegal use.
- Use at your own risks.
- I'm not a professional developer.
- This does not include any torrent indexer search or RD downloader.
- ⚠️ File Deletion in the virtual folder actually deletes corresponding files of the underlying file-systems.

## 📥️ Installation (or upgrade)

Follow sections 1/ to 7/

### ✋ 1/ Prerequisites

- Linux system 🐧.
- FUSE installed on host.
- Tested on x86 system, should build on ARM and should run on a Raspberry 4, not tested yet.
- Docker 🐳.
- Git client to clone this repo (TODO: provide a prebuilt image)
- Crontab to trigger included http services.
- Having a Real-Debrid account is better.


### 🚧 2/ Build

Find a conveniant directory on your system, beware this folder will store the rclone cache _(0.5%~ of your real-debrid storage size)_ and this folder is represented by a dot "." in this page.

````
git clone https://github.com/philamp/jellygrail.git
cd jellygrail/docker
sudo docker build -t philamp/jellygrail .
````

> If you upgrade, replace the git clone command by a git pull command inside the root jellygrail folder

### ✨ 3/ Configuration wizard

> You can find your Real-Debrid API key here : https://real-debrid.com/apitoken.

Make sure you're back in the root folder where _PREPARE.SH_ is located:


````
cd ..
````

#### 3.1/ First install

Run the bash script:
````
sudo chmod u+x PREPARE.SH
sudo ./PREPARE.SH
````

#### 3.2/ Upgrade

Run the bash script:
````
sudo chmod u+x PREPARE.SH
sudo ./PREPARE.SH upgrade
````

This creates settings files and also prepares "rshared" mounted folder ``./Video_Library/`` (so its content reflects the magic ✨ happening inside the docker container)
> Learn more about "rshared" here : https://forums.docker.com/t/make-mount-point-accesible-from-container-to-host-rshared-not-working/108759

### 🐳 4/ Docker command

Take a notepad and progressively paste portions of code in sub-sections 4.1 to 4.3 below:
> don't forget the "\\" before a new line
>
> ignore blank lines and "..."

#### 🐳 4.1/ Docker run base

Example with common transcoding device access mounted and running in host mode (TODO: provide ports forwarding version)
> The first time you launch this command, you can run with "run -it" instead of "run -d" if you want, so that you can see the output, once first tasks are finished it stops and restarts in deamonized mode anyway.

````
sudo docker run -d --privileged --security-opt apparmor=unconfined \
--cap-add MKNOD \
--cap-add SYS_ADMIN \
--device /dev/fuse \
--device /dev/dri/renderD128 \
--device /dev/dri/card0 \
--network host \
-v ${PWD}/jellygrail:/jellygrail \
-v ${PWD}/Video_Library:/Video_Library:rshared \
-v ${PWD}/mounts/remote_realdebrid:/mounts/remote_realdebrid \
-v ${PWD}/fallbackdata:/mounts/fallback \

...
````

> ⚠ Not yet tested without "--privileged --security-opt apparmor=unconfined", so I let it and thus it's unsecure. **Remember its experimental stuff.**

#### 🐳 4.2/ Mounting local storages (optionnal)

Example with 2 local folders

````
...

-v /volume1/video:/mounts/local_drive1 \
-v /volumeUSB1/usbshare/video:/mounts/local_drive2 \

...
````

> ⚠ Your local folders must be mounted inside ``/mounts`` and they must contain at least a _movies_ folder or a _shows_ folder (it follows the same naming convention as when mounting with rclone RD fork)
> 
> ⚠ local storage _movies/_ folders also supports video files that would be directly inside this folder. But shows must always be in a subfolder (ex : _video/shows/scrubs/video.mkv_)

#### 🐳 4.3/ Final part

````
...

--restart unless-stopped \
--name jellygrail \
philamp/jellygrail:latest
````



### 🚀 5/ Run

1. Verify that ``./jellygrail/config/settings.env`` is populated with proper values.
2. Verify that ``./mounts/remote_realdebrid/rclone.conf`` is populated with proper values.
3. Verify that your working directory is the folder containing _PREPARE.SH_ file (= root folder of this repo).
4. Paste your docker command in your bash prompt.
6. Hit enter !

### 📡 6/ Tasks triggering 

On ``http://your_system_ip:6502`` an http service is provided on you can open these below paths and/or configure them in you crontab (TODO: provide more help on how to use crontab) :

#### 📡 Path: ``/scan``

> Not mandatory to be set as cron as rd_progress _potentially_ calls it every 2 minutes.

should be triggered to scan your folders in order to fill the ``./Video_Library/virtual/`` folder and refresh Jellyfin Library.

#### 📡 Path: ``/backup`` 

should be triggered frequently to backup your RD torrents (dump file stored in ``./jellygrail/data/backup``).

#### 📡 Path: ``/remotescan``

to trigger the pull of new hashes from another JellyGrail instance (if configured in ``./jellygrail/config/settings.env``)

> ⚠️ ``/remotescan`` is the local trigger that will call a remote service (which is actually ``/getrdincrement``) on the other JellyGrail instance (but no secured proxy or VPN is provied here, so be careful). 
>
> ⚠️ You should absolutely not open the python service to internet (do not open port 6502).

Basically you won't use this trigger unless you want to synchronize your RD torrents with another instance of this app (aka friend remote instance).

#### 📡 Path: ``/rd_progress``

> Not mandatory to be set as cron as it is triggered every 2 minutes.

This is a service to check if there are changes worth calling ``/scan`` subsequently.

### ➰ 7/  Daily restart

> Not mandatory as it restarts by itself at 6.30am every day 🕡
~~As JellyGrail is experimental, a daily restart is recommended: add in your crontab a daily call to ``./RESTART.SH``.~~
~~It also remakes the rshared mounted folder ``./Video_Library/`` (so it's accessible from the host)~~


## 🚀 First and daily Usage

1. Verify that you have some torrents in your RD account _(JellyGrail does not provide any torrent indexer search or RD downloader)_.
2. Wait for the ``./Video_Library/virtual/`` folder to be filled (The first library scan is called within 2 minutes if there are torrents in your RD account)
    - or trigger it with  ``/scan`` (See 📡 Tasks triggering section above).
4. Access the content in ``./Video_Library/virtual/`` (in the folder you ran the docker command).
5. Jellyfin is ready to run and preconfigured with corresponding libraries on http://your_system_ip:8096.
    - Initialize the user and language and don't do anoything else (don't add librairies)
    - You can also point your plex Libraries to the ``./Video_Library/virtual/movies/`` and ``./Video_Library/virtual/shows/`` folders.
    - TODO: functionnality to disable jellyfin.
6. For TV/Projector usage : it's recommended to use _Kodi + Jellyfin add-on_ on an Android TV device (or LibreELEC/Coreelec on specific devices).
7. On Mobile device, you can install Jellyfin app and switch to native included player in its settings (in other words: avoid the webview player because it leads Jellyfin to do unnecessary transcoding)
8. Beware to have a paid RD account:
    - configure ``/backup`` cron (See 📡 Tasks triggering section above).
    - (if you forgot a payment you can find your torrents backup in jellygrail/data/backup/ ) TODO: service to restore the dump.
9. ⚠️ If you need to have your virtual folder rebooted with fresh entries, do not delete file items in ``./Video_Library/virtual/`` folder, as it will also delete corresponding files in the underlying file-systems. Just delete the ``./jellygrail/.bindfs_jelly.db`` file, **restart the docker container** and trigger a new ``/scan``
10. You can re-arrange your virtual/shows and virtual/movies folders the way you like as if it were a normal file-system. Future calls to /scan service won't mess-up with your changes. Don't forget to refresh Jellyfin library after your changes.

> ``./fallbackdata/`` folder contains files added by you or any process that tries to write a file in _virtual_ folder and its subfolders.
> 
> ``./Video_Library/virtual_dv/`` is a dynamically filtered folder containing only Dolby Vision MP4/MKV files.
> 
> ``./Video_Library/virtual_bdmv/`` is a dynamically filtered folder containing only DVDs and Blu-rays data.


## ✅ Sanity checks / Troubleshooting (Draft section)

You can check it's running with following commands:

### ✅ Is the container running ? 

````
sudo docker ps
````

### ✅ Logs

logs are in ``./jellygrail/log/``.
you can do:

````
tail -f ./jellygrail/log/jelly_update.log
````

### ✅ Live container logs

````
sudo docker logs --follow jellygrail
````

### ✅ Python service 

````
curl http://localhost:6502/test
````

### ✅ Jellyfin 

Open http://your_system_ip:8096 to launch Jellyfin web interface.

## Good to know / Known issues
- Check **🚀 First and daily Usage** section above
- only last 2500 real-debrid torrents are backuped.
- m2ts files not inside a BDMV structure are ignored.
- **Some current limitations related to multi-threading in BindFS makes so that multi-access to same or different files through BindFS is not efficient (for instance: watching a movie while a scanning service is running has bad performance).**
- ⚠️ If you've restarted your system, the docker container was maybe restarted but the rshared mount of folder ``./Video_Library/`` was not made so you have to run ``./RESTART.SH`` to fix it.
- JELLYFIN_FFmpeg__analyzeduration reduced to 4 seconds to be light on Real-Debrid requests and rclone cache. On some video files ffprobe report might be uncomplete. TODO: reconsider an increase of JELLYFIN_FFmpeg__analyzeduration.
- TODO: add librairies after the first scan
- Additional Remote mounts points : You can add other rclone remote mount points (with your favorite cloud provider) by following the same structure as the provided example used for real_debrid in ``./mounts/`` folder provided but:
    - Follow this convention:
      - name your rclone config title (in between [ ] ) the same as the parent folder containing this rclone config file.
      - and name the file "rclone.conf".
- Underlying files deletion:
  - REMOTE : follows rclone RD fork system : Inside folders containing multiple video files, only 1 file will be deleted (TODO: fix this issue to improve other cloud provider support). In other words it means that underlying files deletion are sometimes uncomplete in this case.
  - LOCAL : Underlying files are deleted but not folders (TODO:fix)
- A daily docker restart is still needed so far.
- RD Torrents that becomes unavailable (despite rclone fork trying to re-download them) are not fully detected by JellyGrail: corresponding virtual files are not displayed and Jellyfin will thus remove them from library but corresponding parent folders will stay (TODO: trying to fix that in a next version)
- 3 Jellyfin plugins are pre-installed:
  - ``SubBuzz:``  not enabled on library scan but can be used on induvidual items. You can enable it on library scan if you want but beware it will cause additional download requests to Real-Debrid.
  - ``Merge Versions:`` Movies not merged by initial scan can be merged thanks to this Jellyfin plugin. Shows episodes are not set to be merged because in this case it causes troubles (like whole season merged into one media item).
  - ``Kodi Sync Queue:`` to improve the experience with Jellyfin kodi add-on 
- rclone_jelly is an experimental fork of https://github.com/itsToggle/rclone_RD to change the normal behavior of rclone's vfs_cache and thus it's not a "cache" anymore: it stores RAR/ISO file structure data to improve access reliability especially when using Real-Debrid service.
  - This cache will have a size equal to 0.5%~ of your real-debrid storage size, using it on an SSD is better (but not mandatory).
- bindfs_jelly is a fork of https://github.com/mpartel/bindfs that brings virtual folders and virtual renaming.
  - Its sqlite DB is initialized through inluded Python service that scans mounted local and remote folders (upon first start the virtual folder is empty).
- ⚠️ You can manage your assets *only* through the virtual folder (rename, delete, move) otherwise if you do it directly on the underlying filesystems, linkage will be lost between virtual tree and actual trees.
- You can use a Real-Debrid download manager like [rdt-client](https://github.com/rogerfar/rdt-client) and disable downloading files to host since you don't need to have these files stored locally anymore. Thus you also have to stop using rename-and-organize feature of Radarr and Sonarr (basically you have to stop radarr/sonarr handling of finished downloads). 
- if the Video_Library folder is then accessed through a SMB protocol in windows, renaming does not seem to work (an error pops up) but it's actually working, just refresh the content of the folder and you'll see the renaming is effective. (TODO: fix that in bindfs_jelly if possible).

## Kodi setup (recommended)

### Devices
- Nvidia Shield: https://www.kodinerds.net/thread/69428-maven-s-kodi-builds-f%C3%BCr-android/ -> Nexus release (arm64-v8a)) 
- Chromecast with Google TV: https://www.kodinerds.net/thread/69428-maven-s-kodi-builds-f%C3%BCr-android/ -> Nexus release (armeabi-v7a)
(to be completed...)

### Add-ons
- Jellyfin add-on ``*``
  - with 'add-on' paths, not 'native' paths, otherwise you loose the functionnality to choose the video variant upon play.

- Artic Horizon 2 skin ``*``
  - Allow third party default dependencies in add-on settings before instlaling the skin.

- a4k subtitles add-on ``*``
- Up Next (optionnal)
- Keymap editor add-on (optionnal)

> ``*`` Kodi repo included (with "install from zip") in HTTP WebDAV server provided on port 8085 in ``./Video_Library/actual/kodi/software/``








