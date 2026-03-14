from base import *
from base.littles import *
from base.constants import *
from kodi_services.sqlkodi import sqlKodiDB
import requests
import urllib.parse
import websocket
import threading
from datetime import datetime
from jg_services import get_premium_time_left
from kodi_services.kodiInstances import kodiDBRegistry



KODI_MAIN_URL = "172.22.2.28" # TODO remove, to be deprecated

kodi_url = f"http://{KODI_MAIN_URL}:8080/jsonrpc"
kodi_ws_url = f"ws://{KODI_MAIN_URL}:9090/jsonrpc"
kodi_username = "kodi"
kodi_password = "kodi"

last_clean = 0


headers = {
    'Content-Type': 'application/json',
}

is_scanning = False
is_cleaning = False
refresh_is_safe = False

def lowersArray(array):
    return [m.lower() for m in array]

def extract_triplets(s: str):
    out = []
    for inner in re.findall(r'[\[{]([A-Za-z]+)[\]}]', s):
        out.extend(re.findall(r'[A-Za-z]{3}', inner))  # prend chaque bloc de 3
    return out

def extract_triplets_audio(s: str):
    out = []
    for inner in re.findall(r'\{([A-Za-z]+)\}', s):
        out.extend(re.findall(r'[A-Za-z]{3}', inner))
    return out

def getTableAndColumnFromMediatype(ptype):
    tablekeys = {
        "movie": ("movie_view", "idMovie"),
        "tvshow": ("tvshow_view", "idShow"),
        "episode": ("episode_view", "idEpisode"),
        "season": ("season_view", "idShow")
    }

    return tablekeys.get(ptype, (None, None))

def getKodiInfo(puid, pmediatype, pmediaid):

    if not kodiDBRegistry.get_all_instances_pointer().get(puid, None):
        return {}

    kdb = kodiDBRegistry.get_all_instances_pointer().get(puid, None).get("dbname")


    returned_data = []

    try:
        db = sqlKodiDB(kdb)

        #table, idcol = getTableAndColumnFromMediatype(pmediatype)

        if pmediatype == "movie":
            for (tmdbid, oid, opath, ofilename, otitle) in db.fetch_same_uid_movies(pmediaid):
                returned_data.append({
                    "mediaType": pmediatype,
                    "mediaId": oid,
                    "movieTitle": otitle,
                    "virtualFilename": urllib.parse.unquote(ofilename),
                    "virtualPath": urllib.parse.unquote(opath).split("/virtual", 1)[1],
                    "tmdbId": tmdbid,
                })
        
        elif pmediatype == "season":
            for (tmdbid, otitle, oseason, opath, oid) in db.fetch_same_uid_seasons(pmediaid):
                returned_data.append({
                    "mediaType": pmediatype,
                    "mediaId": oid,
                    "movieTitle": otitle,
                    "season": oseason,
                    "virtualPath": urllib.parse.unquote(opath).split("/virtual", 1)[1],
                    "tmdbId": tmdbid,
                })
            

            
        else:
            return []

        return returned_data

    except ValueError as e:
        return []

    finally:
        if db is not None:
            db.close()


def full_nfo_refresh_call(kid, deltamode=False):

    kdb = kodiDBRegistry.get_all_instances_pointer().get(kid, None).get("dbname")

    if deltamode:
        kodiDBRegistry.get_all_dbs_pointer().get(kdb, {}).get("toDeltaNfoRefresh").set()
    else:
        kodiDBRegistry.get_all_dbs_pointer().get(kdb, {}).get("toFullNfoRefresh").set()



# update or insert
def set_kodi_instance(puid, pdbname, pkodi_ip, pkodi_version):

    if not kodiDBRegistry.update(puid, dbname=pdbname, kodi_ip=pkodi_ip, kodi_version = pkodi_version):
        kodiDBRegistry.add(puid, pdbname, pkodi_ip, pkodi_version)
        kodiDBRegistry.get_all_dbs_pointer().get(pdbname, {}).get("toNfoRefresh").set()
        kodiDBRegistry.get_all_dbs_pointer().get(pdbname, {}).get("toScan").set()

    return True


