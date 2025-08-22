import requests
from base import *
from datetime import datetime


BASE_URI = "http://localhost:8096"
BASE_AUTH_STR = 'MediaBrowser Client="JellyGrail Agent", Device="JellyGrail Docker", DeviceId="jellygrail001", Version="3"'
JF_LOGIN = os.getenv('JF_LOGIN') or "admin"
JF_PASSWORD = os.getenv('JF_PASSWORD')

jfapikey = None

def AUTHSTRING():
    global jfapikey
    if jfapikey is not None:
        return f'{BASE_AUTH_STR}, Token="{jfapikey}"'
    else:
        return BASE_AUTH_STR

def authByName():
    global jfapikey
    json_payload = {
        "Username": JF_LOGIN,
        "Pw": JF_PASSWORD
    }
    resp = jellyfin_req('Users/AuthenticateByName', method='post', json=json_payload)
    if resp.status_code != 200:
        logger.critical("    JF-API/ FAILURE to authenticate to Jellyfin API, check your JF_LOGIN and JF_PASSWORD settings.env variables")
        return False
    jfapikey = resp.json().get('AccessToken')
    logger.info("    JF-API/ ... Authenticated to Jellyfin API")
    return True


def jellyfin(path, method='get', **kwargs):
    if jfapikey is None:
        if authByName():
            return jellyfin_req(path, method, **kwargs)
        else:
            return None
    else:
        return jellyfin_req(path, method, **kwargs)


def jellyfin_req(path, method='get', **kwargs):
    retries = 3
    delay = 2
    url = f'{BASE_URI}/{path}'
    headers = {'Authorization': AUTHSTRING()}
    retryable = {500, 502, 503, 504}

    for attempt in range(1, retries + 1):
        try:
            response = getattr(requests, method)(url, headers=headers, **kwargs)
            if response.status_code == 200:
                return response
            elif response.status_code in retryable:
                logger.debug(f"    JF-API/ Attempt {attempt}: Received retryable status {response.status_code}")
            else:
                # Don't retry for 404, 400, 401, etc.
                response.raise_for_status()
                return response
        except requests.RequestException as e:
            logger.debug(f"    JF-API/ Attempt {attempt}: Exception occurred: {e}")
        
        if attempt < retries:
            time.sleep(delay)

    # Final attempt failed
    response.raise_for_status()
    return response

def wait_for_jfscan_to_finish():
    # while libraryrunning dont do anything
    if jfapikey is not None:
        try:
            tasks = jellyfin('ScheduledTasks').json()
            tasks_name_mapping = {task.get('Key'): task for task in tasks}
            ref_task_id = tasks_name_mapping.get('RefreshLibrary').get('Id')
            while True:
                time.sleep(2)
                task = jellyfin(f'ScheduledTasks/{ref_task_id}').json()
                if task.get('State') != "Running":
                    break
                else:
                    time.sleep(8) #toimprove : retry every 8+2 seconds toimprove, jellyfin is overloaded, but fix it later in a more clever way
        except Exception as e:
            logger.warning("    JF-API| ... Jellyfin Library refreshed. (but API overloaded by status requests :( )")
            return True

    logger.info("         3| ...Jellyfin Library refresh complete")
    return True


# maybe deprecated
'''
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
'''

def lib_refresh_all():
    if jfapikey is not None:
        resp = jellyfin(f'Library/Refresh', method='post')
        if resp.status_code == 204:
            #logger.info("TASK-START~ Jellyfin Library refresh ...")
            pass
        else:
            logger.critical(f"FAILURE to update library. Status code: {resp.status_code}")

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