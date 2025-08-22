#rd api
from base import *
from base.constants import *
import requests
from jg_services.jelly_rdapi import RDE
from datetime import datetime
RD = None
# plug to same logging instance as main
#logger = logging.getLogger('jellygrail')



# one shot token
oneshot_token = None
rs_working = False
lastrddump = 0

# rd remote location:
REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')

# now hardcoded:
DEFAULT_INCR = 0
WHOLE_CONTENT = True


def premium_timeleft():
    global RD
    RD = RDE()
    try:
        udata = RD.user.get().json()

        expseconds = udata.get('premium')
        
        

    except Exception as e:
        logger.error(f"!! Error accessing RD: {e}")
        # return "Server running but RD test has failed (DNS or Network failure)"
        return 0
    else:
        return expseconds


def test():
    try:
        
        inbelements = 4
        nbelements = inbelements
        data = []
        ipage=1
        while nbelements == inbelements and ipage < 2 :
            idata = RD.torrents.get(limit=inbelements, page=ipage).json()
            data += idata
            ipage += 1
            nbelements = len(idata)

        dumped_data = json.dumps(data)

        udata = RD.user.get().json()

        expdays = "--- exp: "+json.dumps(udata.get('expiration'))+"; secconds premium:"+json.dumps(udata.get('premium'))
        
        

    except Exception as e:
        logger.error(f"!! Error accessing RD: {e}")
        return "Server running but RD test has failed (DNS or Network failure)"
    else:
        return "This server is running and its last own RD torrents are:   \n"+dumped_data+expdays

def file_to_array(filename):
    try:
        with open(filename, 'r') as file:
            first_line = file.readline().strip()  # Read the first line and strip newline character
            rest_of_lines = [line.strip() for line in file]  # Read the rest of the lines into a list
            return first_line, rest_of_lines  # Return a tuple with the first line and the list of the rest
    except FileNotFoundError:
        return "", [] 

def array_to_file(filename, array, initialize_with_unique_key=False):
    try:
        with open(filename, 'a') as file:
            if initialize_with_unique_key:
                file.write(''.join(random.choice('0123456789') for _ in range(16)) + "\n")
            for item in array:
                try:
                    # Convert item to string to ensure compatibility with the "+" operator
                    file.write(str(item) + "\n")
                except TypeError as e:
                    logger.critical(f"!!! Error writing item to file: {e}")
                    # Handle or log the TypeError (e.g., item cannot be converted to string)
                    # You might want to continue to the next item or handle this situation differently.
    except IOError as e:
        logger.critical(f"!!! Error opening or writing to the file: {e}")
        # Handle or log the IOError (e.g., file cannot be opened or written to)


class noIdReturned(Exception):
    pass

class noFilesReturned(Exception):
    pass


def just_select(returnid):

    # wait for waiting_files_selection to be available
    info_output = RD.torrents.info(returnid).json()
    iters = 0
    while iters < 8:
        iters += 1
        if info_output.get("status") != 'waiting_files_selection':
            logger.info(f"    RD-API| ... {returnid} RD item not ready for file selection, retrying in 0.5sec, max 8 tries ...")
            time.sleep(0.5) # ensure waiting enough 
            info_output = RD.torrents.info(returnid).json()
        else:
            break
    
    # so even if "status" is still not 'waiting_files_selection' we continue (it can be magnet conversion and have file selection), so we don't raise an exception

    if all_ids := [str(item['id']) for item in info_output.get('files', [])]:
        if info_output.get("status") == 'magnet_conversion':
            logger.warning(f"    RD-API| Weird: {returnid} item returned magnet_conversion but files seems present anyway")
        if WHOLE_CONTENT:
            get_string = ",".join(all_ids)
            RD.torrents.select_files(returnid, get_string)
        else:
            RD.torrents.select_files(returnid, 'all')
    else:
        raise noFilesReturned(f"No RD files returned, so select can't be done (will be retried later) on RD item: {returnid} with filename: {info_output.get('filename')}")


# great !
def push_and_select(hash):
    returned = RD.torrents.add_magnet(hash).json()
    if returnid := returned.get('id'):
        just_select(returnid)
    else:
        raise noIdReturned(f"No RD ID returned for hash: {hash}.")

