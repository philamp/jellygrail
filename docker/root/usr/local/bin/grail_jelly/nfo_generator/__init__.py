# import requests
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
import jfapi
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jgscan.jgsql import *

# Name of librairies
# LIB_NAMES = ("Movies", "Shows")

# Jellyfin.Plugin.KodiSyncQueue/1197e3fbeaee4d1e905a5b3ef7f5380c/GetItems?lastUpdateDt=2024-06-12T00:00:00.0000000Z
# {{baseUrl}}/Items?ParentId=f137a2dd21bbc1b99aa5c0f6bf02a805&Fields=MediaSources,ProviderIds,Overview

# Webdav ip + port specified for local network (as seen by a local network device)
# is it still useful if it's decided on nginx side ? maybe if later its not nginx anymore
# WEBDAV_LAN_HOST = os.getenv('WEBDAV_LAN_HOST')

def build_jg_nfo_video(nfopath, pathjg, nfotype):
    root = ET.Element(nfotype) # ...indeed
    pathwoext = get_wo_ext(nfopath)
    title = os.path.basename(pathwoext)
    dirnames = os.path.dirname(pathjg)
    if nfotype == "tvshow":
        ET.SubElement(root, "title").text = os.path.basename(os.path.dirname(nfopath))
    else:
        ET.SubElement(root, "title").text = title
    ET.SubElement(root, "uniqueid", {"type": "jellygrail", "default": "true"}).text = (os.path.dirname(nfopath)).replace("/", "_").replace(" ", "-")


    #get tech details return et.element -----------
    if nfotype == "movie" or nfotype == "episodedetails": 
        if tech_details := get_tech_xml_details(pathwoext):
            root.append(tech_details)

    #tree = ET.ElementTree(root)
    xml_str = ET.tostring(root, encoding="unicode")
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
    #print(pretty_xml_str)



    try:
        os.makedirs(dirnames, exist_ok = True)
        with open(pathjg, "w", encoding="utf-8") as file:
            file.write(pretty_xml_str)
    except Exception as e:
        return False

    return True


def get_tech_xml_details(pathwoext):
    # build the tech part of the nfo
    init_database()
    if (ff_result := [ffpitem[0] for ffpitem in get_path_props_woext(pathwoext) if ffpitem[0] is not None]):
        info = json.loads(ff_result[0].decode("utf-8"))

        fileinfo = ET.Element('fileinfo')
        streamdetails = ET.SubElement(fileinfo, 'streamdetails')

        # Mapping of ffprobe keys to desired XML tags
        AV_KEY_MAPPING = {
            'codec_name': 'codec',
            'display_aspect_ratio': 'aspect',
            'width': 'width',
            'height': 'height',
            'channels': 'channels'
        }

        T_FORMAT = "%H:%M:%S"
        
        # Iterate over streams and add details to 'streamdetails' 
        for stream in info.get('streams', []):
            # VIDEO
            hdrtype = None
            if stream.get('codec_type') == "video" and stream.get('codec_name') != "mjpeg" and stream.get('codec_name') != "png":
                video_element = ET.Element('video')
                for ffprobe_key, xml_tag in AV_KEY_MAPPING.items():
                    if ffprobe_key in stream:
                        sub_element = ET.SubElement(video_element, xml_tag)
                        sub_element.text = str(stream[ffprobe_key])
                
                # HDR
                if stream.get('color_transfer') == "smpte2084":
                    hdrtype = "hdr10"
                if( sideinfo := stream.get('side_data_list') ):
                    if(sideinfo[0].get('dv_profile')):
                        hdrtype = "dolbyvision"
                if hdrtype:
                    sub_element = ET.SubElement(video_element, "hdrtype").text = hdrtype

                # VTAGS
                if( tags := stream.get('tags') ):
                    if (tags.get('DURATION')):
                        parsed_time = datetime.strptime(tags.get('DURATION')[:8], T_FORMAT)
                        total_seconds = parsed_time.hour * 3600 + parsed_time.minute * 60 + parsed_time.second
                        ET.SubElement(video_element, "durationinseconds").text = str(total_seconds)
                    if (tags.get('language')):
                        ET.SubElement(video_element, "language").text = tags.get('language')

                streamdetails.append(video_element)
            # AUDIO
            if stream.get('codec_type') == "audio":
                audio_element = ET.Element('audio')
                for ffprobe_key, xml_tag in AV_KEY_MAPPING.items():
                    if ffprobe_key in stream:
                        sub_element = ET.SubElement(audio_element, xml_tag)
                        sub_element.text = str(stream[ffprobe_key])
                if( tags := stream.get('tags') ):
                    if (tags.get('language')):
                        ET.SubElement(audio_element, "language").text = tags.get('language')
                streamdetails.append(audio_element)
            # Subs
            if stream.get('codec_type') == "subtitle":
                subtitle_element = ET.Element('subtitle')
                if( tags := stream.get('tags') ):
                    if (tags.get('language')):
                        ET.SubElement(subtitle_element, "language").text = tags.get('language')
                streamdetails.append(subtitle_element)


        sqclose()
        return fileinfo

    sqclose()
    return None

