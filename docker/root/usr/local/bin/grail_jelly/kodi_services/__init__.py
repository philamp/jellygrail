from base import *
from base.littles import *
from base.constants import *
from kodi_services.sqlkodi import fetch_media_id, video_versions, link_vv_to_kept_mediaid,define_kept_mediaid, delete_other_mediaid, kodi_mysql_init_and_verify, check_if_vvtype_exists, insert_new_vvtype, mariadb_close, get_undefined_collection_arts, insert_collection_art, new_set_resume_times_and_lastplayed, return_last_played_max, return_last_file_id_max
import requests
import urllib.parse
import websocket
import threading
from datetime import datetime

KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

NGINX_HOST = os.getenv('WEBDAV_LAN_HOST')

kodi_url = f"http://{KODI_MAIN_URL}:8080/jsonrpc"
kodi_ws_url = f"ws://{KODI_MAIN_URL}:9090/jsonrpc"
kodi_username = "kodi"  
kodi_password = "kodi"

last_clean = 0

last_max_lastplayed = ""
last_max_fileid = 0

headers = {
    'Content-Type': 'application/json',
}

is_scanning = False
is_cleaning = False
refresh_is_safe = False

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


def is_kodi_alive():
    payload = {
        "jsonrpc": "2.0",
        "method": "JSONRPC.Ping",
        "id": 1
    }

    try:
        response = requests.post(kodi_url, json=payload, headers=headers, timeout=10)

        logger.debug(f"kodi responded with {response.status_code}")

        if response.status_code == 401:
            logger.debug("Kodi is alive and responsive")
            return True
        else:
            logger.debug("Kodi responded, but the result was unexpected")
            return False
    except requests.exceptions.RequestException as e:
        logger.debug(f"Failed to connect to Kodi: {e}")
        return False

def on_message(ws, message):
    global is_scanning
    global is_cleaning
    data = json.loads(message)

    # Look for the scan start and finish events
    if "method" in data:
        if data["method"] == "VideoLibrary.OnScanFinished":
            is_scanning = False
        if data["method"] == "VideoLibrary.OnCleanFinished":
            is_cleaning = False

def on_error(ws, error):
    global is_scanning
    global refresh_is_safe
    logger.error(f"  KODI-API| Please enable 'Allow remote control from applications on other systems' via Kodi UI in Settings/Services/Control; WebSocket error is: {error}")
    refresh_is_safe = False

def on_close(ws, close_status_code, close_msg):
    logger.debug(". WebSocket connection closed. [kodi_services]")

def on_open(ws):
    global refresh_is_safe
    #logger.info("  KODI-API| Waiting for Kodi to finish jobs via websocket trigger...")
    refresh_is_safe = True


