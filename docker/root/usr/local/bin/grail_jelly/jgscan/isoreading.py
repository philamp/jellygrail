import os
import threading
import pycdlib


MAX_READ_BYTES = 34_000_000
READ_TIMEOUT = 604


def iso_path_type(iso: pycdlib.PyCdlib) -> str:
    if iso.has_udf():
        return "udf_path"
    if iso.has_rock_ridge():
        return "rr_path"
    if iso.has_joliet():
        return "joliet_path"
    return "iso_path"


def normalize_iso_name(name) -> str:
    if isinstance(name, bytes):
        name = name.decode("utf-8", errors="ignore")
    return name.rstrip(";1")


def join_iso_path(dirpath: str, filename: str) -> str:
    path = os.path.join(dirpath, filename).replace("\\", "/")
    if not path.startswith("/"):
        path = "/" + path
    return path


def get_iso9660_extents(rec):
    """
    Pour DirectoryRecord ISO9660/Joliet/Rock Ridge.
    Retourne une liste de tuples: (extent, length, extra_offset).
    """
    if rec.is_dir():
        return []

    # Multi-extent possible pour très gros fichiers.
    extents = []
    current = rec

    while current is not None:
        extent = current.extent_location()
        length = current.data_length
        extents.append((extent, length, 0))
        current = getattr(current, "data_continuation", None)

    return extents


def get_udf_extents(rec):
    """
    Pour UDFFileEntry.
    Retourne une liste de tuples: (extent, length, extra_offset).

    Notes:
    - UDFShortAD / UDFLongAD: extent = log_block_num
    - UDFInlineAD: données inline dans la File Entry elle-même, offset != 0
    """
    extents = []

    for ad in rec.alloc_descs:
        extent = ad.log_block_num
        length = ad.extent_length
        extra_offset = getattr(ad, "offset", 0)

        # extent_type existe sur UDFShortAD.
        # 0 = allocated recorded, généralement les données réelles.
        # Si tu veux être strict, ignore les autres types.
        extent_type = getattr(ad, "extent_type", 0)
        if extent_type != 0:
            continue

        extents.append((extent, length, extra_offset))

    return extents


def get_record_extents(iso: pycdlib.PyCdlib, iso_inner_path: str, path_kw: str):
    rec = iso.get_record(**{path_kw: iso_inner_path})

    if rec.is_dir():
        return []

    if path_kw == "udf_path":
        return get_udf_extents(rec)

    return get_iso9660_extents(rec)


def read_iso_extents_prefix(
    iso_fp,
    extents,
    logical_block_size: int,
    wanted_bytes: int = MAX_READ_BYTES,
) -> bytes:
    """
    Lit au maximum wanted_bytes depuis les extents du fichier.
    Ne parcourt pas le fichier complet.
    """
    chunks = []
    remaining = wanted_bytes

    for extent, length, extra_offset in extents:
        if remaining <= 0:
            break

        to_read = min(length, remaining)
        byte_offset = extent * logical_block_size + extra_offset

        iso_fp.seek(byte_offset)
        chunk = iso_fp.read(to_read)

        if not chunk:
            break

        chunks.append(chunk)
        remaining -= len(chunk)

        if len(chunk) < to_read:
            break

    return b"".join(chunks)


def read_iso_file_prefix_with_timeout(
    iso_path: str,
    iso: pycdlib.PyCdlib,
    iso_inner_path: str,
    path_kw: str,
    timeout: int = READ_TIMEOUT,
    wanted_bytes: int = MAX_READ_BYTES,
) -> bool:
    success = True

    def worker():
        nonlocal success

        try:
            extents = get_record_extents(iso, iso_inner_path, path_kw)
            if not extents:
                return

            with open(iso_path, "rb") as iso_fp:
                _ = read_iso_extents_prefix(
                    iso_fp=iso_fp,
                    extents=extents,
                    logical_block_size=iso.logical_block_size,
                    wanted_bytes=wanted_bytes,
                )

        except Exception as e:
            logger.error(f" - FAILURE_read : low-level ISO read failed on {iso_inner_path}: {e}.")
            success = False

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        logger.error(
            f" - FAILURE_read : Waited {timeout} seconds : "
            f"Reading ISO file {iso_inner_path} took too long and was aborted"
        )
        return False

    if not success:
        logger.error(f" - FAILURE_read : Reading ISO file {iso_inner_path} failed due to an IO error.")
        return False

    return True