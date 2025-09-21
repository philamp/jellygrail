# imports
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
import jfapi
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jgscan.jgsql import *
#from jfconfig.jfsql import *
import urllib.parse
import requests
from xml.sax.saxutils import escape
import copy
import msgspec
import io


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

# --- msgspec structs ----
class RemoteImage(msgspec.Struct, omit_defaults=True):
    ImageType: str | None = None
    Path: str | None = None

class BoxSetItem(msgspec.Struct, omit_defaults=True):
    Name: str | None = None
    ImageUrl: str | None = None

class ProviderIds(msgspec.Struct, omit_defaults=True):
    Imdb: str | None = None
    Tmdb: str | None = None
    TmdbCollection: str | None = None

class GenreItem(msgspec.Struct):
    Name: str

class Person(msgspec.Struct):
    Id: str
    Name: str
    Role: str | None = None
    Type: str | None = None

class MediaSource(msgspec.Struct, omit_defaults=True):
    Path: str | None = None
    VideoType: str | None = None

class Item(msgspec.Struct, omit_defaults=True):
    Id: str
    Type: str
    Name: str | None = None
    IndexNumber: int | None = None
    ParentId: str | None = None
    PremiereDate: str | None = None
    Overview: str | None = None
    OriginalTitle: str | None = None
    TagLines: list[str] = []
    RunTimeTicks: int | None = None
    SeriesName: str | None = None
    People: list[Person] = []
    ProviderIds: dict[str, str] = {}
    GenreItems: list[GenreItem] = []
    Tags: list[str] = []
    MediaSources: list[MediaSource] = []
    Path: str | None = None
    ProductionLocations: list[str] = []
    CriticRating: int | None = None


def build_jg_nfo_video(nfopath, pathjg, nfotype):
    # mapping NFO2XMLTYPE → root tag
    root_tag = NFO2XMLTYPE.get(nfotype, "movie")
    pathwoext = get_wo_ext(nfopath)
    title = os.path.basename(pathwoext)
    dirnames = os.path.dirname(pathjg)

    xml_parts = ['<?xml version="1.0" ?>']

    # ouverture du XML
    xml_parts.append(f"<{root_tag}>")

    # choix du titre
    if nfotype in ("bdmv", "dvd"):
        val = os.path.basename(os.path.dirname(os.path.dirname(nfopath)))
    elif nfotype in ("movie", "episodedetails"):
        val = title
    elif nfotype == "tvshow":
        val = os.path.basename(os.path.dirname(nfopath))
    else:
        val = title  # fallback
    xml_parts.append(f"  <title>{val}</title>")

    # uniqueid
    uid = os.path.dirname(nfopath).replace("/", "_").replace(" ", "-")
    xml_parts.append(f'  <uniqueid type="jellygrail" default="true">{uid}</uniqueid>')

    # tech details (si get_tech_xml_details retourne un str XML au lieu d’un Element)
    if nfotype in ("movie", "episodedetails", "dvd", "bdmv"):
        if tech_details := get_tech_xml_details(pathwoext):
            xml_parts.append(str(tech_details))

    # fermeture du root
    xml_parts.append(f"</{root_tag}>")

    # assemblage
    xml_str = "\n".join(xml_parts)

    # pretty print via minidom
    #pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    try:
        os.makedirs(dirnames, exist_ok=True)
        with open(pathjg, "w", encoding="utf-8") as file:
            file.write(xml_str)
    except Exception:
        return False

    return True

'''
def build_jg_nfo_video(nfopath, pathjg, nfotype):

     # to get collection id which is in JF api but a pain to fetch :(

    

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
'''