'''
def push_array_of_items(array):

    for item in array:
        try:
            #logger.debug(f"  * Try adding RD Hash from restored backup: {item} ... [restoreitem]")

            # RD calls below !! caution !!
            
            returned = RD.torrents.add_magnet(item).json()
            if WHOLE_CONTENT:
                # part to really get the whole stuff BEGIN
                info_output = RD.torrents.info(returned.get('id')).json()
                all_ids = [str(item['id']) for item in info_output.get('files')]
                get_string = ",".join(all_ids)
                # part to really get the whole stuff END
                # RD.torrents.select_files(returned.get('id'), 'all') changed to :
                RD.torrents.select_files(returned.get('id'), get_string)
            else:
                RD.torrents.select_files(returned.get('id'), 'all')
            
            
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 403:
                logger.warning(f"...! Hash {item} is not accepted by RD")
                continue
        except Exception as e:
            logger.error(f"An Error has occured on pushing hash to RD (+cancellation of whole batch, so please retry) : {e}")
            return "Wrong : An Error has occured on pushing hash to RD (+cancellation of whole batch, so please retry)"
        else:
            logger.info(f"       RD| * RD Hash {item} restored [restoreitem]")

    return "Backup restored with success, please verify on your RD account"

'''

# #######

# -----------
    
def restoreitem(filename, token):

    global oneshot_token
    global rs_working

    logger.debug(f"! provided token is : {token}, wanted token is: {oneshot_token} [restoreitem]")

    if token == oneshot_token:
        oneshot_token = None
        # .... proceed
        if os.path.exists(os.path.join(RDUMP_BACKUP_FOLDER, filename)):
            # ...proceed
            try:
                with open(os.path.join(RDUMP_BACKUP_FOLDER, filename), 'r') as f:
                    backup_data = json.load(f)
                    
            except FileNotFoundError:
                return None
            
            else:
                if(local_data := rdump_backup(including_backup = True, returning_data = True)):

                    rs_working = True

                    local_data_hashes = [iteml.get('hash') for iteml in local_data]
                    push_to_rd_hashes = [item.get('hash') for item in backup_data if item.get('hash') not in local_data_hashes]

                    if len(push_to_rd_hashes) > 0:
                        logger.info(f"    RD-API| Restoring RD items from {filename} ...")
                        for backup_hash in push_to_rd_hashes:

                            try:
                                push_and_select(backup_hash)
                            except requests.exceptions.HTTPError as http_err:
                                if http_err.response.status_code == 403:
                                    logger.warning(f"    RD-API| Hash {backup_hash} is not accepted by RD.")

                                    continue # this is ok
                                else:
                                    # this is not OK : we don't increment further and stop the batch
                                    logger.error(f"    RD-API| JOB stopped: An HTTP Error has occured on pushing backup hash to RD : {http_err}")
                                    rs_working = False
                                    return "Backup not fully restored, please launch same job again to complete it"
                            except noFilesReturned as e:
                                pass
                            except noIdReturned as e:
                                logger.error(f"    RD-API| JOB stopped: {e}")
                                rs_working = False
                                return "Backup not fully restored, please launch same job again to complete it"
                            except Exception as e:
                                logger.error(f"    RD-API| JOB stopped: An Error has occured on pushing backup hash to RD : {e}")
                                # is select files fails, it will be retried later
                                rs_working = False
                                return "Backup not fully restored, please launch same job again to complete it"
                            else:
                                # if no other excaption, seems fine
                                logger.info(f"    RD-API| {backup_hash} is a backup hash added successfully from backup file to your RD account")

                        rs_working = False
                        return "Backup restored with success, please verify on your RD account; Torrent File selection may not be complete but will be progressively fixed."
                    else:
                        rs_working = False
                        return "This backup file has no additionnal hash compared to your RD account"
    
                else:
                    rs_working = False
                    logger.critical(f"No local data has been retrieved via rdump_backup() in restoreitem()")
                    return "Wrong local rdump data fetch" # wrong is mandatory here (return format)

        else:
            rs_working = False
            return "Wrong backup filename" # wrong is mandatory here (return format)
    else:
        rs_working = False
        return "Wrong Token" # wrong is mandatory here (return format)



