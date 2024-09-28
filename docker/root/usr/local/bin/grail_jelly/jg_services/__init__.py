#rd api
from base import *
from base.constants import *
import requests
from jg_services.jelly_rdapi import RD
from datetime import datetime
RD = RD()
# plug to same logging instance as main
#logger = logging.getLogger('jellygrail')



# one shot token
oneshot_token = None
rs_working = False

# rd remote location
REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')
DEFAULT_INCR = os.getenv('DEFAULT_INCR')
WHOLE_CONTENT = os.getenv('ALL_FILES_INCLUDING_STRUCTURE') != "no"

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
        
        

    except Exception as e:
        logger.error(f"!! Error accessing RD: {e}")
        return "Server running but RD test has failed (DNS or Network failure)"
    else:
        return "This server is running and its last own RD torrents are:   \n"+dumped_data

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

def rd_progress():
# rd_progress NEW: Fill the pile chronologically each time it's called in server and new stuff arrives
    # this will trigger /scan if any downloading finished on own RD account
    # so the order is : /remotescan, /rd_progress -> /scan (+daily forced scan if needed)

    #if remoteScan working, stop rdprogress
    if rs_working:
        logger.warning("RDAPI-PACER~ New downloads checker will trigger when remote hashes fetcher has completed")
        return ""

    if data := rdump_backup(including_backup = False, returning_data= True):

        if "Error" not in data:

            # open the pile in raw mode 
            # parse it like array
            # update array with new hashes if hasehs comes from a completed RD item
            # if does not exists : append everything

            # loop in data to get stuff waiting file selection
            for data_item in data:
                if data_item.get('status') == 'waiting_files_selection' or data_item.get('status') == 'magnet_conversion':
                    logger.warning(f"        RD~ The {data_item.get('filename')} file selection has not been done, now forcing it")
                    try:
                        if WHOLE_CONTENT:
                            # part to really get the whole stuff BEGIN
                            info_output = RD.torrents.info(data_item.get('id')).json()
                            all_ids = [str(item['id']) for item in info_output.get('files')]
                            get_string = ",".join(all_ids)
                            # part to really get the whole stuff END
                            # RD.torrents.select_files(returned.get('id'), 'all') changed to :
                            RD.torrents.select_files(data_item.get('id'), get_string)
                        else:
                            RD.torrents.select_files(data_item.get('id'), 'all')
                    except Exception as e:
                        logger.error(f"  - ...but an error has occured forcing file selection (will be retried later) on {data_item.get('filename')} : {e}")
                    


            dled_rd_hashes = [data_item.get('hash') for data_item in data if data_item.get('status') == 'downloaded']

            if (os.path.exists(PILE_FILE)):
                _, cur_pile = file_to_array(PILE_FILE)
                if len(dled_rd_hashes) > 0:
                    delta_elements = [item for item in dled_rd_hashes if item not in cur_pile]
                    array_to_file(PILE_FILE, delta_elements)

                    if len(delta_elements) > 0:
                        logger.info("        RD| New downloaded torrent(s) >> refresh triggered")
                        return "PLEASE_SCAN"
                    else:
                        #logger.debug("RD_PROGRESS > I did not detect any new torrents with 'downloaded' status")
                        return ""
                else:
                    logger.warning("        RD| Not any downloaded item in Real-Debrid (normal if you just started using it)")
                    return ""
                
            else:
                # 1st pile write tagged with unique identifier
                array_to_file(PILE_FILE, dled_rd_hashes, initialize_with_unique_key=True)
                return "PLEASE_SCAN"
        else:
            logger.critical(f"An error occurred on getting RD data")
            return ""
    else:
        logger.critical(f"An error occurred on getting RD data")
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

# -----------
    
def restoreitem(filename, token):

    global oneshot_token

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

                    if "Error" not in local_data:
                        local_data_hashes = [iteml.get('hash') for iteml in local_data]
                        push_to_rd_hashes = [item.get('hash') for item in backup_data if item.get('hash') not in local_data_hashes]

                        if len(push_to_rd_hashes) > 0:
                            logger.info(f"        RD| Restoring RD items from {filename} ...")
                            for item in push_to_rd_hashes:
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
                                        logger.warning(f"...! Hash {item} is not accepted by RD.")
                                        continue
                                except Exception as e:
                                    logger.error(f"An Error has occured on pushing hash to RD (+cancellation of whole batch, so please retry) : {e}")
                                    return "Wrong : An Error has occured on pushing hash to RD (+cancellation of whole batch, so please retry)"
                                else:
                                    logger.info(f"       RD| * RD Hash {item} restored [restoreitem]")
                            return "Backup restored with success, please verify on your RD account"
                        else:
                            return "This backup file has no additionnal hash compared to your RD account"
                    else:
                        logger.critical(f"No local data has been retrieved via rdump_backup() in restoreitem()")
                        return "Wrong local rdump data fetch"           
                else:
                    logger.critical(f"No local data has been retrieved via rdump_backup() in restoreitem()")
                    return "Wrong local rdump data fetch" # wrong is mandatory here (return format)

        else:
            return "Wrong backup filename" # wrong is mandatory here (return format)
    else:
        return "Wrong Token" # wrong is mandatory here (return format)



