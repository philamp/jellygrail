# imports
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
import jfapi
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jgscan.jgsql import *
from jfconfig.jfsql import *

# for build_jg_nfo_video()
NFO2XMLTYPE = {
    "episodedetails":"episodedetails",
    "bdmv":"movie",
    "dvd":"movie",
    "tvshow":"tvshow",
    "movie":"movie"
}

# for get_tech_xml_details()
AV_KEY_MAPPING = {
    'codec_name': 'codec',
    'display_aspect_ratio': 'aspect',
    'width': 'width',
    'height': 'height',
    'channels': 'channels'
}

T_FORMAT = "%H:%M:%S"

def build_jg_nfo_video(nfopath, pathjg, nfotype):


    root = ET.Element(NFO2XMLTYPE.get(nfotype,"movie")) # ...indeed
    pathwoext = get_wo_ext(nfopath)
    
    title = os.path.basename(pathwoext)
    dirnames = os.path.dirname(pathjg)

    # take the temp title that fits not too badly
    if nfotype == "bdmv" or nfotype == "dvd":
        ET.SubElement(root, "title").text = os.path.basename(os.path.dirname(os.path.dirname(nfopath)))
    elif nfotype == "movie" or nfotype == "episodedetails":
        ET.SubElement(root, "title").text = title
    elif nfotype == "tvshow":
        ET.SubElement(root, "title").text = os.path.basename(os.path.dirname(nfopath))


    ET.SubElement(root, "uniqueid", {"type": "jellygrail", "default": "true"}).text = (os.path.dirname(nfopath)).replace("/", "_").replace(" ", "-")


    #get tech details return et.element -----------
    if nfotype in "movie episodedetails dvd bdmv":
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
    #init_database()
    if "video_ts" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(pathwoext) + "/VTS_01_1.VOB"
    elif "bdmv" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(os.path.dirname(pathwoext))
    
    #logger.debug(f"build nfo with pathwoext = {pathwoext}")

    if (ff_result := [ffpitem[0] for ffpitem in get_path_props_woext(pathwoext) if ffpitem[0] is not None]):
        info = json.loads(ff_result[0].decode("utf-8"))

        fileinfo = ET.Element('fileinfo')
        streamdetails = ET.SubElement(fileinfo, 'streamdetails')

        # Mapping of ffprobe keys to desired XML tags
        
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


        #sqclose()
        return fileinfo

    #sqclose()
    return None

