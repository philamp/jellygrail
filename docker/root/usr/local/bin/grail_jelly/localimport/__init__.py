# JG base libs
from base import *
from base.littles import *

# JG constants
from base.constants import *

# JG modules
from jgscan.jgsql import jellyDB
from kodi_services import getKodiInfo, extract_triplets, lowersArray, extract_triplets_audio
from jg_services import premium_timeleft

# libs
from pathlib import Path
from typing import Optional
import signal

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
'''
def getActualPath(vpath, jgDB):
    for (actual_path,) in jgDB.get_path_actual(vpath):
        return actual_path
    return None
'''


def criteriaQualification(vfn):
    nLmatches = lowersArray(extract_triplets(vfn))

    anLmatches = lowersArray(extract_triplets_audio(vfn))

    Qpol = 0
    Lpol = 0
    L2pol = 0

    if 'UHD' in vfn or '2160p' in vfn or '2159p' in vfn or '2158p' in vfn or '2157p' in vfn or '2156p' in vfn:
        Qpol = 2
    elif 'FHD' in vfn or '1080p' in vfn or '1079p' in vfn or '1078p' in vfn or '1077p' in vfn or '1076p' in vfn:
        Qpol = 1


    if PREFLANG in anLmatches:
        Lpol = 2
    elif PREFLANG in nLmatches:
        Lpol = 1

    if PREFLANG2 in anLmatches:
        L2pol = 2
    elif PREFLANG2 in nLmatches:
        L2pol = 1


    # returns a tuple : vfn, Q_pol, L_Pol

    return (vfn, Qpol, Lpol, L2pol)



def globalLevelExtractor(vfn, uhdarray, hdarray, sdarray):

    nLmatches = lowersArray(extract_triplets(vfn))

    #matchb = re.search(r'(\d+)Mbps', vfn)

    if 'UHD' in vfn or '2160p' in vfn or '2159p' in vfn or '2158p' in vfn or '2157p' in vfn or '2156p' in vfn:
        if PREFLANG in nLmatches:
            uhdarray.append(2)
        else:
            uhdarray.append(1)

    elif 'FHD' in vfn or '1080p' in vfn or '1079p' in vfn or '1078p' in vfn or '1077p' in vfn or '1076p' in vfn:
        if PREFLANG in nLmatches:
            hdarray.append(2)
        else:
            hdarray.append(1)
    else:
        if PREFLANG in nLmatches:
            sdarray.append(2)
        else:
            sdarray.append(1)


def setPolicy(parentPaths, Qpolicy, Lpolicy):
    jgDB = jellyDB()

    for path in parentPaths:
        logger.info(f"LOC_IMPORT| Setting policy for virtual path {path} to Qpolicy {Qpolicy} and Lpolicy {Lpolicy}")
        jgDB.lc_set_policy_virtual_folder(path, Qpolicy, Lpolicy, 0)

    jgDB.sqcommit()

    jgDB.sqclose()

'''
def setCompletion(path, comp):
    jgDB = jellyDB()
    jgDB.lc_set_dl_completion_specific(path, comp)
    jgDB.sqcommit()
    jgDB.sqclose()

def getDlPlaylist():
    jgDB = jellyDB()
    result = jgDB.lc_get_dl_playlist()
    jgDB.sqclose()

    return result
'''

def rsync_partial_download_sync_strict_progress(
    source: str,
    dest_final: Path,
    *,
    stop_event: threading.Event,
    rsync_path: str = "rsync",
    idle_timeout_s: float = 30.0,
    temp_suffix: str = ".part",
    stat_interval_s: float = 0.5,
) -> int:
    """
    Return codes:
      -1 : error / timeout / rsync failed
       1 : stopped by external stop_event
       2 : completed successfully
    """
    dest_part = dest_final.with_name(dest_final.name + temp_suffix)
    dest_part.parent.mkdir(parents=True, exist_ok=True)

    args = [
        rsync_path,
        "--partial",
        "--no-inc-recursive",
        "--inplace",
        str(source),
        str(dest_part),
    ]

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        bufsize=0,
        preexec_fn=os.setsid,
    )

    logger.info(f"  DOWNLOAD| from {str(source)} TO {str(dest_part)}")

    last_progress_ts = time.monotonic()
    last_size: Optional[int] = None

    def safe_get_size() -> int:
        try:
            return dest_part.stat().st_size
        except FileNotFoundError:
            return 0
        except Exception:
            return -1

    def terminate_process():
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            proc.wait()

    def delete_part_file():
        try:
            dest_part.unlink(missing_ok=True)
            logger.info(f"  DOWNLOAD| Deleted partial file {dest_part}")
        except Exception as e:
            logger.warning(f"  DOWNLOAD| Failed to delete partial file {dest_part}: {e}")

    try:
        while True:
            if stop_event.is_set():
                logger.info("  DOWNLOAD| stopped!")
                terminate_process()
                return 1

            if proc.poll() is not None:
                logger.info("  DOWNLOAD| completed!")
                break

            sz = safe_get_size()
            if sz >= 0:
                if last_size is None:
                    last_size = sz
                    last_progress_ts = time.monotonic()
                elif sz > last_size:
                    last_size = sz
                    last_progress_ts = time.monotonic()

            if (time.monotonic() - last_progress_ts) > idle_timeout_s:
                logger.info("  DOWNLOAD| fails (idle timeout), cleaning up part file")
                terminate_process()
                delete_part_file()
                return -1

            time.sleep(stat_interval_s)

        rc = proc.wait()
        if rc != 0:
            return -1

        os.replace(dest_part, dest_final)
        logger.info(f"  DOWNLOAD| Done, final renaming to {str(dest_final)} and db changes")
        return 2

    finally:
        terminate_process()