def get_tech_xml_details(pathwoext):
    # build the tech part of the nfo
    if "video_ts" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(pathwoext) + "/VTS_01_1.VOB"
    elif "bdmv" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(os.path.dirname(pathwoext))

    if (ff_result := [ffpitem[0] for ffpitem in get_path_props_woext(pathwoext) if ffpitem[0] is not None]):
        first_subs = []
        last_subs = []
        info = json.loads(ff_result[0].decode("utf-8"))

        parts = []
        parts.append("<fileinfo>")
        parts.append("  <streamdetails>")

        for stream in info.get('streams', []):
            # VIDEO
            hdrtype = None
            if stream.get('codec_type') == "video" and stream.get('codec_name') not in ("mjpeg", "png"):
                parts.append("    <video>")
                for ffprobe_key, xml_tag in AV_KEY_MAPPING.items():
                    if ffprobe_key in stream:
                        val = str(stream[ffprobe_key])
                        parts.append(f"      <{xml_tag}>{val}</{xml_tag}>")
                
                # HDR
                if stream.get('color_transfer') == "smpte2084":
                    hdrtype = "hdr10"
                if (sideinfo := stream.get('side_data_list')):
                    if (sideinfo[0].get('dv_profile')):
                        hdrtype = "dolbyvision"
                if hdrtype:
                    parts.append(f"      <hdrtype>{hdrtype}</hdrtype>")

                # VTAGS
                if (tags := stream.get('tags')):
                    if (tags.get('DURATION')):
                        parsed_time = datetime.strptime(tags.get('DURATION')[:8], T_FORMAT)
                        total_seconds = parsed_time.hour * 3600 + parsed_time.minute * 60 + parsed_time.second
                        parts.append(f"      <durationinseconds>{total_seconds}</durationinseconds>")
                    if (tags.get('language')):
                        parts.append(f"      <language>{tags.get('language')}</language>")

                parts.append("    </video>")
            
            # AUDIO
            if stream.get('codec_type') == "audio":
                parts.append("    <audio>")
                for ffprobe_key, xml_tag in AV_KEY_MAPPING.items():
                    if ffprobe_key in stream:
                        val = str(stream[ffprobe_key])
                        parts.append(f"      <{xml_tag}>{val}</{xml_tag}>")
                if (tags := stream.get('tags')):
                    if (tags.get('language')):
                        parts.append(f"      <language>{tags.get('language')}</language>")
                parts.append("    </audio>")

            # SUBS
            if stream.get('codec_type') == "subtitle":
                if (tags := stream.get('tags')):
                    if (sub_l := tags.get('language')):
                        if sub_l in INTERESTED_LANGUAGES:
                            first_subs.append(sub_l)
                        else:
                            last_subs.append(sub_l)

        # éviter doublons
        first_subs = list(set(first_subs))
        last_subs  = list(set(last_subs))
        first_subs.extend(last_subs)
        for lang in first_subs:
            parts.append("    <subtitle>")
            parts.append(f"      <language>{lang}</language>")
            parts.append("    </subtitle>")

        parts.append("  </streamdetails>")
        parts.append("</fileinfo>")

        return "\n".join(parts)

    return None

'''
def get_tech_xml_details(pathwoext):
    # build the tech part of the nfo
    #init_database()
    if "video_ts" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(pathwoext) + "/VTS_01_1.VOB"
    elif "bdmv" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(os.path.dirname(pathwoext))
    
    #logger.debug(f"build nfo with pathwoext = {pathwoext}")

    if (ff_result := [ffpitem[0] for ffpitem in get_path_props_woext(pathwoext) if ffpitem[0] is not None]):
        first_subs = []
        last_subs = []
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
                if( tags := stream.get('tags') ):
                    if sub_l := (tags.get('language')):
                        if sub_l in INTERESTED_LANGUAGES:
                            first_subs.append(sub_l)
                        else:
                            last_subs.append(sub_l)
                    
        first_subs = list(set(first_subs)) #mention each language only once
        last_subs = list(set(last_subs)) #mention each language only once             
        first_subs.extend(last_subs)
        for lang in first_subs:
            subtitle_element = ET.Element('subtitle')
            ET.SubElement(subtitle_element, "language").text = lang
            streamdetails.append(subtitle_element)


        #sqclose()
        return fileinfo

    #sqclose()
    return None
'''