def refresh_kodi():

    if not is_kodi_alive() or not kodi_mysql_init_and_verify(just_verify=True):
        return False

    global is_scanning
    global is_cleaning
    global last_clean
    global refresh_is_safe
    refresh_is_safe = False
    is_scanning = True
    is_cleaning = True # even if not started right away, it does not change anything to declare its running here

    ws = websocket.WebSocketApp(kodi_ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_open=on_open,
                                on_close=on_close)

    # Run the WebSocket in a separate thread to allow for graceful shutdown
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()



    logger.debug(f"kodi url is: {KODI_MAIN_URL}")

    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "VideoLibrary.Scan",
        "id": "1"
    })

    clean_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "VideoLibrary.Clean",
        "params": {
            "showdialogs": False
        },
        "id": "1"
    })

    waitloop = 0
    while refresh_is_safe == False and waitloop < 5:
        waitloop += 1
        time.sleep(1)

    if waitloop > 5:
        logger.error("    MANUAL| Kodi websocket (port 9090) not available, either offline suddenly or try enable 'Allow remote control from applications on other systems' in Kodi/Settings/Services/Control and then restart JellyGrail. JellyGrail can't work properly without websocket API")
        return False # consider jellygrail can't work properly without websocket
        
    try:
        response = requests.post(
            kodi_url,
            headers=headers,
            data=payload,
            auth=(kodi_username, kodi_password),
            timeout=15
        )

    except Exception as e:
        logger.error(f"!! Kodi refreshing trigger failed with {e} [refresh_kodi]")
        ws.close()
        return False
    else:
        if response.status_code == 200:
            started_at = time.time()
            #logger.info("TASK-START~ Kodi Library refresh...")

            notify_kodi("JG Refresh", "Started...", 3000)
            
        else:
            logger.error(f"Error on kodi lib refresh with http response code: {response.status_code}")
    #ik = 0
    while True:
        #ik += 1
        # if hanging since 2 hours, declare it's done ?
        if is_scanning == False:
            logger.info("  KODI-API| ...Kodi Library refreshed, will now try cleaning if necessary...")
            notify_kodi("JG Refresh", "...completed.", 3000)
            break
        if (time.time() - started_at) > 3600:
            logger.warning("  KODI-API| ...Kodi Library refreshed (more than 1 hour)")
            notify_kodi("JG Refresh", "...considered completed (> 1 hour !)", 3000)
            break
        if not refresh_is_safe or not is_kodi_alive():
            logger.warning("  KODI-API| ...Kodi Library refreshed (halted as WS interrupted)")
            notify_kodi("JG Refresh", "...considered completed (halted as WS interrupted)", 3000)
            ws.close()
            return False
            #break
        #logger.info(f"refresh wait loop iter {ik}")
        time.sleep(2)

    # toimprove : the code can be easilly factorized

    
    # clean once to twice max per day
    if (time.time() - last_clean) > 12*3600:
        
        try:
            response = requests.post(
                kodi_url,
                headers=headers,
                data=clean_payload,
                auth=(kodi_username, kodi_password),
                timeout=1500
            )

        except Exception as e:
            logger.warning(f"!! Kodi cleaning maybe triggered but there is this error: {e} [refresh_kodi]")
            ws.close()
            return True
        else:
            if response.status_code == 200:
                started_at = time.time()
                last_clean = time.time()
                #logger.info("TASK-START~ Kodi Library cleaning...")

                notify_kodi("JG Cleaning", "Started...", 3000)
                
            else:
                logger.error(f"! Error on kodi lib refresh with http response code: {response.status_code}")
        
        while True:
            
            # if hanging since 1 hour, declare it's done
            if is_cleaning == False:
                logger.info("  KODI-API| ...Kodi Library cleaned")
                notify_kodi("JG Cleaning", "...completed", 3000)
                break
            if (time.time() - started_at) > 3600:
                logger.warning("  KODI-API| ...Kodi Library cleaned (more than 1hour)")
                notify_kodi("JG Cleaning", "...considered completed (> 1 hour !)", 3000)
                break
            if not refresh_is_safe or not is_kodi_alive():
                logger.warning("  KODI-API| ...Kodi Library cleaned (halted as WS interrupted)")
                notify_kodi("JG Cleaning", "...considered completed (halted as WS interrupted)", 3000)
                ws.close()
                return False
                #break
            
            time.sleep(2)
    else:
        notify_kodi("JG Cleaning", "Bypassed: already done in last 12h", 3000)
        logger.info("  KODI-API| Kodi Library cleaning bypassed")


    ws.close()
    return True

