import logging
import os
#rd api
from rdapi import RD
import requests
import json
import subprocess
from datetime import datetime
from script_runner import ScriptRunner
RD = RD()
# plug to same logging instance as main
logger = logging.getLogger('jellygrail')

# rd local dump cron-backups folder
rdump_backup_folder = '/jellygrail/data/backup'

# rd local dump location
rdump_file = '/jellygrail/data/rd_dump.json'

# pile file
pile_file = '/jellygrail/data/rd_pile.json' 

# rd last date of import file
rdincr_file = '/jellygrail/data/rd_incr.txt'

# rd remote location
REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')

DEFAULT_INCR = os.getenv('DEFAULT_INCR')

def test():
    dumped_data = json.dumps(RD.torrents.get(limit=2, page=1).json())
    return dumped_data

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
                    logger.info("RD_PROGRESS > I detected new torrents having 'downloaded' status, so I started /scan method")
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
            return ""

    else:
        logger.critical(f"An error occurred on getting RD data in rd_progress method")
        return ""


# ----------------------------------
        
def remoteScan():

    # take data from remote RD account
    # if no local data, take it (we have to compare later on)

# compare with rdump not pile
    

    if REMOTE_RDUMP_BASE_LOCATION.startswith('http'):
         # -> ok but if remotescan is called a lot ... lot of backups....
        cur_incr = int(read_incr_from_file())
        remote_loc = f"{REMOTE_RDUMP_BASE_LOCATION}/getrdincrement/{cur_incr}"
        try:
            response = requests.get(remote_loc)
            response.raise_for_status()
            server_data = response.json()
        except requests.RequestException as e:
            logger.critical(f"Error fetching data from server: {e}")
        else:
            if server_data is not None:
                if len(server_data['hashes']) > 0:
                    if last_added_incr := server_data['lastid']:
                        save_incr_to_file(str(last_added_incr))
                else:
                    logger.debug(f"Data was fetched but no new data")
                    return None
            else:
                logger.critical(f"Data was fetched but data returned is None")
                return None
            
            if(local_data := rdump_backup(including_backup = False, returning_data = True)):
                local_data_hashes = [iteml.get('hash') for iteml in local_data]
                push_to_rd_hashes = [item for item in server_data['hashes'] if item not in local_data_hashes]
                for item in push_to_rd_hashes:
                    try:
                        logger.debug(f"> ajout du magnet: {item}")
                        returned = RD.torrents.add_magnet(item).json()
                        RD.torrents.select_files(returned.get('id'), 'all')
                    except Exception as e:
                        logger.error(f"An Error has occured on pushing hashes to RD : {e}")
            else:
                logger.critical(f"No local data has been retrieved via rdump_backup() in remoteScan()")

    else:
        logger.warning("---- No REMOTE_RDUMP_BASE_LOCATION specified, ignoring ----")

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

def read_incr_from_file():
    try:
        with open(rdincr_file, 'r') as file:
            date = file.read().strip()
            return date
    except FileNotFoundError:
        return DEFAULT_INCR

def save_incr_to_file(date):
    try:
        with open(rdincr_file, 'w') as file:
            file.write(date)
    except IOError as e:
        logger.critical(f"Error saving date to file: {e}")