def jf_xml_create(item: Item, is_updated: bool, sdata: dict[str, list[dict]] | None = None):
    tstmp = int(time.time())
    s = io.StringIO()
    logger.debug(f"NFO wrinting stuff part 1")
    # --- ouverture
    if item.Type == "Movie":
        s.write("<movie>\n")
    elif item.Type == "Episode":
        s.write("<episodedetails>\n")
    elif item.Type == "Series":
        s.write("<tvshow>\n")
        seasons_data = sdata.get(item.Id, []) if sdata else []
    else:
        logger.warning(f"Unsupported type {item.Type}")
        return

    # --- spécifique épisode
    if item.Type == "Episode":
        s.write(f"<showtitle>{escape(item.SeriesName or '')}</showtitle>\n")
        s.write(f"<aired>{(item.PremiereDate or '')[:10]}</aired>\n")

    # --- communs
    s.write(f"<title>{escape(item.Name or '')}</title>\n")
    s.write(f"<premiered>{(item.PremiereDate or '')[:10]}</premiered>\n")
    s.write(f"<plot>{escape(item.Overview or '')}</plot>\n")
    s.write(f"<originaltitle>{escape(item.OriginalTitle or '')}</originaltitle>\n")

    if item.TagLines:
        s.write(f"<tagline>{escape(item.TagLines[0])}</tagline>\n")

    s.write(f"<runtime>{ticks_to_minutes(item.RunTimeTicks or 60)}</runtime>\n")
    logger.debug(f"NFO getting images")
    # --- images principales
    try:
        imgs_raw = jfapi.jellyfin(f"Items/{item.Id}/Images").content
        item_images = msgspec.json.decode(imgs_raw, type=list[RemoteImage])
    except Exception as e:
        logger.error(f"> Get JF pics failed: {e}")
        item_images = []

    for im in item_images:
        if not im.Path:
            continue
        url = f"http://[HOST_PORT]/pics{im.Path[JF_MD_SHIFT:]}?{tstmp}"
        if im.ImageType == "Primary":
            aspect = "thumb" if item.Type == "Episode" else "poster"
            s.write(f"<thumb aspect=\"{aspect}\">{escape(url)}</thumb>\n")
        elif im.ImageType == "Logo":
            s.write(f"<thumb aspect=\"clearlogo\">{escape(url)}</thumb>\n")
        elif im.ImageType == "Backdrop":
            s.write(f"<thumb aspect=\"fanart\">{escape(url)}</thumb>\n")
            s.write(f"<thumb aspect=\"banner\">{escape(url)}</thumb>\n")

    # --- images saisons (Series)
    if item.Type == "Series":
        for season in seasons_data:
            try:
                simgs_raw = jfapi.jellyfin(f"Items/{season['suid']}/Images").content
                simgs = msgspec.json.decode(simgs_raw, type=list[RemoteImage])
            except Exception as e:
                logger.error(f"> Get JF pics TVSHOW failed: {e}")
                simgs = []
            for im in simgs:
                if not im.Path:
                    continue
                url = f"http://[HOST_PORT]/pics{im.Path[JF_MD_SHIFT:]}?{tstmp}"
                s.write(
                    f"<thumb aspect=\"poster\" type=\"season\" season=\"{season['sidx']}\">{escape(url)}</thumb>\n"
                )
    logger.debug(f"NFO wrinting actor stuff + simages")
    # --- cast & crew
    if item.Type in ("Movie", "Episode", "Series"):
        for actor in item.People or []:
            s.write("<actor>\n")
            s.write(f"<name>{escape(actor.Name or '')}</name>\n")
            s.write(f"<role>{escape(actor.Role or '')}</role>\n")
            if actor.Type == "Director" and item.Type in ("Movie", "Episode"):
                s.write(f"<director>{escape(actor.Name or '')}</director>\n")
            try:
                aimgs_raw = jfapi.jellyfin(f"Items/{actor.Id}/Images").content
                aimgs = msgspec.json.decode(aimgs_raw, type=list[RemoteImage])
            except Exception as e:
                logger.error(f"> Get JF actor pic failed: {e}")
                aimgs = []
            for im in aimgs:
                if not im.Path:
                    continue
                url = f"http://[HOST_PORT]/pics{urllib.parse.quote(im.Path[JF_MD_SHIFT:], safe=SAFE)}?{tstmp}"
                s.write(f"<thumb>{escape(url)}</thumb>\n")
            s.write("</actor>\n")

    # --- pays
    if item.Type == "Movie" and item.ProductionLocations:
        s.write(f"<country>{escape(item.ProductionLocations[0])}</country>\n")

    # --- rating
    if item.CriticRating is not None:
        s.write("<ratings>\n")
        s.write("<rating name=\"tomatometerallaudience\" max=\"100\" default=\"true\">\n")
        s.write(f"<value>{item.CriticRating}</value>\n")
        s.write("</rating>\n</ratings>\n")

    # --- Provider IDs + gestion TMDB collection
    did_write_collection = False
    for key, val in (item.ProviderIds or {}).items():
        if key.lower() == "imdb":
            s.write(f"<uniqueid type=\"{key.lower()}\" default=\"true\">{escape(val)}</uniqueid>\n")
        else:
            s.write(f"<uniqueid type=\"{key.lower()}\">{escape(val)}</uniqueid>\n")

        if not did_write_collection and key.lower() == "tmdbcollection":
            # Récupération des infos de la collection (boxset)
            logger.debug(f"REMOTE SEARCH TMDBCOLLECTION {val}")
            payload = {"SearchInfo": {"ProviderIds": {"Tmdb": f"{val}"}}}
            try:
                bs_raw = jfapi.jellyfin("Items/RemoteSearch/BoxSet", json=payload, method="post").content
                collec_items = msgspec.json.decode(bs_raw, type=list[BoxSetItem])
            except Exception as e:
                logger.warning(f"      TASK| Getting movie collection metadata failed: {e}")
                collec_items = []

            for c in collec_items:
                if not c.Name:
                    continue
                # <set><name>...</name></set>
                s.write("<set>\n")
                s.write(f"<name>{escape(c.Name)}</name>\n")
                s.write("</set>\n")

                # Télécharger l'image de collection si absente
                folderstorepath = JF_METADATA_ROOT + "/collections"
                filestorepath = folderstorepath + "/" + c.Name + ".jpg"
                if c.ImageUrl and not os.path.exists(filestorepath):
                    os.makedirs(folderstorepath, exist_ok=True)
                    try:
                        resp = requests.get(c.ImageUrl, stream=True, timeout=15)
                        resp.raise_for_status()
                        with open(filestorepath, "wb") as file:
                            for chunk in resp.iter_content(chunk_size=8192):
                                file.write(chunk)
                    except Exception as e:
                        logger.debug(f"dling collection image {val} failed: {e}")
                did_write_collection = True
                break  # on ne prend que la première correspondance utile
    logger.debug(f"NFO wrinting tag stuff and closing")
    # --- genres
    for genre in item.GenreItems or []:
        s.write(f"<genre>{escape(genre.Name or '')}</genre>\n")

    # --- tags
    if item.Type in ("Movie", "Series"):
        for tag in item.Tags or []:
            s.write(f"<tag>{escape(tag)}</tag>\n")

    # --- fermeture
    if item.Type == "Movie":
        s.write("</movie>")
    elif item.Type == "Episode":
        s.write("</episodedetails>")
    elif item.Type == "Series":
        s.write("</tvshow>")

    xml = s.getvalue()

    # --- écriture
    if item.Type != "Series":
        for ms in item.MediaSources or []:
            path = ms.Path or ""
            if ms.VideoType == "BluRay":
                nfo_full_path = JFSQ_STORED_NFO + path[JG_VIRT_SHIFT:] + "/BDMV/index.nfo.jf"
            elif ms.VideoType == "Dvd":
                nfo_full_path = JFSQ_STORED_NFO + path[JG_VIRT_SHIFT:] + "/VIDEO_TS/VIDEO_TS.nfo.jf"
            else:
                nfo_full_path = JFSQ_STORED_NFO + get_wo_ext(path[JG_VIRT_SHIFT:]) + ".nfo.jf"
            write_to_disk(xml, nfo_full_path, is_updated)
    else:
        if item.Path:
            nfo_full_path = JFSQ_STORED_NFO + item.Path[JG_VIRT_SHIFT:] + "/tvshow.nfo.jf"
            write_to_disk(xml, nfo_full_path, is_updated)


