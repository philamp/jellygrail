#!/usr/bin/env python3
# coding: utf-8
import sqlite3
import os
import PTN
import subprocess
import time
import re
import pycountry
import json
import shlex
import threading
import datetime
import pyinotify

# import script_runner threading class (ScriptRunnerSub) and its smart instanciator (ScriptRunner)
from script_runner import ScriptRunner

# for Jellyfin API
# from typing import List, Dict
import requests
from typing import List, Dict

# for similarity
from thefuzz import fuzz
from thefuzz import process
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from colorlog import ColoredFormatter
import urllib
import random

# dotenv for RD API management
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')

#rd api services wrapper
import jg_services
# from rdapi import RD
# RD = RD()

# no need for DATA anymore TODELETE
# from datetime import datetime

# http threader
# Set up logging
# logging.basicConfig(filename='/jellygrail/log/jelly_update.log', level=logging.INFO) todo: delete this comment

# Create or get the logger
logger = logging.getLogger("jellygrail")
# Set the lowest level to log messages; this can be DEBUG, INFO, WARNING, ERROR, CRITICAL
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Create file handler which logs even debug messages
fh = logging.FileHandler('/jellygrail/log/jelly_update.log')
fh.setLevel(logging.DEBUG)  # Set the level for the file handler

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)  # Set the level for the stream handler; adjust as needed

# Create formatter and add it to the handlers
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') -- updated for below to add colors
formatterfh = ColoredFormatter("%(asctime)s %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
formatterch = ColoredFormatter("%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
fh.setFormatter(formatterfh)
ch.setFormatter(formatterch)

# Add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)




# endpoints array
dual_endpoints = []

# Global sqlite connection object
conn = None

mounts_root = "/mounts"

dest_root = "/Video_Library"

db_path = "/jellygrail/.bindfs_jelly.db"

# JF
jfapikey = None

BASE_URI = "http://localhost:8096"

present_virtual_folders = []
present_virtual_folders_shows = []

# sub exts
SUB_EXTS = ('.srt', '.sub', '.idx', '.ssa', '.ass', '.sup', '.usf')

# video exts
VIDEO_EXTENSIONS = ('.mkv', '.avi', '.mp4', '.mov', '.m4v', '.wmv', '.iso', '.vob', '.mpg')

# merge those 2 elements
ALLOWED_EXTENSIONS = SUB_EXTS + VIDEO_EXTENSIONS

create_table_sql = '''
CREATE TABLE IF NOT EXISTS main_mapping (
    virtual_fullpath TEXT PRIMARY KEY COLLATE SCLIST,
    actual_fullpath TEXT,
    jginfo_rd_torrent_folder TEXT,
    jginfo_rclone_cache_item TEXT,
    mediatype TEXT
);
'''

update_table_sql_v2 = '''
ALTER TABLE main_mapping ADD COLUMN last_updated INTEGER;
'''

create_index = '''
CREATE INDEX IF NOT EXISTS rename_depth ON main_mapping (virtual_fullpath COLLATE SCDEPTH);
'''
def tpl(str_value, preffix = ''):
    if str_value is not None:
        return f" {preffix}{str_value}"
    return ''

def ytpl(value):
    if value is not None:
        return f" ({str(value)})"
    return ''

def get_ext(filename):
    last_dot_index = filename.rfind('.')
    if last_dot_index == -1:
        return ""
    return filename[last_dot_index:]

def get_wo_ext(filename):
    last_dot_index = filename.rfind('.')
    if last_dot_index == -1:
        return filename
    return filename[:last_dot_index]

def get_tuple(filename):
    last_dot_index = filename.rfind('.')
    if last_dot_index == -1:
        return (filename, "")
    return (filename[:last_dot_index], filename[last_dot_index:])

def get_ffprobe(file_path):
    # Construct the ffprobe command to get the format information, which includes the overall bitrate
    try:
        command = [
            "ffprobe", 
            "-v", "error",  # Hide logging
            "-analyzeduration", '4000000',
            "-select_streams", "v:0",
            "-show_entries", "format=bit_rate",  # Show overall bitrate
            "-show_streams",
            "-of", "json",  # Output format as JSON
            file_path
        ]

        # Execute the command
        result = subprocess.run(command, capture_output=True, text=True)
        output = result.stdout
        info = json.loads(output)
        bitrate = round(int(info["format"]["bit_rate"]) / 1000000)
        # Extract overall bitrate

    except subprocess.CalledProcessError as e:
        logger.critical(f" - FAILURE_ffprobe decode: SubprocessCallError on {file_path} : {e}")
        return (None, None)

    except (KeyError, IndexError, json.JSONDecodeError):
        logger.error(f" - FAILURE_ffprobe decode: Unable to extract even basic information on {file_path}")
        return (None, None)

    dvprofile = None
    if( sideinfo := info['streams'][0].get('side_data_list') ):
        dvprofile = sideinfo[0].get('dv_profile')

    return ( f"{bitrate}Mbps", dvprofile)

# RARs
def unrar_to_void(rar_file_path):

    try:
        logger.debug(f"      > Trying to void-unrar it ...")
        subprocess.run(['unrar', 't', "-sl34000000", "-y", "-ierr", rar_file_path], check=True, stderr=subprocess.PIPE)

    except subprocess.CalledProcessError as e:
        # The command failed, check if it's the specific error we're looking for
        if "Input/output error" in e.stderr.decode():
            return "ERROR_IO"
        elif "No files to extract" in e.stderr.decode():
            return "ERROR_NOFILES"
        elif "Unexpected end of archive" in e.stderr.decode():
            return "ERROR_IO"
        else:
            logger.error("      - The unrar command failed for unknown reason 1:", e.stderr.decode())
        return "ERROR"
    except Exception as e:
        logger.error("      - The unrar command failed for unknown reason 2:", str(e))
        return "ERROR"
    else:
        logger.debug("      > ... SUCCESS !")
    return "OK"

# ISOs
def mount_iso(iso_path, mount_folder):
    logger.debug(f"      > MOUNTING ISO to cache small metadata files in rclone: {iso_path}\n      ")
    # Create the mount folder if it doesn't exist
    if not os.path.exists(mount_folder):
        os.makedirs(mount_folder)
    
    # Build and execute the mount command
    mount_command = f"mount -o loop '{iso_path}' {mount_folder}"
    try:
        subprocess.run(shlex.split(mount_command), check=True, timeout=60)
    except subprocess.TimeoutExpired:
        logger.error(f" - FAILURE_Mount : Mount operation timed out after 60 seconds on {iso_path}")
        


def unmount_iso(mount_folder):
    # Build and execute the unmount command
    unmount_command = f"umount {mount_folder}"
    subprocess.run(shlex.split(unmount_command), check=True)
    
    # Remove the mount folder
    os.rmdir(mount_folder)

def read_file_with_timeout(file_path, timeout = 604):
    def worker():
        try:
            with open(file_path, 'rb') as f:
                _ = f.read(34000000)  # Tente de lire les 34 000 000 premiers octets
        except Exception as e:
            logger.error(f" - FAILURE_read : An error occurred on direct read {file_path}: {e}.")
            nonlocal success  # Pour modifier la variable `success` en dehors de cette sous-fonction
            success = False  # Marque l'échec de la lecture en raison d'une exception

    success = True  # Initialise le succès à True avant de commencer
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        logger.error(f" - FAILURE_read : Waited 604 seconds (10m) : Reading file {file_path} took too long and was aborted.")
        return False
    elif not success:
        # Si `worker` a rencontré une exception, `success` aura été changé en False
        logger.error(f" - FAILURE_read : Reading file {file_path} failed due to an IO error.")
        return False
    else:
        print("r", end="")
        return True

def read_small_files(src_folder):
    for root, dirs, files in os.walk(src_folder):
        for file in files:
            file_path = os.path.join(root, file)
            
            # if os.path.getsize(file_path) <= max_size_bytes: -> removed to read all files including > 34000000 but read_file_with_timeout will only take the 34000000 first bytes
            if not read_file_with_timeout(file_path):
                logger.error(f" - FAILURE_read : Abandoning due to timeout or IO Error on mounted iso on {src_folder}")

def sqcommit():
    """ Commit the transaction """
    global conn
    conn.commit()

def sqrollback():
    """ Rollback the transaction """
    global conn
    conn.rollback()

def init_database(path):
    """ Initialize the database connection """
    global conn
    conn = sqlite3.connect(path, isolation_level='DEFERRED')
    conn.enable_load_extension(True)
    conn.load_extension("/usr/local/share/bindfs-jelly/libsupercollate.so")
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    cursor.execute(create_index)
    sqcommit()
    """ TABLE UPDATES : v2 """
    try:
        cursor.execute(update_table_sql_v2)
        sqcommit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.info("> UPDATE DATAMODEL : The column already exists. Skipping addition.")
        else:
            logger.critical("> An operational error occurred:", e)


def insert_data(virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype = None):
    """ Insert data into the database """
    global conn
    cursor = conn.cursor()
    # when a virtual_path already exists, it updates all other fileds but virtual_path 
    # ... but to avoid downgrading a mediatype value from something to None, on conflict we don't insert if mediatype == none for the item we overwrite
    # (mediatype is then used in bindfs to do filtering based on virtual folders suffixes (virtual_dv, virtual_bdmv))
    if mediatype != None:
        cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, last_updated) VALUES (depenc(?), ?, ?, depenc(?), ?, strftime('%s', 'now')) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), mediatype=?, last_updated=strftime('%s', 'now')", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, mediatype))
    else:
        cursor.execute("INSERT INTO main_mapping (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, last_updated) VALUES (depenc(?), ?, ?, depenc(?), strftime('%s', 'now')) ON CONFLICT(virtual_fullpath) DO UPDATE SET actual_fullpath=?, jginfo_rd_torrent_folder=?, jginfo_rclone_cache_item=depenc(?), last_updated=strftime('%s', 'now')", (virtual_fullpath, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item, actual_fullpath, jginfo_rd_torrent_folder, jginfo_rclone_cache_item))


