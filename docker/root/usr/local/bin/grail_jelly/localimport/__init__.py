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

# called in executor
def getMenuItems(mediatype, mediaid, uid):


    ctMenu = {}


    if not (result := getKodiInfo (uid, mediatype, mediaid)):
        return False
    
    #else

   


    splittedPaths = [item['virtualPath'].split('/',3) for item in result]
    # join to get to level of ddepth array:
    twDepthPaths = ['/'.join(parts[:(2 if mediatype == 'movie' else 3)]) for parts in splittedPaths]
    twDepthPaths = set(twDepthPaths)

    logger.info(f"API       | Found {twDepthPaths} distinct top-level paths for mediaid {mediaid}")

    # compute what's available locally and remotely for this mediaid/mediatype
    jgDB = jellyDB()



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

    jgDB.sqclose()