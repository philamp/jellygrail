#rd api
from base import *
import requests
from rdapi import RD
from datetime import datetime
from script_runner import ScriptRunner
RD = RD()
# plug to same logging instance as main
#logger = logging.getLogger('jellygrail')

# rd local dump cron-backups folder
rdump_backup_folder = '/jellygrail/data/backup'

# rd local dump location
rdump_file = '/jellygrail/data/rd_dump.json'

# pile file
pile_file = '/jellygrail/data/rd_pile.json'

# rd last date of import file
rdincr_file = '/jellygrail/data/rd_incr.txt'

# one shot token
oneshot_token = None

# rd remote location
REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')
DEFAULT_INCR = os.getenv('DEFAULT_INCR')
WHOLE_CONTENT = os.getenv('ALL_FILES_INCLUDING_STRUCTURE') != "no"

def test():
    try:
        dumped_data = json.dumps(RD.torrents.get(limit=2, page=1).json())
    except Exception as e:
        logger.error(f"Error accessing RD: {e}")
        return "Server running but RD test has failed (DNS or Network failure)"
    else:
        return "This server is running and its last own RD torrents are:   \n"+dumped_data

def file_to_array(filename):
    try:
        with open(filename, 'r') as file:
            # List comprehension to strip newline characters from each line
            return [line.strip() for line in file]
    except FileNotFoundError:
        # Return an empty list if the file does not exist
        return []

def array_to_file(filename, array):
    try:
        with open(filename, 'a') as file:

            for item in array:
                try:
                    # Convert item to string to ensure compatibility with the "+" operator
                    file.write(str(item) + "\n")
                except TypeError as e:
                    logger.critical(f"Error writing item to file: {e}")
                    # Handle or log the TypeError (e.g., item cannot be converted to string)
                    # You might want to continue to the next item or handle this situation differently.
    except IOError as e:
        logger.critical(f"Error opening or writing to the file: {e}")
        # Handle or log the IOError (e.g., file cannot be opened or written to)

def rd_progress():
# rd_progress NEW: Fill the pile chronologically each time it's called in server and new stuff arrives
    # this will trigger /scan if any downloading finished on own RD account
    # so the order is : /remotescan, /rd_progress -> /scan (+daily forced scan if needed)

    if data := rdump_backup(including_backup = False, returning_data= True):

        if "Error" not in data:

            # open the pile in raw mode 
            # parse it like array
            # update array with new hashes if hasehs comes from a completed RD item
            # if does not exists : append everything
            dled_rd_hashes = [data_item.get('hash') for data_item in data if data_item.get('status') == 'downloaded']

            if (os.path.exists(pile_file)):
                cur_pile = file_to_array(pile_file)
                if len(dled_rd_hashes) > 0:
                    delta_elements = [item for item in dled_rd_hashes if item not in cur_pile]
                    array_to_file(pile_file, delta_elements)

                    if len(delta_elements) > 0:
                        logger.debug("RD_PROGRESS > I detected new torrents having 'downloaded' status, so I started /scan method")
                        return "PLEASE_SCAN"
                    else:
                        logger.debug("RD_PROGRESS > I did not detect any new torrents with 'downloaded' status")
                        return ""
                else:
                    logger.debug("RD_PROGRESS > No item with downloading status from local RD")
                    return ""
                
            else:
                # 1st pile write
                array_to_file(pile_file, dled_rd_hashes)
                return "PLEASE_SCAN"
        else:
            logger.critical(f"An error occurred on getting RD data in rd_progress method")
            return ""
    else:
        logger.critical(f"An error occurred on getting RD data in rd_progress method")
        return ""


# ------------
    
def restoreList():

    global oneshot_token
    backupList = []
    i = 0

    # set a one time use token
    oneshot_token = ''.join(random.choice('0123456789abcdef') for _ in range(32))

    for f in os.scandir(rdump_backup_folder):
        i += 1
        if f.is_file():
            backupList.append(f'-- <a href="/restoreitem?filename={f.name}&token={oneshot_token}" title="{f.name}">{f.name}</a> | {os.path.getsize(f.path)} kb --')

    if len(backupList):
        return "</br>".join(backupList)

# -----------
    
def restoreitem(filename, token):

    global oneshot_token

    logger.debug(f"provided token is : {token}, wanted token is: {oneshot_token}")

    if token == oneshot_token:
        oneshot_token = None
        # .... proceed
        if os.path.exists(os.path.join(rdump_backup_folder, filename)):
            # ...proceed
            try:
                with open(os.path.join(rdump_backup_folder, filename), 'r') as f:
                    backup_data = json.load(f)
                    
            except FileNotFoundError:
                return None
            
            else:
                if(local_data := rdump_backup(including_backup = True, returning_data = True)):

                    if "Error" not in local_data:
                        local_data_hashes = [iteml.get('hash') for iteml in local_data]
                        push_to_rd_hashes = [item.get('hash') for item in backup_data if item.get('hash') not in local_data_hashes]

                        if len(push_to_rd_hashes) > 0:

                            for item in push_to_rd_hashes:
                                try:
                                    logger.debug(f"  - Adding RD Hash from restored backup: {item} ...")

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

                                except Exception as e:
                                    logger.error(f"An Error has occured on pushing hash to RD (+cancellation of whole batch) : {e}")
                                    return "Wrong : An Error has occured on pushing hash to RD (+cancellation of whole batch)"
                                else:
                                    return "Backup restored with success, please verify on your RD account"
                        else:
                            return "This backup file has no additionnal hash compared to your RD account"
                    else:
                        logger.critical(f"No local data has been retrieved via rdump_backup() in restoreitem()")
                        return "Wrong local rdump data fetch"           
                else:
                    logger.critical(f"No local data has been retrieved via rdump_backup() in restoreitem()")
                    return "Wrong local rdump data fetch"

        else:
            return "Wrong backup filename"
    else:
        return "Wrong Token"



