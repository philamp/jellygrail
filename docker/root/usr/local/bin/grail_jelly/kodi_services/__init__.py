from base import *
from base.littles import *
from base.constants import *
from kodi_services.sqlkodi import test
import requests

KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

def refresh_kodi():
    kodi_url = f"{KODI_MAIN_URL}/jsonrpc" 
    kodi_username = "kodi"  
    kodi_password = "kodi"  

    headers = {
        'Content-Type': 'application/json',
    }

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
            "message": "Kodi scan completed.",
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

    # select all media items in kodi 
    # browse nfos
        # find corresponding video path (maping between kodi and filesystem)
    test()

    return