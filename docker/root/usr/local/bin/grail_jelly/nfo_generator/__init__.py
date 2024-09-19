# import requests
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
from jfconfig.jfsql import *
from nfo_generator.xmlnfo import *
from pathlib import Path

# Name of librairies
# LIB_NAMES = ("Movies", "Shows")

# Jellyfin.Plugin.KodiSyncQueue/1197e3fbeaee4d1e905a5b3ef7f5380c/GetItems?lastUpdateDt=2024-06-12T00:00:00.0000000Z
# {{baseUrl}}/Items?ParentId=f137a2dd21bbc1b99aa5c0f6bf02a805&Fields=MediaSources,ProviderIds,Overview

# Webdav ip + port specified for local network (as seen by a local network device)
# is it still useful if it's decided on nginx side ? maybe if later its not nginx anymore
# WEBDAV_LAN_HOST = os.getenv('WEBDAV_LAN_HOST')


# for fetch_nfo()
NFO_FALLBACK = "/mounts/filedefaultnfo_readme_p.txt" # put a default path


def fetch_nfo(nfopath):

    # given a bindfs provided virtual nfo path, give a populatednfo path
    # movie : find .jf else .jg else generate .jg with fileinfo thanks to ffp data in db
    # show : find .jf else .jg else generate .jg with dummy data
    # 
    # careful to M_DUP and S_DUP management : no more identical.mkv + identical.mp4

    #logger.debug(f"nfo requested ?:{nfopath}")
    
    path = JFSQ_STORED_NFO + get_wo_ext(nfopath) + ".nfo"
    pathjf = path + ".jf"
    pathjf_done = pathjf + ".done"
    pathjf_updated = pathjf + ".updated"
    pathjg = path + ".jg"

    nfotype = None

    # switch case for video file
    if "bdmv" in nfopath.lower():
        if os.path.basename(nfopath).lower() == "index.nfo":
            nfotype = "bdmv"
    
    elif "video_ts" in nfopath.lower():
        if os.path.basename(nfopath).lower() == "video_ts.nfo":
            nfotype = "dvd" 

    elif "/movies" in nfopath[:7]:
        nfotype = "movie"
                
    # switch for tvshow file
    elif os.path.basename(nfopath) == "tvshow.nfo":
        nfotype = "tvshow"

    # switch for episode
    elif "/shows" in nfopath[:6]:
        nfotype = "episodedetails"


    if nfotype != None:
        if os.path.exists(pathjf_updated):
            return pathjf_updated
        elif os.path.exists(pathjf):
            return pathjf
        elif os.path.exists(pathjf_done):
            return pathjf_done
        
        if os.path.exists(pathjg):
            return pathjg
        else:
            # build the jg simple nfo ....
            # logger.debug(f"pathjg that will be written is: {pathjg}")
            if build_jg_nfo_video(nfopath, pathjg, nfotype):
                return pathjg

    else:
        return NFO_FALLBACK


