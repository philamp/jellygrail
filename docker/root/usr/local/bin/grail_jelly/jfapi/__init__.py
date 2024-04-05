import requests
from base import *
import datetime


BASE_URI = "http://localhost:8096"

jfapikey = None

def merge_versions():
    if jfapikey is not None:
        tasks = jellyfin('ScheduledTasks').json()
        tasks_name_mapping = {task.get('Key'): task for task in tasks}
        ref_task_id = tasks_name_mapping.get('RefreshLibrary').get('Id')
        if tasks_name_mapping.get('MergeEpisodesTask') is not None:
            # mergeS_task_id = tasks_name_mapping.get('MergeEpisodesTask').get('Id')
            mergeM_task_id = tasks_name_mapping.get('MergeMoviesTask').get('Id')

            # while libraryrunning dont do anything
            logger.debug(". Waiting for library refresh to end.")
            while True:
                task = jellyfin(f'ScheduledTasks/{ref_task_id}').json()
                if task.get('State') == "Running":
                    print (".", end="")
                else:
                    # jellyfin(f'ScheduledTasks/Running/{mergeS_task_id}', method='post') -> this is not working well :( it merges different episodes number like its one :(
                    jellyfin(f'ScheduledTasks/Running/{mergeM_task_id}', method='post')
                    logger.info("> Videos variants merged (only for movies)")
                    break
                time.sleep(3)

def jellyfin(path, method='get', **kwargs):
    return getattr(requests, method)(
        f'{BASE_URI}/{path}',
        headers={'X-MediaBrowser-Token': jfapikey},
        **kwargs
    )

def lib_refresh_all():
    if jfapikey is not None:
        resp = jellyfin(f'Library/Refresh', method='post')
        if resp.status_code == 204:
            logger.info("> Library update started successfully.")
        else:
            logger.critical(f"> FAILURE to update library. Status code: {resp.status_code}")

'''
def restart_jellygrail_at(target_hour=6, target_minute=30):
    while True:
        # Get the current time
        now = datetime.datetime.now()
        next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if next_run < now:
            next_run += datetime.timedelta(days=1)
        sleep_time = (next_run - now).total_seconds()
        logger.info(f"~ Jellyfin next restart in {sleep_time} seconds.")
        time.sleep(sleep_time)
        if jfapikey is not None:
            logger.info(f"JellyGrail will now shutdown for restart, beware '--restart unless-stopped' must be set in your docker run otherwise it won't restart !!")
            jellyfin(f'System/Shutdown', method='post')
'''