# ----------------------------------
        
def remoteScan():
    global rs_working
    # take data from remote RD account
    # if no local data, take it (we have to compare later on)

    # compare with rdump not pile
    discarded_hashes = []
    # toimprove : add wait until select files is available (mitigated by regular retry)

    if REMOTE_RDUMP_BASE_LOCATION.startswith('http'):

        rs_working = True

         # -> ok but if remotescan is called a lot ... lot of backups....
        cur_incr = read_data_from_file(RDINCR_FILE)

        cur_key = read_data_from_file(REMOTE_PILE_KEY_FILE)

        remote_loc = f"{REMOTE_RDUMP_BASE_LOCATION}/getrdincrement/{cur_incr}"

        try:
            response = requests.get(remote_loc, timeout=10)
            response.raise_for_status()
            server_data = response.json()
        except Exception as e:
            logger.warning(f" REMOTE-JG| Remote JellyGrail Instance is simply not running or other error: {e}")
            rs_working = False
            return None

        if server_data.get('pilekey') != cur_key or cur_incr > server_data.get('lastid'):
            logger.warning(f" REMOTE-JG| New Remote pile (identifier changed) or impossible increment (higher thant remote), reset with increment found in settings.env")
            cur_incr = int(DEFAULT_INCR)
            remote_loc = f"{REMOTE_RDUMP_BASE_LOCATION}/getrdincrement/{cur_incr}"
            try:
                response = requests.get(remote_loc, timeout=10)
                response.raise_for_status()
                server_data = response.json()
            except Exception as e:
                logger.warning(f" REMOTE-JG| Remote JellyGrail Instance is simply not running or other error:  {e}")
                rs_working = False
                return None
            save_data_to_file(REMOTE_PILE_KEY_FILE, server_data.get('pilekey'))

        if server_data:
            if server_data['hashes']:
                logger.info(f" REMOTE-JG| Has new hashes that your local JG will now try to push starting with incr: {cur_incr}...")
            else:
                logger.info(f" REMOTE-JG| No new RD hashes, incr is still: {cur_incr}")
                rs_working = False
                return None     
        else:
            logger.critical(f" REMOTE-JG| Data was fetched but not usable. Theorically already handled by generic exception catcher")
            rs_working = False
            return None
        
        if(local_data := rdump_backup(including_backup = False, returning_data = True)):
            local_data_hashes = [iteml.get('hash') for iteml in local_data]

            # base for incr is remote
            for remote_hash in server_data['hashes']:
                if remote_hash not in local_data_hashes:
                    try:
                        push_and_select(remote_hash)
                    except requests.exceptions.HTTPError as http_err:
                        if http_err.response.status_code == 403:
                            logger.warning(f"    RD-API| Hash {remote_hash} is not accepted by RD")

                            discarded_hashes.append(remote_hash)
                            #cur_incr += 1 # we can increment
                        else:
                            # this is not OK : we don't increment further and stop the batch
                            logger.error(f"    RD-API| JOB stopped: An HTTP Error has occured on pushing backup hash to RD (job stopped but resumed next time): {http_err}")
                            break
                    except noFilesReturned as e:
                        logger.warning(f"    RD-API| {remote_hash} hash imported from remote JG to your RD account, but without file selection")
                    except noIdReturned as e:
                        logger.error(f"    RD-API| JOB stopped: {e} (job stopped but resumed next time)")
                        break # not ok
                    except Exception as e:
                        logger.error(f"    RD-API| JOB stopped: An unknown Error has occured on pushing hash to RD (job stopped but resumed next time) Error is: {e}")
                        # is select files fails, it will be retried later
                        break
                    else:
                        # if no other excaption, seems fine
                        logger.info(f"    RD-API| {remote_hash} hash imported from remote JG to your RD account")
                        #cur_incr += 1


            # whatever the batch progression we test the progress of new hashes beeing really pushed or not
            if(post_local_data := rdump_backup(including_backup = False, returning_data = True)):
                post_local_data_hashes = [iteml.get('hash') for iteml in post_local_data]
                for remote_hash in server_data['hashes']:
                    if remote_hash in post_local_data_hashes or remote_hash in discarded_hashes:
                        cur_incr += 1
                    else:
                        break # chain is broken here, we stop incrmeenting
            else:
                logger.critical(f"    RD-API| An error occurred on getting post-batch local RD data [remoteScan]")

            logger.info(f" REMOTE-JG| The current increment after batch is now: {cur_incr} (local) / {server_data.get('lastid')} (remote JG cinrement)")
            if cur_incr < server_data.get('lastid'):
                logger.warning(" REMOTE-JG| So local incr. inferior to remote incr. Will be completed on next call ...")

            # job finished completely or not, we save the real cur incr
            save_data_to_file(RDINCR_FILE, cur_incr)




        else:
            logger.critical(f"    RD-API| An error occurred on getting local RD data [remoteScan]")

        rs_working = False

    else:
        logger.warning("---- No REMOTE_RDUMP_BASE_LOCATION specified, ignoring but remotescan can't work ----")



