<p align="center">
<img alt="jg" src="jg.png" />
</p>
<p>
<strong>One compatibility layer to merge them all, manage them all in Jellyfin and play them all in Kodi ; and in their RAR keep them</strong>
</p>
<p align="center">This project is still experimental, way more stable than previous release though</p>

<p align="center">
  <a href="#prerequisites">Prerequisites</a> &bull;
  <a href="#build">Build</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#run">Run</a> &bull;
  <a href="#performance">Performance</a> &bull;
  <a href="#add-on">Add-on</a>
</p>

---

- Merging multiple sources into one virtualized filesystem - https://github.com/philamp/bindfs_jelly
  - Extras files can be written
  - Renaming is possible
  - Deleting in the virtual FS also deletes underlying actual files
- On-the-fly unraring - https://github.com/hasse69/rar2fs
- Real-Debrid optimized (with iso/rar structure cache) - https://github.com/philamp/rclone_jelly
- Zero-click Jellyfin setup
- Lightweight WebDAV server - nginx
- Keep extras and subtitles in the most compatible way
- Kodi backend emulation / Kodi add-on
  - Metadata synced from Jellyfin (manage your medias in Jellyfin only)
  - Multi database support - MariaDB
  - Auto-merging of movies variants
  - Click to keep a media locally
- Fully open-source solution
- Plex compatibility

## Prerequisites

- Linux x86 system 🐧 with Bash shell.
- Docker 🐳.
- Git client to clone this repo.
- Configure Bypass media import from your Radarr / Sonarr : Uncheck `Automatically import completed downloads from download client`.
- Local torrent download
  - check `Append .!qB extension to incomplete files` in qBittorrent (or equivalent in other clients)
- Remote torrent manager
  - Configure RealDebrid client not to download files.

> [!CAUTION]
> - I'm not responsible of any data loss / I'm not responsible of any illegal use / Use at your own risks.
> - This solution does not include any torrent indexer search. 
> - Do not open ports 8085, 8089 and 6502 to the internet.
> - ⚠️ File Deletion in the virtual folder actually deletes corresponding files of underlying file-system(s).
> - Jellygrail is still experimental/BETA : you should not submit any issues to the XBMC (Kodi backend emulation disrupts the way Kodi works by modifying with the database directly !).

## Build

````
git clone https://github.com/philamp/jellygrail.git
cd jellygrail/docker
sudo docker build -t philamp/jellygrail .
````

> [!TIP]
> To update, replace the git clone command by `git pull`

## Configuration

While compilation takes place, run the config wizard:
````
cd ..
sudo chmod u+x jf-config.sh _MOUNT.SH
./jg-config.sh
````

## Run
Once compilation is done, launch your adapted variant of this docker run command, still inside the root folder of the projet.
````
sudo docker run -d --privileged --security-opt apparmor=unconfined \
--cap-add MKNOD \
--cap-add SYS_ADMIN \
--device /dev/fuse \
--device /dev/dri \
--network host \
--memory="8g"                                                 # Increase if you have a very big library \
--log-driver json-file \
--log-opt max-size=10m \
--log-opt max-file=7 \
-e S6_CMD_WAIT_FOR_SERVICES_MAXTIME=120000                    # Avoid s6 failing when services are taking time \
-v ${PWD}/jellygrail:/jellygrail                              # Stores config and runtime data \
-v ${PWD}/Video_Library:/Video_Library:rshared                # The resulting virtualized folder \
-v ${PWD}/fallbackdata:/mounts/fallback                       # where extra files are really stored \
-v /path/to/local-video-imports:/mounts/local_import          # this is where "click-to-keep" medias will be stored \
-v /path/to/a-local-video-folder:/mounts/local_drive1         # the '/mounts/local_' pattern should be used \
-v /path/to/another-local-video-folder:/mounts/local_drive2   # the '/mounts/local_' pattern should be used \
-v /path/remote_yourservice:/mounts/remote_yourservice        # the '/mounts/remote_' pattern should be used, see below \
--restart unless-stopped \
--name jellygrail \
philamp/jellygrail:latest
````

Then run `sudo docker logs -f jellygrail` to monitor the output and have some helpful info.

> [!TIP]
> Beware that by default this working folder will store `jellygrail` subfolder with config and runtime data such as the rclone ISO/RAR structure cache _(0.5%~ of your real-debrid storage size)_.

> [!WARNING]
> - If you're not running an Ubuntu/Debian system you will need to run _MOUNT.SH script (with sudo!) to make a two-way bind mount https://forums.docker.com/t/make-mount-point-accesible-from-container-to-host-rshared-not-working/108759
>   - To mount : `sudo ./_MOUNT.SH mount`
>   - To unmount : `sudo ./_MOUNT.SH unmount`

### Put your custom rclone.conf file
Real-Debrid support is included, but if you have another cloud storage service ocmpatible with rclone you can add it this way:
- Create a dedicated folder named `remote_yourservice`
- Put the rclone file in it
- The rclone file content should start with `[remote_yourservice]`

### Folder selectivity inside the given mounted sources