def jf_xml_create(item, sdata = None):

    if item.get('Type') == 'Movie':
        root = ET.Element("movie")
        logger.debug("THIS IS A MOVIE")
    elif item.get('Type') == 'Episode':
        root = ET.Element("episodedetails")
        logger.debug("THIS IS AN EPISODE")
    elif item.get('Type') == 'Series':
        logger.debug("THIS IS A TVSHOW")
        seasons_data = []
        root = ET.Element("tvshow")
        if sdata:
            seasons_data = sdata.get(item.get('Id'), [])

    if item.get('Type') == 'Episode':
        ET.SubElement(root, "showtitle").text = item.get('SeriesName', "")
    
    ET.SubElement(root, "title").text = item.get("Name", "")
    ET.SubElement(root, "premiered").text = str(item.get("ProductionYear", ""))
    ET.SubElement(root, "plot").text = item.get("Overview", "")
    ET.SubElement(root, "originaltitle").text = item.get("OriginalTitle", "")

    if(item.get("TagLines")):
        ET.SubElement(root, "tagline").text = item.get("TagLines")[0]
    ET.SubElement(root, "runtime").text = str(ticks_to_minutes(item.get("RunTimeTicks", 60)))

    # fetch collectiondata from sqlite db
    if item.get('Type') == 'Movie':
        if (itemdata_array := [itemdata[0] for itemdata in fetch_item_data(item["Id"]) if itemdata[0] is not None]):
            itemjsondb = json.loads(itemdata_array[0])
            if tmdb_collection := itemjsondb.get("TmdbCollectionName", None):
                setxml = ET.SubElement(root, "set")
                ET.SubElement(setxml, "name").text = tmdb_collection

    # nbseasons total in lib
    # nbepisodes total in lib TODO

    # get images from API + ensure nginx serve them
    try:
        item_images = jfapi.jellyfin(f'Items/{item["Id"]}/Images').json()
    except Exception as e:
        logger.error(f"> Get JF pics failed with error: {e}")
    else:
        for itmimg in item_images:
            if itmimg.get('ImageType') == 'Primary':
                if item.get('Type') == 'Episode':
                    ET.SubElement(root, "thumb", {"aspect": "thumb"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
                else:
                    ET.SubElement(root, "thumb", {"aspect": "poster"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
            elif itmimg.get('ImageType') == 'Logo':
                ET.SubElement(root, "thumb", {"aspect": "clearlogo"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
            elif itmimg.get('ImageType') == 'Backdrop':
                ET.SubElement(root, "thumb", {"aspect": "landscape"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
                ET.SubElement(root, "thumb", {"aspect": "banner"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"
                ET.SubElement(root, "thumb", {"aspect": "clearart"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"

    if item.get('Type') == 'Series':
        for season_data in seasons_data:
            try:
                item_images = jfapi.jellyfin(f'Items/{season_data["suid"]}/Images').json()
            except Exception as e:
                logger.error(f"> Get JF pics TVSHOW failed with error: {e}")
            else:
                for itmimg in item_images:
                    ET.SubElement(root, "thumb", {"aspect": "poster", "type": "season", "season": str(season_data['sidx']) }).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"


    if item.get('Type') in "Movie Episode Series":
        if people := item.get('People',[]):
            for actor in people:
                actorxml = ET.SubElement(root, "actor")
                ET.SubElement(actorxml, "name").text = actor.get("Name", "")
                ET.SubElement(actorxml, "role").text = actor.get("Role", "")
                try:
                    item_images = jfapi.jellyfin(f'Items/{actor["Id"]}/Images').json()
                except Exception as e:
                    logger.error(f"> Get JF actor pic failed with error: {e}")
                else:
                    for itmimg in item_images:
                        ET.SubElement(actorxml, "thumb").text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}"

    if item.get('Type') == "Movie":
        for prodloc in item.get('ProductionLocations', []):
            ET.SubElement(root, "country").text = prodloc
            break


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
        ET.SubElement(root, "genre").text = genre.get("Name", "")
    
    # tags
    if item.get('Type') in "Movie Series":
        for tag in item.get("Tags", []):
            ET.SubElement(root, "tag").text = tag


    # save this nfo for all paths in mediasources
    if item.get('Type') != 'Series':
        for mediasource in item.get('MediaSources'):
            

            if mediasource.get("VideoType") == "BluRay":
                get_wo_ext_out = mediasource.get('Path')[JG_VIRT_SHIFT:]
                nfo_full_path = JFSQ_STORED_NFO + mediasource.get('Path')[JG_VIRT_SHIFT:] + "/BDMV/index.nfo.jf"
            elif mediasource.get("VideoType") == "Dvd":
                get_wo_ext_out = mediasource.get('Path')[JG_VIRT_SHIFT:] + "/VIDEO_TS/VIDEO_TS"
                nfo_full_path = JFSQ_STORED_NFO + mediasource.get('Path')[JG_VIRT_SHIFT:] + "/VIDEO_TS/VIDEO_TS.nfo.jf"
            else:
                get_wo_ext_out = get_wo_ext(mediasource.get('Path')[JG_VIRT_SHIFT:])
                nfo_full_path = JFSQ_STORED_NFO + get_wo_ext(mediasource.get('Path')[JG_VIRT_SHIFT:]) + ".nfo.jf"

            if tech_details := get_tech_xml_details(get_wo_ext_out):
                root.append(tech_details)

            xml_str = ET.tostring(root, encoding="unicode")
            pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
            os.makedirs(os.path.dirname(nfo_full_path), exist_ok = True)
            with open(nfo_full_path, "w", encoding="utf-8") as file:
                file.write(pretty_xml_str)

    else:
        nfo_full_path = JFSQ_STORED_NFO + get_wo_ext(item.get('Path')[JG_VIRT_SHIFT:]) + "/tvshow.nfo.jf"

        xml_str = ET.tostring(root, encoding="unicode")
        pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
        os.makedirs(os.path.dirname(nfo_full_path), exist_ok = True)
        with open(nfo_full_path, "w", encoding="utf-8") as file:
            file.write(pretty_xml_str)