# #######


def rd_progress():
# rd_progress NEW: Fill the pile chronologically each time it's called in server and new stuff arrives
    # this will trigger /scan if any downloading finished on own RD account
    # so the order is : /remotescan, /rd_progress -> /scan (+daily forced scan if needed)

    #if remoteScan working, stop rdprogress
    if rs_working:
        logger.info("RD-CHECKER| Cant run RD download checker when remotescan or restoreitem is running ...")
        return ""

    if data := rdump_backup(including_backup = False, returning_data= True):

        # open the pile in raw mode 
        # parse it like array
        # update array with new hashes if hasehs comes from a completed RD item
        # if does not exists : append everything

        # loop in data to get stuff waiting file selection
        for data_item in data:
            if data_item.get('status') == 'waiting_files_selection' or data_item.get('status') == 'magnet_conversion':

                logger.warning(f"RD-CHECKER| File selection missing on {data_item.get('filename')}. Now retrying it ...")

                try:
                    just_select(data_item.get('id'))
                except noFilesReturned as e:
                    logger.warning(f"RD-CHECKER| ... but {e}")
                except Exception as e:
                    logger.error(f"RD-CHECKER| ... but an unknwown error has occured when doing file selection (will be retried later) on {data_item.get('filename')} : {e}")
                


        dled_rd_hashes = [data_item.get('hash') for data_item in data if data_item.get('status') == 'downloaded'] # ensure dl status

        if (os.path.exists(PILE_FILE)):
            _, cur_pile = file_to_array(PILE_FILE)
            if len(dled_rd_hashes) > 0:
                delta_elements = [item for item in dled_rd_hashes if item not in cur_pile] #ensure not in cur pile

                delta_elements = list(dict.fromkeys(reversed(delta_elements))) # ensure : reversed, , then unniqueness applies, then converted back to an array (after having ensure dled status and not in cur pile)

                array_to_file(PILE_FILE, delta_elements)

                if len(delta_elements) > 0:
                    logger.info("    RD-API| New downloaded torrent(s) >> Refresh triggered or queued")
                    return "PLEASE_SCAN"
                else:
                    logger.debug("    RD-API| NO new downloaded torrent(s). No trigger.")
                    return ""
            else:
                logger.warning("    RD-API| Zero downloaded torrent (normal if you just started using it)")
                return ""
            
        else:
            # 1st pile write tagged with unique identifier
            array_to_file(PILE_FILE, dled_rd_hashes, initialize_with_unique_key=True)
            return "PLEASE_SCAN" #toimprove ? maybe thanks to that, the very first container start will scan, so subsequent ones are really needed ? yes
    else:
        logger.critical(f"An error occurred on getting local RD data")
        return ""


# ------------
    
def restoreList():

    global oneshot_token
    backupList = []
    i = 0

    # set a one time use token
    oneshot_token = ''.join(random.choice('0123456789abcdef') for _ in range(32))

    for f in os.scandir(RDUMP_BACKUP_FOLDER):
        i += 1
        if f.is_file():
            backupList.append(f'-- <a href="/restoreitem?filename={f.name}&token={oneshot_token}" title="{f.name}">{f.name}</a> | {os.path.getsize(f.path)} kb --')

    if len(backupList):
        return "</br>".join(backupList)


# ----------------------------------
# rd_progress Fill the pile chronologically each time it's called in server and new stuff arrives
# getrdincrement
        
