from base import *
from base.littles import *
import sqlite3
# logger = logging.getLogger('jellygrail')

conn = None

db_path = "/jellygrail/.bindfs_jelly.db"

def sqcommit():
    """ Commit the transaction """
    global conn
    conn.commit()

def sqclose():
    global conn
    conn.close()

def sqrollback():
    """ Rollback the transaction """
    global conn
    conn.rollback()

def set_current_version(version):
    # Mise à jour de la version dans la base de données
    global conn
    cursor = conn.cursor()
    conn.execute('DELETE FROM schema_version')
    conn.execute('INSERT INTO schema_version (version) VALUES (?)', (version,))

def get_current_version():
    global conn
    cursor = conn.cursor()
    # Lecture de la version actuelle depuis la base de données
    try:
        cursor.execute('SELECT version FROM schema_version')
        row = cursor.fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        # Si la table schema_version n'existe pas encore, return default value
        return 0

def apply_migration(migration_file):
    global conn
    cursor = conn.cursor()
    with open(migration_file, 'r') as file:
        sql = file.read()
    try:
        conn.executescript(sql)
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.debug("jgscan/jgsql/apply_migration | The column already exists. Skipping addition.")
            return True
        else:
            logger.critical("jgscan/jgsql/apply_migration | Migration failure, SQLite error is: ", e)
            return False
    else:
        return True

def jg_datamodel_migration():
    global conn
    cursor = conn.cursor()

    # look for the current version if possible
    incr = get_current_version()

    sqlfiles_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datamodels")

    for migration_file in sorted(os.listdir(sqlfiles_folder)):
        migration_version = int(get_wo_ext(migration_file))
        if migration_version > incr:
            if apply_migration(os.path.join(sqlfiles_folder, migration_file)):
                set_current_version(migration_version)
                sqcommit()
                logger.warning(f'Applied {migration_file} migr. file and commited')
            else:
                logger.critical("Migration failure just happened")


def init_database():
    """ Initialize the database connection """
    global conn
    conn = sqlite3.connect(db_path, isolation_level='DEFERRED')
    conn.enable_load_extension(True)
    conn.load_extension("/usr/local/share/bindfs-jelly/libsupercollate.so")



def insert_data(virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype = None, ffprobe = None):
    """ Insert data into the database """
    global conn
    cursor = conn.cursor()
    # when a virtual_path already exists, it updates all other fileds but virtual_path 
    # ... but to avoid downgrading a mediatype value from something to None, on conflict we don't insert if mediatype == none for the item we overwrite
    # (mediatype is then used in bindfs to do filtering based on virtual folders suffixes (virtual_dv, virtual_bdmv))
    if mediatype != None:
        cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, last_updated, ffprobe) VALUES (depenc(?), ?, ?, depenc(?), ?, strftime('%s', 'now'), ?) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), mediatype=?, last_updated=strftime('%s', 'now'), ffprobe=?", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, ffprobe, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, ffprobe))
    else:
        cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, last_updated, ffprobe) VALUES (depenc(?), ?, ?, depenc(?), strftime('%s', 'now'), ?) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), last_updated=strftime('%s', 'now'), ffprobe=?", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, ffprobe, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, ffprobe))


def fetch_present_virtual_folders():
    """ Query data from the database """
    global conn
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT depdec(virtual_fullpath), SUBSTR(depdec(virtual_fullpath), 2, 5) FROM main_mapping WHERE actual_fullpath IS NULL AND SUBSTR(virtual_fullpath, 1, 4) = '0002'")
    return cursor.fetchall()

def fetch_present_release_folders():
    """ Query data from the database """
    global conn
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT jginfo_rd_torrent_folder FROM main_mapping')
    return cursor.fetchall()

def ls_virtual_folder(folder_path):
    global conn
    cursor = conn.cursor()
    cursor.execute("SELECT depdec(virtual_fullpath) FROM main_mapping WHERE virtual_fullpath BETWEEN depenc( ? || '//') AND depenc( ? || '/\\')", (folder_path, folder_path))
    return cursor.fetchall()


'''
def init_jellyfin_db(path):
    """ Initialize the jf db connection """
    global connjf
    connjf = sqlite3.connect(path, isolation_level='DEFERRED')

def insert_api_key(key):
    global connjf
    cursorjf = connjf.cursor()
    cursorjf.execute("INSERT OR IGNORE INTO ApiKeys (DateCreated, DateLastActivity, Name, AccessToken) VALUES (?, ?, ?, ?)", ('2024-01-30 10:10:10.1111111','0001-01-01 00:00:00','jellygrail',key))
    connjf.commit()

def fetch_api_key():
    """ Query data from the jf database """
    global connjf
    cursorjf = connjf.cursor()
    cursorjf.execute("SELECT * FROM ApiKeys WHERE Name = 'jellygrail'")
    return cursorjf.fetchall()
'''