def get_kodi_instances_by_kodi_version(pkodi_version, puid):


    jginfo = {
        "pdays": get_premium_time_left(),
        "version": VERSION,
        "davport": WEBDAV_INTERNAL_PORT,
        "proxyurl": PROXY_URL,
        "port": KODI_MYSQL_CONFIG.get('port', 0),
        "user": KODI_MYSQL_CONFIG.get('user', "0"), 
        "pwd": KODI_MYSQL_CONFIG.get('password', "0")
    }

    for uid, entry in kodiDBRegistry.get_all_instances_pointer().items():
        if uid == puid and entry.get("kodi_version") == pkodi_version:

            return {
                "jginfo": jginfo,
                "avail_dbs": {
                    uid: entry
                }
            }


    available_instances = {
        uid: entry
        for uid, entry in kodiDBRegistry.get_all_instances_pointer().items()
        if entry.get("kodi_version") == pkodi_version
    }

    available_instances[puid] = {
        "dbname": f"{puid}_JGx_",
        "db_created_date": "New DB"
    }

    return {
        "jginfo": jginfo,
        "avail_dbs": available_instances
    }

'''
def set_nfo_done(puid, pid, ptable):


    sqlmatch = {
        "movie": "idMovie",
        "tvshow": "idShow",
        "episode": "idEpisode"
    }


    if thiskodi := kodiDBRegistry.get(puid):
        try:
            db = sqlKodiDB(thiskodi.get('dbname'))


        except ValueError as e:
            return False

        else:
            for (strPath,) in db.fetch_media_str_with_id(pid, ptable, sqlmatch.get(ptable)):
                # rename NFO to done TODO
                pass

        finally:
            db.close()
'''

def clean_all_consumed_nfo_batches():

    for bid in list(kodiDBRegistry.get_all_batches_pointer().keys()):
        if all(bid in instance.get("consumedBatches", []) for instance in kodiDBRegistry.get_all_instances_pointer().values()):
            kodiDBRegistry.remove_nfo_batch(bid)
    kodiDBRegistry.SaveNfoBatches()


# unused
def set_previous_batches_as_consumed(puid):
    if not kodiDBRegistry.get(puid):
        return

    # put existing nfobatches to consumed for this kodi instances:
    for batchid, batchdict in kodiDBRegistry.get_all_batches_pointer().items():
        if batchdict.get("done", False) == True:
            if puid not in kodiDBRegistry.get_all_instances_pointer().get(puid, {}).get("consumedBatches", []):
                kodiDBRegistry.get_all_instances_pointer().get(puid, {}).setdefault("consumedBatches", []).append(batchid)
    kodiDBRegistry._save()

    clean_all_consumed_nfo_batches()

    return


def kodi_marks_will_update(puid):

    if not (thiskodi := kodiDBRegistry.get(puid)):
        return

    try:
        db = sqlKodiDB(thiskodi.get('dbname'))
        db.register_dav_if_empty(f"{LAN_IP}:{WEBDAV_INTERNAL_PORT}")

        # check if uidtype = jellygrail still exists

    except ValueError as e:
        return

    finally:
        if db is not None:
            db.close()

    return

def reset_kodi_instances_refresh(service="toScan"):


    # the issue is scan masks the need to push nfo
    # so the solution would be to consume any DONE unconsumed batch before scan
    # this would only go through db existing items
    # unexisting db items can be set as consumed as they will be consumed naturally by scan
    '''
    if service=="toScan":
        for _, dbdict in kodiDBRegistry.get_all_dbs_pointer().items():
            dbdict["toNfoRefresh"].set()
    '''
    # above is not necessary (only on first scan)

    # warning, called by sync and async funcitons, dont' put blocking code here
    for _, dbdict in kodiDBRegistry.get_all_dbs_pointer().items():
        dbdict[service].set()


def get_kodidb_entry(pdbname):

    return kodiDBRegistry.get_all_dbs_pointer().get(pdbname, None)

def get_kodiid_entry(pid):

    return kodiDBRegistry.get_all_instances_pointer().get(pid, None)

def append_batch_to_kodi_instance(kid, batchid):

    '''
    if instance := kodiDBRegistry.get_all_instances_pointer().get(kid, None):
        if batchid not in instance.get("consumedBatches", []):
            instance.setdefault("consumedBatches", []).append(batchid)
            kodiDBRegistry._save()
            return True
    '''

    kdb = kodiDBRegistry.get_all_instances_pointer().get(kid, None).get("dbname")
        
    # get all kodi instances having same dbname and set there too
    for uid, instance in kodiDBRegistry.get_all_instances_pointer().items():
        if instance.get("dbname", "") == kdb:
            if batchid not in instance.get("consumedBatches", []):
                instance.setdefault("consumedBatches", []).append(batchid)
                logger.info(f"set batch {batchid} as consumed in kodi {uid}")
    kodiDBRegistry._save()
    # if a batch is consumed by all known kodi instances, remove it from batches registry
    clean_all_consumed_nfo_batches()
    return True