def send_nfo_to_kodi():


    if not is_kodi_alive() or not kodi_mysql_init_and_verify():
        return False
    
    files_to_rename = []

    already_sent_ids = []

    # browse nfos
    previous_root = ""
    potential_nfo_to_send = 0
    xiem = 0

    for root, _, files in os.walk(JFSQ_STORED_NFO):
        for filename in files:
            if filename.lower().endswith(('.nfo.jf', '.nfo.jf.updated')):
                potential_nfo_to_send += 1
                
    if potential_nfo_to_send == 0:
        #notify_kodi("JG NFO refresh", f"No new iNFO to send", 3000)
        logger.info("  KODI-API| ...no new NFO to send")
        pass
    else:
        notify_kodi("JG Metadata refresh", f"Sending {potential_nfo_to_send} metadatas...", 3000)


    for root, _, files in os.walk(JFSQ_STORED_NFO):

        #nfo refresh is on parent folder basis (root)
        updated = False

        for filename in files: # if one nfo is updated among its siblings within same root, all are considered "updated"
            if filename.lower().endswith('.nfo.jf.updated'):
                updated = True

        for filename in files:
            tofetch = os.path.basename(root)
            if filename.lower().endswith(('.nfo.jf', '.nfo.jf.updated')):
                xiem += 1
                if root == previous_root: #nfo refresh is on parent folder basis (root), so no need to trigger upon next nfo files found in same folder
                    files_to_rename.append(root + "/" + filename)
                    continue
                previous_root = root
                # very small chance that a movie or episode contains those strings but theorically we should test substring with endswith()
                if "video_ts.nfo.jf" in filename.lower() or "index.nfo.jf" in filename.lower(): 
                    tofetch = os.path.basename(os.path.dirname(root))
                    tabletofetch = "movie_view"
                    idtofetch = "idMovie"
                    reftype = "Movie"
                    typeid = "movieid"
                elif "tvshow.nfo.jf" in filename.lower():
                    tabletofetch = "tvshow_view"
                    idtofetch = "idShow"
                    reftype = "TVShow"
                    typeid = "tvshowid"
                elif "/shows" == root[JFSQ_STORED_NFO_SHIFT:JFSQ_STORED_NFO_SHIFT+6]:
                    tabletofetch = "episode_view"
                    idtofetch = "idEpisode"
                    reftype = "Episode"
                    typeid = "episodeid"
                    # put full path without like ?
                else:
                    idtofetch = "idMovie"
                    tabletofetch = "movie_view"
                    reftype = "Movie"
                    typeid = "movieid"

                tofetch = urllib.parse.quote(tofetch, safe=SAFE)
                tofetch = tofetch.replace("%", r"\%")
                #debug toremove DEBU
                #logger.info(f"DEBU fetching media: {tofetch} IN TABLE {tabletofetch}")
                logger.debug(f". Kodi mysqldb fetching : {root}/{filename}")
                if results := [(line[0],line[1]) for line in fetch_media_id(tofetch, tabletofetch, idtofetch)]:
                    #toimprove, redundant unpacking here
                    for (result, uidtype) in results:
                        #logger.info(f"DEBU found mediaid: {result}")
                        # todo : have the possibility to refresh every single NFO discarding criterias below 
                        if result not in already_sent_ids and (uidtype == 'jellygrail' or updated == True):
                            
                            #logger.info(f"{xiem} / {potential_nfo_to_send} metadatas sent")
                            #logger.info(f"ID: result ; uid type: {uidtype}")
                            time.sleep(1)
                            refresh_payload = json.dumps({
                                "jsonrpc": "2.0",
                                "method": f"VideoLibrary.Refresh{reftype}",
                                "params": {
                                    f"{typeid}": result
                                },
                                "id": "1"
                            })

                            try:
                                response = requests.post(
                                    kodi_url,
                                    headers=headers,
                                    data=refresh_payload,
                                    auth=(kodi_username, kodi_password),
                                    timeout=15
                                )

                            except Exception as e:
                                logger.error(f"  KODI-API| Nfo refresh failed [refresh_kodi], error is : {e}")
                                mariadb_close()
                                return False
                            else:
                                if response.status_code == 200:
                                    logger.debug(f"{xiem} / {potential_nfo_to_send} metadatas sent")
                                    notify_kodi("JG Metadata refresh", f"{xiem} / {potential_nfo_to_send} metadatas sent", 3000)
                                    already_sent_ids.append(result)

                                    #rename_to_done(root + "/" + filename)
                                    files_to_rename.append(root + "/" + filename)
                                else:
                                    logger.error(f"  KODI-API| not http200 returned on kodi nfo refresh, http returned code is: {response.status_code}")
                                    mariadb_close()
                                    return False
                        else:
                            #rename_to_done(root + "/" + filename) # - case where nfo was already taken through another way than nfo refresher
                            files_to_rename.append(root + "/" + filename)

                else:
                    files_to_rename.append(root + "/" + filename) # renaming to done does not prevent kodi to find them later if finally available
                    logger.warning(f"! {tofetch} has no kodi db correspondance (corresponding video file maybe deleted or Kodi hasn't scanned this item yet)") #toimprove : bindfs should also delete the corresponding nfo files when main file deleted
                

        # find corresponding video path (maping between kodi and filesystem)

    files_to_rename = list(set(files_to_rename))
    for file_to_mv in files_to_rename:
        rename_to_done(file_to_mv)

    if(potential_nfo_to_send > 1):
        notify_kodi("JG Metadata refresh", f"...completed.", 3000)

    mariadb_close()
    return True

def rename_to_done(filepath):
    # as we are on linux, we can then rename the file even if it's being accessed by another process
    # rename to .done will ensure that this file won't be sent to kodi again
    try:
        if os.path.exists(filepath):
            if filepath.endswith('.updated'):
                new_name = filepath[:-8] + '.done'
            else:
                new_name = filepath+".done"
            os.rename(filepath, new_name)
        else:
            logger.critical(f"!!! file (to rename to .done) does not exist (theorically impossible) [send_nfo_to_kodi]")
    except Exception as e:
        logger.debug(f"!! An error occured on renaming .nfo.jf to .nfo.jf.done : {e}")

