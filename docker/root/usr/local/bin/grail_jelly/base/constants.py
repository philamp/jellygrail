# sub exts
SUB_EXTS = ('.srt', '.sub', '.idx', '.ssa', '.ass', '.sup', '.usf')

# video exts
VIDEO_EXTENSIONS = ('.mkv', '.avi', '.mp4', '.mov', '.m4v', '.wmv', '.mpg', '.ts')

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

# kodi mysql config
KODI_MYSQL_CONFIG = {
    'host' : 'localhost',
    'user' : 'kodi',
    'password' : 'kodi',
    'database' : 'kodi_video131',
    'port' : 6503
}