<p align="center">
<img alt="jg" src="jg.png" />
</p>
<p align="center">
<strong>Virtualized filesystem merging multiples storage sources + Kodi backend emulation</strong>
</p>
<p align="center">WARNING: This project is still experimental !</p>

<p align="center">
  <a href="#prerequisites">Prerequisites</a> &bull;
  <a href="#build">Build</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#run">Run</a> &bull;
  <a href="#kodi-add-on">Kodi add-on</a> &bull;
  <a href="#usage">Usage</a> &bull;
  <a href="#troubleshooting">Troubleshooting</a> &bull;
  <a href="#performance">Performance</a>
</p>

---

- Merging multiple sources into one virtualized filesystem - https://github.com/philamp/bindfs_jelly.
  - Extras files can be written.
  - Renaming is possible.
  - Deleting in the virtual FS also deletes underlying actual files.
  - On-the-fly unraring - https://github.com/hasse69/rar2fs.
  - Real-Debrid optimized (with iso/rar structure cache) - https://github.com/philamp/rclone_jelly.
  - Keep extras and subtitles in the most compatible way.
  - ffprobe wrapper to avoid redundant ffprobe requests.
- Kodi backend emulation.
  - Kodi add-on - https://github.com/philamp/grail_kodi.
  - Metadata synced from Jellyfin.
  - Multi Kodi players support.
  - Auto-merging of movies variants.
  - Exclusive add-on features (Click to keep a media locally).
  - Lightweight WebDAV server (nginx).
  - Kodi DB server side (MariaDB).
- Zero-click Jellyfin setup.
- Easy add-on setup.
- Fully open-source solution.
- Plex compatibility.

## Prerequisites

- Linux x86 system 🐧 with Bash shell.
- Docker 🐳.
- Git client to clone this repo.
- Bypass media import from your Radarr / Sonarr instances: 
  - Uncheck `Automatically import completed downloads from download client`.
- Local torrent download config:
  - Check `Append .!qB extension to incomplete files` (example for `qBittorrent`, but other clients have similar functionnality).
- Remote torrent download config:
  - `Post Torrent Download Action` > `Don't download any files to host` (example for `RealDebrid Client`, but other clients have similar functionnality).

> [!CAUTION]
> - I'm not responsible of any data loss / I'm not responsible of any illegal use / Use at your own risks.
> - This solution does not include any torrent indexer search. 
> - Do not open ports 8085, 8089 and 6502 to the internet.
> - ⚠️ File Deletion in the virtual folder actually deletes corresponding files of underlying file-system(s).
> - Jellygrail is still experimental/BETA : you should not submit any issues to the XBMC team (Kodi backend emulation disrupts the way Kodi works by modifying the database directly !).

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

> [!TIP]
> Beware that by default this working folder will store `jellygrail` subfolder with config and runtime data such as the rclone ISO/RAR structure cache _(0.5%~ of your real-debrid storage size)_.

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

> [!WARNING]
> - If you're not running an Ubuntu system you will need to run _MOUNT.SH script (with sudo!) to make a two-way bind mount https://forums.docker.com/t/make-mount-point-accesible-from-container-to-host-rshared-not-working/108759.
>   - To mount : `sudo ./_MOUNT.SH mount`.
>   - To unmount : `sudo ./_MOUNT.SH unmount`.

> [!TIP]
> - run `sudo docker logs -f jellygrail` to monitor the console output.
> - Check http://your-server-ip:6502/status.

### Put your custom rclone.conf file
Real-Debrid support is included, but if you have another rclone compatible cloud storage you can add it this way:
- Create a dedicated folder named `remote_yourservice`.
- Put the rclone file in it.
- The rclone file content should start with `[remote_yourservice]`.
- Check docker run command above (`-v /path/remote_yourservice:/mounts/remote_yourservice  `) to mount it.

## Kodi Add-on

<img alt="jg" width="200" src="kodi.png" />\
A Kodi add-on is now provided to ease the Kodi Webdav/SQL configuration process and provide new functionnalities.

### Add-on installation
Before installing the add-on, please do the following:
* In `Settings`/`Medias`/`Library`:
  * Disable `Update library on startup`.
  * Enable `Ignore different versions on scan` (managed by the backend).
  * Disable `Ignore video extras on scan`.
* In `Settings`/`Medias`/`Videos`, (to increase scanning speed):
  * Disable `Extract video information from files`.
  * Disable `Extract chapter thumbnails`.
  * Disable `Extract thumnails from video files`.

Make sur Webdav is available on your local network : `http://your-server-ip:8085`:
- Go to `Settings` > `File mananager` > `Add source` > `Browse` > `Add network location` > `webdav`.
- `Protocol` : `WebDAV (HTTP)`.
- `Server address` : Your server local ip.
- `Port` : `8085`.
- Click `Ok`.
- Go back to `Settings` > `Add-ons` > `Install from zip file`.
- In the newly created location browse to `actual/kodi/software`.
- Click on `context.kodi_grail-2026xxxx.zip`.

> [!WARNING]
> - If you have custom `<video> <sources>` nodes in profile/sources.xml, they will be erased.
> - If you have custom `<videodatabase>` nodes in profile/advancedsettings.xml, they will be erased.


### Add-on features

At installation, the add-on auto detects the Jellygrail server and let you choose the compatible DB among existing ones, otherwise a new DB will be created on the server.

- Long click on a *movie* or a TVshow *season*, a contextual manu appears with this item: `}{ JeallyGrail Menu` at the bottom:

<img width="300" src="https://github.com/user-attachments/assets/aae497cf-3153-4e24-8c7c-32f8ac05a1c2" />

