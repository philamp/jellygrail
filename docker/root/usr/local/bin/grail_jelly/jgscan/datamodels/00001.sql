CREATE TABLE IF NOT EXISTS main_mapping (
    virtual_fullpath TEXT PRIMARY KEY COLLATE SCLIST,
    actual_fullpath TEXT,
    jginfo_rd_torrent_folder TEXT,
    jginfo_rclone_cache_item TEXT,
    mediatype TEXT
);
CREATE INDEX IF NOT EXISTS rename_depth ON main_mapping (virtual_fullpath COLLATE SCDEPTH);
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);