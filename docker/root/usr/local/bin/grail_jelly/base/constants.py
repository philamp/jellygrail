import os
# Defaults used if not set in environment (same values are also set in settings.env.template so it's double ensured)
INT_LANG_DEFAULTS = 'fre eng' # JG made in french speaking country so its the defaults but can be set in settings.env....

DEFAULT_JF_COUNTRY = "CH"

DEFAULT_JF_LANGUAGE = "fr"

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

INTERESTED_LANGUAGES = os.getenv('INTERESTED_LANGUAGES') or INT_LANG_DEFAULTS

codes = set(INTERESTED_LANGUAGES.split())
USED_LANGS = set(codes) # the result
USED_LANGS_JF = USED_LANGS.copy()
for code in codes:
    if code in SUB_LANG_EQUIVALENTS:
        USED_LANGS.add(SUB_LANG_EQUIVALENTS[code])
USED_LANGS.add("und")