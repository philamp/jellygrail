# JG base libs
from base import *

# JG constants
from base.constants import *

# JG modules
from jgscan.jgsql import jellyDB
from kodi_services import getKodiInfo, extract_triplets


# function to 

# called by jobmanager, loop through jgDB items to fetch for items to copy locally
# progress should be in bytes
# store filesize in jgDB as well
'''
def importMediaItems():
    jgDB = jellyDB()
    cursor = jgDB.conn.cursor()
    cursor.execute("SELECT depdec(virtual_fullpath), actual_fullpath, completion FROM main_mapping WHERE completion < 2 AND (actual_fullpath IS NOT NULL AND actual_fullpath != '')")
    items_to_import = cursor.fetchall()

    for (vpath, actual_path, completion) in items_to_import:



    jgDB.sqclose()
'''

# get actual path in jgDB using a provided db connector
# MAYBE not used TODO verify
def getActualPath(vpath, jgDB):
    for (actual_path,) in jgDB.get_path_actual(vpath):
        return actual_path
    return None

def levelExtractor(vfn, PREFLANG, uhdarray, hdarray):

    Lmatches = extract_triplets(vfn)
    nLmatches = [m.lower() for m in Lmatches]

    #matchb = re.search(r'(\d+)Mbps', vfn)

    if 'UHD' in vfn or '2160p' in vfn:
        if PREFLANG in nLmatches:
            uhdarray.append(2)
        else:
            uhdarray.append(1)

    elif 'FHD' in vfn or 'HD' in vfn or '1080p' in vfn or '720p' in vfn:
        if PREFLANG in nLmatches:
            hdarray.append(2)
        else:
            hdarray.append(1)

# called in executor
def getMenuItems(mediatype, mediaid, uid):


    ctMenu = {}
    ctMenu['payload'] = []
    ctMenu['menu'] = {}

    parentList = []

    R_HD_lang_level = []
    R_UHD_lang_level = []

    L_UHD_lang_level = []
    L_HD_lang_level = []

    Title = ""

    PREFLANG = USED_LANGS_JF[0].lower()

    if not (result := getKodiInfo (uid, mediatype, mediaid)):
        return ctMenu
    
    #else

    # embed uinique ids in payload to be used back by module
    for item in result:
        
        vp = item['virtualPath']
        vp = vp[:-1] if vp.endswith("/") else vp

        parentList.append(vp)

        Title = item.get("movieTitle", "")


    #unique
    parentList = list(set(parentList))

    ctMenu['payload'] = parentList

    logger.info(f"menubuilder       | Found parent paths: {parentList}")

    ## LS each parentpath to get all actualpaths and completion status

    jgDB = jellyDB()

    for path in parentList:
        for (vfn,actual_path,_) in jgDB.lc_ls_virtual_folder(path):

            if actual_path:
                logger.info(f"menubuilder       | Found virtual filename {vfn} in virtual folder {path} mapped to actual path {actual_path}")

                logger.info(f"menubuilder       | actual_path split: {actual_path.split('/',2)}")
                # LOCAL
                if "remote" not in actual_path.split("/", 2)[2]:
                    levelExtractor(vfn, PREFLANG, L_UHD_lang_level, L_HD_lang_level)

                # REMOTE
                else:
                    levelExtractor(vfn, PREFLANG, R_UHD_lang_level, R_HD_lang_level)

    jgDB.sqclose()

    # build information string based on findings
    final_L_UHD_lang_level = max(L_UHD_lang_level) if L_UHD_lang_level else 0
    final_L_HD_lang_level = max(L_HD_lang_level) if L_HD_lang_level else 0
    final_R_UHD_lang_level = max(R_UHD_lang_level) if R_UHD_lang_level else 0
    final_R_HD_lang_level = max(R_HD_lang_level) if R_HD_lang_level else 0


    L_info_tpl = "L:"
    L_info_tpl += " UHD" if final_L_UHD_lang_level > 0 else ""
    L_info_tpl += f" with {PREFLANG}" if final_L_UHD_lang_level > 1 else ""

    L_info_tpl += ", HD" if final_L_HD_lang_level > 0 else ""
    L_info_tpl += f" with {PREFLANG}" if final_L_HD_lang_level > 1 else ""

    R_info_tpl = "R:"
    R_info_tpl += " UHD" if final_R_UHD_lang_level > 0 else ""
    R_info_tpl += f" with {PREFLANG}" if final_R_UHD_lang_level > 1 else ""
    R_info_tpl += ", HD" if final_R_HD_lang_level > 0 else ""
    R_info_tpl += f" with {PREFLANG}" if final_R_HD_lang_level > 1 else ""

    ctMenu['menu'][f'{Title}'] = "#NULL"
    ctMenu['menu'][f"{L_info_tpl} | {R_info_tpl}"] = "#NULL"

    ctMenu['menu'][f'Keep this {mediatype}'] = "#KEEPLOCAL"
    ctMenu['menu'][f'Keep this {mediatype} + 4K'] = "#KEEPLOCALUHD"




    return ctMenu

    '''
    splittedPaths = [item['virtualPath'].split('/',3) for item in result]
    # join to get to level of ddepth array:
    twDepthPaths = ['/'.join(parts[:(2 if mediatype == 'movie' else 3)]) for parts in splittedPaths]
    twDepthPaths = set(twDepthPaths)

    logger.info(f"API       | Found {twDepthPaths} distinct top-level paths for mediaid {mediaid}")
    '''
    


    '''
    for item in result:
        vpath = item.get("virtualPath", "")
        vfn = item.get("virtualFilename", "")
        
        prefLangHere = 0
        logger.info(f"API       | Processing {vpath}")
        
        if not (actual_path := getActualPath(vpath, jgDB)):
            continue


        logger.info(f"API       | Processing virtual filename {vfn} with actual path {actual_path}")
        Lmatches = extract_triplets(vfn)
        nLmatches = [m.lower() for m in Lmatches]

        matchb = re.search(r'(\d+)Mbps', vfn)
        
        # LOCAL
        if "remote" not in actual_path.split("/", 2)[2]:
            # construct menu actions based on actual_path
            
            # if find INTERESTED_LANGUAGES is present str values in [] and {} in the filename:
            # use regexp to extract them from filename

            if USED_LANGS_JF[0].lower() in nLmatches:
                local_prefLangPresentQLevel = 1
                if 'UHD' in vfn:
                    local_prefLangPresentQLevel = 2



        # REMOTE
        else:
            
            if matchb:
                mbps_value = int(matchb.group(1))
            else:
                mbps_value = 25 

            if USED_LANGS_JF[0].lower() in nLmatches:
                prefLangHere = 1
            if 'UHD' in vfn:
                candidateVPathUHD_Tuples.append((vfn, prefLangHere, mbps_value))
            else:
                candidateVPath_Tuples.append((vfn, prefLangHere, mbps_value))
    '''
    