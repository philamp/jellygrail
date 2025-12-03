# import requests
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
# from jfconfig.jfsql import *
import jfapi
from nfo_generator.xmlnfo import Item, build_jg_nfo_video, jf_xml_create
from kodi_services.kodiInstances import kodiDBRegistry
from pathlib import Path
import msgspec

# Jellyfin.Plugin.KodiSyncQueue/1197e3fbeaee4d1e905a5b3ef7f5380c/GetItems?lastUpdateDt=2024-06-12T00:00:00.0000000Z
# {{baseUrl}}/Items?ParentId=f137a2dd21bbc1b99aa5c0f6bf02a805&Fields=MediaSources,ProviderIds,Overview


# --- msgspec structs ---
class User(msgspec.Struct):
    Id: str

class SyncQueue(msgspec.Struct, omit_defaults=True):
    ItemsAdded: list[str] = []
    ItemsUpdated: list[str] = []

class ItemsResponse(msgspec.Struct):
    Items: list[Item]



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


def nfo_loop_service(stopEvent) -> bool:
    nbofmovieorepisode = 0
    nbofmovie = 0
    nbofepisode = 0
    nboftvshow = 0

    whole_jf_json_dump: list[Item] | None = None

    # --- get first user ---

    if users_raw := jfapi.jellyfin("Users").content:
        users = msgspec.json.decode(users_raw, type=list[User])
    else:
        logger.error(f"   NFO-GEN| ...so nfo generation failed immediately at getting JF users")
        return False

    user_id = users[0].Id

    # --- syncqueue ---

    if syncqueue_raw := jfapi.jellyfin(
        f"Jellyfin.Plugin.KodiSyncQueue/{user_id}/GetItems",
        params=dict(lastUpdateDt=read_jfsqdate_from_file())
    ).content:
        syncqueue = msgspec.json.decode(syncqueue_raw, type=SyncQueue)
    else:
        logger.critical(f"   NFO-GEN| ...so nfo generation failed only at getting Jellyfin.Plugin.KodiSyncQueue")
        return False

    nowdate = datetime.now().isoformat()

    items_added_and_updated_pre = syncqueue.ItemsAdded + syncqueue.ItemsUpdated
    if not items_added_and_updated_pre:
        return False
    
    # new nfo batch generation
    batchId = kodiDBRegistry.newNfoBatch()

    logger.info("   NFO-GEN| ...New NFOs: metadata JSON dump (can take a while)...")

    # --- deduplication ---
    items_added_and_updated_pre = list(set(items_added_and_updated_pre))
    items_added_and_updated: list[tuple[str, bool]] = [
        (iid, iid in syncqueue.ItemsUpdated) for iid in items_added_and_updated_pre
    ]

    s_data: dict[str, list[dict]] = {}

    # --- full dump (movies + episodes + seasons) ---

    if stopEvent.is_set():
        return False

    if dump_raw := jfapi.jellyfin(
        "Items",
        params=dict(
            userId=user_id,
            Recursive=True,
            includeItemTypes="Season,Movie,Episode",
            Fields="MediaSources,ProviderIds,Overview,OriginalTitle,RemoteTrailers,"
                    "Taglines,Genres,Tags,ParentId,Path,People,ProductionLocations"
        )
    ).content:
        whole_jf_json_dump = msgspec.json.decode(dump_raw, type=ItemsResponse).Items
    else:
        logger.critical(f"   NFO-GEN| ...so nfo generation failed only at getting at /Items")
        return False

    # --- enrich sync list with parent episodes/seasons ---
    for item in whole_jf_json_dump:
        if item.Type == "Episode":
            for item_id, is_updated in items_added_and_updated:
                if item.Id == item_id and item.ParentId and item.ParentId not in items_added_and_updated_pre:
                    items_added_and_updated.append((item.ParentId, is_updated))

            # for mediasource in item.MediaSources:
                # if mediasource.Path:
                    # path = Path(mediasource.Path)
                    # logger.debug(f"Episode media path: {path}")

        elif item.Type == "Season":
            for item_id, is_updated in items_added_and_updated:
                if item.Id == item_id and item.ParentId and item.ParentId not in items_added_and_updated_pre:
                    items_added_and_updated.append((item.ParentId, is_updated))

    # --- collect season info per tvshow ---
    for item in whole_jf_json_dump:
        if item.Type == "Season" and item.ParentId:
            if any(pid == item.ParentId for pid, _ in items_added_and_updated):
                s_data.setdefault(item.ParentId, [])
                s_data[item.ParentId].append({"sidx": item.IndexNumber, "suid": item.Id})

    # --- fetch TV shows ---

    if stopEvent.is_set():
        return False

    if dump_s_raw := jfapi.jellyfin(
        "Items",
        params=dict(
            userId=user_id,
            Recursive=True,
            includeItemTypes="Series",
            Fields="ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines,Genres,Tags,ParentId,Path"
        )
    ).content:
        whole_jf_json_dump_s = msgspec.json.decode(dump_s_raw, type=ItemsResponse).Items
    else:
        logger.critical(f"   NFO-GEN| ...so nfo generation failed only at getting at /Items (bis)")
        whole_jf_json_dump = None
        return False

    if stopEvent.is_set():
        return False

    # --- XML creation for movies & episodes ---
    for item in whole_jf_json_dump:
        for item_id, is_updated in items_added_and_updated:
            if item.Id == item_id and item.Type in ("Movie", "Episode"):
                if jf_xml_create(item, is_updated, sdata=None, batchUid=batchId):
                    nbofmovieorepisode += 1
                    if item.Type == "Movie":
                        nbofmovie += 1
                    else:
                        nbofepisode += 1
                    if nbofmovieorepisode % 10 == 0:
                        logger.info(f"   NFO-GEN| Movie[{nbofmovie}], Episode[{nbofepisode}], TvShow[0]")

    if stopEvent.is_set():
        return False

    # --- XML creation for TV shows ---
    for item in whole_jf_json_dump_s:
        for item_id, is_updated in items_added_and_updated:
            if item.Id == item_id and item.Type == "Series":
                if jf_xml_create(item, is_updated, sdata=s_data, batchUid=batchId):
                    nboftvshow += 1
                    if nboftvshow % 10 == 0:
                        logger.info(f"   NFO-GEN| Movie[{nbofmovie}], Episode[{nbofepisode}], TvShow[{nboftvshow}]")

    logger.info(f"   NFO-GEN| Movie[{nbofmovie}], Episode[{nbofepisode}], TvShow[{nboftvshow}] ...completed")

    whole_jf_json_dump = None
    whole_jf_json_dump_s = None
    
    kodiDBRegistry.saveNfoBatches(batchId)
    save_jfsqdate_to_file(nowdate)
    return True

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