def fetch_present_virtual_folders():
    """ Query data from the database """
    global conn
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT depdec(virtual_fullpath), SUBSTR(depdec(virtual_fullpath), 2, 5) FROM main_mapping WHERE actual_fullpath IS NULL AND SUBSTR(virtual_fullpath, 1, 4) = '0002'")
    return cursor.fetchall()

def fetch_present_release_folders():
    """ Query data from the database """
    global conn
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT jginfo_rd_torrent_folder FROM main_mapping')
    return cursor.fetchall()

def ls_virtual_folder(folder_path):
    global conn
    cursor = conn.cursor()
    cursor.execute("SELECT depdec(virtual_fullpath) FROM main_mapping WHERE virtual_fullpath BETWEEN depenc( ? || '//') AND depenc( ? || '/\\')", (folder_path, folder_path))
    return cursor.fetchall()

def clean_string(s):
    s = s.replace(".", " ")
    s = s.replace("-", "")
    s = s.strip()
    s = s.capitalize()
    return s

def find_most_similar(input_str, string_list):
    # This returns the best match, its score and index
    best_match = process.extractOne(input_str, string_list)
    return best_match

def subtitle_extension(file_name):
    _attribs = []
    special_attribs = {"default", "sdh", "forced", "foreign"}
    patterns = r'[\.\[\]_()]'

    # Check if the filename ends with .srt
    if not file_name.lower().endswith(SUB_EXTS):
        return None  # Return None if the file is not an .srt file

    base_name, ext = get_tuple(file_name)

    # splitting using pattern and not taking empty parts
    parts = list(filter(None, re.split(patterns, base_name.lower())))
    parts = parts[-4:] if len(parts) >= 4 else parts
    
    for part in parts:
        # If the part is a recognized special attribute, append it to other_attribs
        if part in special_attribs:
            if part == "foreign":
                _attribs.append("forced")
            else:
                _attribs.append(part)
        else:
            # Check if it's a valid 2 or 3-char language code or a full language name
            lang = pycountry.languages.get(alpha_2=part) or pycountry.languages.get(alpha_3=part) or pycountry.languages.get(name=part.capitalize())
            if lang:
                lang_code = getattr(lang, 'alpha_2', None)
                if lang_code:
                    _attribs.append(lang_code)
                else:
                    lang_code = getattr(lang, 'name', None)
                    if lang_code:
                        _attribs.append(lang_code.lower())

    # if there is really nothing return the only last split found
    if(len(_attribs) < 1):
        _attribs.append(parts[-1])

    # fix if original filenames kind-of-mentionned same language 2 times (fr.french for example)
    if len(_attribs) > 1 and (_attribs[-1] == _attribs[-2]):
        _attribs.pop(-1)
        
    if(len(_attribs) > 0):
        return "."+".".join(_attribs) + ext
    else:
        return ext

