import urllib
import time
import jfapi
from jfconfig.jfsql import *
from base import *
from base.constants import *

JF_COUNTRY = os.getenv('JF_COUNTRY') or DEFAULT_JF_COUNTRY
JF_LANGUAGE = os.getenv('JF_LANGUAGE') or DEFAULT_JF_LANGUAGE
JF_LOGIN = os.getenv('JF_LOGIN') or "admin"
JF_PASSWORD = os.getenv('JF_PASSWORD')

def jfconfig():
    # check if Jellyfin is available
    if is_jf_available():
        return jfsetup_req()
    else:
        return "ZERO-RUN"

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

def jfsetup_req():
    if jfapi.jellyfin_req(method='get', path='Startup/Configuration').status_code != 200:

        logger.info("  JELLYFIN/ First setup...")

        # set language and country
        json_payload = {
            "UICulture": "en-US",
            "MetadataCountryCode": JF_COUNTRY,
            "PreferredMetadataLanguage": JF_LANGUAGE
        }
        try:
            jfapi.jellyfin_req('Startup/Configuration', method='post', json=json_payload)
        except Exception as e:
            logger.critical(f"  JELLYFIN/ FAILURE to set language and country: {e}")
            return "ZERO-RUN"
        time.sleep(1)

        # set username and password
        json_payload = {
            "Name": JF_LOGIN,
            "Password": JF_PASSWORD
        }
        try:
            jfapi.jellyfin_req('Startup/User', method='post', json=json_payload)
        except Exception as e:
            logger.critical(f"  JELLYFIN/ FAILURE to set username and password: {e}")
            return "ZERO-RUN"
        time.sleep(1)

        # complete setup
        try:
            jfapi.jellyfin_req('Startup/Complete', method='post')
        except Exception as e:
            logger.critical(f"  JELLYFIN/ FAILURE to set username and password: {e}")
            return "ZERO-RUN"
        time.sleep(1)

    else:
        logger.info("  JELLYFIN/ First setup already done")

    # go on with config
    return jfconfig_forjg()


