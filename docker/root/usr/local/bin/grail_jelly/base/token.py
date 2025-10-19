import secrets
from pathlib import Path

class SSDPToken:
    """Static manager for a persistent SSDP token."""

    _path = None
    _token = None

    @classmethod
    def set_path(cls, path: str):
        """Set a custom path for the SSDP token file."""
        cls._path = Path(path)

    @classmethod
    def get(cls) -> str:
        """Return the persistent SSDP token (load or create)."""
        if cls._token is None:
            cls._token = cls._load_or_create()
        return cls._token

    @classmethod
    def _load_or_create(cls) -> str:
        cls._path.parent.mkdir(parents=True, exist_ok=True)

        if cls._path.exists():
            token = cls._path.read_text().strip()
            if token:
                return token

        token = secrets.token_hex(16)
        cls._path.write_text(token)
        return token