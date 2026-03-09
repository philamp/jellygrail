#!/bin/bash
cd /mounts/kodi/software

# Define URLs and filenames
urls=(
    "https://a4k-openproject.github.io/a4kSubtitles/packages/a4kSubtitles-repository.zip"
    "https://github.com/philamp/grail_kodi/releases/download/20260309/context.kodi_grail-20260309.zip"
)

# Loop through URLs
for url in "${urls[@]}"; do
    # Extract the filename from the URL
    filename=$(basename "$url")

    # Check if the file already exists
    if [ -f "$filename" ]; then
        echo "$filename already exists, skipping download."
    else
        wget "$url"
    fi
done
