
from base import *
import sqlite3
# logger = logging.getLogger('jellygrail')

# ------ JF

connjf = None
connjf_ro = None

def jfclose():
    global connjf
    connjf.close()

def jfclose_ro():
    global connjf_ro
    connjf_ro.close()

def init_jellyfin_db_ro(db_path):
    global connjf_ro
    try:
        # Using URI to specify the database in read-only mode
        uri = f"file:{db_path}?mode=ro&nolock=1"
        connjf_ro = sqlite3.connect(uri, uri=True, timeout=5, check_same_thread=False)
        cursor = connjf_ro.cursor()
        #cursor.execute('PRAGMA journal_mode=WAL;')

    except sqlite3.OperationalError as e:
        logger.critical(f"init jf library db failed: {e}")


def init_jellyfin_db(path):
    """ Initialize the jf db connection """
    global connjf
    try:
        connjf = sqlite3.connect(path, isolation_level='DEFERRED', timeout=5)
    except sqlite3.OperationalError as e:
        logger.critical(f"init jf config db failed: {e}")

def insert_api_key(key):
    global connjf
    cursorjf = connjf.cursor()
    cursorjf.execute("INSERT OR IGNORE INTO ApiKeys (DateCreated, DateLastActivity, Name, AccessToken) VALUES (?, ?, ?, ?)", ('2024-01-30 10:10:10.1111111','0001-01-01 00:00:00','jellygrail',key))
    connjf.commit()

def fetch_api_key():
    """ Query data from the jf database """
    global connjf
    cursorjf = connjf.cursor()
    try:
        cursorjf.execute("SELECT * FROM ApiKeys WHERE Name = 'jellygrail'")
    except sqlite3.OperationalError as e:
        logger.critical(f"fetching api key from jf db failed: {e}")
        return []
    return cursorjf.fetchall()

def fetch_item_data(inputid):
    """ Query data from the jf database """
    global connjf_ro
    cursorjf = connjf_ro.cursor()
    try:
        cursorjf.execute("SELECT data FROM TypedBaseItems WHERE PresentationUniqueKey = ?",(inputid,))
    except sqlite3.OperationalError as e:
        logger.critical(f"fetching json data for videoasset from jf db failed: {e}")
        return []
    return cursorjf.fetchall()