# imports
from base import *
from base.littles import *
from base.constants import *
from datetime import datetime
import jfapi
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jgscan.jgsql import jellyDB, staticDB
#from jgscan.jgsql import *
#from jfconfig.jfsql import *
import urllib.parse
import requests
from xml.sax.saxutils import escape
import copy
import msgspec
import io
import glob
from kodi_services.kodiInstances import kodiDBRegistry


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

    try:
        os.makedirs(dirnames, exist_ok=True)
        with open(pathjg, "w", encoding="utf-8") as file:
            file.write(xml_str)
    except Exception:
        return False

    return True

def get_tech_xml_details(pathwoext):
    # build the tech part of the nfo
    if "video_ts" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(pathwoext) + "/VTS_01_1.VOB"
    elif "bdmv" in pathwoext.lower().split(os.sep):
        pathwoext = os.path.dirname(os.path.dirname(pathwoext))

    if (ff_result := [ffpitem[0] for ffpitem in staticDB.s.get_path_props_woext(pathwoext) if ffpitem[0] is not None]):
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

def add_images_from_fs_people(s: io.StringIO, pname: str, tstmp: int):

    prefix = pname[:1]
    folder = os.path.join(JF_METADATA_ROOT+"/People", prefix, pname)

    for fpath in glob.glob(os.path.join(folder, "*")):
        fname = os.path.basename(fpath).lower()
        #url = f"http://[PROTO_HOST_PORT]/pics{fpath[JF_MD_SHIFT:]}?{tstmp}"
        url = f"[PROTO_HOST_PORT]/pics{urllib.parse.quote(fpath[JF_MD_SHIFT:], safe=SAFE)}?[TIME]"
        if "folder" in fname:
            s.write(f"<thumb>{url}</thumb>\n")


def add_images_from_fs_season(s: io.StringIO, season: list, tstmp: int):

    prefix = season["suid"][:2]
    folder = os.path.join(JF_METADATA_ROOT+"/library", prefix, season["suid"])

    #older = get_item_metadata_folder(item.Id)
    #if not os.path.exists(folder):
    #    logger.error(f"No pic folder for {item.Id}")
    #    return

    for fpath in glob.glob(os.path.join(folder, "*")):
        fname = os.path.basename(fpath).lower()
        url = f"[PROTO_HOST_PORT]/pics{fpath[JF_MD_SHIFT:]}?[TIME]"

        if "poster" in fname:
            s.write(f"<thumb aspect=\"poster\" type=\"season\" season=\"{season['sidx']}\">{escape(url)}</thumb>\n")


def add_images_from_fs(s: io.StringIO, item: Item, tstmp: int):

    prefix = item.Id[:2]
    folder = os.path.join(JF_METADATA_ROOT+"/library", prefix, item.Id)

    #older = get_item_metadata_folder(item.Id)
    #if not os.path.exists(folder):
    #    logger.error(f"No pic folder for {item.Id}")
    #    return

    for fpath in glob.glob(os.path.join(folder, "*")):
        fname = os.path.basename(fpath).lower()
        url = f"[PROTO_HOST_PORT]/pics{fpath[JF_MD_SHIFT:]}?[TIME]"


        if "poster" in fname:
            aspect = "thumb" if item.Type == "Episode" else "poster"
            s.write(f"<thumb aspect=\"{aspect}\">{url}</thumb>\n")
        elif "logo" in fname:
            s.write(f"<thumb aspect=\"clearlogo\">{url}</thumb>\n")
        elif "backdrop" in fname:
            s.write(f"<thumb aspect=\"fanart\">{url}</thumb>\n")
            s.write(f"<thumb aspect=\"banner\">{url}</thumb>\n")




