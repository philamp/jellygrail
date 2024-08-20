from base import *
from base.littles import *
from base.constants import *
from kodi_services.sqlkodi import fetch_media_id
import requests
import urllib.parse


KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

kodi_url = f"http://{KODI_MAIN_URL}/jsonrpc" 
kodi_username = "kodi"  
kodi_password = "kodi"

headers = {
    'Content-Type': 'application/json',
}


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



def refresh_kodi():

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

def send_nfo_to_kodi():

    # browse nfos
    previous_root = ""
    for root, folders, files in os.walk(JFSQ_STORED_NFO):
        for filename in files:
            tofetch = os.path.basename(root)
            if filename.lower().endswith(('.nfo.jf')):
                if root == previous_root: #nfo refresh is on parent folder basis (root), so no need to trigger upon next nfo files found in same folder
                    continue
                previous_root = root
                if filename.lower() == "video_ts.nfo.jf" or filename.lower() == "index.nfo.jf":
                    tofetch = os.path.basename(os.path.dirname(root))
                    tabletofetch = "movie_view"
                    idtofetch = "idMovie"
                    reftype = "Movie"
                    typeid = "movieid"
                elif filename.lower() == "tvshow.nfo.jf":
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
                if results := [line[0] for line in fetch_media_id(tofetch, tabletofetch, idtofetch)]:
                    for result in results:
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
                            # todo stop at the first sent failed ?
                        else:
                            if response.status_code == 200:
                                logger.debug(f"> Nfo refresh ok on id item {result} [refresh_kodi]")
                            else:
                                logger.warning(f"! Error on kodi nfo refresh: {response.status_code}")

                else:
                    logger.warning(f"   ---- > {tofetch} has NO correspondance")
                

        # find corresponding video path (maping between kodi and filesystem)

    return