def release_browse(endpoint, releasefolder, rar_item, release_folder_path, storetype):
    logger.info(f"  > BROWSING PATH: {endpoint}/{releasefolder}")

    # 0 - init some default values
    multiple_movie_or_disc_present = False
    bdmv_present = False
    season_present = False
    one_movie_present = False
    nbvideos = 0
    nbvideos_e = 0
    stopthere = False
    atleastoneextra = False

    # M_DUP duplicate workaround for one-movie releases / RESET idxdup at release level
    idxdupmovset = 1

    # S_DUP duplicate workaround for shows by sXeX by release scanned / RESET ARRAY at release level
    idxdupshowset_a = {}

    # Multi Dim Array for S DIVE
    dive_s_ = {}

    # Multi Dim Array for E DIVE
    # dive_e_ = {'rootfilenames': [], 'rootfoldernames': [], 'mediatype' : None, 'premetas': ''}

    # Multi Dim Array for E DIVE V2
    # 'rootfoldernames' {'eroot': '', 'efilename': '', 'efilesize': 0}
    dive_e_ = {'rootfiles': [], 'rootfoldernames': [], 'mediatype' : None, 'premetas': ''}

    # make the present_virtual_folders_* global so that we can write in them on the fly (list of release folders)
    global present_virtual_folders
    global present_virtual_folders_shows

    # DIVE S similar check + write + cache-heater 
    # also: DIVE E write + cache-heater (similar check is done elsewhere, on release folder basis)
    for root, folders, files in os.walk(os.path.join(endpoint, releasefolder)):
        for filename in files:
            if not "(sample)" in filename.lower() and not "sample.mkv" in filename.lower() and not '@eaDir' in root and not "DS_Store" in filename.lower() and not ('BDMV' not in os.path.normpath(root).split(os.sep) and filename.lower().endswith(('.m2ts', '.ts'))):
                
                # B - cache item fetching 
                # folder insert will use rar_item (could be none or the parent rar file) 
                # file insert will use rd_cache_item (could be a direct file or the parent rar file)

                # S case with itegrated similar show/season/episode fetch (at file loop level):
                if re.search(r's\d{2}\.?e\d{2}|\b\d{2}x\d{2}\b|s\d{2}\.\d{2}', filename, re.IGNORECASE):
                    if filename.lower().endswith(ALLOWED_EXTENSIONS):
                        season_present = True
                        # it's an episode file or sub
                        filename_base = get_wo_ext(filename)
                        match = re.search(r'(.+?)\s*((?:s\d{2}\.?e\d{2})|(?:\b\d{2}x\d{2}\b)|(?:s\d{2}\.\d{2}))\s*(.*?)', filename_base, re.IGNORECASE)
                        if match:
                            show, season_episode, episode_title = match.groups()
                            if 'x' in season_episode or 'X' in season_episode:  # it's the 02x03 format
                                season, episode_num = map(str, season_episode.split('x'))
                            elif not 'e' in season_episode and not 'E' in season_episode : # it's the S02.03 format
                                season_episode_match = re.search(r's(\d+)\.(\d+)', season_episode, re.IGNORECASE)
                                season, episode_num = season_episode_match.groups()
                            else:  # it's the S02E03 format
                                season_episode_match = re.search(r's(\d+)\.?e(\d+)', season_episode, re.IGNORECASE)
                                season, episode_num = season_episode_match.groups()

                            # clean catpured data
                            show = clean_string(show)

                            # find existing show folder with thefuzz
                            result = find_most_similar(show, present_virtual_folders_shows)

                            will_idx_check = False
                            if result is not None:
                                most_similar_string, similarity_score = result

                                if similarity_score > 94:
                                    show = most_similar_string
                                    logger.debug(f"      # similarshow check on : {show}")
                                    logger.debug(f"      # similarshow found is : {most_similar_string} with score {similarity_score}")

                                    # S_DUP
                                    will_idx_check = True

                                else:
                                    present_virtual_folders_shows.append(show)
                            else:
                                present_virtual_folders_shows.append(show)
                            
                            logger.debug(f"      ## definitive sim show folder : {show}")

                            # dive S WRITE

                            # ensuring structure
                            dive_s_.setdefault(show, {}).setdefault(season, {}).setdefault(episode_num, {'rootfilenames': [], 'mediatype_s' : None, 'premetas': ''})

                            dive_s_[show][season][episode_num]['rootfilenames'].append(os.path.join(root, filename))



                # E case:
                else:


                    # add to another array for E cases (v2 structure)
                    dive_e_['rootfiles'].append({'as_if_vroot': root, 'eroot': root, 'efilename': filename, 'efilesize':os.path.getsize(os.path.join(root, filename))})
                    

                    # EF case
                    if 'BDMV' in os.path.normpath(root).split(os.sep) or 'VIDEO_TS' in os.path.normpath(root).split(os.sep) or filename.lower().endswith('.iso'):
                        multiple_movie_or_disc_present = True
                        bdmv_present = True
                        dive_e_['mediatype'] = '_bdmv'

                # -- END DIVE write E+S (except folders for E) ---

                # cache heating or ffprobe for E or S cases:
                if(filename.lower().endswith(VIDEO_EXTENSIONS)):

                    # nbvideos incr
                    nbvideos += 1
                    
                    if not filename.lower().endswith('.iso'):
                        # and storetype == 'remote' missing and rar_item ignored means we run ffprobe on mkv even if they're cache-heated with void-unrar
                        # cache-heater 1 for all files but iso
                        (bitrate, dvprofile) = get_ffprobe(os.path.join(root, filename))

                        if season_present: 
                            if(dvprofile) and dive_s_[show][season][episode_num]['mediatype_s'] == None:
                                dive_s_[show][season][episode_num]['mediatype_s'] = '_dv'
                            else:
                                dive_s_[show][season][episode_num]['mediatype_s'] = None
                            
                            dive_s_[show][season][episode_num]['premetas'] = f" -{tpl(bitrate)}{tpl(dvprofile, 'DVp')} JGx"

                        else:
                            if not bdmv_present and dive_e_['mediatype'] == None:
                                if(dvprofile):
                                    dive_e_['mediatype'] = '_dv'
                                else:
                                    dive_e_['mediatype'] = None
                                
                                dive_e_['premetas'] = f" -{tpl(bitrate)}{tpl(dvprofile, 'DVp')}"

                    elif filename.lower().endswith('.iso'):

                        # cache-heater 0bis for all iso files if storing is remote
                        if storetype == 'remote':
                            iso_file_path = os.path.join(root, filename)
                            try:
                                mount_iso(iso_file_path, "/mnt/tmp")
                                read_small_files("/mnt/tmp")
                            except Exception as e:
                                logger.error(f" - FAILURE_iso: issues with reading iso: {iso_file_path}")

                            finally:
                                unmount_iso("/mnt/tmp")



                elif rar_item == None and storetype == 'remote':
                    # cache-heater 2 for all other files in S and E when in remote + when no rar_item (as unrar has already cache-heated those files)
                    if not read_file_with_timeout(os.path.join(root, filename)):
                        logger.error(f" - FAILURE_direct_read: IO or timeout on {os.path.join(root, filename)}")


        if not season_present:
            for folder in folders:
                # E case folder DIVE write:
                if not '@eaDir' in os.path.join(root, folder):
                    dive_e_['rootfoldernames'].append(os.path.join(root, folder))

    # extras management with 0.3 rule
    
    if not season_present and nbvideos > 1:
        # desc sorting (including other all types all files)

        dive_e_['rootfiles'] = sorted(dive_e_['rootfiles'], key=lambda x: x['efilesize'], reverse=True)

        # max filesize
        maxfs = dive_e_['rootfiles'][0]['efilesize'] * 0.3

        # rewrite eroot if efilesize < maxfs only if video file
        for key, item in enumerate(dive_e_['rootfiles']):
            if item['efilename'].endswith(VIDEO_EXTENSIONS):
                if item['efilesize'] < maxfs :
                    dive_e_['rootfiles'][key]['as_if_vroot'] = os.path.join(endpoint, releasefolder, 'extras')
                    atleastoneextra = True
                else:
                    nbvideos_e += 1
    
    # DIVE write END
    # Logging some hints + setting multiple_movie_or_disc_present also when video_files > 1
    # multiple_movie_or_disc_present is common and triggered in these 3 scenarios : >1 movie files or BDMV present or ISO
    if nbvideos < 1 and not bdmv_present:
        logger.warning(f" - No valid files in release: {os.path.join(endpoint, releasefolder)} (or .m2ts not inside a BDMV/DVD structure). Its possible that RD downloading is not completed yet")
        stopthere = True
    elif(nbvideos_e > 1):
        multiple_movie_or_disc_present = True
        logger.info("    -- Multiple videos release with or without extras --")
    elif bdmv_present:
        logger.info("    -- BDMV or DVD Release with or without extras --")
    elif season_present:
        logger.info("    -- TV show release --")
    else:
        logger.info("    -- One video release with our without extras (last possibility) --")

    # ---- DIVE S READ + insert + S_DUP idxcheck, unless stopthere is true-----
    if season_present and not stopthere:

        # S_DUP / reset idxdup at dive_s_ loop level 
        idxdup = 1

        for keyshow, seasonlist in dive_s_.items():
            for seasonkey, episodelist in seasonlist.items():
                for episodekey, episodeattribs in episodelist.items():
                    for rootfilename in episodeattribs['rootfilenames']:

                        # B cache item fetching
                        rd_cache_item = rootfilename if rar_item == None else rar_item

                        # metas compute
                        # S_DUP
                        metas = episodeattribs['premetas']
                        if (will_idx_check):
                        # LS the sim folder with no ext files (because we loop check at filename level, we want to list video only and not subs)
                            ls_virtual_folder_a = []
                            for itemv in ls_virtual_folder("/shows/"+keyshow+"/Season "+seasonkey+"/"+f"{keyshow} S{seasonkey}E{episodekey}"):
                                if os.path.basename(itemv[0]).lower().endswith(VIDEO_EXTENSIONS):
                                    ls_virtual_folder_a.append(get_wo_ext(os.path.basename(itemv[0])))

                            # We deduplicate anyway to have videofilename.* count as one entry
                            
                            if(f"{show} S{season}E{episode_num}" not in idxdupshowset_a):
                                for existing_file in ls_virtual_folder_a:
                                    if f"{show} S{season}E{episode_num}"+metas+str(idxdup) == existing_file:
                                        idxdup += 1
                                idxdupshowset_a[f"{show} S{season}E{episode_num}"] = idxdup
                            else:
                                idxdup = idxdupshowset_a[f"{show} S{season}E{episode_num}"]
                        metas = metas + str(idxdup)
                        # S_DUP

                        # filename ext compute
                        filename_ext = get_ext(os.path.basename(rootfilename))

                        # S FOLDERS INSERT 
                        insert_data("/shows/"+keyshow, None, None, None, episodeattribs['mediatype_s'])
                        insert_data("/shows/"+keyshow+"/Season "+seasonkey, None, None, None, episodeattribs['mediatype_s'])
                        insert_data("/shows/"+keyshow+"/Season "+seasonkey+"/"+f"{keyshow} S{seasonkey}E{episodekey}", None, None, None, episodeattribs['mediatype_s'])
                        # S FILES INSERT
                        insert_data("/shows/"+keyshow+"/Season "+seasonkey+"/"+f"{keyshow} S{seasonkey}E{episodekey}"+"/"+f"{keyshow} S{seasonkey}E{episodekey}{metas}{filename_ext}", rootfilename, release_folder_path, rd_cache_item, episodeattribs['mediatype_s'])

    if not season_present and not stopthere:
        
        if not (multiple_movie_or_disc_present):
            # A - prepare parse for single movie release
            release_parse = PTN.parse(releasefolder)
            # GENERIC META FOR Esingle case
            title_year = f"{release_parse['title']}{ytpl(release_parse.get('year'))}"
            relmetas = f"{tpl(release_parse.get('resolution'))}{tpl(release_parse.get('quality'))}{tpl(release_parse.get('codec'))} JGx"
            # ... fuzzy mathing to merge with similar releases
            result = find_most_similar(title_year, present_virtual_folders)

            will_idx_check = False
            if result is not None:
                most_similar_string, similarity_score = result

                if similarity_score > 94:
                    title_year = most_similar_string
                    logger.debug(f"      # similarmovie check on : {title_year}")
                    logger.debug(f"      # similarmovie found is : {most_similar_string} with score {similarity_score}")

                    # LS the sim folder with no ext files (because we loop check at release level, we don't need to filter by ext, we just deduplicate the array)
                    ls_virtual_folder_a = [get_wo_ext(os.path.basename(itemv[0])) for itemv in ls_virtual_folder("/movies/"+title_year)]

                    # deduplicate the array + We deduplicate anyway to have videofilename.* count as one entry
                    ls_virtual_folder_a = list(set(ls_virtual_folder_a))

                    # M_DUP:
                    will_idx_check = True

                else:
                    present_virtual_folders.append(title_year)
            else:
                present_virtual_folders.append(title_year)
            logger.debug(f"      ## definitive sim movie folder : {title_year}")

        # ----- DIVE E READ + M_DUP check idx + insert
        for item in dive_e_['rootfiles']:
            
            rootfilename = os.path.join(item['eroot'], item['efilename'])
            asifrootfilename = os.path.join(item['as_if_vroot'], item['efilename'])

            # B cache item fetching
            rd_cache_item = rootfilename if rar_item == None else rar_item

            # compute ext
            filename_ext = get_ext(os.path.basename(rootfilename))

            # EF case
            if multiple_movie_or_disc_present:

                insert_data("/movies/"+releasefolder+"/"+os.path.relpath(asifrootfilename, os.path.join(endpoint, releasefolder)), rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'])

            # Esingle case
            elif rootfilename.lower().endswith(ALLOWED_EXTENSIONS):

                # M_DUP:
                metas = f"{dive_e_['premetas']}{relmetas}"
                if(will_idx_check):
                    if(idxdupmovset == 1):
                        for existing_file in ls_virtual_folder_a:
                            if title_year+metas+str(idxdupmovset) == existing_file:
                                idxdupmovset += 1
                metas = metas + str(idxdupmovset)
                # M_DUP

                if not rootfilename.lower().endswith(VIDEO_EXTENSIONS):
                    insert_data("/movies/"+title_year+"/"+title_year+metas+subtitle_extension(os.path.basename(asifrootfilename)), rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'])
                else:
                    if item['as_if_vroot'].endswith('extras'):
                        insert_data("/movies/"+title_year+"/"+os.path.relpath(asifrootfilename, os.path.join(endpoint, releasefolder)), rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'])
                    else:
                        insert_data("/movies/"+title_year+"/"+title_year+metas+filename_ext, rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'])

                    one_movie_present = True

        for rootfoldername in dive_e_['rootfoldernames']:
            if multiple_movie_or_disc_present:
                insert_data("/movies/"+releasefolder+"/"+os.path.relpath(rootfoldername, os.path.join(endpoint, releasefolder)), None, release_folder_path, rar_item, dive_e_['mediatype'])


        # COLLECT BASE FOLDER IF APPLIES
        # EF 
        if multiple_movie_or_disc_present:
            insert_data("/movies/"+releasefolder, None, None, None, dive_e_['mediatype'])
            if atleastoneextra:
                insert_data("/movies/"+releasefolder+"/extras", None, None, None, dive_e_['mediatype'])

        # Esingle folder
        if one_movie_present:
            insert_data("/movies/"+title_year, None, None, None, dive_e_['mediatype'])
            if atleastoneextra:
                insert_data("/movies/"+title_year+"/extras", None, None, None, dive_e_['mediatype'])
        # S folders are done in first filename loop


def scan():

    init_database(db_path)

    #global logger

    logger.debug("... Waiting 10s for any fresh RD file(s) to be available in the rclone mount ...")
    time.sleep(10)

    idxdupmovset = 1

    present_folders = [item[0] for item in fetch_present_release_folders()]

    global present_virtual_folders
    global present_virtual_folders_shows
    present_virtual_folders = [os.path.basename(itemv[0]) for itemv in fetch_present_virtual_folders() if (itemv[1] == 'movie' or itemv[1] == 'conce') ]
    present_virtual_folders_shows = [os.path.basename(itemv[0]) for itemv in fetch_present_virtual_folders() if itemv[1] == 'shows' ]

    # browse each release folder of each first endpoint
    for (src1, src2, storetype) in dual_endpoints:
        for f in os.scandir(src1):
            if f.path not in present_folders:
                if f.is_dir() and not '@eaDir' in f.name:
                    logger.info(f"> FOUND NEW RELEASE FOLDER: {f.name}")
                    browse = True
                    endpoint2browse = src1
                    rar_item = None
                    for g in os.scandir(f.path):
                        if g.name.lower().endswith('.rar') :
                            rar_item = g.path
                            endpoint2browse = src2
                            logger.info(f"  > FOUND NEW RAR FILE: {g.name}")
                            if storetype == "remote":
                                for i in range(2):
                                    # cache-heater 0 for RAR files and rar2fs
                                    unrar_result = unrar_to_void(g.path)
                                    if not unrar_result == "OK":
                                        if unrar_result == "ERROR_IO":
                                            logger.error(f" - IO Error on first try, waits 10 minutes and retry ... {g.path}")
                                            if i == 0:
                                                time.sleep(604)
                                            if i == 1:
                                                logger.error(f" - FAILURE_unrar : IO Error on second try {g.path}")
                                                browse = False
                                                break
                                        elif unrar_result == "ERROR_NOFILES":
                                            logger.warning("    - No Files in this RAR")
                                            browse = False
                                            break
                                        elif unrar_result == "ERROR":
                                            logger.error(f" - FAILURE_unrar : unknown on {g.path}")
                                            browse = False
                                            break
                                    else:
                                        break

                    if browse:
                    # Browse it through !
                        release_browse(endpoint2browse, f.name, rar_item, f.path, storetype)
                        sqcommit()

                elif f.name.lower().endswith(VIDEO_EXTENSIONS):
                    #file not in a release folder

                    # A - prepare parse for single movie release
                    release_parse = PTN.parse(f.name)

                    # compute ext
                    filename_ext = get_ext(os.path.basename(f.path))

                    # GENERIC META FOR Esingle case
                    title_year = f"{release_parse['title']}{ytpl(release_parse.get('year'))}"
                    relmetas = f"{tpl(release_parse.get('resolution'))}{tpl(release_parse.get('quality'))}{tpl(release_parse.get('codec'))} JGx"
           
                    result = find_most_similar(title_year, present_virtual_folders)

                    will_idx_check = False
                    if result is not None:
                        most_similar_string, similarity_score = result

                        if similarity_score > 94:
                            title_year = most_similar_string
                            logger.debug(f"      # similar movie check on : {title_year}")
                            logger.debug(f"      # similar movie found is : {most_similar_string} with score {similarity_score}")

                            # LS the sim folder with no ext files (because we loop check at release level, we don't need to filter by ext, we just deduplicate the array)
                            ls_virtual_folder_a = [get_wo_ext(os.path.basename(itemv[0])) for itemv in ls_virtual_folder("/movies/"+title_year)]

                            # deduplicate the array + We deduplicate anyway to have videofilename.* count as one entry
                            ls_virtual_folder_a = list(set(ls_virtual_folder_a))

                            # Mdup:
                            will_idx_check = True

                        else:
                            present_virtual_folders.append(title_year)
                    else:
                        present_virtual_folders.append(title_year)

                    logger.debug(f"      ## definitive similar movie folder : {title_year}")

                    bitrate = None
                    dvprofile = None
                    mediatype = None
                    if not f.name.lower().endswith('.iso'):
                        (bitrate, dvprofile) = get_ffprobe(f.path)
                        if(dvprofile):
                            mediatype = '_dv'
                    else:
                        mediatype = '_bdmv'
                    
                    premetas = f" -{tpl(bitrate)}{tpl(dvprofile, 'DVp')}"

                    # M_DUP:
                    metas = f"{premetas}{relmetas}"
                    if(will_idx_check):
                        if(idxdupmovset == 1):
                            for existing_file in ls_virtual_folder_a:
                                if title_year+metas+str(idxdupmovset) == existing_file:
                                    idxdupmovset += 1
                    metas = metas + str(idxdupmovset)
                    # M_DUP


                    logger.info(f"> FOUND NEW STANDALONE VIDEO FILE: {f.name}")
                    insert_data("/movies/"+title_year, None, f.path, None, mediatype)
                    insert_data("/movies/"+title_year+"/"+title_year+metas+filename_ext, f.path, f.path, None, mediatype)
                    sqcommit()

    # Close the connection
    conn.close()

    # refresh the jellyfin library and merge variants
    lib_refresh_all()
    merge_versions()

    # Snapshot of RD status (horodated) 
    # server : rd dump updated for later date segmentation and response to client 
    # client : rd dump comparison with own RD dump (client) 
    # both: for later archive
    #logger.info("> DUMPING RD DATA LOCALLY ...")
    #rdump() TODO
    #logger.info("> DUMPING RD DATA DONE")


class RequestHandler(BaseHTTPRequestHandler):

    def standard_headers(self, type='text/html'):
        self.send_response(200)
        self.send_header('Content-type', type)
        self.end_headers()

    def do_GET(self):

        global thrdinsts

        # parse the path
        url_path = urllib.parse.urlparse(self.path).path

        if url_path == '/scan':
            _scan_instance = ScriptRunner.get(scan)
            _scan_instance.run()
            if _scan_instance.queued_execution:
                message = "### scan() queued for later ! (Forces a library scan)\n"
            else:
                message = "### scan() directly executed ! (Forces a library scan)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == '/rd_progress':
            _rdprog_instance = ScriptRunner.get(jg_services.rd_progress)
            _rdprog_instance.run()
            if _rdprog_instance.queued_execution:
                message = "### rd_progress() queued for later ! (Checks Real-Debrid status)\n"
            else:
                message = "### rd_progress() directly executed ! (Checks Real-Debrid status)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))
            if(_rdprog_instance.get_output() == 'PLEASE_SCAN'):
                _scan_instance = ScriptRunner.get(scan)
                _scan_instance.run()

        elif url_path == '/remotescan':
            _remoteScan_instance = ScriptRunner.get(jg_services.remoteScan)
            _remoteScan_instance.run()
            if _remoteScan_instance.queued_execution:
                message = "### remoteScan() queued for later ! (Checks for remote's new RD hashes)\n"
            else:
                message = "### remoteScan() directly executed ! (Checks for remote's new RD hashes)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))


        elif url_path == '/test':
            _test_instance = ScriptRunner.get(jg_services.test)
            _test_instance.run()
            dumped_data = _test_instance.get_output()
            self.standard_headers()
            self.wfile.write(bytes(dumped_data, "utf8"))


        elif url_path == "/backup":
            _rdump_backup_instance = ScriptRunner.get(jg_services.rdump_backup)
            _rdump_backup_instance.run()
            if _rdump_backup_instance.queued_execution:
                message = "### rdump_backup() queued for later ! (backup the cur dump and dump)\n"
            else:
                message = "### rdump_backup() directly executed ! (backup the cur dump and dump)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == "/restore":
            _rdump_restorelist_instance = ScriptRunner.get(jg_services.restoreList)
            _rdump_restorelist_instance.run()
            self.standard_headers()
            output = _rdump_restorelist_instance.get_output()
            self.wfile.write(bytes(output, "utf8"))
            # choix will go to /restoreitem/i        

        elif url_path.startswith("/getrdincrement/"):
            try:
                incr = int(url_path[len("/getrdincrement/"):].rstrip('/'))
                # self.filter_and_send_data(input_date)
            except ValueError:
                self.send_error(400, "Invalid increment format")
            else:   
                _getrdincr_instance = ScriptRunner.get(jg_services.getrdincrement)
                _getrdincr_instance.resetargs(incr)
                _getrdincr_instance.run()
                self.standard_headers('application/json')
                output = _getrdincr_instance.get_output()
                if output != '':
                    self.wfile.write(output)
                else:
                    self.send_error(503, "Client triggered service, not yet available - rd dump file not yet created on server, please retry in few seconds")



def run_server(server_class=HTTPServer, handler_class=RequestHandler, port=6502):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logger.info(f"~ Server running on port {port}")
    httpd.serve_forever()

def restart_jellygrail_at(target_hour=6, target_minute=30):
    global jfapikey
    while True:
        # Get the current time
        now = datetime.datetime.now()
        next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if next_run < now:
            next_run += datetime.timedelta(days=1)
        sleep_time = (next_run - now).total_seconds()
        logger.info(f"Next restart in {sleep_time} seconds.")
        time.sleep(sleep_time)
        if jfapikey is not None:
            logger.info(f"JellyGrail will now shutdown for restart, beware '--restart unless-stopped' must be set in your docker run otherwise it won't restart !!")
            jellyfin(f'System/Shutdown', method='post')

def periodic_trigger(seconds=120):
    global thrdinsts
    _rdprog_instance = ScriptRunner.get(jg_services.rd_progress)
    while True:
        time.sleep(seconds)
        _rdprog_instance.run()
        if(_rdprog_instance.get_output() == 'PLEASE_SCAN'):
            # logger.info("periodic trigger is working")
            _scan_instance = ScriptRunner.get(scan)
            _scan_instance.run()


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

def jellyfin(path, method='get', **kwargs):
    return getattr(requests, method)(
        f'{BASE_URI}/{path}',
        headers={'X-MediaBrowser-Token': jfapikey},
        **kwargs
    )

def lib_refresh_all():
    global jfapikey
    if jfapikey is not None:
        resp = jellyfin(f'Library/Refresh', method='post')
        if resp.status_code == 204:
            logger.info("> Library update started successfully.")
        else:
            logger.critical(f"> FAILURE to update library. Status code: {resp.status_code}")

def merge_versions():
    global jfapikey
    if jfapikey is not None:
        tasks = jellyfin('ScheduledTasks').json()
        tasks_name_mapping = {task.get('Key'): task for task in tasks}
        ref_task_id = tasks_name_mapping.get('RefreshLibrary').get('Id')
        if tasks_name_mapping.get('MergeEpisodesTask') is not None:
            # mergeS_task_id = tasks_name_mapping.get('MergeEpisodesTask').get('Id')
            mergeM_task_id = tasks_name_mapping.get('MergeMoviesTask').get('Id')

            # while libraryrunning dont do anything
            logger.debug(". Waiting for library refresh to end.")
            while True:
                task = jellyfin(f'ScheduledTasks/{ref_task_id}').json()
                if task.get('State') == "Running":
                    print (".", end="")
                else:
                    # jellyfin(f'ScheduledTasks/Running/{mergeS_task_id}', method='post') -> this is not working well :( it merges different episodes number like its one :(
                    jellyfin(f'ScheduledTasks/Running/{mergeM_task_id}', method='post')
                    logger.info("> Videos variants merged (only for movies)")
                    break
                time.sleep(3)
    
def jfconfig():
    global jfapikey

    # check if /jellygrail/jellyfin/config/data/jellyfin.db exists

    proceedinjf = None

    iwait = 0
    while iwait < 20:
        iwait += 1
        try:
            if not urllib.request.urlopen('http://localhost:8096/health').read() == b'Healthy':
                logger.debug(f"... Jellyfin not yet available, try number {iwait} ...")
                time.sleep(3)
                continue
        except OSError as e:
            logger.debug(f"... Jellyfin not yet available, try number {iwait} ...")
        else:
            proceedinjf = True
            break
        time.sleep(3)

    if iwait >= 20:
        logger.warning("> Jellyfin is absent...will work without it, if you start it, restart the container as well so this script reboots")

    # Whole JF config --------------------------
    if proceedinjf and urllib.request.urlopen('http://localhost:8096/health').read() == b'Healthy':
    
        if os.path.exists("/jellygrail/jellyfin/config/data/jellyfin.db"):

            init_jellyfin_db("/jellygrail/jellyfin/config/data/jellyfin.db")
            
            array = [item[4] for item in fetch_api_key()]

            if len(array) > 0:
                
                jfapikey = array[0]
                # logger.info(f"> retrieved API key is {jfapikey}")
                logger.info(f"> retrieved API key is ***")
            
            else:
                key = ''.join(random.choice('0123456789abcdef') for _ in range(32))
                insert_api_key(key)
                # logger.info(f"> Api Key {key} inserted")
                logger.info(f"> Api Key *** inserted")
                jfapikey = key

            connjf.close()
        
        else:
            logger.critical("There is an issue with jellyfin config db: not reachable")

        # 1 - Install repo if necessary
        # get list of repos, if len < 3, re-declare
        declaredrepos = jellyfin(f'Repositories', method='get').json()
        if len(declaredrepos) < 3:
            #declare all repos
            repodata = [
                {
                    "Name": "Jellyfin Stable",
                    "Url": "https://repo.jellyfin.org/releases/plugin/manifest-stable.json",
                    "Enabled": True
                },
                {
                    "Name": "Merge",
                    "Url": "https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json",
                    "Enabled": True
                },
                {
                    "Name": "subbuzz",
                    "Url": "https://raw.githubusercontent.com/josdion/subbuzz/master/repo/jellyfin_10.8.json",
                    "Enabled": True
                }
            ]

            jellyfin(f'Repositories', json=repodata, method='post')

            #install KSQ
            jellyfin(f'Packages/Installed/Kodi%20Sync%20Queue', method='post')

            #install subbuzz
            jellyfin(f'Packages/Installed/subbuzz', method='post')

            #install merge
            jellyfin(f'Packages/Installed/Merge%20Versions', method='post')

            #delete unwanted triggers (chapter images and auto subtitle dl)
            triggerdata = []
            jellyfin(f'ScheduledTasks/4e6637c832ed644d1af3370a2506e80a/Triggers', json=triggerdata, method='post')
            jellyfin(f'ScheduledTasks/2c66a88bca43e565d7f8099f825478f1/Triggers', json=triggerdata, method='post')
            jellyfin(f'ScheduledTasks/7738148ffcd07979c7ceb148e06b3aed/Triggers', json=triggerdata, method='post') # disable libraryscan as well
            jellyfin(f'ScheduledTasks/dcaf151dd1af25aefe775c58e214477e/Triggers', json=triggerdata, method='post') # disable merge episodes which is not working well

            logger.warning("> IMPORTANT: Jellyfin Additional plugins are installed and unefficient tasks are disabled, \nThe container will now restart. \nBut if you did not put --restart unless-stopped in your run command, please execute: 'docker start thenameyougiven'")

            # thanks to --restart unless-stopped, drawback: it will restart in a loop if it does not find 3 declared repos (todo: find a more resilient way to test it)
            jellyfin(f'System/Shutdown', method='post')


        else:
            declaredlibs = jellyfin(f'Library/VirtualFolders', method='get').json()
            # (todo: find a more resilient way to test if libraries are declared)
            if len(declaredlibs) < 2:
                MetaSwitch = [
                    "TheMovieDb",
                    "The Open Movie Database",
                ]
                MetaSwitchTMDBonly = [
                    "TheMovieDb",
                ]
                logger.info("> Now we can add Librariries")
                movielib = {
                    "LibraryOptions": {
                        "PreferredMetadataLanguage": "fr",
                        "MetadataCountryCode": "FR",
                        "EnableRealtimeMonitor": False,
                        "EnableChapterImageExtraction": False,
                        "ExtractChapterImagesDuringLibraryScan": False,
                        "AutomaticallyAddToCollection": False,
                        "MetadataSavers": [],
                        "DisabledSubtitleFetchers": [
                            "subbuzz"
                        ],
                        "SubtitleDownloadLanguages": [
                            "eng",
                            "fre"
                        ],
                        "RequirePerfectSubtitleMatch": False,
                        "SaveSubtitlesWithMedia": True,
                        "AllowEmbeddedSubtitles": "AllowAll",
                        "PathInfos": [
                            {
                                "Path": "/Video_Library/virtual/movies",
                                "NetworkPath": ""
                            }
                        ],
                        "TypeOptions": [
                            {
                                "Type": "Movie",
                                "MetadataFetchers": MetaSwitch,
                                "MetadataFetcherOrder": MetaSwitch,
                                "ImageFetchers": MetaSwitch,
                                "ImageFetcherOrder": MetaSwitch,
                                "ImageOptions": []
                            }
                        ]
                    }
                }
                jellyfin(f'Library/VirtualFolders', json=movielib, method='post', params=dict(
                    name='Movies', collectionType="movies", paths="/Video_Library/virtual/movies", refreshLibrary=False
                ))

                concertlib = {
                    "LibraryOptions": {
                        "PreferredMetadataLanguage": "fr",
                        "MetadataCountryCode": "FR",
                        "EnableRealtimeMonitor": False,
                        "EnableChapterImageExtraction": False,
                        "ExtractChapterImagesDuringLibraryScan": False,
                        "AutomaticallyAddToCollection": False,
                        "MetadataSavers": [],
                        "DisabledSubtitleFetchers": [
                            "subbuzz"
                        ],
                        "SubtitleDownloadLanguages": [
                            "eng",
                            "fre"
                        ],
                        "RequirePerfectSubtitleMatch": False,
                        "SaveSubtitlesWithMedia": True,
                        "AllowEmbeddedSubtitles": "AllowAll",
                        "PathInfos": [
                            {
                                "Path": "/Video_Library/virtual/concerts",
                                "NetworkPath": ""
                            }
                        ],
                        "TypeOptions": [
                            {
                                "Type": "Movie",
                                "MetadataFetchers": MetaSwitch,
                                "MetadataFetcherOrder": MetaSwitch,
                                "ImageFetchers": MetaSwitch,
                                "ImageFetcherOrder": MetaSwitch,
                                "ImageOptions": []
                            }
                        ]
                    }
                }
                jellyfin(f'Library/VirtualFolders', json=concertlib, method='post', params=dict(
                    name='Concerts', collectionType="movies", paths="/Video_Library/virtual/concerts", refreshLibrary=False
                ))

                tvshowlib = {
                    "LibraryOptions": {
                        
                        "PreferredMetadataLanguage": "fr",
                        "MetadataCountryCode": "FR",
                        "EnableRealtimeMonitor": False,
                        "EnableAutomaticSeriesGrouping": True,
                        "EnableChapterImageExtraction": False,
                        "ExtractChapterImagesDuringLibraryScan": False,
                        "MetadataSavers": [],
                        "DisabledSubtitleFetchers": [
                            "subbuzz"
                        ],
                        "SubtitleDownloadLanguages": [
                            "eng",
                            "fre"
                        ],
                        "RequirePerfectSubtitleMatch": False,
                        "SaveSubtitlesWithMedia": True,
                        "AllowEmbeddedSubtitles": "AllowAll",
                        "PathInfos": [
                            {
                                "Path": "/Video_Library/virtual/shows",
                                "NetworkPath": ""
                            }
                        ],
                        "TypeOptions": [
                            {
                                "Type": "Series",
                                 "MetadataFetchers": MetaSwitch,
                                "MetadataFetcherOrder": MetaSwitch,
                                "ImageFetchers": MetaSwitchTMDBonly,
                                "ImageFetcherOrder": MetaSwitchTMDBonly,
                                "ImageOptions": []
                            },
                            {
                                "Type": "Season",
                                "MetadataFetchers": MetaSwitchTMDBonly,
                                "MetadataFetcherOrder": MetaSwitchTMDBonly,
                                "ImageFetchers": MetaSwitchTMDBonly,
                                "ImageFetcherOrder": MetaSwitchTMDBonly,
                                "ImageOptions": []
                            },                            
                            {
                                "Type": "Episode",
                                "MetadataFetchers": MetaSwitch,
                                "MetadataFetcherOrder": MetaSwitch,
                                "ImageFetchers": MetaSwitch,
                                "ImageFetcherOrder": MetaSwitch,
                                "ImageOptions": []
                            }
                        ]
                    }
                }
                jellyfin(f'Library/VirtualFolders', json=tvshowlib, method='post', params=dict(
                    name='Shows', collectionType="tvshows", paths="/Video_Library/virtual/shows", refreshLibrary=False
                ))


            logger.warning("> don't forget to configure : \n - encoder in /web/index.html#!/encodingsettings.html  \n - and opensub account in /web/index.html#!/configurationpage?name=SubbuzzConfigPage")
                
            
    # ---- end config

class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        self.inotify_run()
    def process_IN_DELETE(self, event):
        self.inotify_run()
    def process_IN_MODIFY(self, event):
        self.inotify_run()
    def process_IN_MOVED_FROM(self, event):
        self.inotify_run()
    def process_IN_MOVED_TO(self, event):
        self.inotify_run()
    def inotify_run(self):
        _scan_instance = ScriptRunner.get(scan)
        _scan_instance.run()


def inotify_deamon():
    # ----- inotify 

    # Set up watch manager
    wm = pyinotify.WatchManager()

    for item2watch in to_watch:
        wm.add_watch(item2watch, pyinotify.ALL_EVENTS, rec=True, auto_add=True)
        logger.info(f"~ Activity monitored on : {item2watch}")

    # Event handler
    event_handler = EventHandler()

    # Notifier
    notifier = pyinotify.Notifier(wm, event_handler)

    notifier.loop()
    # ----- inotify END

if __name__ == "__main__":

    # Initialize the database connection
    init_database(db_path)

    # create movies and shows parent folders
    insert_data("/movies", None, None, None, 'all')
    insert_data("/shows", None, None, None, 'all')
    insert_data("/concerts", None, None, None, 'all')
    sqcommit()
    conn.close()

    jfconfig()

    # walking in mounts and subwalk only in remote_* and local_* folders
    # fetch dual mountpoints

    for f in os.scandir(mounts_root): 
        if f.is_dir() and (f.name.startswith("remote_") or f.name.startswith("local_")) and not '@eaDir' in f.name:
            logger.info(f"> FOUND MOUNTPOINT: {f.name}")
            type = "local" if f.name.startswith("local_") else "remote"
            for d in os.scandir(f.path):
                if d.is_dir() and d.name != '@eaDir':
                    dual_endpoints.append(( mounts_root+"/"+f.name+"/"+d.name,mounts_root+"/rar2fs_"+f.name+"/"+d.name, type))
    
    to_watch = [point for (point, _, point_type) in dual_endpoints if point_type == 'local']    
    
    # threads A B C

    # rd_progress called automatically
    thread_a = threading.Thread(target=periodic_trigger)
    thread_a.daemon = True  # exists when parent thread exits
    thread_a.start()

    # restart_jellygrail_at
    thread_b = threading.Thread(target=restart_jellygrail_at)
    thread_b.daemon = True  # exists when parent thread exits
    thread_b.start()

    # inotify deamon
    thread_c = threading.Thread(target=inotify_deamon)
    thread_c.daemon = True  # exists when parent thread exits
    thread_c.start()

    #thread D, server
    run_server()


