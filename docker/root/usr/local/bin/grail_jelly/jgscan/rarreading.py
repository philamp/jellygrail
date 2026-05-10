from __future__ import annotations



import libarchive
import hashlib
from pathlib import Path
from base import *




from dataclasses import dataclass
import os
import struct
from typing import Iterator, Optional

RAR_CACHE_LIMIT = 17 * 1024 * 1024  # 17 MiB

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".m2ts",
    ".vob", ".ogv", ".rm", ".rmvb", ".asf",
}

def heat_rar_with_libarchive(
    rar_file_path: str,
    max_bytes: int = RAR_CACHE_LIMIT,
):
    with libarchive.file_reader(rar_file_path) as archive:
        for entry in archive:
            if not entry.isfile:
                continue

            path = entry.pathname
            ext = Path(path).suffix.lower()
            is_video = ext in VIDEO_EXTENSIONS

            h = hashlib.sha256()
            total = 0

            # Pour les vidéos : lire 0 byte
            if not is_video:
                for block in entry.get_blocks():
                    if total >= max_bytes:
                        break

                    take = min(len(block), max_bytes - total)
                    if take:
                        h.update(block[:take])
                        total += take

            yield {
                "path": path,
                "file_size": entry.size,
                "bytes_read": total,
                "sha256": h.hexdigest(),
                "truncated": total < entry.size,
                "is_video": is_video,
            }
            



RAR4_SIG = b"Rar!\x1a\x07\x00"
RAR5_SIG = b"Rar!\x1a\x07\x01\x00"

# RAR3/4
RAR4_MAIN_HEAD = 0x73
RAR4_FILE_HEAD = 0x74
RAR4_ENDARC_HEAD = 0x7B

RAR4_LONG_BLOCK = 0x8000

RAR4_MHD_PASSWORD = 0x0080  # encrypted headers

RAR4_LHD_SPLIT_BEFORE = 0x0001
RAR4_LHD_SPLIT_AFTER = 0x0002
RAR4_LHD_PASSWORD = 0x0004
RAR4_LHD_SOLID = 0x0010
RAR4_LHD_LARGE = 0x0100
RAR4_LHD_UNICODE = 0x0200
RAR4_LHD_DIRECTORY = 0x00E0

RAR4_METHOD_STORE = 0x30

# RAR5
RAR5_MAIN_HEAD = 1
RAR5_FILE_HEAD = 2
RAR5_SERVICE_HEAD = 3
RAR5_ENCRYPTION_HEAD = 4
RAR5_ENDARC_HEAD = 5

RAR5_FLAG_EXTRA = 0x0001
RAR5_FLAG_DATA = 0x0002
RAR5_FLAG_SPLIT_BEFORE = 0x0008
RAR5_FLAG_SPLIT_AFTER = 0x0010
RAR5_FLAG_DEPENDS_PREV = 0x0020

RAR5_FILE_DIRECTORY = 0x0001
RAR5_FILE_MTIME = 0x0002
RAR5_FILE_CRC32 = 0x0004
RAR5_FILE_UNKNOWN_SIZE = 0x0008

RAR5_EXTRA_FILE_ENCRYPTION = 0x01
RAR5_METHOD_STORE = 0


@dataclass(frozen=True)
class RarStoredEntry:
    name: str
    data_offset: int
    file_size: int
    packed_size: int
    rar_version: int
    method: int
    header_offset: int


class RarFormatError(RuntimeError):
    pass


class _UnicodeFilename:
    """
    Décodeur minimal des noms Unicode RAR3/4.

    RAR3/4 peut stocker :
      - un nom 8-bit,
      - puis parfois une variante Unicode compressée.
    """

    def __init__(self, std_name: bytes, encdata: bytes):
        self.std_name = bytearray(std_name)
        self.encdata = bytearray(encdata)
        self.pos = 0
        self.encpos = 0
        self.buf = bytearray()
        self.failed = False

    def enc_byte(self) -> int:
        if self.encpos >= len(self.encdata):
            self.failed = True
            return 0
        c = self.encdata[self.encpos]
        self.encpos += 1
        return c

    def std_byte(self) -> int:
        if self.pos >= len(self.std_name):
            self.failed = True
            return ord("?")
        return self.std_name[self.pos]

    def put(self, lo: int, hi: int) -> None:
        self.buf.append(lo & 0xFF)
        self.buf.append(hi & 0xFF)
        self.pos += 1

    def decode(self) -> str:
        hi = self.enc_byte()
        flagbits = 0
        flags = 0

        while self.encpos < len(self.encdata):
            if flagbits == 0:
                flags = self.enc_byte()
                flagbits = 8

            flagbits -= 2
            t = (flags >> flagbits) & 3

            if t == 0:
                self.put(self.enc_byte(), 0)
            elif t == 1:
                self.put(self.enc_byte(), hi)
            elif t == 2:
                self.put(self.enc_byte(), self.enc_byte())
            else:
                n = self.enc_byte()

                if n & 0x80:
                    correction = self.enc_byte()
                    count = (n & 0x7F) + 2

                    for _ in range(count):
                        self.put((self.std_byte() + correction) & 0xFF, hi)
                else:
                    count = n + 2

                    for _ in range(count):
                        self.put(self.std_byte(), 0)

        return self.buf.decode("utf-16le", "replace")


