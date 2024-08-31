from base import *
from base.littles import *
from base.constants import *
from kodi_services.sqlkodi import fetch_media_id, video_versions, link_vv_to_kept_mediaid,define_kept_mediaid, delete_other_mediaid, kodi_mysql_init_and_verify, check_if_vvtype_exists, insert_new_vvtype
import requests
import urllib.parse
import websocket
import threading


KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

kodi_url = f"http://{KODI_MAIN_URL}:8080/jsonrpc"
kodi_ws_url = f"ws://kodi:kodi@{KODI_MAIN_URL}:9090/jsonrpc"
kodi_username = "kodi"  
kodi_password = "kodi"

headers = {
    'Content-Type': 'application/json',
}

is_scanning = False

def is_kodi_alive():
    payload = {
        "jsonrpc": "2.0",
        "method": "JSONRPC.Ping",
        "id": 1
    }

    try:
        response = requests.post(kodi_url, json=payload, headers=headers)

        logger.debug(f"kodi responded with {response.status_code}")

        if response.status_code == 401:
            logger.debug("Kodi is alive and responsive.")
            return True
        else:
            logger.debug("Kodi responded, but the result was unexpected.")
            return False
    except requests.exceptions.RequestException as e:
        logger.debug(f"Failed to connect to Kodi: {e}")
        return False

def on_message(ws, message):
    global is_scanning
    data = json.loads(message)

    # Look for the scan start and finish events
    if "method" in data:
        if data["method"] == "VideoLibrary.OnScanFinished":
            is_scanning = False

def on_error(ws, error):
    global is_scanning
    logger.error(f"!! WebSocket error: {error}, please enable 'Allow remote control from applications on other systems' via Kodi UI in Settings/Services/Control [kodi_services]")
    is_scanning = False #Assume scanning is finished but then TODO : send NFO later if websocket can't work

def on_close(ws, close_status_code, close_msg):
    logger.debug(". WebSocket connection closed. [kodi_services]")

def on_open(ws):
    logger.info("~ WebSocket waiting for Kodi scan to be finished [kodi_services] ~")


def refresh_kodi():

    if not is_kodi_alive():
        return False

    global is_scanning
    is_scanning = True

    ws = websocket.WebSocketApp(kodi_ws_url,
                                on_message=on_message,
                                on_error=on_error,
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

    notification_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "GUI.ShowNotification",
        "params": {
            "title": "JG library refresh",
            "message": "Kodi library refresh triggered by Jellygrail",
            "displaytime": 3000  # Temps d'affichage en millisecondes (ici 5 secondes)
        },
        "id": "2"
    })

    try:
        response = requests.post(
            kodi_url,
            headers=headers,
            data=payload,
            auth=(kodi_username, kodi_password),
            timeout=5
        )

    except Exception as e:
        logger.error("!! Kodi refreshing trigger failed [refresh_kodi]")
        return False
    else:
        if response.status_code == 200:
            logger.debug("~ Kodi lib refreshing... [refresh_kodi]")
            
        else:
            logger.warning(f"! Error on kodi lib refresh: {response.status_code}")

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
        logger.debug(f"!! Kodi message failed with: {e}")
        return False
    
    while True:
        if is_scanning == False or not is_kodi_alive():
            logger.info("~> Kodi Library scan has finished <~")
            break
        time.sleep(2)
    
    ws.close()
    return True