def fetch_nfo(nfopath):

    # given a bindfs provided virtual nfo path, give a populatednfo path
    # movie : find .jf else .jg else generate .jg with fileinfo thanks to ffp data in db
    # show : find .jf else .jg else generate .jg with dummy data
    # 
    # careful to M_DUP and S_DUP management : no more identical.mkv + identical.mp4

    fallback = "/mounts/filedefaultnfo_readme_p.txt" # put a default path

    #logger.debug(f"movies str equal ?:{nfopath}")
    
    path = JFSQ_STORED_NFO + get_wo_ext(nfopath) + ".nfo"
    pathjf = path + ".jf"
    pathjg = path + ".jg"

    nfotype = None

    # switch case for video file
    if "/movies" in nfopath[:7] and "bdmv" not in nfopath.lower() and "video_ts" not in nfopath.lower():
        nfotype = "movie"
                
    # switch for tvshow file
    elif os.path.basename(nfopath) == "tvshow.nfo":
        nfotype = "tvshow"

    # switch for episode
    elif "/shows" in nfopath[:6]:
        nfotype = "episodedetails"

    # todo switch for others

    # ----

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
        return fallback

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
        syncqueue = jfapi.jellyfin(f'Jellyfin.Plugin.KodiSyncQueue/{user_id}/GetItems', params = dict(lastUpdateDt=read_jfsqdate_from_file())).json()
    except Exception as e:
        logger.critical(f"> Get JF sync queue failed with error: {e}")
        return False

    nowdate = datetime.now().isoformat()

    # lists
    # items_added_and_updated = syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated')


    # loop added and updated
    if items_added_and_updated := syncqueue.get('ItemsAdded') + syncqueue.get('ItemsUpdated'):
        # refresh ram dumps #todo remove season item type ?
        try:
            whole_jf_json_dump = jfapi.jellyfin(f'Items', params = dict(userId = user_id, Recursive = True, includeItemTypes='Season,Movie,Episode,Series', Fields = 'MediaSources,ProviderIds,Overview,OriginalTitle,RemoteTrailers,Taglines,Genres,Tags,ParentId,Path')).json()['Items']
        except Exception as e:
            logger.critical(f"> Get JF lib json dump failed with error: {e}")
            return False
        

        for item in whole_jf_json_dump:
            if item.get('Id') in items_added_and_updated:

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
                        item_images = jfapi.jellyfin(f'Items/{item["Id"]}/Images').json()
                    except Exception as e:
                        logger.critical(f"> Get JF pics failed with error: {e}")
                        return False

                    for itmimg in item_images:
                        if itmimg.get('ImageType') == 'Primary':
                            ET.SubElement(root, "thumb", {"aspect": "poster"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
                        elif itmimg.get('ImageType') == 'Logo':
                            ET.SubElement(root, "thumb", {"aspect": "clearlogo"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
                        elif itmimg.get('ImageType') == 'Backdrop':
                            ET.SubElement(root, "thumb", {"aspect": "landscape"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"

                    #rating
                    if(ratingvalue := item.get("CriticRating", None)):
                        ratings = ET.SubElement(root, "ratings")
                        rating = ET.SubElement(ratings, "rating", {"name": "tomatometerallaudience", "max": "100", "default": "true"})
                        ET.SubElement(rating, "value").text = f"{ratingvalue}"

                    # movie db keys vals
                    for key, val in item.get("ProviderIds", {}).items():
                        ET.SubElement(root, "uniqueid", {"type": key.lower()}).text = val
                    
                    # genres
                    for genre in item.get("GenreItems", []):
                        ET.SubElement(root, "genre").text = genre.get("Name")
                    
                    # tags
                    for tag in item.get("Tags", []):
                        ET.SubElement(root, "tag").text = tag

                    






                    #tree = ET.ElementTree(root)
                    xml_str = ET.tostring(root, encoding="unicode")
                    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
                    #print(pretty_xml_str)

                    # save this nfo for all paths in mediasources
                    for mediasource in item.get('MediaSources'):
                        nfo_full_path = JFSQ_STORED_NFO + get_wo_ext(mediasource.get('Path')[JG_VIRT_SHIFT:]) + ".nfo.jf"
                        os.makedirs(os.path.dirname(nfo_full_path), exist_ok = True)
                        with open(nfo_full_path, "w", encoding="utf-8") as file:
                            file.write(pretty_xml_str)



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