Folders containing 'movi', 'conc', 'show', or 'disc' will be scanned

### Folder selectivity inside the ./Video_Library

At start /movies and /shows are created. Do not create other folders on this level.

## Performance

To workaround Jellyfin issues, the following has been implemented:

- On first setup, `LibraryScanFanoutConcurrency = 2` (can be modified)
- `LD_PRELOAD /usr/lib/x86_64-linux-gnu/libjemalloc.so.2`
- `MALLOC_TRIM_THRESHOLD_ 100000`

> [!TIP]
> - Avoid complex bluray copies
> - Increase `m̀emory` in docker run attribute while keeping it well under system max


## Add-on

A Kodi add-on is now provided to ease the installation process and provide new functionnalities.

### Add-on installation

Before you install Add-on please do the following:
* In `Settings`/`Medias`/`Library`:
  * Disable `Update library on startup` (Automatically triggered by Jellygrail)
  * Enable `Ignore different versions on scan` (Automatically merged by Jellygrail SQL special ops)
  * Disable `Ignore video extras on scan`
* In `Settings`/`Medias`/`Videos`, disable all "Extract *" settings (important to speed up scanning):
  * Disable `Extract video information from files` (Already present in NFO generated by Jellygrail)
  * Disable `Extract chapter thumbnails`
  * Disable `Extract thumnails from video files`

Make sur Webdav is available on your local network : `http://your-server-ip:8085`:
- Go to `Settings` > `File mananager` > `Àdd source` > `Browse` > `Add network location` > `webdav`
- `Protocol` : `WebDAV (HTTP)`
- `Server address` : Your server local ip 
- `Port` : `8085` (default)
- Click `ok`
- Go back to `Settings` > `Add-ons` > `Install from zip file`
- Browse to the newly created location
- Go to `actual/kodi/software`
- Click on the obvious choice

> [!WARNING]
> - If you have custom `video <sources>` in profile/sources.xml, they will be erased
> - If you have custom `<videodatabase>` in profile/advancedsettings.xml, they will be erased


### Add-on features

At installation, the add-on auto detects the Jellygrail server and let you choose the compatible DB you can use among existing ones, otherwise a new db will be created on the server.

- Long click on a movie or a TVshow *season*, the last item `}{ JeallyGrail Menu` will appear:

<img width="300" src="https://github.com/user-attachments/assets/aae497cf-3153-4e24-8c7c-32f8ac05a1c2" />

- Then you have some new functionnalities
  - keep medias
  - check their current local or remote availability





## Usage

1. Verify that you have some torrents in your RD account _(JellyGrail does not provide any torrent indexer search or RD downloader)_.
2. Wait for the ``./Video_Library/virtual/`` folder to be filled (The first library scan is called within 15 seconds if there are torrents in your RD account)
3. Access the content in ``./Video_Library/virtual/`` via WebDAV (http://your_system_ip:8085), Jellyfin or Kodi 
4. For Plex you can point your librairies to ``./Video_Library/virtual/movies/`` and ``./Video_Library/virtual/shows/`` folders. If you don't need the virtual filesystem functionnality, you can as well point your Plex libraries to folders inside ``./Video_Library/actual/rar2fs_*/``.
5. On Mobile device, you can install Jellyfin app and switch to native included player in its settings (avoid the webview player because it leads Jellyfin to do unnecessary transcoding)
6. JellyGrail being experimental, it restarts by itself at 6.30am 🕡 every wednesday

## Troubleshoot

- Jellygrail scans files that are currently downloading
  - Solution : Configure Bittorrent client to append a temporary extension to uncomplete files
- Some files are not scanned
  - Solution : Verify that, inside the given mounted sources, folder names contains `movi`, `conc`, `disc` or `show`
- Kodi does not show some posters and pictures
  - Long click on an item then `}{ JellyGrail Menu` then `Admin actions` > `Trigger delta NFO refresh` or `Trigger full NFO refresh`

> [!CAUTION]
> ⚠️ If you need to have your virtual folder rebooted with fresh entries, do not delete file items in ``./Video_Library/virtual/`` folder, as it will also delete corresponding files in the underlying file-systems. Just delete the ``./jellygrail/data/bindfs/.bindfs_jelly.db`` file and **restart the docker container**

### Is the container running ? 

````
sudo docker ps
````

### Container logs

````
sudo docker logs -f jellygrail
````

### Python service HTTP test

````
curl http://localhost:6502/app/test
````

### Jellyfin 

Open http://your_system_ip:8096 to launch Jellyfin web interface.

## Todo

- Local sources change detection
- RD backup
- Add audio support
- Call full stack refresh whenever virtual renaming happens
- Fix versions sync progress if set to unwatched in kodi
- Update jellyfin version
- Update rclone
- Integration of other services
- Add DNLA server
- Other folders could be created but they must start with 'movies' or 'shows' (make jellfin conf and kodi conf accordingly)
- Explain the rmeote feature

----







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




# ✅ Sanity checks / Troubleshooting

You can check it's running with following commands:





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


