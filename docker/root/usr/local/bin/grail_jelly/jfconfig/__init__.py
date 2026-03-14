import urllib
import time
import jfapi
#from jfconfig.jfsql import * DEPRECATED
from base import *
from base.constants import *

JF_COUNTRY = os.getenv('JF_COUNTRY') or DEFAULT_JF_COUNTRY
JF_LANGUAGE = os.getenv('JF_LANGUAGE') or DEFAULT_JF_LANGUAGE
JF_LOGIN = os.getenv('JF_LOGIN') or "admin"
JF_PASSWORD = os.getenv('JF_PASSWORD') or "admin"

def jellystart(path, method='get', **kwargs):
    
    resp = jfapi.jellyfin_req(path, method, **kwargs)
    if resp is not None and (resp.status_code == 200 or resp.status_code == 204):
        logger.info(f"  JELLYFIN| ...@ {path} done.")
        return True

    logger.critical(f"  JELLYFIN| First setup failed at {path}, status code: {resp.status_code}.")
    return False

def is_jf_available():
    logger.info("  JELLYFIN| API Ping...")
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
            #logger.info("  JELLYFIN| ...Successfully started")
            if resp := jfapi.jellyfin_req(method='get', path='System/Info/Public'):
                if resp.status_code == 200:
                    if resp.json().get('ServerName') is not None:
                        return True
            # else
            logger.critical("  JELLYFIN| seems present but API calls fail...")
        time.sleep(3)

    if iwait >= 20:
        logger.warning("  JELLYFIN| seems absent... docker will now restart to retry. Please check logs with 'docker logs jellygrail -f'")
    return False

# ----

def jfconfig():
    jfapi.jf_login = JF_LOGIN
    jfapi.jf_password = JF_PASSWORD
    # check if Jellyfin is available
    if is_jf_available(): #JG STARTUP
        return jfsetup_req()
    else:
        logger.critical("  JELLYFIN| Config failed, please stop the container and fix the error. If login/password lost, you can reset Jellyfin by emptying /jellygrail/jellyfin/config and /jellygrail/jellyfin/cache folders but it will remove all your Jellyfin libraries, configuration and users.")
        return False
    
def jfsetup_req():
    # at this point, jfapikey is None, so we are not authenticated yet, so jellyfin_req will not add a token to the header
    if jfapi.jellyfin_req(method='get', path='Startup/Configuration').status_code == 200:

        logger.info("  JELLYFIN| First setup...")

        if not (
            jellystart('Startup/Configuration', method='post', json={
                "UICulture": "en-US",
                "MetadataCountryCode": JF_COUNTRY,
                "PreferredMetadataLanguage": JF_LANGUAGE
            }) and
            jellystart('Startup/User', method='get') and
            jellystart('Startup/User', method='post', json={
                "Name": JF_LOGIN,
                "Password": JF_PASSWORD
            }) and
            jellystart('Startup/Complete', method='post')
        ):
            logger.critical("  JELLYFIN| First setup globally failed.")
            return False
        else:
            if not is_jf_available():
                return False

    else:
        logger.info("  JELLYFIN| First setup already done")

    # go on with config for JG
    return jfconfig_forjg()

def jfconfig_forjg():
    if not install_addons():
        return False
    if not install_librairies():
        return False
    return True

def install_addons():

    if declaredrepos := jfapi.jellyfin(f'Repositories', method='get'):
        declaredrepos = declaredrepos.json()
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
                logger.critical("  JELLYFIN| Add-ons installation failed.")
                return False
            else:
                logger.info("  JELLYFIN| Add-ons installed.")
            
            logger.info("  JELLYFIN| Restarting to finalize add-ons installation... (3s)")
            jfapi.jellyfin(f'System/Shutdown', method='post')
            time.sleep(3)
            if is_jf_available():
                return True
            else:
                return False
        else:
            return True
    else:
        return False


