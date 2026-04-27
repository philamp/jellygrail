"""
udf_reader.py

Small embeddable Python wrapper around libudfread for reading UDF images.

Scope:
  - UDF-only backend
  - no CLI
  - no pycdlib
  - no libarchive
  - designed to be imported into a larger project

Capabilities:
  - open a UDF image file
  - recursively list files
  - get file size
  - get physical byte extents inside the image via udfread_file_lba()
  - read at most the first N bytes of a file
  - stream bytes to a consumer without extracting the whole image

System dependency:
  Debian/Ubuntu:
    apt-get install -y libudfread0 libudfread-dev

The block size used by UDF optical images is normally 2048 bytes. libudfread's
public API exposes file logical-block -> image LBA mapping through
udfread_file_lba().
"""

from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import BinaryIO, Callable, Iterator, Optional


UDF_BLOCK_SIZE = 2048

UDF_DT_UNKNOWN = 0
UDF_DT_DIR = 1
UDF_DT_REG = 2

DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_HEAD_BYTES = 30 * 1024 * 1024


@dataclass(frozen=True)
class Extent:
    """A physical byte range inside the source image."""

    offset: int
    length: int


@dataclass(frozen=True)
class UdfFileInfo:
    """Metadata for a regular file inside a UDF image."""

    path: str
    size: int
    extents: Optional[tuple[Extent, ...]] = None


@dataclass(frozen=True)
class UdfHeadReadResult:
    """Result of reading the first N bytes of a UDF file."""

    path: str
    file_size: int
    bytes_read: int
    sha256: str
    truncated: bool
    extents: Optional[tuple[Extent, ...]] = None


class LibUdfReadError(RuntimeError):
    pass


class UdfDirent(ctypes.Structure):
    _fields_ = [
        ("d_type", ctypes.c_uint),
        ("d_name", ctypes.c_char_p),
    ]


