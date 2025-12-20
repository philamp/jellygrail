import os
from base.token import SSDPToken
import socket

ISO_639_2T_TO_2B = {
    "bod": "tib",  # Tibetan
    "ces": "cze",  # Czech
    "cym": "wel",  # Welsh
    "deu": "ger",  # German
    "ell": "gre",  # Greek (Modern)
    "eus": "baq",  # Basque
    "fas": "per",  # Persian
    "fra": "fre",  # French
    "hye": "arm",  # Armenian
    "isl": "ice",  # Icelandic
    "kat": "geo",  # Georgian
    "mkd": "mac",  # Macedonian
    "mri": "mao",  # Maori
    "msa": "may",  # Malay
    "mya": "bur",  # Burmese
    "nld": "dut",  # Dutch
    "ron": "rum",  # Romanian
    "slk": "slo",  # Slovak
    "sqi": "alb",  # Albanian
    "zho": "chi",  # Chinese
}

def normalize_to_iso639_2b(code: str) -> str:
    c = (code or "").strip().lower()
    return ISO_639_2T_TO_2B.get(c, c)

def guess_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        lip = s.getsockname()[0]
    except Exception as e:
        return False 
    else:
        return lip
    finally:
        s.close()

SSDPToken.set_path("/jellygrail/data/ssdp_token.txt")
SSDP_TOKEN = SSDPToken.get()

KODI_INSTANCES_FILE = "/jellygrail/data/kodi_instances.json"

NFO_BATCHES_FILES = "/jellygrail/data/nfo_batches.json"

VERSION = "20250808" # Should be aligned to settings.env.template and early_init.sh and kodi addon init_context!!!

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
#stopEvent = threading.Event()

KODI_INSTANCES_JSON = "/jellygrail/data/kodi_instances.json"
CONFIG_VERSION = os.getenv('CONFIG_VERSION') or VERSION # explain : getenv of empty returns "", "" is falsy so CONFIG_VERSION will be VERSION if not set
REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')
USE_REMOTE_RDUMP_ACTUALLY = True if REMOTE_RDUMP_BASE_LOCATION.startswith('http') and REMOTE_RDUMP_BASE_LOCATION != "http://hostname-or-ip:1234" else False
# Defaults used if not set in environment (same values are also set in settings.env.template so it's double ensured)
INT_LANG_DEFAULTS = 'fre eng' # JG made in french speaking country so its the defaults but can be set in settings.env....
LAN_IP = guess_lan_ip() or "127.0.0.1" 
INCR_KODI_REFR_MAX = 8

#default that can be overriden in config/settings.env
WEBDAV_INTERNAL_PORT = int(os.getenv('WEBDAV_INTERNAL_PORT', 0)) or 8085
WEBSERVICE_INTERNAL_PORT = int(os.getenv('WEBSERVICE_INTERNAL_PORT', 0)) or 6502
SSDP_PORT = int(os.getenv('SSDP_PORT', 0)) or 1900

# kodi mysql config
# used by ssdp message
KODI_MYSQL_CONFIG = {
    'host' : 'localhost',
    'user' : 'kodi',
    'password' : 'kodi',
    #'database' : 'kodi_video131',
    'port' : int(os.getenv('MYSQL_INTERNAL_PORT', 0)) or 6503
}

# ip set in config:
#WEBDAV_LAN_HOST = os.getenv('WEBDAV_LAN_HOST')

DEFAULT_JF_COUNTRY = "CH"

DEFAULT_JF_LANGUAGE = "fr"

SUB_FOLDER_SELECTIVITY = ('movi', 'conc', 'show', 'disc') # if a subfolder contains one of these words (case insensitive) it will be scanned, else ignored

# for fetch_nfo()
NFO_FALLBACK = "/mounts/filedefaultnfo_readme_p.txt" # put a default path

# sub exts
SUB_EXTS = ('.srt', '.sub', '.idx', '.ssa', '.ass', '.sup', '.usf')

# video exts
VIDEO_EXTENSIONS = ('.mkv', '.avi', '.mp4', '.mov', '.m4v', '.wmv', '.mpg', '.ts')

KNOWN_LANGUAGES = [
    "Afrikaans",
    "Arabic",
    "Bengali",
    "Bulgarian",
    "Catalan",
    "Cantonese",
    "Croatian",
    "Czech",
    "Danish",
    "Dutch",
    "Lithuanian",
    "Malay",
    "Malayalam",
    "Panjabi",
    "Tamil",
    "English",
    "Finnish",
    "French",
    "German",
    "Greek",
    "Hebrew",
    "Hindi",
    "Hungarian",
    "Indonesian",
    "Italian",
    "Japanese",
    "Javanese",
    "Korean",
    "Norwegian",
    "Polish",
    "Portuguese",
    "Romanian",
    "Russian",
    "Serbian",
    "Slovak",
    "Slovene",
    "Spanish",
    "Swedish",
    "Telugu",
    "Thai",
    "Turkish",
    "Ukrainian",
    "Vietnamese",
    "Welsh",
    "Sign language",
    "Algerian",
    "Aramaic",
    "Armenian",
    "Berber",
    "Burmese",
    "Bosnian",
    "Brazilian",
    "Bulgarian",
    "Cypriot",
    "Corsica",
    "Creole",
    "Scottish",
    "Egyptian",
    "Esperanto",
    "Estonian",
    "Finn",
    "Flemish",
    "Georgian",
    "Hawaiian",
    "Indonesian",
    "Inuit",
    "Irish",
    "Icelandic",
    "Latin",
    "Mandarin",
    "Nepalese",
    "Sanskrit",
    "Tagalog",
    "Tahitian",
    "Tibetan",
    "Gypsy",
]

