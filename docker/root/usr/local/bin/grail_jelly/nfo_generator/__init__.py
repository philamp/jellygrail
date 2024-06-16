# import requests
from base import *
from base.littles import *
from datetime import datetime
import jfapi
import xml.etree.ElementTree as ET
from xml.dom import minidom


# jf_syncqueue_last_requested_date_file
JFSQ_LAST_REQUEST = '/jellygrail/data/jf_sync_queue_last_request.txt'

# folder to store nfos
JFSQ_STORED_NFO = '/jellygrail/data/nfos'

# Webdav ip + port specified for local network (as seen by a local network device)
WEBDAV_LAN_HOST = os.getenv('WEBDAV_LAN_HOST')

# Name of librairies
# LIB_NAMES = ("Movies", "Shows")

# Jellyfin.Plugin.KodiSyncQueue/1197e3fbeaee4d1e905a5b3ef7f5380c/GetItems?lastUpdateDt=2024-06-12T00:00:00.0000000Z
# {{baseUrl}}/Items?ParentId=f137a2dd21bbc1b99aa5c0f6bf02a805&Fields=MediaSources,ProviderIds,Overview

def nfo_loop_service():

    # jf_json_dump to store whole response
    whole_jf_json_dump = None

    # get first user, needed to request syncqueue
    users = jfapi.jellyfin('Users').json()  
    users_name_mapping = [user.get('Id') for user in users]
    user_id = users_name_mapping[0]

    # get Movies and shows perent lib ID
    # libraries = jellyfin(f'Items', params = dict(userId = user_id)).json()['Items']
    # libids = [lib.get('Id') for lib in libraries if libraries in LIB_NAMES]

    # while loop can start here !!!!!!!!!!!!!!!!!!!!!!!!

    # currentqueue
    try:
        syncqueue = jfapi.jellyfin(f'Jellyfin.Plurgin.KodiSyncQueue/{user_id}/GetItems', params = dict(lastUpdateDt=read_jfsqdate_from_file())).json()
    except Exception as e:
        logger.critical(f"> Get JF sync queue failed with error: {e}")
        return False

    nowdate = datetime.now().isoformat()

    # lists
    # items_added_and_updated = syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated')


    # loop added and updated
    if items_added_and_updated := syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated'):
        # refresh ram dumps
        try:
            whole_jf_json_dump = jfapi.jellyfin(f'Items', params = dict(userId = user_id, Recursive = True, includeItemTypes='Season,Movie,Episode,Series', Fields = 'MediaSources,ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines')).json()['Items']
        except Exception as e:
            logger.critical(f"> Get JF lib json dump failed with error: {e}")
            return False
        

        for item in whole_jf_json_dump:
            if item.get('Id') in items_added_and_updated:
                print(item['Id']) # todo remove

                # DEVIDE by video type starting from here ---------------
                if(item.get('Type') == 'Movie'):

                    root = ET.Element("movie") # ...indeed
                    
                    ET.SubElement(root, "title").text = item.get("Name", "")
                    ET.SubElement(root, "plot").text = item.get("Overview", "")
                    ET.SubElement(root, "originaltitle").text = item.get("OriginalTitle", "")

                    if(item.get("TagLines")):
                        ET.SubElement(root, "tagline").text = item.get("TagLines")[0]
                    ET.SubElement(root, "runtime").text = str(ticks_to_minutes(item.get("RunTimeTicks", 60)))


                    # get images from API + ensure nginx serve them
                    try:
                        item_images = jfapi.jellyfin(f'Items/{item['Id']}/Images').json()
                    except Exception as e:
                        logger.critical(f"> Get JF sync queue failed with error: {e}")
                        return False

                    for itmimg in item_images:
                        if itmimg.get('ImageType') == 'Primary':
                            ET.SubElement(root, "thumb", {"aspect": "poster"}).text = "dav://URI_PORT/" + 





                    tree = ET.ElementTree(root)
                    xml_str = ET.tostring(root, encoding="unicode")
                    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
                    print(pretty_xml_str)


                    # ---- end movie case


        # print(whole_jf_json_dump)
        # loop added
        # for item in items_added:









    # ---- if finished correctly
    # save_jfsqdate_to_file(nowdate)


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