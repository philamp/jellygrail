from base import *
from base.littles import *
import sqlite3
# logger = logging.getLogger('jellygrail')

def bdd_install():

    dbinstance = jellyDB()
    #init_database() already in the object init
    # Play migrations
    dbinstance.jg_datamodel_migration()

    # create movies and shows parent folders
    dbinstance.insert_data("/movies", None, None, None, 'all')
    dbinstance.insert_data("/shows", None, None, None, 'all')
    #insert_data("/concerts", None, None, None, 'all')
    dbinstance.sqcommit()
    dbinstance.sqclose()
    
    del dbinstance

class jellyDB:
    db_path = "/jellygrail/data/bindfs/.bindfs_jelly.db"
    sq_extension = "/usr/local/share/bindfs-jelly/libsupercollate.so"

    def __init__(self, cst: bool = True):
        self.conn = sqlite3.connect(jellyDB.db_path, isolation_level='DEFERRED', check_same_thread=cst, timeout=5)
        self.conn.execute("PRAGMA journal_mode=WAL;") # can be called multiple times (set in db file)
        if True or not getattr(jellyDB, "_extension_loaded", False): # should be caled only once
            self.conn.enable_load_extension(True)
            self.conn.load_extension(jellyDB.sq_extension)
            jellyDB._extension_loaded = True
        # below is to detect a potential race condition but will never happen as we load the extension far before multithreaded db writers use the class, so no need to go further in precision
        '''
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT depenc('/wqefwqfewq')")
        except sqlite3.OperationalError as e:
            logger.critical("  JELLY-DB/ lib supercollate non chargée dans ce thread")
        '''
        
    def sqbegin(self):
        if not self.conn.in_transaction:
            self.conn.execute('BEGIN IMMEDIATE')

    def sqcommit(self):
        self.conn.commit()

    def sqclose(self):
        self.conn.close()

    def apply_migration(self, migration_file):
        with open(migration_file, 'r') as file:
            sql = file.read()
        try:
            self.conn.executescript(sql)
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.debug("  JELLY-DB/ The column already exists. Skipping addition.")
                return True
            else:
                logger.critical("  JELLY-DB/ Migration failure, SQLite error is: ", e)
                return False
        else:
            return True

    def set_current_version(self, version):
        self.conn.execute('DELETE FROM schema_version')
        self.conn.execute('INSERT INTO schema_version (version) VALUES (?)', (version,))

    def get_current_version(self):
        cursor = self.conn.cursor()
        # Lecture de la version actuelle depuis la base de données
        try:
            cursor.execute('SELECT version FROM schema_version')
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            # Si la table schema_version n'existe pas encore, return default value
            return 0

    def jg_datamodel_migration(self):
        incr = self.get_current_version()
        sqlfiles_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datamodels")
        for migration_file in sorted(os.listdir(sqlfiles_folder)):
            migration_version = int(get_wo_ext(migration_file))
            if migration_version > incr:
                if self.apply_migration(os.path.join(sqlfiles_folder, migration_file)):
                    self.set_current_version(migration_version)
                    self.sqcommit()
                    logger.warning(f'  JELLY-DB/ Applied {migration_file} migr. file and commited')
                else:
                    logger.critical("  JELLY-DB/ Migration failure just happened")


    def insert_data(self, virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype = None, ffprobe = None, completion = None):
        cursor = self.conn.cursor()
        # when a virtual_path already exists, it updates all other fileds but virtual_path 
        # ... but to avoid downgrading a mediatype value from something to None, on conflict we don't insert if mediatype == none for the item we overwrite
        # (mediatype is then used in bindfs to do filtering based on virtual folders suffixes (virtual_dv, virtual_bdmv))
        if mediatype != None:
            cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, last_updated, ffprobe, completion) VALUES (depenc(?), ?, ?, depenc(?), ?, strftime('%s', 'now'), ?, ?) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), mediatype=?, last_updated=strftime('%s', 'now'), ffprobe=?, completion= CASE WHEN main_mapping.completion != 2 THEN ? ELSE main_mapping.completion END", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, ffprobe, completion, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, ffprobe, completion))
        else:
            cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, last_updated, ffprobe, completion) VALUES (depenc(?), ?, ?, depenc(?), strftime('%s', 'now'), ?, ?) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), last_updated=strftime('%s', 'now'), ffprobe=?, completion= CASE WHEN main_mapping.completion != 2 THEN ? ELSE main_mapping.completion END;", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, ffprobe, completion, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, ffprobe, completion))


    def fetch_present_virtual_folders(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT depdec(virtual_fullpath), SUBSTR(depdec(virtual_fullpath), 2, 5) FROM main_mapping WHERE actual_fullpath IS NULL AND SUBSTR(virtual_fullpath, 1, 4) = '0002'")
        return cursor.fetchall()

    def fetch_present_release_folders(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT jginfo_rd_torrent_folder FROM main_mapping')
        return cursor.fetchall()

    def lc_set_policy_virtual_folder(self, folder_path, Qpolicy, Lpolicy, comp):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE main_mapping SET q_policy=?, l_policy=?, completion=? WHERE virtual_fullpath=depenc(?)", (Qpolicy, Lpolicy, comp, folder_path))


    def lc_set_dl_completion_specific(self, path, comp):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE main_mapping SET completion=? WHERE virtual_fullpath=depenc(?)", (comp, path))


    def lc_set_dl_completion(self, likepath, comp):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE main_mapping SET completion=? WHERE virtual_fullpath LIKE '%' || ? || '%'", (comp, likepath))

    def lc_update_actual_path(self, vpath, actual_path):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE main_mapping SET actual_fullpath=? WHERE virtual_fullpath=depenc(?)", (actual_path, vpath))

    def lc_update_blacklist(self, vpath):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE main_mapping SET blacklist=blacklist+1 WHERE virtual_fullpath LIKE '%' || ? || '%'", (vpath,))


    def lc_update_policy_completion(self, vpath, comp):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE main_mapping SET completion=? WHERE virtual_fullpath=depenc(?) AND actual_fullpath is null", (comp, vpath)) 

    def ls_virtual_folder(self, folder_path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT depdec(virtual_fullpath) FROM main_mapping WHERE virtual_fullpath BETWEEN depenc( ? || '//') AND depenc( ? || '/\\')", (folder_path, folder_path))
        # scdepth : between "" and "/\" ; sclist (default, like above) : between "//" and "/\", uses a custom sqlite collation function in bindfs_jelly and loaded from here : "/usr/local/share/bindfs-jelly/libsupercollate.so"
        return cursor.fetchall()
    

    # here maybe we have to get the other fields (jginfo_rd_torrent_folder, jginfo_rclone_cache_item)
    def lc_get_dl_playlist(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT depdec(virtual_fullpath), actual_fullpath, completion FROM main_mapping WHERE completion < 2 AND actual_fullpath is not null AND blacklist < 4 ORDER by blacklist ASC")
        # scdepth : between "" and "/\" ; sclist (default, like above) : between "//" and "/\", uses a custom sqlite collation function in bindfs_jelly and loaded from here : "/usr/local/share/bindfs-jelly/libsupercollate.so"
        return cursor.fetchall()
    
    def lc_ls_parent_paths(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT depdec(virtual_fullpath), q_policy, l_policy, completion FROM main_mapping WHERE completion=0 AND actual_fullpath is null")
        # scdepth : between "" and "/\" ; sclist (default, like above) : between "//" and "/\", uses a custom sqlite collation function in bindfs_jelly and loaded from here : "/usr/local/share/bindfs-jelly/libsupercollate.so"
        return cursor.fetchall()
    
    # list only media files here with "ffprobe is not null"
    def lc_ls_virtual_folder(self, folder_path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT depdec(virtual_fullpath), actual_fullpath, completion FROM main_mapping WHERE ffprobe is not null AND virtual_fullpath BETWEEN depenc( ? || '//') AND depenc( ? || '/\\')", (folder_path, folder_path))
        # scdepth : between "" and "/\" ; sclist (default, like above) : between "//" and "/\", uses a custom sqlite collation function in bindfs_jelly and loaded from here : "/usr/local/share/bindfs-jelly/libsupercollate.so"
        return cursor.fetchall()

    def get_path_props(self, path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT ffprobe FROM main_mapping WHERE virtual_fullpath = depenc(?)", (path,))
        return cursor.fetchall()
    
    # TODO maybe not used anymore
    def get_path_actual(self, path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT actual_fullpath FROM main_mapping WHERE virtual_fullpath = depenc(?)", (path,))
        return cursor.fetchall()

    def get_path_props_woext(self, path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT ffprobe FROM main_mapping WHERE virtual_fullpath LIKE '%' || ? || '%'", (path,))
        return cursor.fetchall()

# one sqlite READ ONLY thread for nforead and ffprobewrappe
class staticDB:
    # The unique shared instance
    s: jellyDB = None

    @classmethod 
    def sinit(cls):
        if cls.s is None: #ensure sinit is not called multiple times
            cls.s = jellyDB(cst=False)

'''
# interesting but overkill
class _StaticDBMeta(type):
    """Métaclasse qui redirige tous les appels vers l'instance unique."""
    _instance: jellyDB = None

    def __call__(cls):
        if cls._instance is None:
            cls._instance = jellyDB()
        return cls._instance

    def __getattr__(cls, name):
        # Délègue automatiquement les attributs manquants à l'instance
        if cls._instance is None:
            raise RuntimeError("staticDB n'est pas encore initialisée.")
        return getattr(cls._instance, name)


class staticDB(metaclass=_StaticDBMeta):
    """Sous-classe statique qui agit comme un proxy vers un jellyDB unique."""
    pass

'''

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

def sqrollback():
    """ Rollback the transaction """
    global conn
    conn.rollback()


def init_database():
    """ Initialize the database connection """
    global conn
    conn = sqlite3.connect(db_path, isolation_level='DEFERRED', check_same_thread=False, timeout=5)
    conn.enable_load_extension(True)
    conn.load_extension("/usr/local/share/bindfs-jelly/libsupercollate.so")

'''