# ----------------------------------
# rd_progress Fill the pile chronologically each time it's called in server and new stuff arrives
# getrdincrement

def kodi_ui_refresh():
    fake_folder_path = 'dummy/path/just/to/refresh'

    # Create the JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.Scan",
        "params": {"directory": fake_folder_path},
        "id": "1"
    }

    # Send the request
    try:
        response = requests.post(kodi_url, data=json.dumps(payload), auth=(kodi_username, kodi_password))
        response.raise_for_status()

    except Exception as e:
        logger.warning(f"  KODI-API| UI Refresh failed (please verify Kodi services settings); error is: {e}")
        return False

    return True


def notify_kodi(title, message, display_time):

    notification_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "GUI.ShowNotification",
        "params": {
            "title": title,
            "message": message,
            "displaytime": display_time  # millisecondes
        },
        "id": "2"
    })

    try:
        notification_response = requests.post(
            kodi_url,
            headers=headers,
            data=notification_payload,
            auth=(kodi_username, kodi_password),
            timeout=5
        )
        notification_response.raise_for_status()
    except Exception as e:
        logger.warning(f"  KODI-API| Notification failed (please verify Kodi services settings); error is: {e}")
        return False

    return True


def delta_nfo_refresh_call(kid, kdb):
    return new_send_full_nfo_to_kodi(kid, kdb, deltamode=True)

def new_send_full_nfo_to_kodi(kid, kdb, deltamode=False):

    already_sent_ids = []

    payload = {}

    batchid = "FULL"

    #i = 0 #toremove

    try:
        dbo = sqlKodiDB(kdb)


        payload[batchid] = {
            "Movie": [],
            "TVShow": [],
            "Episode": []
        }


        for root, _, files in os.walk(JFSQ_STORED_NFO):
            #if i > 50: #toremove
            #    break #toremove
            for filename in files:
            #    i += 1 #toremove
            #    if i > 50: #toremove
            #        break #toremove
                tofetch = os.path.basename(root)
                if filename.lower().endswith(('.nfo.jf',)):
                    # very small chance that a movie or episode contains those strings but theorically we should test substring with endswith()
                    if "video_ts.nfo.jf" in filename.lower() or "index.nfo.jf" in filename.lower(): 
                        tofetch = os.path.basename(os.path.dirname(root))
                        tabletofetch = "movie_view"
                        idtofetch = "idMovie"
                        reftype = "Movie"
                        #typeid = "movieid"
                    elif "tvshow.nfo.jf" in filename.lower():
                        tabletofetch = "tvshow_view"
                        idtofetch = "idShow"
                        reftype = "TVShow"
                        #typeid = "tvshowid"
                    elif "/shows" == root[JFSQ_STORED_NFO_SHIFT:JFSQ_STORED_NFO_SHIFT+6]:
                        tabletofetch = "episode_view"
                        idtofetch = "idEpisode"
                        reftype = "Episode"
                        #typeid = "episodeid"
                        # put full path without like ?
                    else:
                        idtofetch = "idMovie"
                        tabletofetch = "movie_view"
                        reftype = "Movie"
                        #typeid = "movieid"

                    tofetch = urllib.parse.quote(tofetch, safe=SAFE)
                    tofetch = tofetch.replace("%", r"\%")

                    #logger.info(f". Kodi mysqldb fetching : {root}/{filename} as {tofetch} IN TABLE {tabletofetch}")

                    for (result, uidtype) in dbo.fetch_media_id(tofetch, tabletofetch, idtofetch):

                        if result not in already_sent_ids and (uidtype == 'jellygrail' or deltamode == False):
                            already_sent_ids.append(result)
                            payload[batchid][reftype].append(result)

        if already_sent_ids:
            return payload
        else:
            return {}


    except ValueError as e:
        return {}

    finally:
        if dbo is not None:
            dbo.close()


