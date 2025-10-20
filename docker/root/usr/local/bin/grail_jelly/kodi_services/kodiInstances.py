
import json
from pathlib import Path
from datetime import datetime
from base.constants import *

class kodiDBRegistry:
    """Static registry of Kodi Grail databases with automatic persistence."""

    _path = Path("/etc/myapp/grail_dbs.json")
    _data = {}
    _loaded = False

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


    # TODO : temp to renove later
    @classmethod
    def all_poc(cls):
        # return a POC version of all entries
        return {
            "b1ba1e3c-9061-4d34-9a14-f6e3d9fc7506": 
            {
                "dbname": "b1ba1e3c",
                "kodi_ip": "172.22.2.18",
                "kodi_version": 20
            }
        }


    @classmethod
    def all(cls):
        """Return the full registry as a dict."""
        cls._load()
        return dict(cls._data)

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
            "alive": False,
            "refreshed": False
        }
        cls._save()
        return cls._data[uid]

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