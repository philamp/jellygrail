import urllib
import time
import jfapi
from jfconfig.jfsql import *
from base import *
from base.constants import *

JF_COUNTRY = os.getenv('JF_COUNTRY') or DEFAULT_JF_COUNTRY
JF_LANGUAGE = os.getenv('JF_LANGUAGE') or DEFAULT_JF_LANGUAGE
JF_LOGIN = os.getenv('JF_LOGIN') or "admin"
JF_PASSWORD = os.getenv('JF_PASSWORD') or "admin"

def jellystart(path, method='get', **kwargs):
    
    resp = jfapi.jellyfin_req(path, method, **kwargs)
    if resp is not None and (resp.status_code == 200 or resp.status_code == 204):
        logger.info(f"  JELLYFIN/ First setup step at {path} done.")
        return True

    logger.critical(f"  JELLYFIN/ First setup failed at {path}, status code: {resp.status_code}.")
    return False

def is_jf_available():
    logger.info("  JELLYFIN/ Starting... (waiting API up to 2mn max)")
    iwait = 0
    while iwait < 40:
        iwait += 1
        try:
            if not urllib.request.urlopen('http://localhost:8096/health').read() == b'Healthy':
                logger.debug(f". Waiting for Jellyfin to be available: try {iwait} ...")
                time.sleep(3)
                continue
        except OSError as e:
            logger.debug(f". Waiting for Jellyfin to be available: try {iwait} ...")
        else:
            logger.info("  JELLYFIN/ ...Successfully started")
            return True
        time.sleep(3)

    if iwait >= 20:
        logger.warning("  JELLYFIN/ seems absent... docker will now restart to retry. Please check logs with 'docker logs jellygrail -f'")
    return False

# ----

def jfconfig():
    jfapi.jf_login = JF_LOGIN
    jfapi.jf_password = JF_PASSWORD
    # check if Jellyfin is available
    if is_jf_available():
        return jfsetup_req()
    else:
        return False
    
def jfsetup_req():
    # at this point, jfapikey is None, so we are not authenticated yet, so jellyfin_req will not add a token to the header
    if jfapi.jellyfin_req(method='get', path='Startup/Configuration').status_code == 200:

        logger.info("  JELLYFIN/ First setup...")

        if not (
            jellystart('Startup/Configuration', method='post', json={
                "UICulture": "en-US",
                "MetadataCountryCode": JF_COUNTRY,
                "PreferredMetadataLanguage": JF_LANGUAGE
            }) and
            jellystart('Startup/User', method='post', json={
                "Name": JF_LOGIN,
                "Password": JF_PASSWORD
            }) and
            jellystart('Startup/Complete', method='post')
        ):
            logger.critical("  JELLYFIN/ First setup globally failed.")
            return False

    else:
        logger.info("  JELLYFIN/ First setup already done")

    # go on with config for JG
    return jfconfig_forjg()

def jfconfig_forjg():

    if not install_addons():
        return False
    
    if is_jf_available(): # cause we restrarted jellyfin
        if not install_librairies():
            return False
    else:
        return False
    
    return True



def install_addons():

    if declaredrepos := jfapi.jellyfin(f'Repositories', method='get').json():
        if len(declaredrepos) < 2:
            #add subbuzz
            declaredrepos.append({
                "Name": "subbuzz",
                "Url": "https://raw.githubusercontent.com/josdion/subbuzz/master/repo/jellyfin_10.10.json",
                "Enabled": True
            })

            if not (
                jfapi.jellyfin(f'Repositories', json=declaredrepos, method='post')
                and jfapi.jellyfin(f'Packages/Installed/Kodi%20Sync%20Queue', method='post')
                and jfapi.jellyfin(f'Packages/Installed/subbuzz', method='post')
                and jfapi.jellyfin(f'ScheduledTasks/4e6637c832ed644d1af3370a2506e80a/Triggers', json=[], method='post')
                and jfapi.jellyfin(f'ScheduledTasks/2c66a88bca43e565d7f8099f825478f1/Triggers', json=[], method='post')
            ):
                logger.critical("  JELLYFIN/ Add-ons installation failed.")
                return False
            
            jfapi.jellyfin(f'System/Shutdown', method='post')

        return True
    else:
        return False


