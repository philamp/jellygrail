import threading
import shlex
from base import *

logger = logging.getLogger('jellygrail')


def get_plain_ffprobe(file_path):
    # this is plain ffprobe command call returning each part in separated vars, 
    # not decoding stdout !!
    # migrating to 8000000 analyse duration also
    try:
        command = [
            "ffprober", 
            "-v", "error",  # Hide logging
            "-analyzeduration", '8000000',
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            file_path
        ]

        # Execute the command
        result = subprocess.run(command, capture_output=True, check=True, text=False)

    except subprocess.CalledProcessError as e:
        logger.critical(f"get_plain_ffprobe failure:\nReturn code:{e.returncode}\nstdout:{e.output}\nstderr:{e.stderr}")
        return (e.output, e.stderr, e.returncode)
    
    #logger.info(f"get_plain_ffprobe success:\nReturn code:{result.returncode}\nstdout:{result.stdout}\nstderr:{result.stderr}")
    return (result.stdout, result.stderr, result.returncode)


    

'''
def get_ffprobe(file_path):
    # Construct the ffprobe command to get the format information, which includes the overall bitrate
    try:
        command = [
            "ffprobe", 
            "-v", "error",  # Hide logging
            "-analyzeduration", '4000000',
            "-select_streams", "v:0",
            "-show_entries", "format=bit_rate",  # Show overall bitrate
            "-show_streams",
            "-of", "json",  # Output format as JSON
            file_path
        ]

        # Execute the command
        result = subprocess.run(command, capture_output=True, text=True)
        output = result.stdout


    
        info = json.loads(output)
        bitrate = round(int(info["format"]["bit_rate"]) / 1000000)
        # Extract overall bitrate

    except subprocess.CalledProcessError as e:
        logger.critical(f" - FAILURE_ffprobe decode: SubprocessCallError on {file_path} : {e}")
        return (None, None)

    except (KeyError, IndexError, json.JSONDecodeError):
        logger.error(f" - FAILURE_ffprobe decode: Unable to extract even basic information on {file_path}")
        return (None, None)

    dvprofile = None
    if( sideinfo := info['streams'][0].get('side_data_list') ):
        dvprofile = sideinfo[0].get('dv_profile')

    return ( f"{bitrate}Mbps", dvprofile)
'''

# RARs
def unrar_to_void(rar_file_path):

    try:
        logger.debug(f"      > Trying to void-unrar it ...")
        subprocess.run(['unrar', 't', "-sl34000000", "-y", "-ierr", rar_file_path], check=True, stderr=subprocess.PIPE)

    except subprocess.CalledProcessError as e:
        # The command failed, check if it's the specific error we're looking for
        if "Input/output error" in e.stderr.decode():
            return "ERROR_IO"
        elif "No files to extract" in e.stderr.decode():
            return "ERROR_NOFILES"
        elif "Unexpected end of archive" in e.stderr.decode():
            return "ERROR_IO"
        else:
            logger.error("      - The unrar command failed for unknown reason 1:", e.stderr.decode())
        return "ERROR"
    except Exception as e:
        logger.error("      - The unrar command failed for unknown reason 2:", str(e))
        return "ERROR"
    else:
        logger.debug("      > ... SUCCESS !")
    return "OK"

# ISOs
def mount_iso(iso_path, mount_folder):
    logger.debug(f"      > MOUNTING ISO to cache small metadata files in rclone: {iso_path}\n      ")
    # Create the mount folder if it doesn't exist
    if not os.path.exists(mount_folder):
        os.makedirs(mount_folder)
    
    # Build and execute the mount command
    mount_command = f"mount -o loop '{iso_path}' {mount_folder}"
    try:
        subprocess.run(shlex.split(mount_command), check=True, timeout=60)
    except subprocess.TimeoutExpired:
        logger.error(f" - FAILURE_Mount : Mount operation timed out after 60 seconds on {iso_path}")
        


def unmount_iso(mount_folder):
    # Build and execute the unmount command
    unmount_command = f"umount {mount_folder}"
    subprocess.run(shlex.split(unmount_command), check=True)
    
    # Remove the mount folder
    os.rmdir(mount_folder)

def read_file_with_timeout(file_path, timeout = 604):
    def worker():
        try:
            with open(file_path, 'rb') as f:
                _ = f.read(34000000)  # Tente de lire les 34 000 000 premiers octets
        except Exception as e:
            logger.error(f" - FAILURE_read : An error occurred on direct read {file_path}: {e}.")
            nonlocal success  # Pour modifier la variable `success` en dehors de cette sous-fonction
            success = False  # Marque l'échec de la lecture en raison d'une exception

    success = True  # Initialise le succès à True avant de commencer
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        logger.error(f" - FAILURE_read : Waited 604 seconds (10m) : Reading file {file_path} took too long and was aborted.")
        return False
    elif not success:
        # Si `worker` a rencontré une exception, `success` aura été changé en False
        logger.error(f" - FAILURE_read : Reading file {file_path} failed due to an IO error.")
        return False
    else:
        print("r", end="")
        return True

def read_small_files(src_folder):
    isdvd = False
    for root, dirs, files in os.walk(src_folder):
        for file in files:
            file_path = os.path.join(root, file)

            if file.endswith(".vob"):
                isdvd = True
            
            # if os.path.getsize(file_path) <= max_size_bytes: -> removed to read all files including > 34000000 but read_file_with_timeout will only take the 34000000 first bytes
            if not read_file_with_timeout(file_path):
                logger.error(f" - FAILURE_read : Abandoning due to timeout or IO Error on mounted iso on {src_folder}")
    return isdvd