def merge_kodi_versions():
    global last_max_lastplayed
    global last_max_fileid
    # merge only when needed, since the regular trigger of jf_nfo_refresh (step 4), bypass this step if there is no new nfo, it's not a an issue
    if not kodi_mysql_init_and_verify():
        return False

    #results = [(row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[7]) for row in video_versions()]

    returned_max_played = return_last_played_max()
    returned_max_fileid = return_last_file_id_max()

    #logger.info(f"{returned_max_played}")
    #logger.info(f"{returned_max_fileid}")


    if not (( returned_max_played and returned_max_played != last_max_lastplayed) or ( returned_max_fileid and returned_max_fileid != last_max_fileid)):
        # do nothing if nothing changed
        #notify_kodi("JG Custom SQL ops", f"Bypassed.", 3000)
        logger.info("  SQL-KODI| ...custom ops fully bypassed")
        return True

    if is_kodi_alive():
        notify_kodi("JG Custom SQL ops", "Started...", 3000)

    for (_, idmediasR, strpathsR, strfilenamesR, idfilesR, isdefaultsR, bmk_stuff) in video_versions(): #results: 
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
        if returned_max_played and returned_max_played != last_max_lastplayed: # dont do if unnecessary
            if bmk_str_last != "0#0#0":
                bmk_arr_last = bmk_str_last.split("#")
                if len(bmk_arr_last) > 2: # some fail-proof check
                    highest_lp = bmk_arr_last[0]
                    highest_rt = float(bmk_arr_last[1])
                    highest_tt = float(bmk_arr_last[2])
                    new_set_resume_times_and_lastplayed(highest_rt, highest_lp, idfilesR, idfiles, highest_tt)
                    


        #bmk_stuffend

        if returned_max_fileid and returned_max_fileid != last_max_fileid: # dont do if unnecessary

            videoversiontuple = []
            idtokeep = None
            strpathtokeep = None
            imediatokeep = None

            if idfiles and strpaths and idmedias:
                # just looping through sthing of all arrays
                for strfilename in strfilenames:
                    decoded_filename = urllib.parse.unquote(strfilename)
                    match = re.search(r'-\s*(.*?)\s*JGx', decoded_filename)
                    if match:
                        extracted_text = match.group(1)
                        videoversiontuple.append((idfiles[i], extracted_text))
                        matchb = re.search(r'(\d+)Mbps', extracted_text)
                        if matchb:
                            mbps_value = int(matchb.group(1))
                            if mbps_value < currlowest:
                                currlowest = mbps_value
                                idtokeep = idfiles[i]
                                strpathtokeep = strpaths[i]
                    else:
                        videoversiontuple.append((idfiles[i], "Iso Edition"))

                    if imediatokeep == None and isdefaults[i] == 1:
                        imediatokeep = idmedias[i]
            
                    i += 1


                # if did not find any way to find the lowest value, we keep the first ones, will be set to the kept media
                if idtokeep == None:
                    idtokeep = idfiles[0]
                    strpathtokeep = strpaths[0]


                if imediatokeep != None:
                    # proceed to link videoverion to the kept mediaid
                    for idfile, versionlabel in videoversiontuple:
                        # check if extracted text exists in db
                        if new_id := check_if_vvtype_exists(versionlabel):
                            pass
                        else:
                            new_id = insert_new_vvtype(versionlabel)

                        if new_id != None:
                            link_vv_to_kept_mediaid(idfile, imediatokeep, new_id)
                        else:
                            logger.error("new_id is none, thos should not happen")

                    # proceed to set idfile and strpath to the mediaid we keep
                    define_kept_mediaid(idtokeep, strpathtokeep, imediatokeep)

                    # proceed to delete all mediaid but the one we keep
                    for idmedia in idmedias:
                        if idmedia != imediatokeep:
                            delete_other_mediaid(idmedia)
                else:
                    logger.error("imediatokeep is none, this should not happen")
            else:
                logger.error("vv main request gone wrong, this should not happen")

            
    last_max_lastplayed = returned_max_played
    last_max_fileid = returned_max_fileid

    # sets collection images
    for (idset, strset, _) in get_undefined_collection_arts():
        insert_collection_art(idset, "http://"+NGINX_HOST+"/pics/collections/"+urllib.parse.quote(strset, safe=SAFE)+".jpg")
        

    # refresh kodi UI
    if is_kodi_alive():
        kodi_ui_refresh()
        notify_kodi("JG Custom SQL ops", "...completed.", 3000)
    
    logger.info("  SQL-KODI| ...custom ops completed")
        
    mariadb_close()
    return True


def fix_bad_merges():

    # toimprove look for currently merged items in kodi db (path and filename). 
    # look for their nfo.jf.updated / nfo.jf.done / nfo.jf loaded in xml 
    # if their tmdb id is different -> remove the videoversion linked to the failed id and then trigger fix_kodi_glitches (because both issues can exist at the same time) and it will trigger a new scan anyway


    return

def fix_kodi_glitches():

    # toimprove look for release folders being mediatype _bdmv, if they're *not empty* and not in kodi db, change the last_updated date to current unix timestamp

    # and trigger refresh
    return
