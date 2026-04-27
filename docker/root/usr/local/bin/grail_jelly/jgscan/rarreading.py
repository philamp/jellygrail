import hashlib
import libarchive

RAR_CACHE_LIMIT = 30 * 1024 * 1024

def heat_rar_with_libarchive(rar_file_path: str, max_bytes: int = RAR_CACHE_LIMIT):
    with libarchive.file_reader(rar_file_path) as archive:
        for entry in archive:
            if not entry.isfile:
                continue

            h = hashlib.sha256()
            total = 0

            for block in entry.get_blocks():
                if total >= max_bytes:
                    break

                take = min(len(block), max_bytes - total)
                if take:
                    h.update(block[:take])
                    total += take

            yield {
                "path": entry.pathname,
                "file_size": entry.size,
                "bytes_read": total,
                "sha256": h.hexdigest(),
                "truncated": total < entry.size,
            }