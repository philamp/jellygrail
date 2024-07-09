import urllib
import time
import jfapi
from jfconfig.jfsql import *
from base import *

base_v_root = "/Video_Library/virtual"

JF_COUNTRY = os.getenv('JF_COUNTRY')
JF_LANGUAGE = os.getenv('JF_LANGUAGE')

def jfconfig():
    #global jfapikey

    # check if /jellygrail/jellyfin/config/data/jellyfin.db exists
    triggerdata = []
    proceedinjf = None

    iwait = 0
    while iwait < 20:
        iwait += 1
        try:
            if not urllib.request.urlopen('http://localhost:8096/health').read() == b'Healthy':
                logger.debug(f"... Jellyfin not yet available, try number {iwait} ...")
                time.sleep(3)
                continue
        except OSError as e:
            logger.debug(f"... Jellyfin not yet available, try number {iwait} ...")
        else:
            proceedinjf = True
            break
        time.sleep(3)

    if iwait >= 20:
        logger.warning("> Jellyfin is absent...will work without it, if you start it, restart the container as well so this script reboots")

    # Whole JF config --------------------------
    if proceedinjf and urllib.request.urlopen('http://localhost:8096/health').read() == b'Healthy':
    
        if os.path.exists("/jellygrail/jellyfin/config/data/jellyfin.db"):

            init_jellyfin_db("/jellygrail/jellyfin/config/data/jellyfin.db")
            
            array = [item[4] for item in fetch_api_key()]

            if len(array) > 0:
                
                jfapi.jfapikey = array[0]
                # logger.info(f"> retrieved API key is {jfapikey}")
                logger.info(f"> retrieved API key is ***")
            
            else:
                key = ''.join(random.choice('0123456789abcdef') for _ in range(32))
                insert_api_key(key)
                # logger.info(f"> Api Key {key} inserted")
                logger.info(f"> Api Key *** inserted")
                jfapi.jfapikey = key

            jfclose()
        
        else:
            logger.critical("There is an issue with jellyfin config db: not reachable")

        # 1 - Install repo if necessary
        # get list of repos, if len < 3, re-declare
        declaredrepos = jfapi.jellyfin(f'Repositories', method='get').json()
        if len(declaredrepos) < 3:
            #declare all repos
            repodata = [
                {
                    "Name": "Jellyfin Stable",
                    "Url": "https://repo.jellyfin.org/releases/plugin/manifest-stable.json",
                    "Enabled": True
                },
                {
                    "Name": "Merge",
                    "Url": "https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json",
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

            #install merge
            jfapi.jellyfin(f'Packages/Installed/Merge%20Versions', method='post')

            #delete unwanted triggers (chapter images and auto subtitle dl)
            jfapi.jellyfin(f'ScheduledTasks/4e6637c832ed644d1af3370a2506e80a/Triggers', json=triggerdata, method='post')
            jfapi.jellyfin(f'ScheduledTasks/2c66a88bca43e565d7f8099f825478f1/Triggers', json=triggerdata, method='post')

            logger.warning("> IMPORTANT: Jellyfin Additional plugins are installed and unefficient tasks are disabled, \nThe container will now restart. \nBut if you did not put --restart unless-stopped in your run command, please execute: 'docker start thenameyougiven'")

            return "ZERO-RUN"
            # thanks to --restart unless-stopped, drawback: it will restart in a loop if it does not find 3 declared repos (todo: find a more resilient way to test it)
            # jfapi.jellyfin(f'System/Shutdown', method='post')


        else:
            declaredlibs = jfapi.jellyfin(f'Library/VirtualFolders', method='get').json()
            # (todo: find a more resilient way to test if libraries are declared)
            if len(declaredlibs) < 2:
                MetaSwitch = [
                    "TheMovieDb",
                    "The Open Movie Database",
                ]
                MetaSwitchTMDBonly = [
                    "TheMovieDb",
                ]
                logger.info("> Now we can add Librariries")
                movielib = {
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
                                "Path": f"{base_v_root}/movies",
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
                    name='Movies', collectionType="movies", paths=f"{base_v_root}/movies", refreshLibrary=False
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
                                "Path": f"{base_v_root}/concerts",
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
                    name='Concerts', collectionType="movies", paths=f"{base_v_root}/concerts", refreshLibrary=False
                ))

                tvshowlib = {
                    "LibraryOptions": {
                        
                        "PreferredMetadataLanguage": "fr",
                        "MetadataCountryCode": "FR",
                        "EnableRealtimeMonitor": False,
                        "EnableAutomaticSeriesGrouping": True,
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
                                "Path": f"{base_v_root}/shows",
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
                    name='Shows', collectionType="tvshows", paths=f"{base_v_root}/shows", refreshLibrary=False
                ))
                # jfapi.jellyfin(f'ScheduledTasks/7738148ffcd07979c7ceb148e06b3aed/Triggers', json=triggerdata, method='post') # disable libraryscan as well
                jfapi.jellyfin(f'ScheduledTasks/dcaf151dd1af25aefe775c58e214477e/Triggers', json=triggerdata, method='post') # disable merge episodes which is not working well
                return "FIRST_RUN"

            logger.warning("> don't forget to configure : \n - encoder in /web/index.html#!/encodingsettings.html  \n - and opensub account in /web/index.html#!/configurationpage?name=SubbuzzConfigPage")
            
    return ""            
            
    # ---- end config