def nfo_loop_service():


    # stops if any dump fails as result won't be consistent anyway
    #logger.debug("Scan thread selected is nfo generator")
    # jf_json_dump to store whole response
    whole_jf_json_dump = None

    # get first user, needed to request syncqueue
    try:
        users = jfapi.jellyfin('Users').json()
    except Exception as e:
        logger.critical(f"Getting JF users failed [nfo_loop_service] error: {e}")
        #jfclose_ro()
        return False

    users_name_mapping = [user.get('Id') for user in users]
    user_id = users_name_mapping[0]


    # get Movies and shows perent lib ID
    # libraries = jellyfin(f'Items', params = dict(userId = user_id)).json()['Items']
    # libids = [lib.get('Id') for lib in libraries if libraries in LIB_NAMES]

    # while loop can start here !!!!!!!!!!!!!!!!!!!!!!!!

    # currentqueue
    try:
        #logger.debug("goes through kodisync queue")
        syncqueue = jfapi.jellyfin(f'Jellyfin.Plugin.KodiSyncQueue/{user_id}/GetItems', params = dict(lastUpdateDt=read_jfsqdate_from_file())).json()
    except Exception as e:
        logger.critical(f"Get JF sync queue failed [nfo_loop_service] error: {e}")
        #jfclose_ro()
        return False

    nowdate = datetime.now().isoformat()

    # lists
    # items_added_and_updated = syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated')


    # loop added and updated
    if items_added_and_updated_pre := syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated'):
        # 1st deduplication here
        items_added_and_updated_pre = list(set(items_added_and_updated_pre))

        items_added_and_updated = [(item_id, item_id in syncqueue.get('ItemsUpdated')) for item_id in items_added_and_updated_pre]
        s_data = {}
        #t_data = {}
        #pre_t_data = {}

        try:
            whole_jf_json_dump = jfapi.jellyfin(f'Items', params = dict(userId = user_id, Recursive = True, includeItemTypes='Season,Movie,Episode', Fields = 'MediaSources,ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines,Genres,Tags,ParentId,Path,People,ProductionLocations')).json()['Items']
        except Exception as e:
            logger.critical(f"!!! Get JF lib json dump failed [nfo_loop_service] error: {e}")
            #jfclose_ro()
            return False
        

        #loop through episodes
        for item in whole_jf_json_dump:

            # tvshow paths fix
            # toimprove : not sure this way the tvshow.nfo get alwasy written if new episode that don't trigger syncqueue for season type
            if(item.get('Type') == 'Episode'):
                # get all possible tvshow parent paths and store it in { season_parent_id : paths_array[]}
                # tvshow path by season uid (to associate later)
                #sname = item.get('SeriesName')
                #pre_t_data.setdefault(sname, [])
                #pre_t_data[pid].append(item.get('Id'))

                for item_id, is_updated in items_added_and_updated:
                    if item.get('Id') == item_id:
                        pid = item.get('ParentId')
                        if pid not in items_added_and_updated_pre:
                            items_added_and_updated.append((pid, is_updated))

                for mediasource in item.get('MediaSources'):
                    path = Path(mediasource.get('Path'))
                    trimmedPath = str(Path(*path.parts[:5]))
                    #toremove
                    #logger.info(f"----- URL {trimmedPath}")
                    #pre_t_data[sname+re.search(r'\{.*?\}', trimmedPath).group(0)].append(trimmedPath)

        
        for item in whole_jf_json_dump:
            # get tvshows UID to update them
            if(item.get('Type') == 'Season'):
                for item_id, is_updated in items_added_and_updated:
                    if item.get('Id') == item_id:
                        pid = item.get('ParentId')
                        if pid not in items_added_and_updated_pre:
                            items_added_and_updated.append((pid, is_updated))


                #elif(item.get('Type') in "Movie Episode"): -> done beneath after all dumps calls to avoid any inconsistencies
                    #jf_xml_create(item)



        for item in whole_jf_json_dump:
            #loop the neigboors seasons so that tvshow data is complete
            if(item.get('Type') == 'Season'):
                if any(pid == item.get('ParentId') for pid, _ in items_added_and_updated):
                    pid = item.get('ParentId')
                    #sname = item.get('SeriesName') # bind by series name to merge different folders in one
                    sidx = item.get('IndexNumber')
                    suid = item.get('Id')
                    s_data.setdefault(pid, [])
                    s_data[pid].append({'sidx': sidx, 'suid': suid})
                    # append t_data[tvshowid] with pre_t_data indexed by season uids
                    #t_data.setdefault(sname, []) # bind by series name to merge different folders in one
                    #t_data[sname].extend(pre_t_data[sname])

        # deduplicate pre_t_data
        #for key, _ in pre_t_data.items():
            #pre_t_data[key] = list(set(pre_t_data[key]))

        #logger.info(f"#### {t_data}")

        try:
            whole_jf_json_dump_s = jfapi.jellyfin(f'Items', params = dict(userId = user_id, Recursive = True, includeItemTypes='Series', Fields = 'ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines,Genres,Tags,ParentId,Path')).json()['Items']
        except Exception as e:
            logger.critical(f"!!! Get JF lib json TVSHOW dump failed [nfo_loop_service] error: {e}")
            #jfclose_ro()
            whole_jf_json_dump = None # to free memory
            return False
        


        # if everything went well, it will be consistent so we can continue in xml creation
        #already_seen = []
        for item in whole_jf_json_dump:
            for item_id, is_updated in items_added_and_updated:
                #if item_id not in already_seen:
                if item.get('Id') == item_id:
                    if(item.get('Type') in "Movie Episode"):
                        jf_xml_create(item, is_updated)
                    #already_seen.append(item_id)

        '''
        s_ids = []
        for item in whole_jf_json_dump_s:
            s_ids.append(item.get('Id'))
        orphans = [key for key in t_data if key not in s_ids]
        '''



        for item in whole_jf_json_dump_s:
            for item_id, is_updated in items_added_and_updated:
                #if item_id not in already_seen:
                if item.get('Id') == item_id:
                    if(item.get('Type') == 'Series'):
                        jf_xml_create(item, is_updated, sdata = s_data)   
                    #already_seen.append(item_id)         

        # toremove : already_seen complete remove

                    # ---- end movie case


        # print(whole_jf_json_dump)
        # loop added
        # for item in items_added:


        whole_jf_json_dump = None # to free memory
        whole_jf_json_dump_s = None
        logger.info(" TASK-DONE~ Jellyfin NFOs updated")

        #jfclose_ro()
        save_jfsqdate_to_file(nowdate)
    else:
        logger.info(" TASK-DONE~ Not any new or updated NFO")
        return True
    return True
    # ---- if finished correctly


def read_jfsqdate_from_file():
    try:
        with open(JFSQ_LAST_REQUEST, 'r') as file:
            strincr = file.read().strip()
    except FileNotFoundError:
        logger.warning(f"Nfo generator sync queue last sync date not exists yet (taking default then)")
        return "2024-06-16T00:00:00.0000000Z"
    else:
        return strincr

def save_jfsqdate_to_file(datestring):
    try:
        with open(JFSQ_LAST_REQUEST, 'w') as file:
            file.write(datestring)
    except IOError as e:
        logger.critical(f"Error saving last sync queue date to file: {e}")
