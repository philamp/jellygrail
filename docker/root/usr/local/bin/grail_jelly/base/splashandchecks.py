from base import *
from base.constants import *

def play_config_check():
    if VERSION != CONFIG_VERSION:
        logger.error("    CONFIG/ Config version is different from app version, please rerun jg-config.sh and restart container")

    if not JF_WANTED:
        logger.warning("    CONFIG/ Jellyfin is disabled, maybe intentionnaly ? Otherwise please rerun jg-config.sh and restart container.")
    else:
        if os.getenv('JF_LOGIN') is None or os.getenv('JF_LOGIN') == "":
            logger.warning("    CONFIG/ JF wanted but JF_LOGIN environment variable not set. admin will be used as default login")
        if os.getenv('JF_PASSWORD') is None or os.getenv('JF_PASSWORD') == "":
            logger.critical("    CONFIG/ JF wanted but JF_PASSWORD environment variable not set. admin will be used as default password")
        if USE_KODI and (os.getenv('WEBDAV_LAN_HOST') is None or os.getenv('WEBDAV_LAN_HOST') == "" or os.getenv('WEBDAV_LAN_HOST') == "PASTE-WEBDAV-LAN-HOST-HERE" or os.getenv('WEBDAV_LAN_HOST') == "your-nas-ip-or-hostname"):
            logger.critical("    CONFIG/ WEBDAV_LAN_HOST environment variable not set. Nginx WebDAV server will not be reachable by Kodi")

    if not USE_KODI:
        logger.warning("    CONFIG/ Kodi not wanted, maybe intentionnaly ? Otherwise please rerun jg-config.sh and restart container.")
    else:
        if not USE_KODI_ACTUALLY:
            logger.error("    CONFIG/ Kodi wanted but Kodi main url not defined, please check your settings.env file")
        if not JF_WANTED:
            logger.warning("    CONFIG/ Kodi wanted but embedded Jellyfin disabled, Kodi can work without NFO sync from jellyfin, however make sure not to use the Local NFO data scrapper in Kodi video sources configuration.")

    if not USE_PLEX:
        logger.info("    CONFIG/ Plex integration not wanted.")
    else:
        if not USE_PLEX_ACTUALLY:
            logger.error("    CONFIG/ USE_PLEX is set but PLEX_URLS is empty, please check your settings.env file")

    if LAN_IP == '127.0.0.1':
        logger.warning("    CONFIG/ LAN IP could not be guessed, is the container connected to the network properly ? is 8.8.8.8 reachable from inside the container ?")
    elif LAN_IP != WEBDAV_LAN_HOST and USE_KODI_ACTUALLY:
        logger.warning(f"    CONFIG/ LAN IP ({LAN_IP}) is different from WEBDAV_LAN_HOST ({WEBDAV_LAN_HOST}), NFOs might not reference correct URLs")
    

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
     {GREEN}__________________{YELLOW}_{GREEN}__{YELLOW}__{GREEN}_{YELLOW}____________________|""" + RESET)


    # Some info to reassure user
    logger.info(f"|")
    logger.info(f"|  {CYAN}- Prefered languages:             {os.getenv('INTERESTED_LANGUAGES')}")
    if JF_WANTED:
        logger.info(f"|  {CYAN}- Jellyfin Metadata:              Country: {os.getenv('JF_COUNTRY')}")
        logger.info(f"|  {CYAN}                                  Language: {os.getenv('JF_LANGUAGE')}")
        logger.info(f"|  {CYAN}- Jellyfin host:                  http://{LAN_IP}:8096 (login: {os.getenv('JF_LOGIN') or 'admin'})")
        logger.info(f"|  {CYAN}- Nginx WebDAV server:            http://{WEBDAV_HOST_PORT} (no auth, local access only! see README! don't expose it!)")
        logger.info(f"|  {CYAN}- JellyGrail WebService:          http://{LAN_IP}:{WEBSERVICE_INTERNAL_PORT} (no auth, local access only! see README! don't expose it!)")
        logger.info(f"|  {CYAN}- SSDP Broadcasting on port:      {SSDP_PORT} (for Kodi auto-discovery)")
    if USE_KODI_ACTUALLY:
        logger.info(f"|  {CYAN}- Kodi host:                      {KODI_MAIN_URL}")
        logger.info(f"|  {CYAN}                                  (NFO sync: {'enabled' if JF_WANTED else 'disabled'})""")
    if REMOTE_RDUMP_BASE_LOCATION.startswith('http') or REMOTE_RDUMP_BASE_LOCATION != "http://hostname-or-ip:1234":
        logger.info(f"|  {CYAN}- Remote JellyGrail URL:          {REMOTE_RDUMP_BASE_LOCATION}")
    if RD_API_SET:  
        logger.info(f"|  {CYAN}- Real-Debrid API:                Enabled (token set)")
    if USE_PLEX_ACTUALLY:
        logger.info(f"|  {CYAN}- Plex refresh URL(s): {', '.join(PLEX_URLS_ARRAY)}")
    logger.info(f"|________________________________________ __ _")
    logger.info(f" ")