def install_librairies():

    MetaSwitch = [
        "TheMovieDb",
        "The Open Movie Database",
    ]
    MetaSwitchTMDBonly = [
        "TheMovieDb",
    ]

    if declaredlibs := jfapi.jellyfin(f'Library/VirtualFolders', method='get').json():
        if not any(f"{JG_VIRTUAL}/movies" in (dlibs.get("Locations") or []) for dlibs in declaredlibs):


            #logger.info("> Now we can add Librariries")
            movielib = {
                "LibraryOptions": {
                    "PreferredMetadataLanguage": JF_LANGUAGE,
                    "MetadataCountryCode": JF_COUNTRY,
                    "EnableRealtimeMonitor": False,
                    "EnableChapterImageExtraction": False,
                    "ExtractChapterImagesDuringLibraryScan": False,
                    "AutomaticallyAddToCollection": True,
                    "MetadataSavers": [],
                    "DisabledSubtitleFetchers": [
                        "subbuzz"
                    ],
                    "SubtitleDownloadLanguages": USED_LANGS_JF,
                    "RequirePerfectSubtitleMatch": False,
                    "SaveSubtitlesWithMedia": True,
                    "AllowEmbeddedSubtitles": "AllowAll",
                    "PathInfos": [
                        {
                            "Path": f"{JG_VIRTUAL}/movies",
                            "NetworkPath": ""
                        }
                    ],
                    "TypeOptions": [
                        {
                            "Type": "Movie",
                            "MetadataFetchers": MetaSwitch,
                            "MetadataFetcherOrder": MetaSwitch,
                            "ImageFetchers": MetaSwitch,
                            "ImageFetcherOrder": MetaSwitch,
                            "ImageOptions": []
                        }
                    ]
                }
            }

            if not jfapi.jellyfin(f'Library/VirtualFolders', json=movielib, method='post', params=dict(
                name='Movies', collectionType="movies", paths=f"{JG_VIRTUAL}/movies", refreshLibrary=False
            )):
                logger.critical("  JELLYFIN/ Movies library installation failed.")
                return False
            
        if not any(f"{JG_VIRTUAL}/shows" in (dlibs.get("Locations") or []) for dlibs in declaredlibs):
            tvshowlib = {
                "LibraryOptions": {
                    
                    "PreferredMetadataLanguage": JF_LANGUAGE,
                    "MetadataCountryCode": JF_COUNTRY,
                    "EnableRealtimeMonitor": False,
                    "EnableAutomaticSeriesGrouping": False, #otherwise a metadata mistake is impossible to fix
                    "EnableChapterImageExtraction": False,
                    "ExtractChapterImagesDuringLibraryScan": False,
                    "MetadataSavers": [],
                    "DisabledSubtitleFetchers": [
                        "subbuzz"
                    ],
                    "SubtitleDownloadLanguages": USED_LANGS_JF,
                    "RequirePerfectSubtitleMatch": False,
                    "SaveSubtitlesWithMedia": True,
                    "AllowEmbeddedSubtitles": "AllowAll",
                    "PathInfos": [
                        {
                            "Path": f"{JG_VIRTUAL}/shows",
                            "NetworkPath": ""
                        }
                    ],
                    "TypeOptions": [
                        {
                            "Type": "Series",
                                "MetadataFetchers": MetaSwitch,
                            "MetadataFetcherOrder": MetaSwitch,
                            "ImageFetchers": MetaSwitchTMDBonly,
                            "ImageFetcherOrder": MetaSwitchTMDBonly,
                            "ImageOptions": []
                        },
                        {
                            "Type": "Season",
                            "MetadataFetchers": MetaSwitchTMDBonly,
                            "MetadataFetcherOrder": MetaSwitchTMDBonly,
                            "ImageFetchers": MetaSwitchTMDBonly,
                            "ImageFetcherOrder": MetaSwitchTMDBonly,
                            "ImageOptions": []
                        },                            
                        {
                            "Type": "Episode",
                            "MetadataFetchers": MetaSwitch,
                            "MetadataFetcherOrder": MetaSwitch,
                            "ImageFetchers": MetaSwitch,
                            "ImageFetcherOrder": MetaSwitch,
                            "ImageOptions": []
                        }
                    ]
                }
            }


            if not jfapi.jellyfin(f'Library/VirtualFolders', json=tvshowlib, method='post', params=dict(
                name='Shows', collectionType="tvshows", paths=f"{JG_VIRTUAL}/shows", refreshLibrary=False
            )):
                logger.critical("  JELLYFIN/ Shows library installation failed.")
                return False
    
    jfapi.jellyfin(f'ScheduledTasks/7738148ffcd07979c7ceb148e06b3aed/Triggers', json=[], method='post') # disable libraryscan as well
    return True