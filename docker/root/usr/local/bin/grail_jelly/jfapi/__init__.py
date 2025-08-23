import requests
from base import *
from datetime import datetime


BASE_URI = "http://localhost:8096"
BASE_AUTH_STR = 'MediaBrowser Client="JellyGrail Agent", Device="JellyGrail Docker", DeviceId="jellygrail001", Version="3"'

jfapikey = None
jf_login = None # provided by jfconfig
jf_password = None # provided by jfconfig

def AUTHSTRING():
    global jfapikey
    if jfapikey is not None:
        return f'{BASE_AUTH_STR}, Token="{jfapikey}"'
    else:
        return BASE_AUTH_STR

def authByName():
    global jfapikey
    global jf_login
    global jf_password
    json_payload = {
        "Username": jf_login,
        "Pw": jf_password
    }

    headers = {'Authorization': AUTHSTRING()}

    try:
        resp = requests.post(f'{BASE_URI}/Users/AuthenticateByName', headers=headers, json=json_payload)
        if resp.status_code != 200:
            logger.critical("    JF-API/ FAILURE to authenticate to Jellyfin API, check your JF_LOGIN and JF_PASSWORD settings.env variables")
            return False
        jfapikey = resp.json().get('AccessToken')
        logger.info("    JF-API/ ... Authenticated to Jellyfin API")
        return True
    except requests.RequestException as e:
        logger.critical(f"    JF-API/ Exception during authentication: {e}")
        return False


def jellyfin(path, method='get', **kwargs):
    global jfapikey
    if jfapikey is None:
        if not authByName():
            return None
    # else already authenticated or auth ok
    resp = jellyfin_req(path, method, **kwargs)

    # Handle 401 Unauthorized (token invalid)
    if resp is not None and resp.status_code == 401:
        logger.warning("    JF-API/ Token rejected, attempting re-authentication...")
        jfapikey = None  # reset legacy token
        if authByName():
            resp = jellyfin_req(path, method, **kwargs)
        else:
            return None
    # handle other errors
    elif resp is not None and resp.status_code >= 400:
        logger.critical(f"    JF-API/ FAILURE to get/post API data at {path}, status code: {resp.status_code}")
        return None

    return resp


def jellyfin_req(path, method='get', **kwargs):
    retries = 3
    delay = 2
    url = f'{BASE_URI}/{path}'
    headers = {'Authorization': AUTHSTRING()}
    retryable = {500, 502, 503, 504}
    time.sleep(0.1) # slight delay to avoid overwhelming the server
    for attempt in range(1, retries + 1):
        try:
            response = getattr(requests, method)(url, headers=headers, **kwargs)
            if response.status_code in retryable:
                logger.debug(f"    JF-API/ Attempt {attempt}: Received retryable status {response.status_code}")
            else:
                return response
        except requests.RequestException as e:
            logger.debug(f"    JF-API/ Attempt {attempt}: Exception occurred: {e}")
        
        if attempt < retries:
            time.sleep(delay)

    # Final failure
    logger.critical(f"    JF-API/ Failed after {retries} attempts to reach {url}")
    return None

def wait_for_jfscan_to_finish():
    # while libraryrunning dont do anything
    try:
        tasks = jellyfin('ScheduledTasks').json()
        tasks_name_mapping = {task.get('Key'): task for task in tasks}
        ref_task_id = tasks_name_mapping.get('RefreshLibrary').get('Id')
        while True:
            task = jellyfin(f'ScheduledTasks/{ref_task_id}').json()
            if task.get('State') != "Running":
                break
            else:
                time.sleep(8) # wait 8 seconds before checking again
    except Exception as e:
        logger.warning(f"    JF-API| ... Jellyfin Library refreshed, but not able to retrieve completion, error: {e}")
        return False

    logger.info("         3| ...Jellyfin Library refresh complete")
    return True

def lib_refresh_all():
    resp = jellyfin(f'Library/Refresh', method='post')
    if resp.status_code != 204:
        logger.critical(f"FAILURE to update library. Status code: {resp.status_code}")
        return False
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