# get Token and forced config
def jfconfig_forjg():


    triggerdata = []

    # Whole JF config --------------------------
    if urllib.request.urlopen('http://localhost:8096/health').read() == b'Healthy':

        # 1 - Install repo if necessary
        # get list of repos, if len < 3, re-declare
        time.sleep(1)
        declaredrepos = jfapi.jellyfin(f'Repositories', method='get').json()
        if len(declaredrepos) < 2:
            #declare all repos
            repodata = [
                {
                    "Name": "Jellyfin Stable",
                    "Url": "https://repo.jellyfin.org/releases/plugin/manifest-stable.json",
                    "Enabled": True
                },
                {
                    "Name": "subbuzz",
                    "Url": "https://raw.githubusercontent.com/josdion/subbuzz/master/repo/jellyfin_10.8.json",
                    "Enabled": True
                }
            ]

            jfapi.jellyfin(f'Repositories', json=repodata, method='post')

            #install KSQ
            jfapi.jellyfin(f'Packages/Installed/Kodi%20Sync%20Queue', method='post')

            #install subbuzz
            jfapi.jellyfin(f'Packages/Installed/subbuzz', method='post')

            #delete unwanted triggers (chapter images and auto subtitle dl)
            jfapi.jellyfin(f'ScheduledTasks/4e6637c832ed644d1af3370a2506e80a/Triggers', json=triggerdata, method='post')
            jfapi.jellyfin(f'ScheduledTasks/2c66a88bca43e565d7f8099f825478f1/Triggers', json=triggerdata, method='post')

            logger.warning("  JELLYFIN/ Add-ons installed, \nThe container will now restart. \nBut if you did not put --restart unless-stopped in your run command, please execute: 'docker start thenameyougiven'")

            return "ZERO-RUN"
            # thanks to --restart unless-stopped, drawback: it will restart in a loop if it does not find 2 declared repos (toimprove: find a more resilient way to test it)
            # jfapi.jellyfin(f'System/Shutdown', method='post')


        else:
            declaredlibs = jfapi.jellyfin(f'Library/VirtualFolders', method='get').json()
            # (toimprove: find a more resilient way to test if libraries are declared)
            if len(declaredlibs) < 2:
                MetaSwitch = [
                    "TheMovieDb",
                    "The Open Movie Database",
                ]
                MetaSwitchTMDBonly = [
                    "TheMovieDb",
                ]
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
                        "SubtitleDownloadLanguages": [
                            "eng",
                            "fre"
                        ],
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
                jfapi.jellyfin(f'Library/VirtualFolders', json=movielib, method='post', params=dict(
                    name='Movies', collectionType="movies", paths=f"{JG_VIRTUAL}/movies", refreshLibrary=False
                ))

                concertlib = {
                    "LibraryOptions": {
                        "PreferredMetadataLanguage": JF_LANGUAGE,
                        "MetadataCountryCode": JF_COUNTRY,
                        "EnableRealtimeMonitor": False,
                        "EnableChapterImageExtraction": False,
                        "ExtractChapterImagesDuringLibraryScan": False,
                        "AutomaticallyAddToCollection": False,
                        "MetadataSavers": [],
                        "DisabledSubtitleFetchers": [
                            "subbuzz"
                        ],
                        "SubtitleDownloadLanguages": [
                            "eng",
                            "fre"
                        ],
                        "RequirePerfectSubtitleMatch": False,
                        "SaveSubtitlesWithMedia": True,
                        "AllowEmbeddedSubtitles": "AllowAll",
                        "PathInfos": [
                            {
                                "Path": f"{JG_VIRTUAL}/concerts",
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
                jfapi.jellyfin(f'Library/VirtualFolders', json=concertlib, method='post', params=dict(
                    name='Concerts', collectionType="movies", paths=f"{JG_VIRTUAL}/concerts", refreshLibrary=False
                ))

                tvshowlib = {
                    "LibraryOptions": {
                        
                        "PreferredMetadataLanguage": "fr",
                        "MetadataCountryCode": "FR",
                        "EnableRealtimeMonitor": False,
                        "EnableAutomaticSeriesGrouping": False, #otherwise a metadata mistake is impossible to fix
                        "EnableChapterImageExtraction": False,
                        "ExtractChapterImagesDuringLibraryScan": False,
                        "MetadataSavers": [],
                        "DisabledSubtitleFetchers": [
                            "subbuzz"
                        ],
                        "SubtitleDownloadLanguages": [
                            "eng",
                            "fre"
                        ],
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
                jfapi.jellyfin(f'Library/VirtualFolders', json=tvshowlib, method='post', params=dict(
                    name='Shows', collectionType="tvshows", paths=f"{JG_VIRTUAL}/shows", refreshLibrary=False
                ))
                jfapi.jellyfin(f'ScheduledTasks/7738148ffcd07979c7ceb148e06b3aed/Triggers', json=triggerdata, method='post') # disable libraryscan as well
                try:
                    jfapi.jellyfin(f'ScheduledTasks/dcaf151dd1af25aefe775c58e214477e/Triggers', json=triggerdata, method='post') # if installed disable merge episodes which is not working well
                except Exception as e:
                    logger.debug(". merging episodes already disabled")
                try:
                    jfapi.jellyfin(f'ScheduledTasks/fd957c84b0cfc2380becf2893e4b76fc/Triggers', json=triggerdata, method='post') # if installed disable merge movies which is not working well
                except Exception as e:
                    logger.debug(". merging movies already disabled")

                return "FIRST_RUN"
            logger.info("  JELLYFIN/ Repos and librairies configuration OK")
            logger.warning("  JELLYFIN/ Manual configuration reminder:\n - encoder in /web/index.html#!/encodingsettings.html\n - and opensub account in /web/index.html#!/configurationpage?name=SubbuzzConfigPage")
            
    return ""            
            
    # ---- end config