def jf_xml_create(item: Item, is_updated: bool, sdata: dict[str, list[dict]] | None = None, batchUid: str | None = None):

    if not batchUid:
        logger.critical("jf_xml_create called without batchUid")
        return

    tstmp = int(time.time())
    s = io.StringIO()
    # --- ouverture

    s.write('<?xml version="1.0" ?>\n')


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
    # --- images principales
    add_images_from_fs(s, item, tstmp)

    # --- images saisons (Series)
    if item.Type == "Series":
        for season in seasons_data:

            add_images_from_fs_season(s, season, tstmp)


    # --- cast & crew
    if item.Type in ("Movie", "Episode", "Series"):
        for actor in item.People or []:
            s.write("<actor>\n")
            s.write(f"<name>{escape(actor.Name or '')}</name>\n")
            s.write(f"<role>{escape(actor.Role or '')}</role>\n")
            if actor.Type == "Director" and item.Type in ("Movie", "Episode"):
                s.write(f"<director>{escape(actor.Name or '')}</director>\n")

            add_images_from_fs_people(s, actor.Name, tstmp)
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
            s.write(f"<uniqueid type=\"{key.lower()}\" default=\"true\">{val}</uniqueid>\n")
        else:
            s.write(f"<uniqueid type=\"{key.lower()}\">{val}</uniqueid>\n")

        if not did_write_collection and key.lower() == "tmdbcollection":
            # Récupération des infos de la collection (boxset)
            logger.debug(f"REMOTE SEARCH TMDBCOLLECTION {val}")
            payload = {"SearchInfo": {"ProviderIds": {"Tmdb": f"{val}"}}}
            if bs_raw := jfapi.jellyfin("Items/RemoteSearch/BoxSet", json=payload, method="post").content:
                collec_items = msgspec.json.decode(bs_raw, type=list[BoxSetItem])
            else:
                logger.warning(f"   NFO-GEN| Getting collection metadata failed")
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
    # --- genres
    for genre in item.GenreItems or []:
        s.write(f"<genre>{escape(genre.Name or '')}</genre>\n")

    # --- tags
    if item.Type in ("Movie", "Series"):
        for tag in item.Tags or []:
            s.write(f"<tag>{escape(tag)}</tag>\n")

    # --- fermeture
    if item.Type == "Movie":
        s.write("</movie>\n")
    elif item.Type == "Episode":
        s.write("</episodedetails>\n")
    elif item.Type == "Series":
        s.write("</tvshow>\n")

    #xml = s.getvalue()

    # --- écriture
    if item.Type != "Series":
        for ms in item.MediaSources or []:

            svariant = io.StringIO(s.getvalue())
            svariant.seek(s.tell())

            mspath = ms.Path or ""
            if ms.VideoType == "BluRay":
                get_wo_ext_out = mspath[JG_VIRT_SHIFT:]
                nfo_full_path = JFSQ_STORED_NFO + mspath[JG_VIRT_SHIFT:] + "/BDMV/index.nfo.jf"
            elif ms.VideoType == "Dvd":
                get_wo_ext_out = mspath[JG_VIRT_SHIFT:] + "/VIDEO_TS/VIDEO_TS"
                nfo_full_path = JFSQ_STORED_NFO + mspath[JG_VIRT_SHIFT:] + "/VIDEO_TS/VIDEO_TS.nfo.jf"
            else:
                get_wo_ext_out = get_wo_ext(mspath[JG_VIRT_SHIFT:])
                nfo_full_path = JFSQ_STORED_NFO + get_wo_ext(mspath[JG_VIRT_SHIFT:]) + ".nfo.jf"

            if tech_details := get_tech_xml_details(get_wo_ext_out):
                svariant.write(tech_details)

            xml = svariant.getvalue()

            new_write_to_disk(xml, nfo_full_path, batchUid)

    else:
        if item.Path:
            xml = s.getvalue()
            nfo_full_path = JFSQ_STORED_NFO + item.Path[JG_VIRT_SHIFT:] + "/tvshow.nfo.jf"
            new_write_to_disk(xml, nfo_full_path, batchUid)


def new_write_to_disk(root, nfo_full_path, batchUid):
    # write to file if changed
    # return True if written, False if not changed
    if os.path.exists(nfo_full_path):
        with open(nfo_full_path, "r", encoding="utf-8") as existing:
            if existing.read() == root:
                #logger.debug(f"No write needed, content identical: {nfo_full_path}")
                return False  # no write needed
    #logger.debug(f"Writing NFO: {nfo_full_path}")

    os.makedirs(os.path.dirname(nfo_full_path), exist_ok = True)
    with open(nfo_full_path, "w", encoding="utf-8") as file:
        file.write(root)

    # else
    kodiDBRegistry.addToNfoBatch(batchUid, nfo_full_path)
    return True


def write_to_disk_OLD(root, nfo_full_path, is_updated):

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


def write_to_disk(root, nfo_full_path, is_updated):
    """
    Writes `root` to disk only if the content differs.
    Returns True if the file was written (i.e., content changed), False otherwise.
    """

    files_to_delete = []
    

    # Determine target path
    if is_updated:
        nfo_full_path_towrite = nfo_full_path + ".updated"
        files_to_delete.append(nfo_full_path)  # delete legacy version if it exists
    else:
        nfo_full_path_towrite = nfo_full_path

    logger.debug(f"Preparing to write NFO: {nfo_full_path_towrite}")

    # --- Detect if new content differs ---
    write_needed = True
    if os.path.exists(nfo_full_path_towrite):
        try:
            with open(nfo_full_path_towrite, "r", encoding="utf-8") as existing:
                if existing.read() == root:
                    logger.debug(f"No write needed, content identical: {nfo_full_path_towrite}")
                    write_needed = False
        except Exception as e:
            logger.debug(f"Could not read existing file (will overwrite): {e}")

    # --- Write only if needed ---
    if write_needed:
        os.makedirs(os.path.dirname(nfo_full_path_towrite), exist_ok=True)
        with open(nfo_full_path_towrite, "w", encoding="utf-8") as file:
            file.write(root)
        logger.debug(f"Updated NFO written: {nfo_full_path_towrite}")
    else:
        logger.debug(f"Skipped writing unchanged NFO: {nfo_full_path_towrite}")

    # --- Cleanup for .done and legacy file ---
    files_to_delete.append(nfo_full_path + ".done")
    for file_to_del in files_to_delete:
        try:
            os.remove(file_to_del)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"An error occurred while deleting {file_to_del}: {e}")

    return write_needed