# ----------------------------------
        
def remoteScan():
    global rs_working
    # take data from remote RD account
    # if no local data, take it (we have to compare later on)

    # compare with rdump not pile

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

        if server_data.get('pilekey') != cur_key:
            logger.warning(f" REMOTE-JG| Remote pile key changed, reset with increment found in settings.env")
            remote_loc = f"{REMOTE_RDUMP_BASE_LOCATION}/getrdincrement/{DEFAULT_INCR}"
            try:
                response = requests.get(remote_loc, timeout=10)
                response.raise_for_status()
                server_data = response.json()
            except Exception as e:
                logger.warning(f" REMOTE-JG| Remote JellyGrail Instance is simply not running or other error:  {e}")
                rs_working = False
                return None
            save_data_to_file(REMOTE_PILE_KEY_FILE, server_data.get('pilekey'))

        if server_data is not None:
            if not len(server_data['hashes']) > 0:
                logger.debug(f" REMOTE-JG| No new RD hashes")
                rs_working = False
                return None
        else:
            logger.critical(f"Data was fetched but data returned is None")
            rs_working = False
            return None
        
        if(local_data := rdump_backup(including_backup = False, returning_data = True)):
            if "Error" not in local_data:
                local_data_hashes = [iteml.get('hash') for iteml in local_data]
                push_to_rd_hashes = [item for item in server_data['hashes'] if item not in local_data_hashes]
                whole_batch_taken = True
                for item in push_to_rd_hashes:
                    try:
                        ## item = 'bf5e32ae2d6c63e0b8ceb7d0c9d7a397ab8b6cd1'
                        # RD calls below !! caution !!
                        #logger.debug(f"  * Adding RD Hash from remote: {item} ...")
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
                            logger.warning(f"...! Hash {item} is not accepted by RD.")
                            continue
                    except Exception as e:
                        logger.error(f"...!! An Error has occured on pushing hash to RD (whole batch cancelled but retried next time) : {e}")
                        # is select files fails, it will be retried later
                        whole_batch_taken = False
                        break
                    else:
                        logger.info(f"        RD| Hash {item} added from remote [remoteScan]")
                        cur_incr += 1
                if whole_batch_taken:
                    # whole batch taken so we can save the real increment given by server
                    if last_added_incr := server_data.get('lastid'):
                        save_data_to_file(RDINCR_FILE, last_added_incr)
                else:
                    # we only save a manually incremented increment to avoid doing the whole batch again if there are one error in the whole batch
                    # as this is incremented on client side only upon new hashes (items not already in RD account), when applied on server side pile it can be deeper in the pile than really necessary, does not matter unless an intentionnal deletion happens on client just after an uncomplete batch containing this item, and in this very rare case, it means that the local deleted item could be then fetched again from remote instance on the next remoteScan.
                    save_data_to_file(RDINCR_FILE, cur_incr)
            else:
                logger.critical(f"No local data retrieved (rdump_backup) for comparison [remoteScan]")
        else:
            logger.critical(f"No local data retrieved (rdump_backup) for comparison [remoteScan]")

        rs_working = False

    else:
        logger.warning("---- No REMOTE_RDUMP_BASE_LOCATION specified, ignoring but remotescan can't work ----")

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


def rdump_backup(including_backup = True, returning_data = False):
    if including_backup:
        if(os.path.exists(RDUMP_FILE)):
            os.makedirs(RDUMP_BACKUP_FOLDER, exist_ok=True)
            # copy with date in filename
            today = datetime.now()
            file_backuped = "/rd_dump_"+today.strftime("%Y%m%d")+".json"
            subprocess.call(['cp', RDUMP_FILE, RDUMP_BACKUP_FOLDER+file_backuped])

    try:
        # create horodated json file of my torrents
        inbelements = 2500
        nbelements = inbelements
        data = []
        ipage=1
        while nbelements == inbelements:
            idata = RD.torrents.get(limit=inbelements, page=ipage).json()
            data += idata
            ipage += 1
            nbelements = len(idata)
    except Exception as e:
        logger.critical(f"!!! Error occurred [rdump_backup]: {e}")
        return "Error"
    else:
        # Store the data in a file
        with open(RDUMP_FILE, 'w') as f:
            json.dump(data, f)
        if returning_data:
            return data
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