def getrdincrement(incr):
    if (os.path.exists(PILE_FILE)):
        # gets full array 
        pile_key, cur_pile = file_to_array(PILE_FILE)
        return json.dumps({'hashes': cur_pile[incr:], 'lastid': len(cur_pile), 'pilekey': int(pile_key)}).encode()
    else:
        rd_progress()
        # it forces this sever to call rd_progress at least once
        # service_rdprog_instance = ScriptRunner.get(rd_progress)
        # service_rdprog_instance.run()
        # if(service_rdprog_instance.get_output() != 'phony'):
            # logger.info("periodic trigger is working")
            # we are forced to consume output from this funciton to avoid disjoined calls to output queue
            # logger.warning(f"> force rd_progress (should happen once) [getrdincrement]")
        return ""

# now only overwrite current dump if done more than 4 hours ago or backup is requested
def rdump_backup(including_backup = True, returning_data = False):
    global lastrddump

    has_to_put_sthing = False

    stopthere = False

    try:
        # create horodated json file of my torrents
        inbelements = 2500
        nbelements = inbelements
        data = []
        #ipage=1
        ipage=1 
        while nbelements == inbelements:
            idata = RD.torrents.get(limit=inbelements, page=ipage).json() # does RD return no json if out of index ? TODO verify
            data += idata
            ipage += 1
            nbelements = len(idata)

    # potentially reaches further than needed causing out of index paging and thus json parsing error
    # ... but this way of managing out of index paging is better then through resp.Header["X-Total-Count"][0] as it will really go through RD returned array without issue when race condition adds or *remove* items just after X-total-count is checked.

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"    RD-API| Getting current RD status failed for HTTP reason! Error is: {http_err}")
        stopthere = True

    except json.JSONDecodeError as json_err:
        if ipage == 1:
            logger.error(f"    RD-API| Getting current RD status failed for JSON parsing reason! Error is: {json_err}")
            has_to_put_sthing = True
            stopthere = True
        else:
            logger.info(f"    RD-API| Json Parsing error due to out of index request. Not a problem and happens when torrent count is just divisible by 2500")

    
    except Exception as e:
        logger.error(f"    RD-API| Getting current RD status failed for another reason than HTTP protocol error! Error is: {e}")
        stopthere = True
        #return "Error"

    if not stopthere:
        # Store the data in a file if not exists or last time was more than 4 hours ago
        if not os.path.exists(RDUMP_FILE) or (time.time() - lastrddump) > 3600*4 or including_backup:
            lastrddump = time.time()
            with open(RDUMP_FILE, 'w') as f:
                json.dump(data, f)

        if including_backup:
            if(os.path.exists(RDUMP_FILE)):
                os.makedirs(RDUMP_BACKUP_FOLDER, exist_ok=True)
                # copy with date in filename
                today = datetime.now()
                file_backuped = "/rd_dump_"+today.strftime("%Y%m%d")+".json"
                subprocess.call(['cp', RDUMP_FILE, RDUMP_BACKUP_FOLDER+file_backuped])

        if returning_data:
            return data

    if has_to_put_sthing:
        logger.warning("    RD-API| Will now try to add at least one torrent to workaround the error")
        try:
            push_and_select("66FBAB37FF7402D5F0A29ADC95299A244E09AADC")
        except Exception as e:
            logger.critical(f"    RD-API| RD API workaround did not work, error is: {e}")

    return None

def read_data_from_file(filepath):
    try:
        with open(filepath, 'r') as file:
            strincr = file.read().strip()
            incr = int(strincr)  # Attempt to convert an empty string to an integer
    except FileNotFoundError:
        logger.warning(f" REMOTE-JG| Sync Increment or Sync Pile Key data file not exists yet, should happen just twice on first use")
        return int(DEFAULT_INCR)
    except ValueError as e:
        logger.critical(f" REMOTE-JG| Error taking increment or pilekey from data file; Error is: {e}")
        return int(DEFAULT_INCR)
    else:
        return incr


def save_data_to_file(filepath, incr):
    try:
        with open(filepath, 'w') as file:
            file.write(str(incr))
    except IOError as e:
        logger.critical(f"!!! Error saving incr to file [save_data_to_file]: {e}")