- Functionnalities:
  - keep medias
  - check their current local or remote availability
  - Admin actions
  - ... more to come

## Usage

1. Verify that you have some torrents in your RD account _(JellyGrail does not provide any torrent indexer search or RD downloader)_.
2. Monitor `sudo docker logs -f jellygrail` to check for JellyGrail progress or errors.
3. Wait for the ``./Video_Library/virtual/`` folder to be filled by the scanner.
4. Access the content in ``./Video_Library/virtual/`` :
    - WebDAV : http://your_system_ip:8085.
    - Jellyfin : http://your_system_ip:8096.
    - or Kodi (see Add-on paragraph above).
5. For Plex you can point your librairies to ``./Video_Library/virtual/movies/`` and ``./Video_Library/virtual/shows/`` folders. If you don't need the virtual filesystem functionnality, you can as well point your Plex libraries to folders inside ``./Video_Library/actual/rar2fs_*/``.
6. Beware that JellyGrail restarts by itself at 5.00am 🕡 every wednesday to improve stability.

### Folder naming pattern

#### inside the given mounted sources:

Level 1 folders containing 'movi', 'conc', 'show', or 'disc' will be scanned.

#### inside the ./Video_Library virtual folder:

At start, level 1 folders /movies and /shows are created. Do not create other folders on this level (not yet supported).

## Troubleshooting

- Jellygrail scans files that are currently downloading.
  - Solution : Configure Bittorrent client to append a temporary extension to uncomplete files.
- Some files are not scanned.
  - Solution : Verify that, inside the given mounted sources, folder names contains `movi`, `conc`, `disc` or `show`.
- Kodi does not show some posters and pictures.
  - Solution : Long click on an item then `}{ JellyGrail Menu` then `Admin actions` > `Trigger delta NFO refresh` or `Trigger full NFO refresh`.
- I moved files in the underlying filesystems.
  - Solution : Don't do that or refresh the virtual filesystem right after (see below).
- I created new folder(s) along `movies` and `shows` inside the ./Video_Library folder and they're not scanned.
  - Solution : don't do that, it's not supported yet. 
- After system restart, container does not start properly.
  - Solution : the rshared mount of folder ``./Video_Library/`` was probably not creaated, so you have to run ``./STOPSTART.SH`` to fix it.
- Jellyfin stops scanning before reaching 100% : Known issue, see _Perforamnce_ paragraph above.
  - Solution : Relaunch the jellyfin scan inside jellyfin untill it reaches 100% + increase the `memory` value in docker run command. Avoid complex bluray structures.

> [!CAUTION]
> ⚠️ If you need to have your virtual folder rebooted with fresh entries, do not delete file items in ``./Video_Library/virtual/`` folder, as it will also delete corresponding files in the underlying file-systems. Just delete the ``./jellygrail/data/bindfs/.bindfs_jelly.db`` file and **restart the docker container**

> [!TIP]
> If you restart your NAS frequently and mounts are not "rshared" by default (like it is in Ubuntu), add STOP.SH script to your shutdown tasks and START.SH script to your startup tasks.

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
Browse to http://localhost:6502/status
````

## Performance

### Jellyfin library scan issues

To workaround Jellyfin issues, the following has been implemented:

- On first setup, `LibraryScanFanoutConcurrency = 2`.
- `LD_PRELOAD /usr/lib/x86_64-linux-gnu/libjemalloc.so.2`.
- `MALLOC_TRIM_THRESHOLD_ 100000`.

### JellyGrail optimization

If you have different types of storage, you can override `jellygrail` specific subfolders with following mountpoints :

- `/jellygrail/data/bindfs` - SQLite JellyGrail database.
- `/jellygrail/data/mariadb` - MariaDB db files.
- `/jellygrail/vfs_cache` - rclone iso/rar structure cache files.

## Todo

- 💡~~inotify sources change detection~~
- 💡RD backup
- 💡Add audio support
- 💡Proxification compatibility (with automatic fallback to local sqlite DB)
- 💡Call full stack refresh whenever virtual renaming happens (or avoid renaming)
- 💡Fix versions sync progress if set to unwatched in kodi
- 💡Update jellyfin version
- 💡Update rclone
- 💡Sync to *arr metadata
- 💡Native Integration of other cloud services
- 💡Preselect audio/subtitles languages in Kodi DB
- 💡Add DNLA server ?
- 💡Other folders could be created but they must start with 'movies' or 'shows' (make jellfin conf and kodi conf accordingly)
- 💡Explain the rmeote feature
- ⚠️When detected as extras, videos are moved into extras subfolder but without their corresponding subtitles if any
- ⚠️Episode files not inside a directory are currently ignored
- ⚠️if the Video_Library folder is then accessed through a SMB protocol, renaming/moving does not seem to work (an error pops up) but it's actually working, just refresh the content of the folder and you'll see the renaming is effective. (fix that in bindfs_jelly if possible).
- ⚠️RD Torrents that becomes unavailable (despite rclone fork trying to re-download them) are not fully detected by JellyGrail: corresponding virtual files are not displayed and Jellyfin will thus remove them from library but corresponding parent folders will stay (TODO: trying to fix that in a next version)
- ⚠️Underlying files deletion:
  - REMOTE : follows rclone RD fork system : Inside folders containing multiple video files, only 1 file will be deleted (TODO: fix this issue to improve other cloud provider support). In other words it means that underlying files deletion are sometimes uncomplete in this case.
  - LOCAL : Underlying files are deleted but not folders (TODO:fix)
- ⚠️deal with m2ts/ts files 
- ⚠️ Deletion of a media item which is actually in a RAR file in the underlying file-system will cause the deletion of the whole RAR file.