# ----------------------------------
        
def remoteScan():

    # take data from remote RD account
    # if no local data, take it (we have to compare later on)

# compare with rdump not pile
    

    if REMOTE_RDUMP_BASE_LOCATION.startswith('http'):
         # -> ok but if remotescan is called a lot ... lot of backups....
        cur_incr = read_incr_from_file()
        remote_loc = f"{REMOTE_RDUMP_BASE_LOCATION}/getrdincrement/{cur_incr}"
        try:
            response = requests.get(remote_loc)
            response.raise_for_status()
            server_data = response.json()
        except Exception as e:
            logger.critical(f"Error fetching data from server or server not ready, please retry later: {e}")
        else:
            if server_data is not None:
                if len(server_data['hashes']) > 0:
                    if last_added_incr := server_data['lastid']:
                        save_incr_to_file(last_added_incr)
                else:
                    logger.debug(f"Data was fetched but no new data")
                    return None
            else:
                logger.critical(f"Data was fetched but data returned is None")
                return None
            
            if(local_data := rdump_backup(including_backup = False, returning_data = True)):
                if "Error" not in local_data:
                    local_data_hashes = [iteml.get('hash') for iteml in local_data]
                    push_to_rd_hashes = [item for item in server_data['hashes'] if item not in local_data_hashes]
                    for item in push_to_rd_hashes:
                        try:
                            # RD calls below !! caution !!
                            logger.debug(f"  - Adding RD Hash from remote: {item} ...")
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

                        except Exception as e:
                            logger.error(f"An Error has occured on pushing hash to RD (+cancellation of whole batch) : {e}")
                            break
                else:
                    logger.critical(f"No local data has been retrieved via rdump_backup() in remoteScan()")
            else:
                logger.critical(f"No local data has been retrieved via rdump_backup() in remoteScan()")

    else:
        logger.warning("---- No REMOTE_RDUMP_BASE_LOCATION specified, ignoring but remotescan can't work ----")

# ----------------------------------
# rd_progress Fill the pile chronologically each time it's called in server and new stuff arrives
# getrdincrement
        
def getrdincrement(incr):
    if (os.path.exists(pile_file)):
        # gets full array 
        cur_pile = file_to_array(pile_file)
        return json.dumps({'hashes': cur_pile[incr:], 'lastid': len(cur_pile)}).encode()
    else:
        # it forces this sever to call rd_progress at least once
        service_rdprog_instance = ScriptRunner.get(rd_progress)
        service_rdprog_instance.run()
        if(service_rdprog_instance.get_output() != 'phony'):
            # logger.info("periodic trigger is working")
            # we are forced to consume output from this funciton to avoid disjoined calls to output queue
            logger.warning(f"rd_progress called in getrdincrement (should happen only once)")
        return ""


def rdump_backup(including_backup = True, returning_data = False):
    if including_backup:
        if(os.path.exists(rdump_file)):
            os.makedirs(rdump_backup_folder, exist_ok=True)
            # copy with date in filename
            today = datetime.now()
            file_backuped = "/rd_dump_"+today.strftime("%Y%m%d")+".json"
            subprocess.call(['cp', rdump_file, rdump_backup_folder+file_backuped])

    try:
        # create horodated json file of my torrents
        data = RD.torrents.get(limit=2500, page=1).json() # todo: it's only the 2500 last items
        # Store the data in a file
        with open(rdump_file, 'w') as f:
            json.dump(data, f)
        if returning_data:
            return data
    except Exception as e:
        logger.critical(f"An error occurred on rdump: {e}")
        return "Error"
    return None

def read_incr_from_file():
    try:
        with open(rdincr_file, 'r') as file:
            strincr = file.read().strip()
            incr = int(strincr)  # Attempt to convert an empty string to an integer
    except FileNotFoundError:
        logger.warning(f"Increment data file not exists yet (taking default then)")
        return int(DEFAULT_INCR)
    except ValueError as e:
        logger.critical(f"Error taking increment from data file, corrupted data (taking default): {e}")
        return int(DEFAULT_INCR)
    else:
        return incr


def save_incr_to_file(incr):
    try:
        with open(rdincr_file, 'w') as file:
            file.write(str(incr))
    except IOError as e:
        logger.critical(f"Error saving incr to file: {e}")
