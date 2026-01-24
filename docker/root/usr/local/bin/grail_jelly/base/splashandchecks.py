from base import *
from base.constants import *

def play_config_check():
    if VERSION != CONFIG_VERSION:
        logger.error("    CONFIG| Config version is different from app version, please rerun jg-config.sh and restart container")

    if not JF_WANTED:
        logger.warning("    CONFIG| Jellyfin is disabled, maybe intentionnaly ? Otherwise please rerun jg-config.sh and restart container.")
    else:
        if os.getenv('JF_LOGIN') is None or os.getenv('JF_LOGIN') == "":
            logger.warning("    CONFIG| JF wanted but JF_LOGIN environment variable not set. admin will be used as default login")
        if os.getenv('JF_PASSWORD') is None or os.getenv('JF_PASSWORD') == "":
            logger.critical("    CONFIG| JF wanted but JF_PASSWORD environment variable not set. admin will be used as default password")

    if not USE_KODI:
        logger.warning("    CONFIG| Kodi not wanted, maybe intentionnaly ? Otherwise please rerun jg-config.sh and restart container.")
    else:
        if not JF_WANTED:
            logger.warning("    CONFIG| Kodi wanted but embedded Jellyfin disabled, Kodi can work without NFO sync from jellyfin, but make sure not to use the Local NFO data scrapper in Kodi video sources configuration.")

    if not USE_PLEX:
        logger.warning("    CONFIG| Plex integration not wanted.")
    else:
        if not USE_PLEX_ACTUALLY:
            logger.error("    CONFIG| USE_PLEX is set but PLEX_URLS is empty, please check your settings.env file")

    if LAN_IP == '127.0.0.1':
        logger.warning("    CONFIG| LAN IP could not be guessed, is the container connected to the network properly ? is 8.8.8.8 reachable from inside the container ?")
    

def play_splash():

    print( """
""" + YELLOW + " ________________________ github.com/philamp/" + f"""
|
|       ___     _ _        ____          _ _
|      |_  |___| | |_   _ / __/ _ ____ _(_) |
|__   _  | / _ \ | | | | | |  _/ '_/ _` | | |  __
     / |_|   __/ |   |_|   |_| | |  (_| | | |    |
     \____/\___,_,_|\__, /\____,_| \__,_,_,_|    |
                     |__/                        |
                                    v{VERSION}    |
 {CYAN}____________________{YELLOW}___{CYAN}___{YELLOW}______________________|""" + CYAN)


    # Some info to reassure user
    print(f"|")
    print(f"|  - Prefered languages:             {os.getenv('INTERESTED_LANGUAGES')}")
    if JF_WANTED:
        print(f"|  - Jellyfin Metadata:              Country: {os.getenv('JF_COUNTRY')}")
        print(f"|                                    Language: {os.getenv('JF_LANGUAGE')}")
        print(f"|  - Jellyfin host:                  http://{LAN_IP}:8096 (login: {os.getenv('JF_LOGIN') or 'admin'})")
        print(f"|  - Nginx WebDAV server for local:  http://{WEBDAV_HOST_PORT} (no auth, local access only! see README! don't expose it!)")
        print(f"|  - Nginx WebDAV server as remote:  http://{WEBDAV_REMOTE_HOST_PORT} (no auth, local access only! see README! don't expose it!)")
        print(f"|  - JellyGrail WebService:          http://{LAN_IP}:{WEBSERVICE_INTERNAL_PORT} (no auth, local access only! see README! don't expose it!)")
        print(f"|  - SSDP Multicast on port:         {SSDP_PORT} (for auto-discovery)")
        print(f"|  - MySQL Port:                     {KODI_MYSQL_CONFIG.get('port', 0)}")
    if USE_KODI_ACTUALLY:
        print(f"|  - Kodi NFO Sync:                  {'Enabled' if JF_WANTED else 'Disabled, do not use Kodi NFO scrapper'}")                       
    if USE_REMOTE_RDUMP_ACTUALLY:
        print(f"|  - Remote JG WS URL:               {REMOTE_RDUMP_BASE_LOCATION}")
    if USE_REMOTE_WED_DAV_ACTUALLY:
        print(f"|  - Remote JG WebDAV URL:           {REMOTE_WED_DAV_LOCATION}")
    if RD_API_SET:
        print(f"|  - Real-Debrid API:                Enabled (token set)")
    if USE_PLEX_ACTUALLY:
        print(f"|  - Plex refresh URL(s): {', '.join(PLEX_URLS_ARRAY)}")
    else:
        print(f"|  - Plex integration:               Disabled")
    print(f"|________________________________________________,")
    print(f" ")