def send_nfo_to_kodi():


    if not is_kodi_alive() or not kodi_mysql_init_and_verify():
        return False
    
    '''
    start_notification_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "GUI.ShowNotification",
        "params": {
            "title": "JG NFO refresh",
            "message": "Kodi metadata refresh from NFOs triggered by Jellygrail",
            "displaytime": 3000  # Temps d'affichage en millisecondes (ici 5 secondes)
        },
        "id": "2"
    })

    finish_notification_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "GUI.ShowNotification",
        "params": {
            "title": "JG NFO refresh COMPLETED",
            "message": "Kodi metadata refresh from NFOs has COMPLETED",
            "displaytime": 3000  # Temps d'affichage en millisecondes (ici 5 secondes)
        },
        "id": "2"
    })

    try:
        notification_response = requests.post(
            kodi_url,
            headers=headers,
            data=start_notification_payload,
            auth=(kodi_username, kodi_password),
            timeout=5
        )
        notification_response.raise_for_status()
    except Exception as e:
        logger.debug(f"!! Kodi message failed with: {e}")
        return False
    '''
    
    files_to_rename = []

    # browse nfos
    previous_root = ""
    for root, _, files in os.walk(JFSQ_STORED_NFO):

        #nfo refresh is on parent folder basis (root), if there is at least one nfo with ".updated" in this folder it will refresh all neigboors in same folder
        updated = False
        for filename in files:
            if filename.lower().endswith('.nfo.jf.updated'):
                updated = True

        for filename in files:
            tofetch = os.path.basename(root)
            if filename.lower().endswith(('.nfo.jf', '.nfo.jf.updated')):
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
                logger.debug(f". Kodi mysqldb fetching : {root}/{filename}")
                if results := [(line[0],line[1]) for line in fetch_media_id(tofetch, tabletofetch, idtofetch)]:
                    for (result, uidtype) in results:
                        if uidtype == 'jellygrail' or updated == True:
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
                                    timeout=5
                                )

                            except Exception as e:
                                logger.error("!! Nfo refresh failed [refresh_kodi]")
                                return False
                            else:
                                if response.status_code == 200:
                                    logger.debug(f"> Nfo refresh ok on id item {result} [refresh_kodi]")

                                    #rename_to_done(root + "/" + filename)
                                    files_to_rename.append(root + "/" + filename)
                                else:
                                    logger.warning(f"! Error on kodi nfo refresh: {response.status_code}")
                                    return False
                        else:
                            #rename_to_done(root + "/" + filename) # - case where nfo was already taken through another way than nfo refresher
                            files_to_rename.append(root + "/" + filename)

                else:
                    logger.warning(f"! {tofetch} has no kodi db correspondance (corresponding video file maybe deleted or Kodi hasn't scanned this item yet)") #todo : bindfs should also delete the corresponding nfo files when main file deleted
                

        # find corresponding video path (maping between kodi and filesystem)

    files_to_rename = list(set(files_to_rename))
    for file_to_mv in files_to_rename:
        rename_to_done(file_to_mv)

    '''
    try:
        notification_response = requests.post(
            kodi_url,
            headers=headers,
            data=finish_notification_payload,
            auth=(kodi_username, kodi_password),
            timeout=5
        )
        notification_response.raise_for_status()
    except Exception as e:
        logger.debug(f"!! Kodi message failed with: {e}")
        return False
    '''

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
    # todo , merge only when needed, in the meantime, the step4 periodic trigger is set to higher value to avoid to many sql queries for nothing
    if not kodi_mysql_init_and_verify:
        return False

    results = [(row[0],row[1],row[2],row[3],row[4],row[5]) for row in video_versions()]

    for (_, idmediasR, strpathsR, strfilenamesR, idfilesR, isdefaultsR) in results:
        #find the incr smallest version
        i=0
        currlowest=200
        idfiles = [int(num) for num in idfilesR.split("¨")]
        strpaths = strpathsR.split("¨")
        strfilenames = strfilenamesR.split("¨")
        isdefaults = [int(num) for num in isdefaultsR.split("¨")]
        idmedias = [int(num) for num in idmediasR.split("¨")]
        videoversiontuple = []
        idtokeep = None
        strpathtokeep = None
        imediatokeep = None
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
                link_vv_to_kept_mediaid(idfile, imediatokeep, new_id)

            # proceed to set idfile and strpath to the mediaid we keep
            define_kept_mediaid(idtokeep, strpathtokeep, imediatokeep)

            # proceed to delete all mediaid but the one we keep
            for idmedia in idmedias:
                if idmedia != imediatokeep:
                    delete_other_mediaid(idmedia)

        

    return True



def fix_bad_merges():

    # todo look for currently merged items in kodi db (path and filename). 
    # look for their nfo.jf.updated / nfo.jf.done / nfo.jf loaded in xml 
    # if their tmdb id is different -> remove the videoversion linked to the failed id and then trigger fix_kodi_glitches (because both issues can exist at the same time) and it will trigger a new scan


    return

def fix_kodi_glitches():

    # todo look for release folders being mediatype _bdmv, if they're not in kodi db, change the last_updated date to current unix timestamp


    return