from base import *
from jgscan.jgsql import *
from jgscan.caching import *
import requests
from jgscan.arena import *
import PTN
#logger = logging.getLogger('jellygrail')

from base.constants import *

# merge those 2 elements
ALLOWED_EXTENSIONS = SUB_EXTS + VIDEO_EXTENSIONS

present_virtual_folders = []
present_virtual_folders_shows = []

dual_endpoints = []



def get_fastpass_ffprobe(file_path):
    # get ffprobe info from sqlite or use ffprobe


    fakestderror = ""


    if (ffprobesq_result := [ffpitem[0] for ffpitem in get_path_props(file_path[file_path.find("/") + JG_VIRT_SHIFT:]) if ffpitem[0] is not None]):
        #logger.debug(f"ffprobe from SQLITE data: {file_path}")

        return (ffprobesq_result[0], fakestderror.encode("utf-8"), 0)


    logger.debug(f"fallback on real ffprobe for: {file_path}")
    return get_plain_ffprobe(file_path)

def init_mountpoints():

    global dual_endpoints
    logger.info("      WAIT| Rclone startup (10s)...") #toimprove with s6 ?
    time.sleep(10)
    for f in os.scandir(MOUNTS_ROOT): 
        if f.is_dir() and (f.name.startswith("remote_") or f.name.startswith("local_")) and not '@eaDir' in f.name:
            type = "local" if f.name.startswith("local_") else "remote"
            logger.info(f"   STORAGE| {f.name}")
            for d in os.scandir(f.path):
                if d.is_dir() and d.name != '@eaDir':
                    dual_endpoints.append(( MOUNTS_ROOT+"/"+f.name+"/"+d.name,MOUNTS_ROOT+"/rar2fs_"+f.name+"/"+d.name, type))
    #print(dual_endpoints)
    to_watch = [point for (point, _, point_type) in dual_endpoints if point_type == 'local']

    return to_watch    

def bdd_install():

    # Play migrations
    jg_datamodel_migration()

    # create movies and shows parent folders
    insert_data("/movies", None, None, None, 'all')
    insert_data("/shows", None, None, None, 'all')
    insert_data("/concerts", None, None, None, 'all')
    sqcommit()