def importUncompleted(stopctxevent):

    #check first if internet is reachable
    if not has_internet():
        logger.error('  DOWNLOAD| Cloudlfare not working, importer halted.')
        return
    
    logger.info('  DOWNLOAD| Cloudflare working, starting importer...')

    # get dl playlist
    jgDB = jellyDB()

    

    if result := jgDB.lc_get_dl_playlist():

        # blacklist live array
        bl_noext_items = []

        for (vpath, apath, comp) in result:
            if stopctxevent.is_set():
                break
            # check bl live array, not checking a file coming from same release as a blacklisted file
            if get_wo_ext(vpath) not in bl_noext_items and "remote" in apath.split("/", 2)[2]:

                jgDB.lc_set_dl_completion_specific(vpath, 1)

            
                # create parent folders
                # convention is : 2 first parts is mountpoint
                src = Path(apath)
                src_mountpoint = Path(*src.parts[:3])   # ('/', 'mnt', 'data')
                relative = src.relative_to(src_mountpoint)
                dst_mountpoint = Path("/mounts/local_import")
                dst_path = dst_mountpoint / relative


                #dst_path.parent.mkdir(parents=True, exist_ok=True)
                #rsync_dest_part = dst_path.with_name(dst_path.name + ".part")
                resdl = rsync_partial_download_sync_strict_progress(
                    src,
                    dst_path,
                    stop_event=genericClass.getEvent(),
                    idle_timeout_s=30,
                )
                if resdl == -1:
                    if premium_timeleft() != 0:
                        bl_noext_items.append(get_wo_ext(vpath))
                        jgDB.lc_update_blacklist(vpath)

                        
                elif resdl == 2:
                    jgDB.lc_set_dl_completion_specific(vpath, 2)
                    jgDB.lc_update_actual_path(vpath, str(dst_path))
                

                #else

                


            '''
            # start DL in async
            # ARGSko
            args = [
                "rsync",
                "--partial",
                "--info=progress2",
                "--no-inc-recursive",  # helps make progress2 updates more consistent for some cases
                src,
                str(rsync_dest_part),
            ]
            '''




        jgDB.sqcommit()
    jgDB.sqclose()


_SXXEYY_RE = re.compile(r"(S\d{1,2}E\d{1,2})", re.IGNORECASE)

def sxxeyy_key(vfn: str) -> str:
    """
    Retourne une clé normalisée 's01e02' depuis vfn.
    Si pas trouvé, fallback: vfn entier (ça évite de tout mélanger).
    """
    m = _SXXEYY_RE.search(vfn or "")
    return m.group(1).lower() if m else (vfn or "").lower()


def computePolicies():
    jgDB = jellyDB()

    for (parentPath, Qpolicy, Lpolicy, pcomp) in jgDB.lc_ls_parent_paths():

        # groups: key 's01e02' -> list[(storage, vfn, Qpol, Lpol, L2pol, ...)]
        groups = {}
        # avoid jgxmultiple and jgxbluray ! (toimprove)
        if "JGxBluRay" in parentPath or "JGxMultiple" in parentPath:
            continue

        # 1) collect + group by SxxEyy
        for (vfn, actual_path, dlcomp) in jgDB.lc_ls_virtual_folder(parentPath):

            
            # LOCAL / REMOTE (ta logique)
            if "remote" not in actual_path.split("/", 2)[2]:
                storage = 1
            else:
                storage = 0

            cand = (storage, *criteriaQualification(vfn))
            key = sxxeyy_key(vfn)
            groups.setdefault(key, []).append(cand)

        # si aucun épisode/candidat
        if not groups:
            jgDB.lc_update_policy_completion(parentPath, 1)
            jgDB.sqcommit()
            continue

        finalCandidatesTuples = []

        # 2) apply A/B/C per episode-group
        for key, candidateVPath_Tuples in groups.items():
            if not candidateVPath_Tuples:
                continue

            # A/ Qpol ASC, Lpol DESC
            finalCandidatesTuples.append(
                min(candidateVPath_Tuples, key=lambda t: (t[2], -t[3]))
            )

            # B/ Qpol DESC, Lpol DESC (si Qpolicy == 2 et qu'il existe un Qpol==2 dans CE groupe)
            if Qpolicy == 2 and any(t[2] == 2 for t in candidateVPath_Tuples):
                finalCandidatesTuples.append(
                    min(candidateVPath_Tuples, key=lambda t: (-t[2], -t[3]))
                )

            # C/ Lpol DESC, Qpol ANY (tu as tie-break Qpol ASC)
            if Lpolicy == 2 and any(t[3] == 2 for t in candidateVPath_Tuples):
                finalCandidatesTuples.append(
                    min(candidateVPath_Tuples, key=lambda t: (-t[3], t[2]))
                )

        # 3) dédup global (tu acceptes perte d'ordre)
        finalCandidatesTuples = list(set(finalCandidatesTuples))

        # 4) remote => dl_completion = 0
        for cand in finalCandidatesTuples:
            if cand[0] == 0:
                jgDB.lc_set_dl_completion(get_wo_ext(cand[1]), 0)

        # 5) mark completion
        jgDB.lc_update_policy_completion(parentPath, 1)
        jgDB.sqcommit()

    jgDB.sqclose()