SUB_LANG_EQUIVALENTS = {
    'fre': 'fra',
    'fra': 'fre',
    'ger': 'deu',
    'deu': 'ger',
    'gre': 'ell',
    'ell': 'gre',
    'alb': 'sqi',
    'sqi': 'alb',
    'arm': 'hye',
    'hye': 'arm',
    'baq': 'eus',
    'eus': 'baq',
    'bur': 'mya',
    'mya': 'bur',
    'chi': 'zho',
    'zho': 'chi',
    'cze': 'ces',
    'ces': 'cze',
    'dut': 'nld',
    'nld': 'dut',
    'geo': 'kat',
    'kat': 'geo',
    'ice': 'isl',
    'isl': 'ice',
    'mac': 'mkd',
    'mkd': 'mac',
    'mao': 'mri',
    'mri': 'mao',
    'may': 'msa',
    'msa': 'may',
    'per': 'fas',
    'fas': 'per',
    'rum': 'ron',
    'ron': 'rum',
    'slo': 'slk',
    'slk': 'slo',
    'tib': 'bod',
    'bod': 'tib',
    'wel': 'cym',
    'cym': 'wel',
}



# remove iso and vob and check

RDUMP_STORE_INTERVAL = 3600*4

MOUNTS_ROOT = "/mounts"

# jellyfin root for metadata and its len
JF_METADATA_ROOT = "/jellygrail/jellyfin/config/metadata"
JF_MD_SHIFT = len(JF_METADATA_ROOT)

JG_VIRTUAL = "/Video_Library/virtual"
JG_VIRT_SHIFT = len(JG_VIRTUAL)
#JG_VIRT_SHIFT_FFP = JG_VIRT_SHIFT + len("file:")

# jf_syncqueue_last_requested_date_file
JFSQ_LAST_REQUEST = "/jellygrail/data/jf_sync_queue_last_request.txt"

# folder to store nfos
JFSQ_STORED_NFO = "/jellygrail/data/nfos"
JFSQ_STORED_NFO_SHIFT = len(JFSQ_STORED_NFO)

#should not be urlencoded
#SAFE="()[]!$&'()*+,;=:@"

SAFE=":/?#[]@!$&'()*+,;="

# rd local dump cron-backups folder
RDUMP_BACKUP_FOLDER = '/jellygrail/data/backup'

# rd local dump location
RDUMP_FILE = '/jellygrail/data/rd_dump.json'

# pile file
PILE_FILE = '/jellygrail/data/rd_pile.json'

# rd last date of import file
RDINCR_FILE = '/jellygrail/data/rd_incr.txt'

# remote rd pile key
REMOTE_PILE_KEY_FILE = '/jellygrail/data/remote_pile_key.txt'

# getenvs

RD_APITOKEN = os.getenv('RD_APITOKEN') or ""
RD_API_SET = RD_APITOKEN != "PASTE-YOUR-KEY-HERE" and RD_APITOKEN != ""

INTERESTED_LANGUAGES = os.getenv('INTERESTED_LANGUAGES') or INT_LANG_DEFAULTS

WEBDAV_HOST_PORT = LAN_IP + ":" + str(WEBDAV_INTERNAL_PORT)

# plain list from spaced string, the first one is the preferred one for context menu in kodi
codes = list(dict.fromkeys(INTERESTED_LANGUAGES.split()))

# list normalized to iso639-2b
USED_LANGS_JF = [normalize_to_iso639_2b(tok) for tok in codes]

# list widened with equivalents, but add them only once
USED_LANGS = codes.copy()
for code in codes:
    if code in SUB_LANG_EQUIVALENTS:
        eq = SUB_LANG_EQUIVALENTS[code]
        if eq not in USED_LANGS:
            USED_LANGS.append(eq)

# always add und, but only once
if "und" not in USED_LANGS:
    USED_LANGS.append("und")



PROXY_URL = os.getenv('PROXY_URL') if (os.getenv('PROXY_URL') != "https://hostname-or-ip:1234" and os.getenv('PROXY_URL') != "") else "0"

USE_KODI = (os.getenv('USE_KODI') or "y") != "n"
USE_KODI_ACTUALLY = USE_KODI
JF_WANTED = (os.getenv('JF_WANTED') or "y") != "n"
JF_WANTED_ACTUALLY = JF_WANTED # ...AND config is true but we don't do config here TODO low-priority
PLEX_URLS_ARRAY = os.getenv('PLEX_URLS', '').split('|')

USE_PLEX = (os.getenv('USE_PLEX') or "y") != "n"
USE_PLEX_ACTUALLY = USE_PLEX and len(PLEX_URLS_ARRAY) > 0 and PLEX_URLS_ARRAY[0] != ""