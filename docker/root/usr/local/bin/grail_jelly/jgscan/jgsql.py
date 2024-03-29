from base import *
import sqlite3
# logger = logging.getLogger('jellygrail')

conn = None

db_path = "/jellygrail/.bindfs_jelly.db"

create_table_sql = '''
CREATE TABLE IF NOT EXISTS main_mapping (
    virtual_fullpath TEXT PRIMARY KEY COLLATE SCLIST,
    actual_fullpath TEXT,
    jginfo_rd_torrent_folder TEXT,
    jginfo_rclone_cache_item TEXT,
    mediatype TEXT
);
'''

update_table_sql_v2 = '''
ALTER TABLE main_mapping ADD COLUMN last_updated INTEGER;
'''

create_index = '''
CREATE INDEX IF NOT EXISTS rename_depth ON main_mapping (virtual_fullpath COLLATE SCDEPTH);
'''

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

def init_database():
    """ Initialize the database connection """
    global conn
    conn = sqlite3.connect(db_path, isolation_level='DEFERRED')
    conn.enable_load_extension(True)
    conn.load_extension("/usr/local/share/bindfs-jelly/libsupercollate.so")
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    cursor.execute(create_index)
    sqcommit()
    """ TABLE UPDATES : v2 """
    try:
        cursor.execute(update_table_sql_v2)
        sqcommit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.info("> UPDATE DATAMODEL : The column already exists. Skipping addition.")
        else:
            logger.critical("> An operational error occurred:", e)


def insert_data(virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype = None):
    """ Insert data into the database """
    global conn
    cursor = conn.cursor()
    # when a virtual_path already exists, it updates all other fileds but virtual_path 
    # ... but to avoid downgrading a mediatype value from something to None, on conflict we don't insert if mediatype == none for the item we overwrite
    # (mediatype is then used in bindfs to do filtering based on virtual folders suffixes (virtual_dv, virtual_bdmv))
    if mediatype != None:
        cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, last_updated) VALUES (depenc(?), ?, ?, depenc(?), ?, strftime('%s', 'now')) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), mediatype=?, last_updated=strftime('%s', 'now')", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype))
    else:
        cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, last_updated) VALUES (depenc(?), ?, ?, depenc(?), strftime('%s', 'now')) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), last_updated=strftime('%s', 'now')", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item))


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

# ------ JF

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