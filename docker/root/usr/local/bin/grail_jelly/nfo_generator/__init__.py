# import requests
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
from jfconfig.jfsql import *
from nfo_generator.xmlnfo import *

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
    pathjg = path + ".jg"

    nfotype = None

    # switch case for video file
    if "bdmv" in nfopath.lower():
        if os.path.basename(nfopath).lower() == "index.nfo":
            nfotype = "bdmv"
    
    elif "video_ts" in nfopath.lower():
        if os.path.basename(nfopath).lower() == "video_ts.nfo":
            #return NFO_FALLBACK
            nfotype = "dvd" #todo test

    elif "/movies" in nfopath[:7]:
        nfotype = "movie"
                
    # switch for tvshow file
    elif os.path.basename(nfopath) == "tvshow.nfo":
        nfotype = "tvshow"

    # switch for episode
    elif "/shows" in nfopath[:6]:
        nfotype = "episodedetails"

    # todo switch for others

    # ----
    #logger.debug(f"check if jg nfo exist = {pathjg}")
    if nfotype != None:
        if os.path.exists(pathjf):
            return pathjf
        else:
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

    init_jellyfin_db_ro("/jellygrail/jellyfin/config/data/library.db") # to get collection id which is in JF api but a pain to fetch :(

    # stops if any dump fails as result won't be consistent anyway

    # jf_json_dump to store whole response
    whole_jf_json_dump = None

    # get first user, needed to request syncqueue
    try:
        users = jfapi.jellyfin('Users').json()
    except Exception as e:
        logger.critical(f"!!! getting JF users failed [nfo_loop_service] error: {e}")
        jfclose_ro()
        return False
    else:
        users_name_mapping = [user.get('Id') for user in users]
        user_id = users_name_mapping[0]


        # get Movies and shows perent lib ID
        # libraries = jellyfin(f'Items', params = dict(userId = user_id)).json()['Items']
        # libids = [lib.get('Id') for lib in libraries if libraries in LIB_NAMES]

        # while loop can start here !!!!!!!!!!!!!!!!!!!!!!!!

        # currentqueue
        try:
            syncqueue = jfapi.jellyfin(f'Jellyfin.Plugin.KodiSyncQueue/{user_id}/GetItems', params = dict(lastUpdateDt=read_jfsqdate_from_file())).json()
        except Exception as e:
            logger.critical(f"!!! Get JF sync queue failed [nfo_loop_service] error: {e}")
            jfclose_ro()
            return False

        nowdate = datetime.now().isoformat()

        # lists
        # items_added_and_updated = syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated')


        # loop added and updated
        if items_added_and_updated := syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated'):
            # refresh ram dumps #todo remove season item type ?
            # 1/ do all but Series, at its id is dependant on child (seasons) updated or not
            # kodi has no nfo for seasons
            s_data = {}

            try:
                whole_jf_json_dump = jfapi.jellyfin(f'Items', params = dict(userId = user_id, Recursive = True, includeItemTypes='Season,Movie,Episode', Fields = 'MediaSources,ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines,Genres,Tags,ParentId,Path,People,ProductionLocations')).json()['Items']
            except Exception as e:
                logger.critical(f"!!! Get JF lib json dump failed [nfo_loop_service] error: {e}")
                jfclose_ro()
                return False
            

            for item in whole_jf_json_dump:
                if item.get('Id') in items_added_and_updated:

                    if(item.get('Type') == 'Season'):
                        pid = item.get('ParentId')
                        items_added_and_updated.append(pid)

                    #elif(item.get('Type') in "Movie Episode"): -> done beneath after all dumps calls to avoid any inconsistencies
                        #jf_xml_create(item)

            #loop the neigboors seasons so that data is complete

            for item in whole_jf_json_dump:
                if(item.get('Type') == 'Season'):
                    if item.get('ParentId') in items_added_and_updated:
                        pid = item.get('ParentId')
                        sidx = item.get('IndexNumber')
                        suid = item.get('Id')
                        s_data.setdefault(pid, [])
                        s_data[pid].append({'sidx': sidx, 'suid': suid})


            try:
                whole_jf_json_dump_s = jfapi.jellyfin(f'Items', params = dict(userId = user_id, Recursive = True, includeItemTypes='Series', Fields = 'ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines,Genres,Tags,ParentId,Path')).json()['Items']
            except Exception as e:
                logger.critical(f"!!! Get JF lib json TVSHOW dump failed [nfo_loop_service] error: {e}")
                jfclose_ro()
                whole_jf_json_dump = None # to free memory
                return False
            

            # if everything went well, it will be consistent so we can continue in xml creation
            for item in whole_jf_json_dump:
                if item.get('Id') in items_added_and_updated:
                    if(item.get('Type') in "Movie Episode"):
                        jf_xml_create(item)

            for item in whole_jf_json_dump_s:
                if item.get('Id') in items_added_and_updated:
                    if(item.get('Type') == 'Series'):
                        jf_xml_create(item, sdata = s_data)            



                        # ---- end movie case


            # print(whole_jf_json_dump)
            # loop added
            # for item in items_added:


            whole_jf_json_dump = None # to free memory
            whole_jf_json_dump_s = None
            logger.info("~> Jellyfin NFOs updated <~")

    jfclose_ro()
    save_jfsqdate_to_file(nowdate)
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
