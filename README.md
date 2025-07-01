> [!CAUTION]
> - New version named "20240915", **don't forget to RERUN PREPARE.SH !!!, also there are differents arguments in the docker run command**
>   - breaking changes:
>     - ./jellygrail/.bindfs_jelly.db is now stored in ./jellygrail/data/bindfs : **Jellygrail will rescan all your library**
>     - Jellyfin is run under user "www-data" so that nginx can natively access to its files (no impact planned)
>     - Merge versions Jellyfin add-on to be removed. It's confusing when deleting library items since some variants are within same folders while other are not. Removing that will remove this ambiguity.
>     - Added Kodi synchronization, you must use [this guide](https://github.com/philamp/jellygrail/wiki/Configure-Kodi-for-Jellygrail) if interested
>     - ffprobe wrapper to reduce remote storage queries (jellygrail stores ffprobe results and gives it back to Jellyfin when requested)
>   - Fixes:
>     - fallbackdata items now displayed in all dynamically filtered folders
>     - real added date in virtual filesystem (so recently added lists are correct)
>     - improved datamodel upgrade management
>     - improved configuration wizard that remembers previous settings

----


<img src="jellygrail_logo.png">

_One compatibility layer to merge them all, manage them all in Jellyfin and play them all in Kodi ; and in their RAR keep them_

# What is JellyGrail ?
JellyGrail is an **experimental** modified Jellyfin* docker image to manage all your video storages (local and cloud/remote) in one merged virtual folder that you can organize as if it were a real one. It's optimized for [Real-Debrid](https://real-debrid.com/) service and provides on-the-fly RAR extraction. And since march 2025, it also provides Kodi integration and synchronization with Jellyfin metadata.
> *Jellyfin is an opensource alternative to Plex.

- Access remote and Real-Debrid files as if they were local (like https://github.com/itsToggle/rclone_RD and Zurg).

- ✨✨ RAR archives extracted on the fly (https://github.com/hasse69/rar2fs):
  - No more hassle to extract your local RAR downloads. 
  - No more hassle downloading and extracting Real-Debrid RAR torrents, now you can just stream and extract on-the-fly.
  - It provides an optimized cache to strongly mitigate Real-Debrid rate-limiting issues that can happen with ISO and RAR files (with my rclone_rd fork : https://github.com/philamp/rclone_jelly)
> Note that:
> RAR on-the-fly extract only works with "archive" mode (= no compression actually used). Other modes are very rarely used in this context anyway.

- ✨ Auto-organized TV shows and movies in a virtual folder:
  - Subtitle files renaming following standards as most as possible.
  - Detects extras and put them in the movie's "extras" subfolder.
  - You can manage the virtual folder as if it were a real one (rename and move files the way you want).
  - Smart deletion of actual assets behind virtual files (including rclone cache files).

- ✨✨ Native Kodi synchronization (with SQL custom operations) *Metadata only, no Jellyfin userdata synchronised*
  - Merging of Movie versions (+synchronizing progress across all versions).
  - Merging of possibly splitted TV show.
  - MariaDB server included.
  - Use [this guide](https://github.com/philamp/jellygrail/wiki/Configure-Kodi-for-Jellygrail) to make sure it will work.
    - Jellygrail log will tell you if it finds the database after Kodi has restarted. Only Kodi can create the database.
  - Plex server/player comparison:
    - You can play copies of DVD/Blurays in Kodi (and manage them in Jellyfin).
    - You can have multiple versions of a movie like in Plex.
    - It's fully open source.

> [!CAUTION]
> Jellygrail is experimental so you should not submit any issues to the XBMC github (Jellygrail disrupts the way Kodi works by dealing with the database directly !)

- ✨ Almost fully automatized Jellyfin configuration (except login/password) and scan triggering:
  - New items detection for Real-Debrid and local files (with rd_api_py and pyinotify), triggering Jellyfin or PLEX library refresh. (Jellyfin can also be disabled if another or no media center used).

- ✨ Can be used without any media center while keeping some practicality:
  - "scrapper-less/offline-mode" filename cleaner for movies (https://github.com/platelminto/parse-torrent-title - accurate 99,8%). This improves filesystem browsing.  
  - Movie variants merged into common folder when possible (with https://github.com/seatgeek/thefuzz).
  - Virtual folder can be shared on your local network through any protocol since it's like a regular file-system (+ WebDAV nginx server included on port 8085). 
  - Every storage is merged into this unique virtual folder (with my BindFS fork: https://github.com/philamp/bindfs_jelly)
 


- Real-Debrid magnet hashes management:
  - Automatic backup of all Real-Debrid torrents hashes + a service to restore them if RD account emptied by mistake.
  - RD torrent-hashes sync from another instance of JellyGrail (although no secured proxy or VPN is provided in this container).

 
> [!CAUTION]
> - I'm not responsible of any data loss / I'm not responsible of any illegal use / Use at your own risks.
> - This solution does not include any torrent indexer search. 
> - Do not open ports 8085 and 6502 to the internet.
> - ⚠️ File Deletion in the virtual folder actually deletes corresponding files of underlying file-system(s).
> - I repeat that Jellygrail is experimental and that you should not submit any issues to the XBMC (Jellygrail disrupts the way Kodi works by dealing with the database directly !).

# 📥️ Installation (or upgrade)

Follow sections 1/ to 7/

## ✋ 1/ Prerequisites

- Linux system 🐧 with Bash shell.
- Tested on x86 system, should build on ARM and should run on a Raspberry 4, but not tested yet.
- Docker 🐳.
- Git client to clone this repo (TODO: provide a prebuilt image).
- Having a Real-Debrid account is better.

## 🚧 2/ Build

Find a conveniant directory on your system, beware this folder will store ``jellygrail`` subfolder and the rclone cache _(0.5%~ of your real-debrid storage size)_. The ``jellygrail`` subfolder created by ``git clone ...`` is represented by a dot ``.`` in this page.

````
git clone https://github.com/philamp/jellygrail.git
cd jellygrail/docker
sudo docker build -t philamp/jellygrail .
````

> If you upgrade, replace the ``git clone ...`` command by a ``git pull`` command inside the ``.`` folder

## ✨ 3/ Configuration wizard for first install and upgrade

> Grab your Real-Debrid API key : https://real-debrid.com/apitoken.

Make sure you're back in the root ``.`` folder where _PREPARE.SH_ is located and run:
````
sudo chmod u+x PREPARE.SH _MOUNT.SH
sudo ./PREPARE.SH
````
> [!TIP]
> You can as well run ``sudo ./PREPARE.SH change`` if you want to change your settings


This creates settings files and also prepares "rshared" mounted folder ``./Video_Library/`` (so its content reflects the magic ✨ happening inside the docker container and is available to the host system, not only inside the container)
> Learn more about "rshared" here : https://forums.docker.com/t/make-mount-point-accesible-from-container-to-host-rshared-not-working/108759

## 🐳 4/ Docker command

Take a notepad and progressively paste portions of code in sub-sections 4.1 to 4.3 below:
> don't forget the "\\" before a new line and ignore "..." lines

### 🐳 4.1/ Docker run base

Example with common transcoding device access mounted and running in host mode (TODO: provide ports forwarding version)
> The first time you launch this command, you can run with "run -it" instead of "run -d" if you want, so that you can see the output right away, once first tasks are finished it stops and restarts in deamonized mode anyway.

````
sudo docker run -d --privileged --security-opt apparmor=unconfined \
--cap-add MKNOD \
--cap-add SYS_ADMIN \
--memory="8g" \
--device /dev/fuse \
--device /dev/dri \
--network host \
-e S6_CMD_WAIT_FOR_SERVICES_MAXTIME=120000 \
-v ${PWD}/jellygrail:/jellygrail \
-v ${PWD}/Video_Library:/Video_Library:rshared \
-v ${PWD}/fallbackdata:/mounts/fallback \
...
````

> ⚠ Not yet tested without "--privileged --security-opt apparmor=unconfined", so I let it and thus it's unsecure. **Remember its experimental stuff.**

### 🐳 4.2/ Mounting local storages (optionnal)

Example with 2 local folders

````
...
-v /volume1/video:/mounts/local_drive1 \
-v /volumeUSB1/usbshare/video:/mounts/local_drive2 \
...
````

> ⚠ Your local folders must be mounted inside ``/mounts`` __with _local\__ prefix__ and they must contain at least a _movies/_ folder or a _shows/_ folder (it follows the same naming convention as rclone_rd )
> 
> ⚠ local-storage _movies/_ folders also supports video files that would be directly inside this folder. But shows must always be in a subfolder (ex : _video/shows/scrubs/video.mkv_)

### 🐳 4.3/ Final part

````
...
--restart unless-stopped \
--name jellygrail \
philamp/jellygrail:latest
````

## 🚀 5/ Run

1. Verify that ``./jellygrail/config/settings.env`` is populated with proper values.
2. Verify that your working directory is ``.`` (the folder containing _PREPARE.SH_ file).
3. Paste your docker command in your bash prompt and hit enter !
4. Run `sudo docker logs -f jellygrail` to monitor the output

## 📡 6/ Tasks triggering 

On ``http://your_system_ip:6502`` an http server is provided to respond to these path calls below. 
> With recent commits, only ``/backup`` should be called manually or via crontab.

### 📡 Path: ``/scan``

> Not mandatory to be set as cron as rd_progress _potentially_ calls it every 2 minutes.

Should be triggered to scan your folders in order to fill the ``./Video_Library/virtual/`` folder and refresh Jellyfin Library.

### 📡 Path: ``/backup`` 

Should be triggered frequently to backup your RD torrents (dump file stored in ``./jellygrail/data/backup``).

### 📡 Path: ``/restore``

Simple web page to choose the backup file to restore from

### 📡 Path: ``/remotescan``

> Not mandatory to be set as cron since it's triggered internally every 7 minutes (if remote endpoint is configured).

to trigger the pull of new hashes from another JellyGrail instance (if configured in ``./jellygrail/config/settings.env``)

> [!TIP]
> ``/remotescan`` is the local trigger that will call a remote service (which is actually ``/getrdincrement``) on the other JellyGrail instance (but no secured proxy or VPN is provied here, so be careful). 

> [!CAUTION]
> You should absolutely not open the python service to internet (do not open port 6502).

Basically you won't use this trigger unless you want to synchronize your RD torrents with another instance of this app (aka friend remote instance).

### 📡 Path: ``/rd_progress``

> Not mandatory to be set as cron since it's triggered internally every 2 minutes.

This is a service to check if there are changes worth calling ``/scan`` subsequently.




# 🚀 First and daily Usage

1. Verify that you have some torrents in your RD account _(JellyGrail does not provide any torrent indexer search or RD downloader)_.
2. Wait for the ``./Video_Library/virtual/`` folder to be filled (The first library scan is called within 2 minutes if there are torrents in your RD account)
    - or trigger it with  ``/scan`` (See 📡 Tasks triggering section above).
4. Access the content in ``./Video_Library/virtual/`` (in the folder you ran the docker command).
5. Jellyfin is ready to run and preconfigured with corresponding libraries on http://your_system_ip:8096.
    - Initialize the user and language and don't do anoything else (don't add librairies)
    - You can also disable Jellyfin at config time and point your plex Libraries to the ``./Video_Library/virtual/movies/`` and ``./Video_Library/virtual/shows/`` folders.
    - If you don't need the filesystem fallback functionnality and use Plex, you can as well point your Plex libraries to folders inside ``./Video_Library/actual/rar2fs_*/``.
6. For TV/Projector usage : it's recommended to use _Kodi + Jellyfin add-on_ on an Android TV device (or LibreELEC/Coreelec on specific devices).
    - or Use the new Kodi integration, see [this guide](https://github.com/philamp/jellygrail/wiki/Configure-Kodi-for-Jellygrail)
8. On Mobile device, you can install Jellyfin app and switch to native included player in its settings (in other words: avoid the webview player because it leads Jellyfin to do unnecessary transcoding)
9. Beware to have a paid RD account:
    - configure ``/backup`` cron (See 📡 Tasks triggering section above).
    - if you forgot a payment or deleted torrents by mistake, you can find your RD hashes backup in ./jellygrail/data/backup/ and use the /restore service (See 📡 Tasks triggering section above).
10. You can re-arrange your virtual/shows and virtual/movies folders the way you like as if it were a normal file-system. Future calls to /scan service won't mess-up with your changes. Don't forget to refresh Jellyfin library after your changes.
11. JellyGrail being experimental, it restarts by itself at 6.30am 🕡 every day to improve reliability
> [!TIP]
> If you restart your NAS frequently, add STOP.SH script to your shutdown tasks and START.SH script to your startup tasks so that shared mount points are still accessible (alternatively, you can use fstab)

> [!NOTE]
> 
> ``./fallbackdata/`` folder contains files added by you or any process that tries to write a file in _virtual_ folder and its subfolders.
> 
> ``./Video_Library/virtual_dv/`` is a dynamically filtered folder containing only Dolby Vision MP4/MKV files.
> 
> ``./Video_Library/virtual_bdmv/`` is a dynamically filtered folder containing only DVDs and Blu-rays data.

> [!CAUTION]
> ⚠️ If you need to have your virtual folder rebooted with fresh entries, do not delete file items in ``./Video_Library/virtual/`` folder, as it will also delete corresponding files in the underlying file-systems. Just delete the ``./jellygrail/data/bindfs/.bindfs_jelly.db`` file, **restart the docker container** and trigger a new ``/scan``


# ✅ Sanity checks / Troubleshooting

You can check it's running with following commands:

## Is the container running ? 

````
sudo docker ps
````
or
````
sudo ./PREPARE.SH
````
> Will output "Your jellygrail instance seems to be running already"

## S6 Logs + Jellygrail python service logs

````
sudo docker logs -f jellygrail
````

## Python service HTTP test

````
curl http://localhost:6502/test
````

## Jellyfin 

Open http://your_system_ip:8096 to launch Jellyfin web interface.

___

# Good to know / Known issues
- Check **🚀 First and daily Usage** section above.
- m2ts/ts files not inside a BDMV structure are ignored.
- ⚠️ Deletion of a media item which is actually in a RAR file in the underlying file-system will cause the deletion of the whole RAR file.
- ⚠️ If you've restarted your system, the docker container was maybe restarted but the rshared mount of folder ``./Video_Library/`` was not made so you have to run ``./STOPSTART.SH`` to fix it.
- JELLYFIN_FFmpeg__analyzeduration reduced to 4 seconds to be light on Real-Debrid requests and rclone cache. On some video files ffprobe report might be uncomplete. TODO: reconsider an increase of JELLYFIN_FFmpeg__analyzeduration.
- Additional Remote mounts points : You can add other rclone remote mount points (with your favorite cloud provider) by following the same structure as this: 
  - create a "*name_of_your_cloud*" folder inside the ``.`` folder, and then create a "rclone.conf" file inside it.
  - name your rclone config title (in between [ ] ) with *name_of_your_cloud* and fill the rest as you would do with rclone (you can generate a dummy config file with rclone).
  - mount the "*name_of_your_cloud*" folder to "/mounts/name_of_your_cloud":
    - (ex : ``-v ${PWD}/name_of_your_cloud:/mounts/name_of_your_cloud``) in the docker run command
  - the cloud mount source is not configurable (yet)
  - video files can't be directly located within the root of the mount (/mounts/remote_mycloud_provider/video.mkv will not be scanned it should rather be /mounts/remote_mycloud_provider/movies/Title/Title.mkv)
- Underlying files deletion:
  - REMOTE : follows rclone RD fork system : Inside folders containing multiple video files, only 1 file will be deleted (TODO: fix this issue to improve other cloud provider support). In other words it means that underlying files deletion are sometimes uncomplete in this case.
  - LOCAL : Underlying files are deleted but not folders (TODO:fix)
- RD Torrents that becomes unavailable (despite rclone fork trying to re-download them) are not fully detected by JellyGrail: corresponding virtual files are not displayed and Jellyfin will thus remove them from library but corresponding parent folders will stay (TODO: trying to fix that in a next version)
- 2 Jellyfin plugins are pre-installed:
  - ``SubBuzz:``  not enabled on library scan but can be used on induvidual items. You can enable it on library scan if you want but beware it will cause additional download requests to Real-Debrid.
  - ``Kodi Sync Queue:`` to improve the experience with Jellyfin kodi add-on 
- rclone_jelly is an experimental fork of https://github.com/itsToggle/rclone_RD to change the normal behavior of rclone's vfs_cache and thus it's not a "cache" anymore: it stores RAR/ISO file structure data to improve access reliability especially when using Real-Debrid service.
  - This cache will have a size equal to 0.5%~ of your real-debrid storage size, using it on an SSD is better (but not mandatory).
- bindfs_jelly is a fork of https://github.com/mpartel/bindfs that brings virtual folders and virtual renaming.
  - Its sqlite DB is initialized through inluded Python service that scans mounted local and remote folders (upon first start the virtual folder is empty).
- ⚠️ You can manage your assets *only* through the virtual folder (rename, delete, move) otherwise if you do it directly on the underlying filesystems, linkage will be lost between virtual tree and actual trees. TODO: autofix when linkage is dead between bindFS and underlying filesystems
- You can use a Real-Debrid download manager like [rdt-client](https://github.com/rogerfar/rdt-client) and disable downloading files to host since you don't need to have these files stored locally anymore. Thus you also have to stop using rename-and-organize feature of Radarr and Sonarr (basically you have to stop radarr/sonarr handling of finished downloads). 
- if the Video_Library folder is then accessed through a SMB protocol, renaming/moving does not seem to work (an error pops up) but it's actually working, just refresh the content of the folder and you'll see the renaming is effective. (TODO: fix that in bindfs_jelly if possible).
- When detected as extras, videos are moved into extras subfolder but without their corresponding subtitles if any

TODO:
- Fix interested language config
- Fix versions sync progress if set to unwatched
- Fix detection of container running or not running in PREPARE.SH
- Fix initialization of Jellyfin user VS. NFO generation and so on...
- Update jellyfin version
- Update rclone
- Integration of other services
- Code refactor of PREPARE.SH
- Add DNLA server
- Add sync of remote JG webdav local files
___

# Archive stuff

> [!CAUTION]
> Since July 12 2024, JellyGrail could not work properly anymore due to Real Debrid API changes impacting rclone_rd app. **This is now fixed in my fork, and with improvements** but looking at the rclone_rd code I realized that:
> - 1/ You should not not change or remove the rclone.tpl.sh ``--tpslimit 4`` argument. Otherwise you'll get 429 http errors from RD service.  **it seems to be the no.1 reason Real Debrid had issues with all API endpoints beeing overloaded because of bad rclone_rd implementations. Jellygrail always had this argument set to 4**.
> - 2/ you should absolutely let a reasonable value for ``--dir-cache-time`` argument, such as ``10s``. If reduced rclone root refresh triggers /torrents endpoint too much -> **it seems to be a potential 2nd reason Real Debrid had issues with /torrents API endpoint beeing overloaded because of bad rclone_rd implementations. Jellygrail always had this argument set to 10s**.
> - 3/ re-starting every rclone instance (jellygrail restarts overnight) is not optimal: **-> FIXED** with regular dump to file for ``/downloads`` and ``/torrent/info`` data. Only ``/torrents`` is fetched regularly.
> - 4/ rclone_rd did not not know how to unrestrict links on the fly (or to fix bad unrestricted links). **-> FIXED**
>   - And it will unrestrict only on very first listing and then keep the old link untill the user really opens the file. Huge difference from original rclone_rd. It decreases unrestricting calls a lot. Combined with jellygrail cache for RAR, ISO and ffprobe data, API endpoints and remote assets are rarely requested.
> - 5/ Log file ``/jellygrail/log/remote_realdebrid`` is still very verbose to track any issue or abnormal API calls.
> - 6/ Note that my rclone_rd fork has a tuned cache system for random access on RAR and ISO file structures, thus avoiding multiple repetitive parallel HTTP sessions. Other solution to avoid these rate-limiting related issues would be to unrestrict a new link but it is surely not a fair-use practice. So Jellygrail won't do that.
>  
> These Real Debrid related quirks are now **-> FIXED**.
> 
> The only remaining issue seems to be that accumulated unrestricted links (accumulation is on purpose) are deduplicated but not aligned upon refreshed torrents list, so this array grows a little bit too much over time, but nothing to worry about in terms of execution speed and RAM. This will be fixed way before it becomes a problem.