def new_send_nfo_to_kodi(kid, kdb):

    if not (batchesToDo := [key for key,_ in kodiDBRegistry.get_all_batches_pointer().items() if key not in kodiDBRegistry.get_all_instances_pointer().get(kid, {}).get("consumedBatches", [])]):
        return {}



    already_sent_ids = []
    already_seen_paths = []

    payload = {}

    try:
        dbo = sqlKodiDB(kdb)


        for batchid in batchesToDo:

            if kodiDBRegistry.get_all_batches_pointer().get(batchid, {}).get("done", True) == False:
                continue


            if nfo_entries := kodiDBRegistry.get_all_batches_pointer().get(batchid, {}).get("items", []):
                

                payload[batchid] = {
                    "Movie": [],
                    "TVShow": [],
                    "Episode": []
                }

                for path in nfo_entries:

                    if path not in already_seen_paths:
                        already_seen_paths.append(path)
                    else:
                        continue

                    root = os.path.dirname(path)
                    tofetch = os.path.basename(root)
                    filename = os.path.basename(path)
                    if filename.lower().endswith(('.nfo.jf',)):
                        # very small chance that a movie or episode contains those strings but theorically we should test substring with endswith()
                        if "video_ts.nfo.jf" in filename.lower() or "index.nfo.jf" in filename.lower(): 
                            tofetch = os.path.basename(os.path.dirname(root))
                            tabletofetch = "movie_view"
                            idtofetch = "idMovie"
                            reftype = "Movie"
                            #typeid = "movieid"
                        elif "tvshow.nfo.jf" in filename.lower():
                            tabletofetch = "tvshow_view"
                            idtofetch = "idShow"
                            reftype = "TVShow"
                            #typeid = "tvshowid"
                        elif "/shows" == root[JFSQ_STORED_NFO_SHIFT:JFSQ_STORED_NFO_SHIFT+6]:
                            tabletofetch = "episode_view"
                            idtofetch = "idEpisode"
                            reftype = "Episode"
                            #typeid = "episodeid"
                            # put full path without like ?
                        else:
                            idtofetch = "idMovie"
                            tabletofetch = "movie_view"
                            reftype = "Movie"
                            #typeid = "movieid"

                        tofetch = urllib.parse.quote(tofetch, safe=SAFE)
                        tofetch = tofetch.replace("%", r"\%")

                        #logger.info(f". Kodi mysqldb fetching : {root}/{filename} as {tofetch} IN TABLE {tabletofetch}")

                        for (result, uidtype) in dbo.fetch_media_id(tofetch, tabletofetch, idtofetch):

                            if result not in already_sent_ids:
                                already_sent_ids.append(result)
                                payload[batchid][reftype].append(result)


        return payload


    except ValueError as e:
        return {}

    finally:
        if dbo is not None:
            dbo.close()





def new_merge_tvshow_seasons(dbo):

    atleastone = False
    # separated_seasons() to get all (tvshowids) for one unqueid
    for (idshowsR, _) in dbo.separated_seasons():
        atleastone = True
        #treat one show
        idshows = [int(num) for num in idshowsR.split(",")]
        showtokeep = idshows[0]
        dbo.link_all_shows_to_keptone(idshowsR, showtokeep)
        # set showtokeep on every idshowfound

        for idshow in idshows:
            if idshow != showtokeep:
                dbo.delete_other_showid(idshow)

    if atleastone:
        return True

    return False

