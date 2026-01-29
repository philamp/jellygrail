
import json
from pathlib import Path
from datetime import datetime
from base.constants import *
import asyncio

# careful : the update method works only in one depth (no nested dict update)
class kodiDBRegistry:
    """Static registry of Kodi Grail databases with automatic persistence."""

    _path = Path(KODI_INSTANCES_FILE)
    _loaded = False
    _data = {}
    
    _dbs = {}

    
    _nfoBatchesPath = Path(NFO_BATCHES_FILES)
    _nfoBatchesLoaded = False
    _nfoBatchesData = {}

    @classmethod
    def _loadNfoBatches(cls):
        """Load registry data from file (once)."""
        if cls._nfoBatchesLoaded:
            return
        if cls._nfoBatchesPath.exists():
            try:
                cls._nfoBatchesData = json.loads(cls._nfoBatchesPath.read_text())
            except json.JSONDecodeError:
                cls._nfoBatchesData = {}
        else:
            cls._nfoBatchesPath.parent.mkdir(parents=True, exist_ok=True)
            cls._nfoBatchesData = {}
        cls._nfoBatchesLoaded = True

    @classmethod
    def newNfoBatch(cls):
        # create a new nfo batch entrey wth  a unique uid and return it
        cls._loadNfoBatches()
        new_uid = str(datetime.now().timestamp()).replace('.','')  # simple unique id
        cls._nfoBatchesData[new_uid] = {"items":[], "done": False}

        #cls._saveNfoBatches()
        return new_uid
    
    @classmethod
    def addToNfoBatch(cls, batch_uid, item):
        cls._loadNfoBatches()
        if batch_uid not in cls._nfoBatchesData:
            return False
        cls._nfoBatchesData[batch_uid]["items"].append(item)
        #cls._saveNfoBatches()
        return True
    
    @classmethod
    def remove_nfo_batch(cls, batch_uid):
        cls._loadNfoBatches()
        if batch_uid in cls._nfoBatchesData:
            del cls._nfoBatchesData[batch_uid]
            return True
        return False

    @classmethod
    def commitNfoBatchAndSave(cls, batch_uid):

        cls._loadNfoBatches() #redondant
        if batch_uid not in cls._nfoBatchesData:
            return False

        cls._nfoBatchesData[batch_uid]["done"] = True
        cls.SaveNfoBatches()

    @classmethod
    def SaveNfoBatches(cls):
        cls._loadNfoBatches() #redondant
        cls._nfoBatchesPath.parent.mkdir(parents=True, exist_ok=True)
        cls._nfoBatchesPath.write_text(json.dumps(cls._nfoBatchesData, indent=2, ensure_ascii=False))

    # ───────────────
    # Core persistence
    # ───────────────
    @classmethod
    def _load(cls):
        """Load registry data from file (once)."""
        if cls._loaded:
            return
        if cls._path.exists():
            try:
                cls._data = json.loads(cls._path.read_text())
            except json.JSONDecodeError:
                cls._data = {}
            for _,dct in cls._data.items():
                cls._dbs[dct.get("dbname")] = {
                    "toScan": asyncio.Event(),
                    "toNfoRefresh": asyncio.Event(),
                    "toFullNfoRefresh": asyncio.Event(),
                    "toDeltaNfoRefresh": asyncio.Event(),
                    "last_max_lastplayed": "",
                    "last_max_fileid": 0
                }

        else:
            cls._path.parent.mkdir(parents=True, exist_ok=True)
            cls._data = {}
        cls._loaded = True

    @classmethod
    def _save(cls):
        """Write current data to file."""
        cls._path.parent.mkdir(parents=True, exist_ok=True)
        cls._path.write_text(json.dumps(cls._data, indent=2, ensure_ascii=False))

    # ───────────────────────────────
    # Public API
    # ───────────────────────────────

    '''
    # POC
    @classmethod
    def all_poc(cls):
        # return a POC version of all entries
        return {
            "b1a1e3c-9061-4d34-9a14-f6e3d9fc7506": 
            {
                "dbname": "shouldmatch_JGx_",
                "kodi_ip": "172.22.2.18",
                "kodi_version": 20,
                "db_created_date": "2024-05-15T10:20:30",
                "alive": False,
            },
            "wqcfwvrf-9061-4d34-9a14-f6e3d9fc7506": 
            {
                "dbname": "wqefwvrf-9061-4d34-9a14-f6e3d9fc7506_JGx_",
                "kodi_ip": "172.22.2.27",
                "kodi_version": 20,
                "db_created_date": "2024-05-16T10:20:30",
                "alive": False,
            }
        }
    '''

    @classmethod
    def get_all_instances_pointer(cls):
        """Return the full registry pointer"""
        cls._load()
        return cls._data
    
    @classmethod
    def get_all_dbs_pointer(cls):
        """Return the full registry pointer"""
        cls._load()
        return cls._dbs
    
    @classmethod
    def get_all_batches_pointer(cls):
        """Return the full registry pointer"""
        cls._loadNfoBatches()
        return cls._nfoBatchesData
    

    # toimprove deprecated ?
    @classmethod
    def get(cls, uid):
        """Retrieve an entry by UID."""
        cls._load()
        return cls._data.get(uid)

    @classmethod
    def add(cls, uid, dbname, kodi_ip, kodi_version, db_created_date=None):
        """Add or overwrite an entry."""
        cls._load()
        if db_created_date is None:
            db_created_date = datetime.now().isoformat(timespec="seconds")

        cls._data[uid] = {
            "dbname": dbname,
            "db_created_date": db_created_date,
            "kodi_ip": kodi_ip,
            "kodi_version": kodi_version,
            "alive": True,
            "consumedBatches": []
        }

        cls._dbs[dbname] = {
            "toScan": asyncio.Event(),
            "toNfoRefresh": asyncio.Event(),
            "toFullNfoRefresh": asyncio.Event(),
            "toDeltaNfoRefresh": asyncio.Event(),
            "last_max_lastplayed": "",
            "last_max_fileid": 0
        }

        cls._save()
        return cls._data[uid]

    '''
    @classmethod # set refresh = False to all known kodi instances
    def reset_all_refresh(cls):
        """Reset 'refreshed' status for all entries."""
        cls._load()
        for entry in cls._data.values():
            entry["refreshed"] = False
        cls._save()
    '''

    @classmethod
    def is_alive_set(cls, uid, is_alive_now: bool):
        """Update the 'alive' status of an entry."""
        cls._load()
        entry = cls._data.get(uid)
        if not entry:
            return None

        entry["alive"] = is_alive_now
        return entry

    @classmethod
    def update(cls, uid, **updates):
        """Update existing entry fields by UID, saving only if something changed."""
        cls._load()
        entry = cls._data.get(uid)
        if not entry:
            return None

        # Compute which fields actually change
        changed = {k: v for k, v in updates.items() if entry.get(k) != v}

        # If nothing changed, skip saving
        if not changed:
            return entry

        '''
        if dbname := changed.get('dbname'):
            cls._dbs[dbname] = {
                "toScan": asyncio.Event(),
                "toNfoRefresh": asyncio.Event(),
                "nfoRefreshBatches": {}
            }
        '''
        
        # Apply only changed fields
        entry.update(changed)
        cls._save()
        return entry

    @classmethod
    def remove(cls, uid):
        """Remove entry by UID."""
        cls._load()
        if uid in cls._data:
            del cls._data[uid]
            cls._save()
            return True
        return False

    @classmethod
    def find_by_version(cls, kodi_version):
        """Return all entries that match the given Kodi version."""
        cls._load()
        return {
            uid: entry
            for uid, entry in cls._data.items()
            if entry.get("kodi_version") == kodi_version
        }