# called in executor
def getMenuItems(mediatype, mediaid, uid):


    ctMenu = {}
    ctMenu['payload'] = []
    ctMenu['menu'] = {}

    parentList = []

    R_HD_lang_level = []
    R_UHD_lang_level = []
    R_SD_lang_level = []

    L_UHD_lang_level = []
    L_HD_lang_level = []
    L_SD_lang_level = []

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

        parentList = list(set(parentList))

        

    if mediatype == "season":
        seasonnb = result[0].get("season")
        seasonstr = f"{seasonnb:02d}"

        seasonParentList = [path+f"/Season {seasonstr}" for path in parentList]

        ctMenu['payload'] = seasonParentList

        ctMenu['menu'][f'{Title} Season {seasonstr}'] = "#NULL"

    elif mediatype == "movie":
        


        #unique
        

        ctMenu['payload'] = parentList

        #logger.info(f"menubuilder       | Found parent paths: {parentList}")

        ## LS each parentpath to get all actualpaths and completion status

        jgDB = jellyDB()

        for path in parentList:
            for (vfn,actual_path,_) in jgDB.lc_ls_virtual_folder(path):

                if actual_path:
                    #logger.info(f"menubuilder       | Found virtual filename {vfn} in virtual folder {path} mapped to actual path {actual_path}")

                    #logger.info(f"menubuilder       | actual_path split: {actual_path.split('/',2)}")
                    # LOCAL
                    if "remote" not in actual_path.split("/", 2)[2]:
                        globalLevelExtractor(vfn, L_UHD_lang_level, L_HD_lang_level, L_SD_lang_level)

                    # REMOTE
                    else:
                        globalLevelExtractor(vfn, R_UHD_lang_level, R_HD_lang_level, R_SD_lang_level)
        jgDB.sqclose()

        # build information string based on findings
        final_L_UHD_lang_level = max(L_UHD_lang_level) if L_UHD_lang_level else 0
        final_L_HD_lang_level = max(L_HD_lang_level) if L_HD_lang_level else 0
        final_R_UHD_lang_level = max(R_UHD_lang_level) if R_UHD_lang_level else 0
        final_R_HD_lang_level = max(R_HD_lang_level) if R_HD_lang_level else 0
        final_R_SD_lang_level = max(R_SD_lang_level) if R_SD_lang_level else 0
        final_L_SD_lang_level = max(L_SD_lang_level) if L_SD_lang_level else 0



        L_info_tpl = "Local:"
        L_info_tpl += " UHD" if final_L_UHD_lang_level > 0 else ""
        L_info_tpl += f" with {PREFLANG}" if final_L_UHD_lang_level > 1 else ""
        L_info_tpl += ", FHD" if final_L_HD_lang_level > 0 else ""
        L_info_tpl += f" with {PREFLANG}" if final_L_HD_lang_level > 1 else ""
        L_info_tpl += ", HD" if final_L_SD_lang_level > 0 else ""
        L_info_tpl += f" with {PREFLANG}" if final_L_SD_lang_level > 1 else ""

        R_info_tpl = "Remote:"
        R_info_tpl += " UHD" if final_R_UHD_lang_level > 0 else ""
        R_info_tpl += f" with {PREFLANG}" if final_R_UHD_lang_level > 1 else ""
        R_info_tpl += ", FHD" if final_R_HD_lang_level > 0 else ""
        R_info_tpl += f" with {PREFLANG}" if final_R_HD_lang_level > 1 else ""
        R_info_tpl += ", HD" if final_R_SD_lang_level > 0 else ""
        R_info_tpl += f" with {PREFLANG}" if final_R_SD_lang_level > 1 else ""

        ctMenu['menu'][f'{Title}'] = "#NULL"
        ctMenu['menu'][f"{L_info_tpl}"] = "#NULL"
        ctMenu['menu'][f"{R_info_tpl}"] = "#NULL"
        


    ctMenu['menu']['----------'] = "#NULL"
    ctMenu['menu'][f'KEEP this {mediatype}'] = "#KEEPLOCAL"
    ctMenu['menu'][f'KEEP this {mediatype} + 4K'] = "#KEEPLOCALUHD"

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
    