def install_librairies():

    at_least_one_installed = False

    MetaSwitch = [
        "TheMovieDb",
        "The Open Movie Database"
    ]
    MetaSwitchTMDBonly = [
        "TheMovieDb"
    ]

    if declaredlibs := jfapi.jellyfin(f'Library/VirtualFolders', method='get'):
        declaredlibs = declaredlibs.json()
        if not any(f"{JG_VIRTUAL}/movies" in (dlibs.get("Locations") or []) for dlibs in declaredlibs):


            #logger.info("> Now we can add Librariries")
            movielib = {
                "LibraryOptions": {
                    "Enabled": True,
                    "EnableArchiveMediaFiles": False,
                    "EnablePhotos": True,
                    "EnableRealtimeMonitor": False,
                    "EnableLUFSScan": True,
                    "ExtractTrickplayImagesDuringLibraryScan": False,
                    "SaveTrickplayWithMedia": False,
                    "EnableTrickplayImageExtraction": False,
                    "ExtractChapterImagesDuringLibraryScan": False,
                    "EnableChapterImageExtraction": False,
                    "EnableInternetProviders": True,
                    "SaveLocalMetadata": False,
                    "EnableAutomaticSeriesGrouping": False,
                    "PreferredMetadataLanguage": JF_LANGUAGE,
                    "MetadataCountryCode": JF_COUNTRY,
                    "SeasonZeroDisplayName": "Specials",
                    "AutomaticRefreshIntervalDays": 0,
                    "EnableEmbeddedTitles": False,
                    "EnableEmbeddedExtrasTitles": False,
                    "EnableEmbeddedEpisodeInfos": False,
                    "AllowEmbeddedSubtitles": "AllowAll",
                    "SkipSubtitlesIfEmbeddedSubtitlesPresent": False,
                    "SkipSubtitlesIfAudioTrackMatches": False,
                    "SaveSubtitlesWithMedia": True,
                    "SaveLyricsWithMedia": False,
                    "RequirePerfectSubtitleMatch": True,
                    "AutomaticallyAddToCollection": True,
                    "PreferNonstandardArtistsTag": False,
                    "UseCustomTagDelimiters": False,
                    "MetadataSavers": [],
                    "TypeOptions": [
                        {
                            "Type": "Movie",
                            "MetadataFetchers": MetaSwitch,
                            "MetadataFetcherOrder": MetaSwitch,
                            "ImageFetchers": MetaSwitch,
                            "ImageFetcherOrder": MetaSwitch
                        }
                    ],
                    "LocalMetadataReaderOrder": [
                        "Nfo"
                    ],
                    "SubtitleDownloadLanguages": list(USED_LANGS_JF),
                    "CustomTagDelimiters": [
                        "/",
                        "|",
                        ";",
                        "\\"
                    ],
                    "DelimiterWhitelist": [],
                    "DisabledSubtitleFetchers": [
                        "subbuzz"
                    ],
                    "SubtitleFetcherOrder": [
                        "subbuzz"
                    ],
                    "DisabledLyricFetchers": [],
                    "LyricFetcherOrder": [],
                    "PathInfos": [
                        {
                            "Path": f"{JG_VIRTUAL}/movies"
                        }
                    ]
                }
            }

            if not jfapi.jellyfin(f'Library/VirtualFolders', json=movielib, method='post', params=dict(
                name='Movies', collectionType="movies", refreshLibrary="true"
            )):
                logger.critical("  JELLYFIN| Movies library installation failed")
                return False
            else:
                logger.info("  JELLYFIN| Movie Library installed")
                at_least_one_installed = True
            
        if not any(f"{JG_VIRTUAL}/shows" in (dlibs.get("Locations") or []) for dlibs in declaredlibs):
            tvshowlib = {
                "LibraryOptions": {
                    "Enabled": True,
                    "EnableArchiveMediaFiles": False,
                    "EnablePhotos": True,
                    "EnableRealtimeMonitor": False,
                    "EnableLUFSScan": True,
                    "ExtractTrickplayImagesDuringLibraryScan": False,
                    "SaveTrickplayWithMedia": False,
                    "EnableTrickplayImageExtraction": False,
                    "ExtractChapterImagesDuringLibraryScan": False,
                    "EnableChapterImageExtraction": False,
                    "EnableInternetProviders": True,
                    "SaveLocalMetadata": False,
                    "EnableAutomaticSeriesGrouping": False,
                    "PreferredMetadataLanguage": JF_LANGUAGE,
                    "MetadataCountryCode": JF_COUNTRY,
                    "SeasonZeroDisplayName": "Specials",
                    "AutomaticRefreshIntervalDays": 0,
                    "EnableEmbeddedTitles": False,
                    "EnableEmbeddedExtrasTitles": False,
                    "EnableEmbeddedEpisodeInfos": False,
                    "AllowEmbeddedSubtitles": "AllowAll",
                    "SkipSubtitlesIfEmbeddedSubtitlesPresent": False,
                    "SkipSubtitlesIfAudioTrackMatches": False,
                    "SaveSubtitlesWithMedia": True,
                    "SaveLyricsWithMedia": False,
                    "RequirePerfectSubtitleMatch": True,
                    "AutomaticallyAddToCollection": False,
                    "PreferNonstandardArtistsTag": False,
                    "UseCustomTagDelimiters": False,
                    "MetadataSavers": [],
                    "TypeOptions": [
                        {
                            "Type": "Series",
                            "MetadataFetchers": MetaSwitch,
                            "MetadataFetcherOrder": MetaSwitch,
                            "ImageFetchers": MetaSwitchTMDBonly,
                            "ImageFetcherOrder": MetaSwitchTMDBonly
                        },
                        {
                            "Type": "Season",
                            "MetadataFetchers": MetaSwitchTMDBonly,
                            "MetadataFetcherOrder": MetaSwitchTMDBonly,
                            "ImageFetchers": MetaSwitchTMDBonly,
                            "ImageFetcherOrder": MetaSwitchTMDBonly
                        },
                        {
                            "Type": "Episode",
                            "MetadataFetchers": MetaSwitch,
                            "MetadataFetcherOrder": MetaSwitch,
                            "ImageFetchers": MetaSwitch,
                            "ImageFetcherOrder": MetaSwitch
                        }
                    ],
                    "LocalMetadataReaderOrder": [
                        "Nfo"
                    ],
                    "SubtitleDownloadLanguages": list(USED_LANGS_JF),
                    "CustomTagDelimiters": [
                        "/",
                        "|",
                        ";",
                        "\\"
                    ],
                    "DelimiterWhitelist": [],
                    "DisabledSubtitleFetchers": [],
                    "DisabledSubtitleFetchers": [
                        "subbuzz"
                    ],
                    "SubtitleFetcherOrder": [
                        "subbuzz"
                    ],
                    "DisabledLyricFetchers": [],
                    "LyricFetcherOrder": [],
                    "PathInfos": [
                        {
                            "Path": f"{JG_VIRTUAL}/shows"
                        }
                    ]
                }
            }

            
            if not jfapi.jellyfin(f'Library/VirtualFolders', json=tvshowlib, method='post', params=dict(
                name='Shows', collectionType="tvshows", refreshLibrary="true"
            )):
                logger.critical("  JELLYFIN| TVShows library installation failed")
                return False
            
            else:
                logger.info("  JELLYFIN| TVShows Library installed")
                at_least_one_installed = True
        if at_least_one_installed:
            logger.info("  JELLYFIN| 500 errors below are ok, don't worry")
            jfapi.jellyfin(f'ScheduledTasks/Running/7738148ffcd07979c7ceb148e06b3aed', method='delete') # should not stat right away, should stop for virtual folder to be completed first
            logger.info("  JELLYFIN| First autoscan halted. Will be managed by JellyGrail later")

            if systemconf := jfapi.jellyfin(f'System/Configuration', method='get'):
                systemconf = systemconf.json()
                systemconf['LibraryScanFanoutConcurrency'] = 2
                systemconf['LibraryMetadataRefreshConcurrency'] = 2
                jfapi.jellyfin(f'System/Configuration', json=systemconf, method='post')

    jfapi.jellyfin(f'ScheduledTasks/7738148ffcd07979c7ceb148e06b3aed/Triggers', json=[], method='post') # disable libraryscan as well

    

    return True