def _decode_rar4_name(raw: bytes, flags: int) -> str:
    if flags & RAR4_LHD_UNICODE:
        if b"\x00" in raw:
            std, enc = raw.split(b"\x00", 1)

            try:
                return _UnicodeFilename(std, enc).decode()
            except Exception:
                return std.decode("utf-8", "surrogateescape")

        return raw.decode("utf-8", "surrogateescape")

    for enc in ("utf-8", "cp437", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    return raw.decode("latin-1", "replace")


class RarStoredScanner:
    """
    Scanner header-only pour RAR3/4 et RAR5.

    Objectif :
      - lire seulement les headers ;
      - calculer data_offset ;
      - sauter les payloads avec un changement d'offset interne ;
      - ne retourner que les fichiers directement seekables, donc stockés sans compression.

    Cela convient au cas :
      pread(rar_fd, buf, size, entry.data_offset + requested_offset)
    """

    def __init__(self, rar_path: str, *, max_sfx_scan: int = 1024 * 1024):
        self.rar_path = rar_path
        self.max_sfx_scan = max_sfx_scan
        self.fd: Optional[int] = None
        self.size = 0

    def __enter__(self) -> "RarStoredScanner":
        flags = os.O_RDONLY

        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC

        self.fd = os.open(self.rar_path, flags)
        self.size = os.fstat(self.fd).st_size
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def iter_stored_files(self) -> Iterator[RarStoredEntry]:
        sig_pos, version = self._find_signature()

        if version == 5:
            yield from self._iter_rar5(sig_pos + len(RAR5_SIG))
        else:
            yield from self._iter_rar4(sig_pos + len(RAR4_SIG))

    def _read_at(self, offset: int, size: int) -> bytes:
        if self.fd is None:
            raise RuntimeError("Use RarStoredScanner as a context manager")

        if size < 0:
            raise ValueError("negative read size")

        data = os.pread(self.fd, size, offset)

        if len(data) != size:
            raise EOFError(
                f"Unexpected EOF at offset {offset}, wanted {size}, got {len(data)}"
            )

        return data

    def _find_signature(self) -> tuple[int, int]:
        """
        Cherche la signature RAR au début ou dans le préfixe SFX.

        La spec RAR5 décrit un module SFX optionnel avant la signature et indique
        qu'il faut chercher la signature dans cette zone.
        """
        n = min(self.size, self.max_sfx_scan + len(RAR5_SIG))
        blob = self._read_at(0, n)

        candidates: list[tuple[int, int]] = []

        p5 = blob.find(RAR5_SIG)
        if p5 >= 0:
            candidates.append((p5, 5))

        p4 = blob.find(RAR4_SIG)
        if p4 >= 0:
            candidates.append((p4, 4))

        if not candidates:
            raise RarFormatError("RAR signature not found in SFX scan window")

        return min(candidates, key=lambda x: x[0])

    def _read_vint_at(self, offset: int) -> tuple[int, int]:
        value = 0
        shift = 0
        pos = offset

        for _ in range(10):
            b = self._read_at(pos, 1)[0]
            pos += 1

            value |= (b & 0x7F) << shift

            if not (b & 0x80):
                return value, pos

            shift += 7

        raise RarFormatError(f"Invalid RAR5 vint at offset {offset}")

    @staticmethod
    def _vint_from(buf: bytes, pos: int) -> tuple[int, int]:
        value = 0
        shift = 0

        for _ in range(10):
            if pos >= len(buf):
                raise EOFError("Unexpected EOF inside RAR5 header vint")

            b = buf[pos]
            pos += 1

            value |= (b & 0x7F) << shift

            if not (b & 0x80):
                return value, pos

            shift += 7

        raise RarFormatError("Invalid RAR5 header vint")

    @classmethod
    def _rar5_extra_has_file_encryption(cls, extra: bytes) -> bool:
        pos = 0

        while pos < len(extra):
            try:
                rec_size, pos = cls._vint_from(extra, pos)
            except EOFError:
                return False

            rec_data_start = pos
            rec_end = rec_data_start + rec_size

            if rec_end > len(extra):
                return False

            try:
                rec_type, _ = cls._vint_from(extra, pos)
            except EOFError:
                return False

            if rec_type == RAR5_EXTRA_FILE_ENCRYPTION:
                return True

            pos = rec_end

        return False

    def _iter_rar5(self, pos: int) -> Iterator[RarStoredEntry]:
        while pos < self.size:
            block_start = pos

            if block_start + 4 > self.size:
                return

            # Header CRC32.
            # On le saute : ici on construit un index d'offsets, on ne valide pas l'archive.
            pos += 4

            header_size, pos = self._read_vint_at(pos)
            header_start = pos
            header_end = header_start + header_size

            if header_size < 1 or header_end > self.size:
                raise RarFormatError(f"Bad RAR5 header size at {block_start}")

            # Lecture du header uniquement. Jamais du payload.
            header = self._read_at(header_start, header_size)
            p = 0

            header_type, p = self._vint_from(header, p)
            header_flags, p = self._vint_from(header, p)

            extra_size = 0
            if header_flags & RAR5_FLAG_EXTRA:
                extra_size, p = self._vint_from(header, p)

            data_size = 0
            if header_flags & RAR5_FLAG_DATA:
                data_size, p = self._vint_from(header, p)

            data_offset = header_end
            next_block = data_offset + data_size

            if next_block > self.size:
                raise RarFormatError(f"RAR5 block points past EOF at {block_start}")

            if header_type == RAR5_ENDARC_HEAD:
                return

            if header_type == RAR5_ENCRYPTION_HEAD:
                raise RarFormatError("RAR5 encrypted headers: cannot scan raw offsets")

            if header_type == RAR5_FILE_HEAD:
                file_flags, p = self._vint_from(header, p)

                is_dir = bool(file_flags & RAR5_FILE_DIRECTORY)
                has_mtime = bool(file_flags & RAR5_FILE_MTIME)
                has_crc = bool(file_flags & RAR5_FILE_CRC32)
                unknown_size = bool(file_flags & RAR5_FILE_UNKNOWN_SIZE)

                unpacked_size, p = self._vint_from(header, p)
                _attrs, p = self._vint_from(header, p)

                if has_mtime:
                    p += 4

                if has_crc:
                    p += 4

                if p > len(header):
                    raise RarFormatError(f"Truncated RAR5 file header at {block_start}")

                compression_info, p = self._vint_from(header, p)
                _host_os, p = self._vint_from(header, p)

                name_len, p = self._vint_from(header, p)

                if p + name_len > len(header):
                    raise RarFormatError(f"Truncated RAR5 filename at {block_start}")

                name_bytes = header[p:p + name_len]
                name = name_bytes.decode("utf-8", "surrogateescape")

                extra = b""
                if extra_size:
                    extra_start = header_size - extra_size

                    if extra_start < 0:
                        raise RarFormatError(f"Bad RAR5 extra size at {block_start}")

                    extra = header[extra_start:header_size]

                # RAR5: bits 8-10, mask 0x0380, méthode de compression.
                # Valeur 0 = no compression.
                method = (compression_info & 0x0380) >> 7

                solid_or_dependent = (
                    bool(compression_info & 0x0040)
                    or bool(header_flags & RAR5_FLAG_DEPENDS_PREV)
                )

                split = bool(
                    header_flags & (RAR5_FLAG_SPLIT_BEFORE | RAR5_FLAG_SPLIT_AFTER)
                )

                encrypted = self._rar5_extra_has_file_encryption(extra)

                if (
                    method == RAR5_METHOD_STORE
                    and not is_dir
                    and not unknown_size
                    and not solid_or_dependent
                    and not split
                    and not encrypted
                    and data_size == unpacked_size
                ):
                    yield RarStoredEntry(
                        name=name,
                        data_offset=data_offset,
                        file_size=unpacked_size,
                        packed_size=data_size,
                        rar_version=5,
                        method=method,
                        header_offset=block_start,
                    )

            # Saut logique : aucun byte du fichier archivé n'est lu ici.
            pos = next_block

    def _iter_rar4(self, pos: int) -> Iterator[RarStoredEntry]:
        while pos < self.size:
            block_start = pos

            if block_start + 7 > self.size:
                return

            common = self._read_at(block_start, 7)
            _head_crc, head_type, head_flags, head_size = struct.unpack(
                "<HBHH",
                common,
            )

            if head_size < 7:
                raise RarFormatError(f"Bad RAR3/4 header size at {block_start}")

            if head_type == RAR4_ENDARC_HEAD:
                return

            if head_type == RAR4_MAIN_HEAD and (head_flags & RAR4_MHD_PASSWORD):
                raise RarFormatError("RAR3/4 encrypted headers: cannot scan raw offsets")

            if head_type == RAR4_FILE_HEAD:
                body_size = head_size - 7

                if body_size < 25:
                    raise RarFormatError(
                        f"Truncated RAR3/4 file header at {block_start}"
                    )

                # Header du fichier uniquement.
                body = self._read_at(block_start + 7, body_size)

                pack_low, unp_low = struct.unpack_from("<II", body, 0)
                method = body[18]
                name_size = struct.unpack_from("<H", body, 19)[0]
                _attr = struct.unpack_from("<I", body, 21)[0]

                p = 25

                pack_high = 0
                unp_high = 0

                if head_flags & RAR4_LHD_LARGE:
                    if body_size < p + 8:
                        raise RarFormatError(
                            f"Truncated RAR3/4 large file header at {block_start}"
                        )

                    pack_high, unp_high = struct.unpack_from("<II", body, p)
                    p += 8

                if body_size < p + name_size:
                    raise RarFormatError(
                        f"Truncated RAR3/4 filename at {block_start}"
                    )

                name_raw = body[p:p + name_size]
                name = _decode_rar4_name(name_raw, head_flags)

                packed_size = pack_low | (pack_high << 32)
                unpacked_size = unp_low | (unp_high << 32)

                data_offset = block_start + head_size
                next_block = data_offset + packed_size

                if next_block > self.size:
                    raise RarFormatError(
                        f"RAR3/4 file block points past EOF at {block_start}"
                    )

                split = bool(
                    head_flags & (RAR4_LHD_SPLIT_BEFORE | RAR4_LHD_SPLIT_AFTER)
                )

                encrypted = bool(head_flags & RAR4_LHD_PASSWORD)
                solid = bool(head_flags & RAR4_LHD_SOLID)

                is_dir = (
                    bool((head_flags & RAR4_LHD_DIRECTORY) == RAR4_LHD_DIRECTORY)
                    or name.endswith("/")
                    or name.endswith("\\")
                )

                if (
                    method == RAR4_METHOD_STORE
                    and not is_dir
                    and not split
                    and not encrypted
                    and not solid
                    and packed_size == unpacked_size
                ):
                    yield RarStoredEntry(
                        name=name,
                        data_offset=data_offset,
                        file_size=unpacked_size,
                        packed_size=packed_size,
                        rar_version=4,
                        method=method,
                        header_offset=block_start,
                    )

                # Saut logique : aucun byte du fichier archivé n'est lu ici.
                pos = next_block
                continue

            # Bloc non-fichier.
            # Si LONG_BLOCK est présent, ADD_SIZE permet de sauter son data block.
            add_size = 0

            if head_flags & RAR4_LONG_BLOCK:
                if block_start + 11 > self.size:
                    raise RarFormatError(
                        f"Truncated RAR3/4 long block at {block_start}"
                    )

                add_size = struct.unpack(
                    "<I",
                    self._read_at(block_start + 7, 4),
                )[0]

            next_block = block_start + head_size + add_size

            if next_block <= block_start or next_block > self.size:
                raise RarFormatError(f"Bad RAR3/4 block size at {block_start}")

            pos = next_block


def scan_rar_stored_files(rar_path: str) -> list[RarStoredEntry]:
    with RarStoredScanner(rar_path) as scanner:
        for entry in scanner.iter_stored_files():
            logger.info(f"RARINSPECT| {rar_path} : {entry.name} at offset {entry.data_offset}, size {entry.file_size}")