def new_merge_kodi_versions(kdb, kver):
    returning = False
    try:
        dbro = kodiDBRegistry.get_all_dbs_pointer().get(kdb, {})

        dbo = sqlKodiDB(kdb)
        
        # fix tvshows merging
        if new_merge_tvshow_seasons(dbo):
            returning = True
 
        if kver < 21:
            logger.info("         6| Custom Kodi MySQL dB Operations bypassed (Kodi version < 21)")
            return returning

        returned_max_played = dbo.return_last_played_max()
        returned_max_fileid = dbo.return_last_file_id_max()

        if not (( returned_max_played and returned_max_played != dbro["last_max_lastplayed"]) or ( returned_max_fileid and returned_max_fileid != dbro["last_max_fileid"])):
            # do nothing if nothing changed
            logger.info("         6| Custom Kodi MySQL dB Operations bypassed")
            return returning
        



        logger.info("         6| Custom Kodi MySQL dB Operations...")

        #bypass kodi alive.
        for (_, idmediasR, strpathsR, strfilenamesR, idfilesR, isdefaultsR, bmk_stuff) in dbo.video_versions():
            #find the incr smallest version
            i=0
            currlowest=200
            idfiles = [int(num) for num in idfilesR.split(",")]
            strpaths = strpathsR.split(" ")
            strfilenames = strfilenamesR.split(" ")
            isdefaults = [int(num) for num in isdefaultsR.split(" ")]
            idmedias = [int(num) for num in idmediasR.split(" ")]
            #bmk_stuff / new manage resumtimes
            bmk_str_last = bmk_stuff.split(",")[0]
            # no need to propagate if nothing is found ? : drawback : if file having lp data is deleted before next propagation, its data wont ever be propagated
            if returned_max_played and returned_max_played != dbro["last_max_lastplayed"]: # dont do if unnecessary
                if bmk_str_last != "0#0#0":
                    bmk_arr_last = bmk_str_last.split("#")
                    if len(bmk_arr_last) > 2: # some fail-proof check
                        highest_lp = bmk_arr_last[0]
                        highest_rt = float(bmk_arr_last[1])
                        highest_tt = float(bmk_arr_last[2])
                        dbo.new_set_resume_times_and_lastplayed(highest_rt, highest_lp, idfilesR, idfiles, highest_tt)
            #bmk_stuffend
            if returned_max_fileid and returned_max_fileid != dbro["last_max_fileid"]: # dont do if unnecessary
                videoversiontuple = []
                idtokeep = None
                strpathtokeep = None
                imediatokeep = None
                fallback_id = None
                fallback_path = None

                if idfiles and strpaths and idmedias:
                    # just looping through sthing of all arrays
                    for strfilename in strfilenames:
                        decoded_filename = urllib.parse.unquote(strfilename)
                        match = re.search(r'-\s*(.*?)\s*JGx', decoded_filename)
                        if match:
                            extracted_text = match.group(1)

                            Lmatches = extract_triplets(extracted_text)
                            nLmatches = [m.lower() for m in Lmatches]

                            videoversiontuple.append((idfiles[i], extracted_text))
                            matchb = re.search(r'(\d+)Mbps', extracted_text)
                            if matchb:
                                mbps_value = int(matchb.group(1))
                                if mbps_value < currlowest:
                                    fallback_id = idfiles[i]
                                    fallback_path = strpaths[i]
                                    currlowest = mbps_value

                                    if USED_LANGS_JF[0].lower() in nLmatches:
                                        idtokeep = idfiles[i]
                                        strpathtokeep = strpaths[i]
                        else:
                            videoversiontuple.append((idfiles[i], "Iso Edition"))
                        if imediatokeep == None and isdefaults[i] == 1:
                            imediatokeep = idmedias[i]
                        i += 1
                    # if did not find any way to find the lowest value, we keep the first ones, will be set to the kept media
                    if idtokeep == None and fallback_id != None:
                        idtokeep = fallback_id
                        strpathtokeep = fallback_path
                    elif idtokeep == None:
                        idtokeep = idfiles[0]
                        strpathtokeep = strpaths[0]
                    if imediatokeep != None:
                        # proceed to link videoverion to the kept mediaid
                        for idfile, versionlabel in videoversiontuple:
                            # check if extracted text exists in db
                            if new_id := dbo.check_if_vvtype_exists(versionlabel):
                                pass
                            else:
                                new_id = dbo.insert_new_vvtype(versionlabel)
                            if new_id != None:
                                dbo.link_vv_to_kept_mediaid(idfile, imediatokeep, new_id)
                            else:
                                logger.error("new_id is none, thos should not happen")
                        # proceed to set idfile and strpath to the mediaid we keep
                        dbo.define_kept_mediaid(idtokeep, strpathtokeep, imediatokeep)
                        # proceed to delete other mediaids
                        for idmedia in idmedias:
                            if idmedia != imediatokeep:
                                dbo.delete_other_mediaid(idmedia)
        dbro["last_max_lastplayed"] = returned_max_played
        dbro["last_max_fileid"] = returned_max_fileid
        

        # sets collection images
        for (idset, strset, _) in dbo.get_undefined_collection_arts():
            dbo.insert_collection_art(idset, "http://"+WEBDAV_HOST_PORT+"/pics/collections/"+urllib.parse.quote(strset, safe=SAFE)+".jpg")


        # else of kodi version < 21 or last_* check
        return True
    
    #except ValueError as e:
        #logger.info("         6| Value error...")
        #return False
    
    finally:
        if dbo is not None:
            dbo.close()


def fix_bad_merges():

    # toimprove look for currently merged items in kodi db (path and filename). 
    # look for their nfo.jf.updated / nfo.jf.done / nfo.jf loaded in xml 
    # if their tmdb id is different -> remove the videoversion linked to the failed id and then trigger fix_kodi_glitches (because both issues can exist at the same time) and it will trigger a new scan anyway


    return

def fix_kodi_glitches():

    # toimprove look for release folders being mediatype _bdmv, if they're *not empty* and not in kodi db, change the last_updated date to current unix timestamp

    # and trigger refresh
    return