class UdfImage:
    """
    Userspace reader for a UDF image using libudfread.

    Example:
        with UdfImage("disc.iso") as udf:
            for info in udf.iter_files(include_extents=True):
                print(info.path, info.size, info.extents)

            result = udf.read_head("/BDMV/index.bdmv", max_bytes=30 * 1024 * 1024)
            print(result.sha256, result.bytes_read)

    Notes:
        - Paths are POSIX-style absolute paths inside the UDF image.
        - This class is not thread-safe. Use one instance per worker/thread.
        - File extents require one udfread_file_lba() call per 2048-byte block;
          for huge files, compute extents only when you need them.
    """

    def __init__(self, image_path: str | os.PathLike[str], lib_path: Optional[str] = None) -> None:
        self.image_path = os.fspath(image_path)
        self.lib = self._load_libudfread(lib_path)
        self._setup_prototypes()

        self._udf = self.lib.udfread_init()
        if not self._udf:
            raise LibUdfReadError("udfread_init() failed")

        rc = self.lib.udfread_open(self._udf, os.fsencode(self.image_path))
        if rc < 0:
            self.lib.udfread_close(self._udf)
            self._udf = None
            raise LibUdfReadError(f"udfread_open() failed for {self.image_path!r}")

    @staticmethod
    def _load_libudfread(lib_path: Optional[str]) -> ctypes.CDLL:
        candidates: list[str] = []

        if lib_path:
            candidates.append(lib_path)
        else:
            found = ctypes.util.find_library("udfread")
            if found:
                candidates.append(found)
            candidates.extend([
                "libudfread.so",
                "libudfread.so.3",
                "libudfread.so.0",
            ])

        errors: list[str] = []
        for candidate in candidates:
            try:
                return ctypes.CDLL(candidate)
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")

        raise LibUdfReadError(
            "libudfread shared library not found. "
            "Install libudfread0/libudfread-dev or pass lib_path=. "
            + "; ".join(errors)
        )

    def _setup_prototypes(self) -> None:
        self.lib.udfread_init.argtypes = []
        self.lib.udfread_init.restype = ctypes.c_void_p

        self.lib.udfread_open.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.udfread_open.restype = ctypes.c_int

        self.lib.udfread_close.argtypes = [ctypes.c_void_p]
        self.lib.udfread_close.restype = None

        self.lib.udfread_opendir.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.udfread_opendir.restype = ctypes.c_void_p

        self.lib.udfread_readdir.argtypes = [ctypes.c_void_p, ctypes.POINTER(UdfDirent)]
        self.lib.udfread_readdir.restype = ctypes.POINTER(UdfDirent)

        self.lib.udfread_closedir.argtypes = [ctypes.c_void_p]
        self.lib.udfread_closedir.restype = None

        self.lib.udfread_file_open.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.udfread_file_open.restype = ctypes.c_void_p

        self.lib.udfread_file_close.argtypes = [ctypes.c_void_p]
        self.lib.udfread_file_close.restype = None

        self.lib.udfread_file_size.argtypes = [ctypes.c_void_p]
        self.lib.udfread_file_size.restype = ctypes.c_int64

        self.lib.udfread_file_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        self.lib.udfread_file_read.restype = ctypes.c_ssize_t

        self.lib.udfread_file_lba.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.lib.udfread_file_lba.restype = ctypes.c_uint32

    def close(self) -> None:
        if getattr(self, "_udf", None):
            self.lib.udfread_close(self._udf)
            self._udf = None

    def __enter__(self) -> "UdfImage":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Normalize an internal UDF path to an absolute POSIX path.

        This prevents accidental use of relative paths or path traversal-style
        strings inside your application-level code. It does not touch the host FS.
        """

        if not path:
            return "/"

        p = PurePosixPath("/" + path.lstrip("/"))
        parts = []
        for part in p.parts:
            if part in ("", "/", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts) if parts else "/"

    @staticmethod
    def _join(parent: str, name: str) -> str:
        return "/" + name if parent == "/" else parent.rstrip("/") + "/" + name

    def _ensure_open(self) -> None:
        if not getattr(self, "_udf", None):
            raise LibUdfReadError("UDF image is closed")

    def _encode_path(self, path: str) -> bytes:
        return self.normalize_path(path).encode("utf-8", errors="surrogateescape")

    def _open_file_handle(self, path: str) -> Optional[int]:
        self._ensure_open()
        return self.lib.udfread_file_open(self._udf, self._encode_path(path)) or None

    def _close_file_handle(self, handle: int) -> None:
        self.lib.udfread_file_close(handle)

    def iter_dir(self, path: str = "/") -> Iterator[tuple[int, str, str]]:
        """
        Yield directory entries as (d_type, name, absolute_path).
        """

        self._ensure_open()
        path = self.normalize_path(path)
        d = self.lib.udfread_opendir(self._udf, self._encode_path(path))
        if not d:
            raise LibUdfReadError(f"cannot open UDF directory: {path}")

        try:
            entry = UdfDirent()
            while True:
                result = self.lib.udfread_readdir(d, ctypes.byref(entry))
                if not result:
                    break
                if not entry.d_name:
                    continue

                name = entry.d_name.decode("utf-8", errors="surrogateescape")
                if name in (".", ".."):
                    continue

                child = self._join(path, name)
                yield int(entry.d_type), name, child
        finally:
            self.lib.udfread_closedir(d)

    def iter_file_paths(self, root: str = "/") -> Iterator[str]:
        """Recursively yield absolute paths for regular files."""

        root = self.normalize_path(root)
        for d_type, _name, child in self.iter_dir(root):
            if d_type == UDF_DT_DIR:
                yield from self.iter_file_paths(child)
            elif d_type == UDF_DT_REG:
                yield child
            else:
                # Some images/libs may report unknown. Try directory first,
                # then file, without failing the whole scan.
                try:
                    yield from self.iter_file_paths(child)
                    continue
                except LibUdfReadError:
                    pass

                handle = self._open_file_handle(child)
                if handle:
                    self._close_file_handle(handle)
                    yield child

    def file_size(self, path: str) -> int:
        """Return the logical size of a file in bytes."""

        path = self.normalize_path(path)
        handle = self._open_file_handle(path)
        if not handle:
            raise LibUdfReadError(f"cannot open UDF file: {path}")

        try:
            size = int(self.lib.udfread_file_size(handle))
            if size < 0:
                raise LibUdfReadError(f"cannot get size for UDF file: {path}")
            return size
        finally:
            self._close_file_handle(handle)

    def file_lbas(self, path: str) -> tuple[int, ...]:
        """
        Return the image LBA for each 2048-byte logical block of a file.

        Warning:
            This returns one integer per file block. For very large files, prefer
            file_extents() directly so the intermediate tuple is not exposed to
            callers. Internally, file_extents() also walks the LBAs once.
        """

        path = self.normalize_path(path)
        handle = self._open_file_handle(path)
        if not handle:
            raise LibUdfReadError(f"cannot open UDF file: {path}")

        try:
            size = int(self.lib.udfread_file_size(handle))
            if size < 0:
                raise LibUdfReadError(f"cannot get size for UDF file: {path}")
            if size == 0:
                return ()

            num_blocks = (size + UDF_BLOCK_SIZE - 1) // UDF_BLOCK_SIZE
            lbas = []
            for block_index in range(num_blocks):
                lba = int(self.lib.udfread_file_lba(handle, block_index))
                if lba == 0:
                    raise LibUdfReadError(
                        f"udfread_file_lba() failed for {path}, block {block_index}"
                    )
                lbas.append(lba)
            return tuple(lbas)
        finally:
            self._close_file_handle(handle)

    def file_extents(self, path: str) -> tuple[Extent, ...]:
        """
        Return compacted physical byte extents for a file inside the image.

        The offsets are absolute byte offsets from the beginning of the ISO/UDF
        image file. Fragmented files may have multiple extents.
        """

        path = self.normalize_path(path)
        handle = self._open_file_handle(path)
        if not handle:
            raise LibUdfReadError(f"cannot open UDF file: {path}")

        try:
            size = int(self.lib.udfread_file_size(handle))
            if size < 0:
                raise LibUdfReadError(f"cannot get size for UDF file: {path}")
            if size == 0:
                return ()

            num_blocks = (size + UDF_BLOCK_SIZE - 1) // UDF_BLOCK_SIZE
            return tuple(_compact_lbas_from_handle(self.lib, handle, path, num_blocks, size))
        finally:
            self._close_file_handle(handle)

    def file_info(self, path: str, include_extents: bool = False) -> UdfFileInfo:
        path = self.normalize_path(path)
        size = self.file_size(path)
        extents = self.file_extents(path) if include_extents else None
        return UdfFileInfo(path=path, size=size, extents=extents)

    def iter_files(self, root: str = "/", include_extents: bool = False) -> Iterator[UdfFileInfo]:
        """Recursively yield UdfFileInfo for regular files."""

        for path in self.iter_file_paths(root):
            yield self.file_info(path, include_extents=include_extents)

    def read_chunks(
        self,
        path: str,
        *,
        max_bytes: Optional[int] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> Iterator[bytes]:
        """
        Yield file data chunks, optionally capped at max_bytes.

        This does not read the entire UDF image. It asks libudfread to read the
        logical file content, and libudfread follows the file's UDF allocation.
        """

        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be >= 0 or None")

        path = self.normalize_path(path)
        handle = self._open_file_handle(path)
        if not handle:
            raise LibUdfReadError(f"cannot open UDF file: {path}")

        try:
            remaining = max_bytes
            buf_size = chunk_size if remaining is None else min(chunk_size, remaining)
            if buf_size == 0:
                return

            buf = ctypes.create_string_buffer(buf_size)
            while remaining is None or remaining > 0:
                want = chunk_size if remaining is None else min(chunk_size, remaining)
                if want <= 0:
                    break
                if want > buf_size:
                    # This only matters if caller passes huge dynamic values.
                    buf_size = want
                    buf = ctypes.create_string_buffer(buf_size)

                n = int(self.lib.udfread_file_read(handle, buf, want))
                if n < 0:
                    raise LibUdfReadError(f"read error in UDF file: {path}")
                if n == 0:
                    break

                if remaining is not None:
                    remaining -= n
                yield ctypes.string_at(buf, n)
        finally:
            self._close_file_handle(handle)

    def read_head(
        self,
        path: str,
        *,
        max_bytes: int = DEFAULT_MAX_HEAD_BYTES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        out: Optional[BinaryIO] = None,
        include_extents: bool = False,
    ) -> UdfHeadReadResult:
        """
        Read up to max_bytes from a file and optionally write them to a stream.

        Returns a hash of exactly the bytes read. Useful for your "first 30 MiB
        of every file" workflow.
        """

        if max_bytes < 0:
            raise ValueError("max_bytes must be >= 0")

        path = self.normalize_path(path)
        size = self.file_size(path)
        h = hashlib.sha256()
        total = 0

        for chunk in self.read_chunks(path, max_bytes=max_bytes, chunk_size=chunk_size):
            h.update(chunk)
            total += len(chunk)
            if out is not None:
                out.write(chunk)

        extents = self.file_extents(path) if include_extents else None
        return UdfHeadReadResult(
            path=path,
            file_size=size,
            bytes_read=total,
            sha256=h.hexdigest(),
            truncated=total < size,
            extents=extents,
        )

    def read_all_heads(
        self,
        *,
        root: str = "/",
        max_bytes: int = DEFAULT_MAX_HEAD_BYTES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        include_extents: bool = False,
        on_file: Optional[Callable[[UdfFileInfo], None]] = None,
        open_output: Optional[Callable[[UdfFileInfo], Optional[BinaryIO]]] = None,
    ) -> Iterator[UdfHeadReadResult]:
        """
        Iterate all files and read up to max_bytes from each.

        Parameters:
            root:
                UDF directory to scan.
            max_bytes:
                Cap per file. Default is 30 MiB.
            chunk_size:
                Read buffer size.
            include_extents:
                Include physical extents in UdfFileInfo and result.
            on_file:
                Optional callback called before reading a file.
            open_output:
                Optional callback returning a writable binary stream for this file.
                The stream is closed by this method if returned.

        Example:
            with UdfImage("disc.iso") as udf:
                for result in udf.read_all_heads(include_extents=True):
                    print(result)
        """

        for info in self.iter_files(root=root, include_extents=include_extents):
            if on_file:
                on_file(info)

            out = open_output(info) if open_output else None
            try:
                yield self.read_head(
                    info.path,
                    max_bytes=max_bytes,
                    chunk_size=chunk_size,
                    out=out,
                    include_extents=include_extents,
                )
            finally:
                if out is not None:
                    out.close()


def _compact_lbas_from_handle(
    lib: ctypes.CDLL,
    handle: int,
    path: str,
    num_blocks: int,
    file_size: int,
    block_size: int = UDF_BLOCK_SIZE,
) -> Iterator[Extent]:
    """Compact udfread_file_lba() results into physical byte extents."""

    start_lba: Optional[int] = None
    prev_lba: Optional[int] = None
    blocks = 0
    emitted = 0

    def emit_current() -> Optional[Extent]:
        nonlocal emitted, start_lba, blocks
        if start_lba is None or blocks <= 0:
            return None
        length = min(blocks * block_size, file_size - emitted)
        if length <= 0:
            return None
        emitted += length
        return Extent(offset=start_lba * block_size, length=length)

    for block_index in range(num_blocks):
        lba = int(lib.udfread_file_lba(handle, block_index))
        if lba == 0:
            raise LibUdfReadError(
                f"udfread_file_lba() failed for {path}, block {block_index}"
            )

        if start_lba is None:
            start_lba = prev_lba = lba
            blocks = 1
            continue

        assert prev_lba is not None
        if lba == prev_lba + 1:
            prev_lba = lba
            blocks += 1
            continue

        extent = emit_current()
        if extent is not None:
            yield extent

        start_lba = prev_lba = lba
        blocks = 1

    extent = emit_current()
    if extent is not None:
        yield extent
