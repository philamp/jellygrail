from base import *
from base.littles import *
from base.constants import *
from kodi_services.sqlkodi import fetch_media_id
import requests
import urllib.parse
import websocket
import threading


KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

kodi_url = f"http://{KODI_MAIN_URL}/jsonrpc"
kodi_ws_url = f"ws://{KODI_MAIN_URL}/jsonrpc"
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
        #logger.debug(f"Failed to connect to Kodi: {e}")
        return False

def on_message(ws, message):
    global is_scanning
    data = json.loads(message)

    # Look for the scan start and finish events
    if "method" in data:
        if data["method"] == "VideoLibrary.OnScanFinished":
            is_scanning = False
            logger.debug(". Library scan has finished.")

def on_error(ws, error):
    logger.error(f"!! WebSocket error: {error} [kodi_services]")

def on_close(ws, close_status_code, close_msg):
    logger.debug(". WebSocket connection closed. [kodi_services]")

def on_open(ws):
    logger.debug(". WebSocket connection opened. Waiting for library scan events... [kodi_services]")

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
            "title": "Jellygrail msg.",
            "message": "Kodi scan triggered by Jellygrail.",
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
        logger.error("!! Kodi refreshed failed [refresh_kodi]")
        return False
    else:
        if response.status_code == 200:
            logger.debug("> Kodi lib refreshed [refresh_kodi]")
            
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
        logger.error(f"!! Kodi message failed with: {e}")
        return False
    
    while True:
        if is_scanning == False or not is_kodi_alive():
            break
        time.sleep(2)
    
    ws.close()
    return True

def send_nfo_to_kodi():

    if not is_kodi_alive():
        return False

    # browse nfos
    previous_root = ""
    for root, folders, files in os.walk(JFSQ_STORED_NFO):
        for filename in files:
            updated = False
            tofetch = os.path.basename(root)
            if filename.lower().endswith(('.nfo.jf', '.nfo.jf.updated')):
                if root == previous_root: #nfo refresh is on parent folder basis (root), so no need to trigger upon next nfo files found in same folder
                    continue
                previous_root = root
                if filename.lower().endswith('.nfo.jf.updated'):
                    updated = True
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
                logger.debug(f"---kodi db fetching : {root}/{filename}")
                # todo : if a retreieved media item has a non jellygrail provider id, it means it is not needed to refresh it
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

                                    rename_to_done(filename)
                                else:
                                    logger.warning(f"! Error on kodi nfo refresh: {response.status_code}")
                                    return False
                        else:
                            rename_to_done(filename) # - case where nfo was already taken through another way than nfo refresher

                else:
                    logger.warning(f"   ---- > {tofetch} has NO correspondance")
                

        # find corresponding video path (maping between kodi and filesystem)
    return True

def rename_to_done(filename):
    # as we are on linux, we can then rename the file even if it's being accessed by another process
    # rename to .done will ensure that this file won't be sent to kodi again
    try:
        if os.path.exists(filename):
            if filename.endswith('.updated'):
                new_name = filename[:-8] + '.done'
            else:
                new_name = filename+".done"
            os.rename(filename, new_name)
        else:
            logger.critical(f"!!! file (to rename to .done) does not exist (theorically impossible) [send_nfo_to_kodi]")
    except Exception as e:
        logger.debug(f"!! An error occured on renaming .nfo.jf to .nfo.jf.done : {e}")