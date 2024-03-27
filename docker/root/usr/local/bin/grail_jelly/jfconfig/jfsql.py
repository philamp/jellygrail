
from base import *
import sqlite3
# logger = logging.getLogger('jellygrail')

# ------ JF

connjf = None

def jfclose():
    global connjf
    connjf.close()

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