def release_browse(endpoint, releasefolder, rar_item, release_folder_path, storetype):

    # E = movie folder
    #   EF = bdmv case or multiple video release
    #   Esingle = one video release
    # E_DUP = Esingle duplicate workaround when merging
    # S = tvshow
    # S_DUP = S duplicate workaround when merging

    #logger.info(f"  > BROWSING PATH: {endpoint}/{releasefolder}")

    # 0 - init some default values
    multiple_movie_or_disc_present = False
    bdmv_present = False
    season_present = False
    at_least_one_movie_present = False
    nbvideos = 0
    nbvideos_e = 0
    stopthere = False
    stopreason = ''
    atleastoneextra = False
    nomergetype = ""
    bdmv_ffprobed = None
    jgxmultiple_parses = []
    will_idx_check = False
    lang_in_release_string = "NOLANGFOUNDYET"

    # E_DUP duplicate workaround for one-movie releases / RESET idxdup at release level
    idxdupmovset = 1

    # S_DUP duplicate workaround for shows by sXeX by release scanned / RESET ARRAY at release level
    idxdupshowset_a = {}

    # Multi Dim Array for S DIVE
    dive_s_ = {}

    # Multi Dim Array for E DIVE V2
    dive_e_ = {'rootfiles': [], 'rootfoldernames': [], 'mediatype' : None, 'single_premetas': None}

    # make the present_virtual_folders_* global so that we can write in them on the fly (list of release folders)
    global present_virtual_folders
    global present_virtual_folders_shows

    # DIVE S similar check + write + cache-heater 
    # also: DIVE E write + cache-heater (similar check is done elsewhere, on release folder basis)
    for root, folders, files in os.walk(os.path.join(endpoint, releasefolder)):
        for filename in files:
            previous_show_folder = ""
            previous_found_folder = ""
            show = ""
            season = ""
            episode_num = ""
            if not "(sample)" in filename.lower() and not "sample.mkv" in filename.lower() and not '@eaDir' in root and not "DS_Store" in filename.lower() and not ('BDMV' not in os.path.normpath(root).split(os.sep) and filename.lower().endswith(('.m2ts'))):

                # B - cache item fetching 
                # folder insert will use rar_item (could be none or the parent rar file) 
                # file insert will use rd_cache_item (could be a direct file or the parent rar file)

                # S case with itegrated similar show/season/episode fetch (at file loop level):
                if filename.lower().endswith(ALLOWED_EXTENSIONS):
                    regexp_base = None
                    if re.search(r's\d{1,2}\.?e\d{1,2}|\b\d{1,2}x\d{1,2}\b|s\d{1,2}\.\d{1,2}|[ .]e\d{1,2}', filename, re.IGNORECASE):
                        regexp_base = get_wo_ext(filename)
                    elif filename.lower().endswith(SUB_EXTS):
                        parent_srt_folder = os.path.basename(root)
                        #logger.info(f"----- releasefolder = {releasefolder} and parent_srt_folder = {parent_srt_folder}")
                        if (parent_srt_folder != releasefolder):
                            if re.search(r's\d{1,2}\.?e\d{1,2}|\b\d{1,2}x\d{1,2}\b|s\d{1,2}\.\d{1,2}|[ .]e\d{1,2}', parent_srt_folder, re.IGNORECASE):
                                regexp_base = parent_srt_folder
                    

                        
                    if regexp_base:
                        season_present = True
                        # it's an episode file or sub

                        # if is a sub file that does not match a regexp but parent is, integrate it as well #TODO (see Subs subfolder in tvshow plain)

                        match = re.search(r'(.+?)\s*((?:s\d{1,2}\.?e\d{1,2})|(?:\b\d{1,2}x\d{1,2}\b)|(?:s\d{1,2}\.\d{1,2})|(?:[ .]e\d{1,2}))\s*(.*?)', regexp_base, re.IGNORECASE)
                        if match:
                            #logger.info(f"")
                            show, season_episode, episode_title = match.groups()
                            #logger.info(f"show is : {show}")
                            #logger.info(f"seaonsepisoide is : {season_episode}")
                            if 'x' in season_episode.lower():  # it's the 02x03 format
                                season, episode_num = map(str, season_episode.split('x'))
                            elif not 'e' in season_episode.lower() : # it's the S02.03 format
                                season_episode_match = re.search(r's(\d+)\.(\d+)', season_episode, re.IGNORECASE)
                                season, episode_num = season_episode_match.groups()
                            elif 's' in season_episode.lower():  # it's the S02E03 format
                                season_episode_match = re.search(r's(\d+)\.?e(\d+)', season_episode, re.IGNORECASE)
                                season, episode_num = season_episode_match.groups()
                            else:
                                season = "01"
                                season_episode_match = re.search(r'[ .]e(\d+)', season_episode, re.IGNORECASE)
                                (episode_num,) = season_episode_match.groups()

                            season = season.zfill(2)
                            episode_num = episode_num.zfill(2)
                            
                            if lang_in_release_string == "NOLANGFOUNDYET": # do it once
                                lang_in_release_string = find_language_in_string(releasefolder)

                            show = clean_string(show) + lang_in_release_string

                            if previous_show_folder != show: # dont find most similar on every file, if it's same as previous file, don't bother redoing it
                                previous_show_folder = show
                                (show, will_idx_check) = show_find_most_similar(show, present_virtual_folders_shows)
                                previous_found_folder = show
                            else:
                                show = previous_found_folder

                            dive_s_.setdefault(show, {}).setdefault(season, {}).setdefault(episode_num, {'rootfilenames': [], 'mediatype_s' : None, 'premetas': '', 'ffprobed': None})
                            dive_s_[show][season][episode_num]['rootfilenames'].append(os.path.join(root, filename)) # all files are here if filename or parent folder respect regexp....
                            #dive_s_[show].setdefault('finalname', show + find_language_in_string(releasefolder)) # called once
                            '''
                            # clean catpured data
                            show = clean_string(show)

                            # find existing show folder with thefuzz
                            result = find_most_similar(show, present_virtual_folders_shows)

                            will_idx_check = False
                            if result is not None:
                                most_similar_string, similarity_score = result

                                if similarity_score > 94:
                                    show = most_similar_string
                                    #logger.debug(f"      # similarshow check on : {show}")
                                    #logger.debug(f"      # similarshow found is : {most_similar_string} with score {similarity_score}")

                                    # S_DUP
                                    will_idx_check = True

                                else:
                                    present_virtual_folders_shows.append(show)
                            else:
                                present_virtual_folders_shows.append(show)
                            
                            #logger.debug(f"      ## definitive sim show folder : {show}")

                            # dive S WRITE

                            # ensuring structure
                            # MOVED dive_s_.setdefault(show, {}).setdefault(season, {}).setdefault(episode_num, {'rootfilenames': [], 'mediatype_s' : None, 'premetas': '', 'ffprobed': None})

                            # MOVED dive_s_[show][season][episode_num]['rootfilenames'].append(os.path.join(root, filename))
                            '''


                # -- END DIVE write S files+folders only
                # now DIVE write E files (folders later)
                # now DIVE write S remaining data
                # -- including cache-heating (pre-reading) if applies---

                # E+S video files
                if(filename.lower().endswith(VIDEO_EXTENSIONS)):

                    # nbvideos incr
                    nbvideos += 1
                    
                    # and storetype == 'remote' missing and rar_item ignored means we run ffprobe on mkv even if they're cache-heated with void-unrar
                    # cache-heater 1 for all files but iso
                    # (bitrate, dvprofile) = get_ffprobe(os.path.join(root, filename))

                    stdout = None
                    (stdout, _, fferr) = get_plain_ffprobe(os.path.join(root, filename))
                    if fferr != 0:
                        stdout = None
                    (premetastpl, dvprofile) = parse_ffprobe(stdout, filename)


                    if season_present: 
                        if show != "": 
                            # ensuring structure
                            # todo : first_audio must be at the show level of dive_s
                            
                            


                            # ensuring end
                            # dive_s_[show]['finalname'] = show + first_audio old way, and it's already set
                            if(dvprofile) and dive_s_[show][season][episode_num]['mediatype_s'] == None:
                                dive_s_[show][season][episode_num]['mediatype_s'] = '_dv'
                            else:
                                dive_s_[show][season][episode_num]['mediatype_s'] = None
                            
                            dive_s_[show][season][episode_num]['premetas'] = f" -{premetastpl} JGx"
                            dive_s_[show][season][episode_num]['ffprobed'] = stdout

                    else:

                        dive_e_['rootfiles'].append({'as_if_vroot': root, 'eroot': root, 'efilename': filename, 'efilesize':os.path.getsize(os.path.join(root, filename)), 'ffprobed' : stdout, 'premetas': f" -{premetastpl} JGx"})
                        
                        dive_e_['single_premetas'] = f" -{premetastpl} JGx"

                        if(dvprofile):
                            dive_e_['mediatype'] = '_dv'
                        else:
                            dive_e_['mediatype'] = None

                # EF non-video files only (ISO)
                elif filename.lower().endswith('.iso') and not season_present:
                    multiple_movie_or_disc_present = True
                    bdmv_present = True
                    dive_e_['mediatype'] = '_bdmv'

                    nomergetype = " - JGxISO"

                    # cache-heater 0bis for all iso files if storing is remote
                    # done here because a RAR can store an ISO
                    # if storetype == 'remote': # change : read them even if not remote to know if its a dvd or bluray
                    nomergetype = " - JGxBluRay"
                    iso_file_path = os.path.join(root, filename)
                    try:
                        mount_iso(iso_file_path, "/mnt/tmp")
                        if read_small_files("/mnt/tmp"):
                            nomergetype = " - JGxDVD"
                    except Exception as e:
                        stopthere = True
                        stopreason += ' >Pre-reading ISO failed'
                        logger.error(f" - FAILURE_iso: mount or read failed on: {iso_file_path}")
                    finally:
                        unmount_iso("/mnt/tmp")
                    stdout = None
                    if not stopthere:
                        prefix = "" if nomergetype == " - JGxDVD" else "bluray:"
                        (stdout, _, fferr) = get_plain_ffprobe(prefix+iso_file_path)
                        if fferr != 0:
                            stdout = None
                        

                        dive_e_['rootfiles'].append({'as_if_vroot': root, 'eroot': root, 'efilename': filename, 'efilesize': 0, 'ffprobed' : stdout})

                # EF non-video files only (BDMV)
                elif ('BDMV' in os.path.normpath(root).split(os.sep) or 'VIDEO_TS' in os.path.normpath(root).split(os.sep)) and not season_present:



                    multiple_movie_or_disc_present = True
                    bdmv_present = True # in the meaning of any disc dvd or bluray
                    dive_e_['mediatype'] = '_bdmv' # bindfs mediatype not yet refined
                    nomergetype = " - JGxBluRay"

                    ffprobed = None

                    if rar_item == None and storetype == 'remote':
                        if not read_file_with_timeout(os.path.join(root, filename)):
                            logger.error(f" - FAILURE_direct_read: IO or timeout on bdmv file: {os.path.join(root, filename)}")
                            stopthere = True
                            stopreason += ' >Pre-reading BDMV files failed'



                    if 'VIDEO_TS' in os.path.normpath(root).split(os.sep): # DVD struct
                        nomergetype = " - JGxDVD"
                        if filename.lower() == "vts_01_1.vob": 
                            (ffprobed, _, fferr) = get_plain_ffprobe(os.path.join(root, filename))
                            if fferr != 0:
                                ffprobed = None

                    elif bdmv_ffprobed == None: #bluray struct
                        (stdout, _, fferr) = get_plain_ffprobe("bluray:"+os.path.join(endpoint, releasefolder))
                        if fferr != 0:
                            stdout = None
                            bdmv_ffprobed = "None" # error code, if it does not work the first time, don't retry and then, later, "None" will be understood as real None
                        else:
                            bdmv_ffprobed = stdout

                    if not stopthere:
                        dive_e_['rootfiles'].append({'as_if_vroot': root, 'eroot': root, 'efilename': filename, 'efilesize': 0, 'ffprobed' : ffprobed})

                # S+E remaining mess
                else:
                    # S+E all other files cache-heat
                    if rar_item == None and storetype == 'remote':
                    # cache-heater 2 for all other files in S and E when in remote + when no rar_item (as unrar has already cache-heated those files)
                        if not read_file_with_timeout(os.path.join(root, filename)):
                            logger.error(f" - FAILURE_direct_read: IO or timeout on file: {os.path.join(root, filename)}")
                            stopthere = True
                            stopreason += ' >Pre-reading non-video files failed'
                    # S 
                    #if filename.lower().endswith(ALLOWED_EXTENSIONS) and season_present:
                    #    (show, will_idx_check) = show_find_most_similar(show, present_virtual_folders_shows)
                    #    dive_s_.setdefault(show, {}).setdefault(season, {}).setdefault(episode_num, {'rootfilenames': [], 'mediatype_s' : None, 'premetas': '', 'ffprobed': None})
                    #    dive_s_[show][season][episode_num]['rootfilenames'].append(os.path.join(root, filename))
                    # E
                    if not season_present and not stopthere:
                        dive_e_['rootfiles'].append({'as_if_vroot': root, 'eroot': root, 'efilename': filename, 'efilesize': 0, 'ffprobed' : None})

            elif ('BDMV' not in os.path.normpath(root).split(os.sep) and filename.lower().endswith(('.m2ts'))):
                stopreason += ' >m2ts outside its BDMV structure (verify ALL_FILES_INCLUDING_STRUCTURE in settings.env)'
                #wont necessarily stop there is other filed are found


        # DIVE folders for S are written upfront
        # DIVE write E folders
        if not season_present and not stopthere:
            for folder in folders:
                # E case folder DIVE write:
                if not '@eaDir' in os.path.join(root, folder):
                    dive_e_['rootfoldernames'].append(os.path.join(root, folder))

    # extras management with 0.3 rule for all E cases
    
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
        stopthere = True
        stopreason += ' >Nothing to scan: RD download unfinished or broken (or not a video release)'
    elif(nbvideos_e > 1):
        multiple_movie_or_disc_present = True
        nomergetype = " - JGxMultiple"
        logger.info("          ~ << Multiple videos release")
    elif bdmv_present:
        logger.info("          ~ << BDMV or DVD Release")
    elif season_present:
        logger.info("          ~ << TV show release")
    else:
        logger.info("          ~ << Single video release")


    if stopthere == True:
        logger.warning(f"          ~ Failed Item: {os.path.join(endpoint, releasefolder)} ; Reasons: {stopreason}")
        return False
    # ---- DIVE S READ + insert + S_DUP idxcheck, unless stopthere is true-----
    if season_present and not stopthere:

        # S_DUP / reset idxdup at dive_s_ loop level 
        

        for keyshow, seasonlist in dive_s_.items():
            for seasonkey, episodelist in seasonlist.items():
                for episodekey, episodeattribs in episodelist.items():
                    for rootfilename in episodeattribs['rootfilenames']:

                        # B cache item fetching
                        rd_cache_item = rootfilename if rar_item == None else rar_item

                        # metas compute
                        # S_DUP
                        idxdup = 1
                        metas = episodeattribs['premetas']
                        if (will_idx_check):
                        # LS the sim folder with no ext files (because we loop check at filename level, we want to list video only and not subs)
                            ls_virtual_folder_a = []
                            for itemv in ls_virtual_folder("/shows/"+keyshow+"/Season "+seasonkey+"/"+f"{keyshow} S{seasonkey}E{episodekey}"):
                                if os.path.basename(itemv[0]).lower().endswith(VIDEO_EXTENSIONS):
                                    ls_virtual_folder_a.append(get_wo_ext(os.path.basename(itemv[0])))

                            # We deduplicate anyway to have videofilename.* count as one entry
                            
                            if(f"{keyshow} S{seasonkey}E{episodekey}" not in idxdupshowset_a):
                                for existing_file in ls_virtual_folder_a:
                                    if f"{keyshow} S{seasonkey}E{episodekey}"+metas+str(idxdup) == existing_file:
                                        idxdup += 1
                                idxdupshowset_a[f"{keyshow} S{seasonkey}E{episodekey}"] = idxdup
                            else:
                                idxdup = idxdupshowset_a[f"{keyshow} S{seasonkey}E{episodekey}"]
                        metas = metas + str(idxdup)
                        # S_DUP

                        # filename ext compute
                        if rootfilename.endswith(VIDEO_EXTENSIONS):
                            filename_ext = get_ext(os.path.basename(rootfilename))
                            ffprobed = episodeattribs['ffprobed'] 
                        else:
                            ffprobed = None
                            filename_ext = subtitle_extension(os.path.basename(rootfilename))

                        # toimprove : try to reimplement subtitles parsing for tvshows
                        # toimprove : put "subs" subfolders back in (ex: agatha raison s04)

                        # S FOLDERS INSERT 
                        insert_data("/shows/"+keyshow, None, None, None, episodeattribs['mediatype_s'])
                        insert_data("/shows/"+keyshow+"/Season "+seasonkey, None, None, None, episodeattribs['mediatype_s'])
                        insert_data("/shows/"+keyshow+"/Season "+seasonkey+"/"+f"{keyshow} S{seasonkey}E{episodekey}", None, None, None, episodeattribs['mediatype_s'])
                        # S FILES INSERT
                        insert_data("/shows/"+keyshow+"/Season "+seasonkey+"/"+f"{keyshow} S{seasonkey}E{episodekey}"+"/"+f"{keyshow} S{seasonkey}E{episodekey}{metas}{filename_ext}", rootfilename, release_folder_path, rd_cache_item, episodeattribs['mediatype_s'], ffprobed)

    if not season_present and not stopthere:
        
        if not (multiple_movie_or_disc_present):
            # A - prepare parse for single movie release
            release_parse = PTN.parse(releasefolder)
            # GENERIC META FOR Esingle case
            title_year = clean_string(f"{release_parse['title']}{ytpl(release_parse.get('year'))}")
            # ... fuzzy mathing to merge with similar releases
            result = find_most_similar(title_year, present_virtual_folders)

            will_idx_check = False
            if result is not None:
                most_similar_string, similarity_score = result

                if similarity_score > 94:
                    title_year = most_similar_string
                    #logger.debug(f"      # similarmovie check on : {title_year}")
                    #logger.debug(f"      # similarmovie found is : {most_similar_string} with score {similarity_score}")

                    # LS the sim folder with no ext files (because we loop check at release level, we don't need to filter by ext, we just deduplicate the array)
                    ls_virtual_folder_a = [get_wo_ext(os.path.basename(itemv[0])) for itemv in ls_virtual_folder("/movies/"+title_year)]

                    # deduplicate the array + We deduplicate anyway to have videofilename.* count as one entry
                    ls_virtual_folder_a = list(set(ls_virtual_folder_a))

                    # E_DUP:
                    will_idx_check = True

                else:
                    present_virtual_folders.append(title_year)
            else:
                present_virtual_folders.append(title_year)
            #logger.debug(f"      ## definitive sim movie folder : {title_year}")

        # ----- DIVE E READ + E_DUP check idx + insert
        for item in dive_e_['rootfiles']:
            
            rootfilename = os.path.join(item['eroot'], item['efilename'])
            asifrootfilename = os.path.join(item['as_if_vroot'], item['efilename'])

            # B cache item fetching
            rd_cache_item = rootfilename if rar_item == None else rar_item

            # compute ext
            filename_ext = get_ext(os.path.basename(rootfilename))

            # EF case --------- can have extras
            if multiple_movie_or_disc_present:
                


                ffprobed = item['ffprobed']
                if not item['as_if_vroot'].endswith('extras') and dive_e_['mediatype'] != "_bdmv" and rootfilename.lower().endswith(VIDEO_EXTENSIONS):
                    jgxmultiple_parse_res = PTN.parse(get_wo_ext(os.path.basename(rootfilename)))
                    # GENERIC META FOR EF case (new!)
                    jgxmultiple_parse = clean_string(f"{jgxmultiple_parse_res['title']}{ytpl(jgxmultiple_parse_res.get('year'))}")+item['premetas']

                    for existing_file in jgxmultiple_parses:
                        if jgxmultiple_parse+str(idxdupmovset) in jgxmultiple_parses:
                            idxdupmovset += idxdupmovset+1
                    jgxmultiple_parse += str(idxdupmovset)
                    jgxmultiple_parses.append(jgxmultiple_parse)
                    insert_data("/movies/"+releasefolder+nomergetype+"/"+jgxmultiple_parse+filename_ext, rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'], ffprobed)
                else:
                    insert_data("/movies/"+releasefolder+nomergetype+"/"+os.path.relpath(asifrootfilename, os.path.join(endpoint, releasefolder)), rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'], ffprobed)

            # Esingle case ------------ can have extras but with switch
            elif rootfilename.lower().endswith(ALLOWED_EXTENSIONS):

                # E_DUP:
                metas = dive_e_['single_premetas'] #deleted {relmetas}here
                if(will_idx_check):
                    if(idxdupmovset == 1):
                        for existing_file in ls_virtual_folder_a:
                            if title_year+metas+str(idxdupmovset) == existing_file:
                                idxdupmovset += 1
                metas = metas + str(idxdupmovset)
                # E_DUP

                if not rootfilename.lower().endswith(VIDEO_EXTENSIONS):
                    insert_data("/movies/"+title_year+"/"+title_year+metas+subtitle_extension(os.path.basename(asifrootfilename)), rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'])
                else:
                    if item['as_if_vroot'].endswith('extras'):
                        insert_data("/movies/"+title_year+"/"+os.path.relpath(asifrootfilename, os.path.join(endpoint, releasefolder)), rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'], item['ffprobed'])
                    else:
                        insert_data("/movies/"+title_year+"/"+title_year+metas+filename_ext, rootfilename, release_folder_path, rd_cache_item, dive_e_['mediatype'], item['ffprobed'])

                    at_least_one_movie_present = True

        # rootfolders for EF case
        for rootfoldername in dive_e_['rootfoldernames']:
            if multiple_movie_or_disc_present:
                insert_data("/movies/"+releasefolder+nomergetype+"/"+os.path.relpath(rootfoldername, os.path.join(endpoint, releasefolder)), None, release_folder_path, rar_item, dive_e_['mediatype'])


        # RELEASE-like BASE FOLDERs including extras subfolder if applies
        # EF folders

        if multiple_movie_or_disc_present:
            bdmv_ffprobed = None if bdmv_ffprobed == "None" else bdmv_ffprobed
            insert_data("/movies/"+releasefolder+nomergetype, None, None, None, dive_e_['mediatype'], bdmv_ffprobed)
            if atleastoneextra:
                insert_data("/movies/"+releasefolder+nomergetype+"/extras", None, None, None, dive_e_['mediatype'])

        # Esingle folders
        if at_least_one_movie_present:
            insert_data("/movies/"+title_year, None, None, None, dive_e_['mediatype'])
            if atleastoneextra:
                insert_data("/movies/"+title_year+"/extras", None, None, None, dive_e_['mediatype'])
        # S folders are done in first filename loop and do not have extras
    return True

def scan():

    #init_database()

    #global logger

    #logger.info("      WAIT| Giving time for rclone wake-up ...") #toimprove
    time.sleep(9)

    items_scanned = 0

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
                    logger.info(f"  NEW-ITEM~ {f.name}")
                    browse = True
                    endpoint2browse = src1
                    rar_item = None
                    for g in os.scandir(f.path):
                        if g.name.lower().endswith('.rar') :
                            rar_item = g.path
                            endpoint2browse = src2
                            logger.info(f"          ~ with a .RAR file: {g.name}")
                            if storetype == "remote":
                                for i in range(2):
                                    # cache-heater 0 for RAR files and rar2fs
                                    unrar_result = unrar_to_void(g.path)
                                    if not unrar_result == "OK":
                                        if unrar_result == "ERROR_IO":
                                            logger.error(f" - IO Error on first try, waits 5s and retry ... {g.path}")
                                            if i == 0:
                                                time.sleep(5)
                                            if i == 1:
                                                logger.error(f" - FAILURE_unrar : IO Error on second try {g.path}")
                                                browse = False
                                                break
                                        elif unrar_result == "ERROR_NOFILES":
                                            logger.warning("          ~ ...but NO Files in this RAR")
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
                        if release_browse(endpoint2browse, f.name, rar_item, f.path, storetype):
                            items_scanned += 1
                        sqcommit()

                
                elif not '@eaDir' in f.name and not '.DS_Store' in f.name and (f.name.lower().endswith(VIDEO_EXTENSIONS) or f.name.lower().endswith('.iso')):
                    items_scanned += 1
                    logger.info(f"  NEW-ITEM~ {f.name} (folder-less)")

                    dvprofile = None
                    mediatype = None
                    nomergetype = ""
                    metas = ""
                    stdout = None

                    idxdupmovset = 1
                    #file not in a release folder

                    # A - prepare parse for single movie release
                    release_parse = PTN.parse(f.name)

                    # compute ext
                    filename_ext = get_ext(os.path.basename(f.path))

                    # GENERIC META FOR Esingle case
                    title_year = clean_string(f"{release_parse['title']}{ytpl(release_parse.get('year'))}")

                    if f.name.lower().endswith(VIDEO_EXTENSIONS):
                        result = find_most_similar(title_year, present_virtual_folders)

                        will_idx_check = False
                        if result is not None:
                            most_similar_string, similarity_score = result

                            if similarity_score > 94:
                                title_year = most_similar_string
                                #logger.debug(f"      # similar movie check on : {title_year}")
                                #logger.debug(f"      # similar movie found is : {most_similar_string} with score {similarity_score}")

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

                        #logger.debug(f"      ## definitive similar movie folder : {title_year}")

                        (stdout, _, fferr) = get_plain_ffprobe(f.path)
                        if fferr != 0:
                            stdout = None
                        
                        (premetastpl, dvprofile) = parse_ffprobe(stdout, f.path)
                        metas = f" -{premetastpl} JGx"

                        #(bitrate, dvprofile) = get_ffprobe(f.path)
                        if(dvprofile):
                            mediatype = '_dv'

                        # E_DUP:
                        if(will_idx_check):
                            for existing_file in ls_virtual_folder_a:
                                if title_year+metas+str(idxdupmovset) == existing_file:
                                    idxdupmovset += 1
                        metas = metas + str(idxdupmovset)
                        # E_DUP

                    elif f.name.lower().endswith('.iso'):
                        mediatype = '_bdmv'

                        # cache-heater 0bis for all iso files if storing is remote
                        # done here because a RAR can store an ISO
                        # if storetype == 'remote': # change : read them even if not remote to know if its a dvd or bluray
                        nomergetype = " - JGxBluRay"
                        iso_file_path = f.path

                        try:
                            mount_iso(iso_file_path, "/mnt/tmp")
                            if read_small_files("/mnt/tmp"):
                                nomergetype = " - JGxDVD"
                        except Exception as e:
                            logger.error(f" - FAILURE_iso: mount or read failed on: {iso_file_path}")
                        else:
                            stdout = None
                            prefix = "" if nomergetype == " - JGxDVD" else "bluray:"
                            (stdout, _, fferr) = get_plain_ffprobe(prefix+iso_file_path)
                            if fferr != 0:
                                stdout = None
                        finally:
                            unmount_iso("/mnt/tmp")
                    
                    insert_data("/movies/"+title_year+nomergetype, None, f.path, None, mediatype)
                    insert_data("/movies/"+title_year+nomergetype+"/"+title_year+metas+filename_ext, f.path, f.path, None, mediatype, stdout)
                    sqcommit()

    return items_scanned
    # Close the connection
    #sqclose()