'''
def jf_xml_create(item, is_updated, sdata = None):

    tstmp = int(time.time())

    if item.get('Type') == 'Movie':
        root = ET.Element("movie")
        #logger.info("    NFOGEN| MOVIE")
    elif item.get('Type') == 'Episode':
        root = ET.Element("episodedetails")
        #logger.info("    NFOGEN| EPISODE")
    elif item.get('Type') == 'Series':
        root = ET.Element("tvshow")
        #logger.info("    NFOGEN| TVSHOW")
        if sdata:
            seasons_data = sdata.get(item.get('Id'), [])
        else:
            seasons_data = []

    if item.get('Type') == 'Episode':
        ET.SubElement(root, "showtitle").text = item.get('SeriesName', "")
        ET.SubElement(root, "aired").text = str(item.get("PremiereDate", ""))[:10]

    
    ET.SubElement(root, "title").text = item.get("Name", "")
    ET.SubElement(root, "premiered").text = str(item.get("PremiereDate", ""))[:10]
    ET.SubElement(root, "plot").text = item.get("Overview", "")
    ET.SubElement(root, "originaltitle").text = item.get("OriginalTitle", "")

    if(item.get("TagLines")):
        ET.SubElement(root, "tagline").text = item.get("TagLines")[0]
    ET.SubElement(root, "runtime").text = str(ticks_to_minutes(item.get("RunTimeTicks", 60)))

    # nbseasons total in lib
    # nbepisodes total in lib toimprove

    # get images from API + ensure nginx serve them
    try:
        item_images = jfapi.jellyfin(f'Items/{item["Id"]}/Images').json()
    except Exception as e:
        logger.error(f"> Get JF pics failed with error: {e}")
    else:
        for itmimg in item_images:
            if itmimg.get('ImageType') == 'Primary':
                if item.get('Type') == 'Episode':
                    ET.SubElement(root, "thumb", {"aspect": "thumb"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"
                else:
                    ET.SubElement(root, "thumb", {"aspect": "poster"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"
            elif itmimg.get('ImageType') == 'Logo':
                ET.SubElement(root, "thumb", {"aspect": "clearlogo"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"
            elif itmimg.get('ImageType') == 'Backdrop':
                ET.SubElement(root, "thumb", {"aspect": "fanart"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"
                ET.SubElement(root, "thumb", {"aspect": "banner"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"
                #ET.SubElement(root, "thumb", {"aspect": "clearart"}).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"

    if item.get('Type') == 'Series':
        for season_data in seasons_data:
            try:
                item_images = jfapi.jellyfin(f'Items/{season_data["suid"]}/Images').json()
            except Exception as e:
                logger.error(f"> Get JF pics TVSHOW failed with error: {e}")
            else:
                for itmimg in item_images:
                    ET.SubElement(root, "thumb", {"aspect": "poster", "type": "season", "season": str(season_data['sidx']) }).text = f"http://[HOST_PORT]/pics{itmimg.get('Path')[JF_MD_SHIFT:]}?{tstmp}"


    if item.get('Type') in "Movie Episode Series":
        if people := item.get('People',[]):
            for actor in people:
                actorxml = ET.SubElement(root, "actor")
                act_name = actor.get("Name", "")
                if actor.get("Type", "") == "Director" and item.get('Type') in "Movie Episode":
                    ET.SubElement(root, "director").text = act_name

                ET.SubElement(actorxml, "name").text = act_name
                ET.SubElement(actorxml, "role").text = actor.get("Role", "")


                try:
                    item_images = jfapi.jellyfin(f'Items/{actor["Id"]}/Images').json()
                except Exception as e:
                    logger.error(f"> Get JF actor pic failed with error: {e}")
                else:
                    for itmimg in item_images:
                        ET.SubElement(actorxml, "thumb").text = f"http://[HOST_PORT]/pics{urllib.parse.quote(itmimg.get('Path')[JF_MD_SHIFT:], safe=SAFE)}?{tstmp}"

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
        if key.lower() == "imdb":
            ET.SubElement(root, "uniqueid", {"type": key.lower(), "default": "true"}).text = val #test with a4ksubs
        else:
            ET.SubElement(root, "uniqueid", {"type": key.lower()}).text = val
        if key.lower() == "tmdbcollection":
            logger.debug(f"REMOTE SERACH TMDBCOLLECTION {val}")
            payload = {
                "SearchInfo": {
                    "ProviderIds": {
                        "Tmdb": f"{val}"
                    }
                }
            }

            try:
                collec_items = jfapi.jellyfin(f'Items/RemoteSearch/BoxSet', json=payload, method='post').json()
            except Exception as e:
                logger.warning(f"      TASK| Getting movie collection meatadata failed with error: {e}")
            else:
                for c_item in collec_items:
                    if setname := c_item.get("Name", None):
                        setxml = ET.SubElement(root, "set")
                        ET.SubElement(setxml, "name").text = setname
                        # ET.SubElement(root, "collectionimage").text = setname
                        folderstorepath = JF_METADATA_ROOT+"/collections"
                        filestorepath = folderstorepath+"/"+setname+".jpg"
                        if not os.path.exists(filestorepath):
                            os.makedirs(folderstorepath, exist_ok=True)
                            try:
                                response = requests.get(c_item.get("ImageUrl", None), stream=True)
                                response.raise_for_status()
                            except Exception as e:
                                logger.debug(f"dling colleciton image {val} failed with error {e}")
                            else:
                                with open(filestorepath, 'wb') as file:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        file.write(chunk)


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
            rootvariant = copy.deepcopy(root)

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
                rootvariant.append(tech_details)

            write_to_disk(rootvariant, nfo_full_path, is_updated)

    else:
        #if tdata is not None:
            #nfo_full_path = JFSQ_STORED_NFO + tdpath[JG_VIRT_SHIFT:] + "/tvshow.nfo.jf" for tdpath in tdata.get(item.get('Name'), [])
        #else:
            #nfo_full_paths = []
        #logger.info(f"---- {nfo_full_paths}")
        nfo_full_path = JFSQ_STORED_NFO + item.get('Path')[JG_VIRT_SHIFT:] + "/tvshow.nfo.jf"
        #toremove
        

        #nfo_full_paths = list(set(nfo_full_paths))
        #for nfo_full_path in nfo_full_paths:
        write_to_disk(root, nfo_full_path, is_updated)
'''

def write_to_disk(root, nfo_full_path, is_updated):

    files_to_delete = []
    
    if is_updated:
        nfo_full_path_towrite = nfo_full_path + ".updated"
        files_to_delete.append(nfo_full_path) # if a previous not "updated" variant is here, delete it
    else:
        nfo_full_path_towrite = nfo_full_path

    logger.debug(f"wrinting NFO: {nfo_full_path_towrite}")
                 
    #xml_str = ET.tostring(root, encoding="unicode")
    #pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
    os.makedirs(os.path.dirname(nfo_full_path_towrite), exist_ok = True)
    with open(nfo_full_path_towrite, "w", encoding="utf-8") as file:
        file.write(root)

    # try to remove a .done file anyway
    files_to_delete.append(nfo_full_path + ".done")
    for file_to_del in files_to_delete:
        try:
            os.remove(file_to_del)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"An error occurred while deleting the file: {e}")
