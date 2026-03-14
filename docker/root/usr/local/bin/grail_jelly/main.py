#!/usr/bin/env python3
# coding: utf-8
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')
from base.constants import *
import time
import threading
import pyinotify
import shlex
from http.server import BaseHTTPRequestHandler, HTTPServer
from script_runner import ScriptRunner
import urllib
import os
import datetime
import socket
import requests
import struct

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

### SETTINGS LOADING ###
#VERSION = "20250808" # now in constants !!! Should be aligned to settings.env.template and early_init.sh and kodi addon init_context!!!
INCR_KODI_REFR_MAX = 8
CONFIG_VERSION = os.getenv('CONFIG_VERSION') or VERSION # explain : getenv of empty returns "", "" is falsy so CONFIG_VERSION will be VERSION if not set
REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')

LAN_IP = "127.0.0.1" # will be guessed later

KODI_MAIN_URL = os.getenv('KODI_MAIN_URL') or ""
# Pre-compute serialized settings
PLEX_URLS_ARRAY = os.getenv('PLEX_URLS', '').split('|')
# Pre-compute some flags

JF_WANTED = (os.getenv('JF_WANTED') or "y") != "n"
JF_WANTED_ACTUALLY = JF_WANTED
USE_PLEX = (os.getenv('USE_PLEX') or "y") != "n"
USE_PLEX_ACTUALLY = USE_PLEX and len(PLEX_URLS_ARRAY) > 0 and PLEX_URLS_ARRAY[0] != ""
USE_KODI = (os.getenv('USE_KODI') or "y") != "n"
USE_KODI_ACTUALLY = USE_KODI

#default filling
socket_started = False
at_least_once_done = [False, False, False, False, False, False, False, False]
post_kodi_run_step = 12

# ------ Contact points
from jg_services import premium_timeleft
from jgscan import init_mountpoints, multiScan, get_fastpass_ffprobe
from jfconfig import jfconfig
#from jgscan.jgsql import init_database, sqclose
from jgscan.jgsql import jellyDB, staticDB
from nfo_generator import nfo_loop_service, fetch_nfo
from kodi_services import refresh_kodi, send_nfo_to_kodi, is_kodi_alive, merge_kodi_versions
from kodi_services.sqlkodi import kodi_mysql_init_and_verify
from jfapi import lib_refresh_all, wait_for_jfscan_to_finish

import jg_services

# setup the logger once
from base import logger_setup
logger = logger_setup.log_setup()

# CONFIG INTEGRITY WARNINGS
if VERSION != CONFIG_VERSION:
    logger.error("    CONFIG/ Config version is different from app version, please rerun jg-config.sh and restart container")

if not JF_WANTED:
    logger.warning("    CONFIG/ Jellyfin is disabled, maybe intentionnaly ? Otherwise please rerun jg-config.sh and restart container.")
else:
    if os.getenv('JF_LOGIN') is None or os.getenv('JF_LOGIN') == "":
        logger.warning("    CONFIG/ JF wanted but JF_LOGIN environment variable not set. admin will be used as default login")
    if os.getenv('JF_PASSWORD') is None or os.getenv('JF_PASSWORD') == "":
        logger.critical("    CONFIG/ JF wanted but JF_PASSWORD environment variable not set. admin will be used as default password")

if not USE_KODI:
    logger.warning("    CONFIG/ Kodi not wanted, maybe intentionnaly ? Otherwise please rerun jg-config.sh and restart container.")
else:
    if not USE_KODI_ACTUALLY:
        logger.error("    CONFIG/ Kodi wanted but Kodi main url not defined, please check your settings.env file")
    if not JF_WANTED:
        logger.warning("    CONFIG/ Kodi wanted but embedded Jellyfin disabled, Kodi can work without NFO sync from jellyfin, however make sure not to use the Local NFO data scrapper in Kodi video sources configuration.")

if not USE_PLEX:
    logger.info("    CONFIG/ Plex integration not wanted.")
else:
    if not USE_PLEX_ACTUALLY:
        logger.error("    CONFIG/ USE_PLEX is set but PLEX_URLS is empty, please check your settings.env file")



class RequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Redirect the log message to the logger
        logger.info("   HTTP-IN/ %s - [%s] %s" % (
            self.client_address[0],
            self.log_date_time_string(),
            format % args))

    def standard_headers(self, type='text/html'):
        self.send_response(200)
        self.send_header('Content-type', type)
        self.end_headers()

    def do_GET(self):

        # parse the path
        url_path = urllib.parse.urlparse(self.path).path

        if url_path == '/test':
            _test_instance = ScriptRunner.get(jg_services.test)
            _test_instance.run()
            dumped_data = _test_instance.get_output()
            self.standard_headers()
            self.wfile.write(bytes(dumped_data, "utf8"))

        elif url_path == '/scan':
            _scan_instance = ScriptRunner.get(refresh_all)
            _scan_instance.resetargs(1)
            _scan_instance.run()
            if _scan_instance.queued_execution:
                message = "### scan() queued for later ! (Forces a library scan)\n"
            else:
                message = "### scan() directly executed ! (Forces a library scan)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == '/kodi_scan':
            _kodirefresh_instance = ScriptRunner.get(refresh_all)
            _kodirefresh_instance.resetargs(2)
            _kodirefresh_instance.run()
            if _kodirefresh_instance.queued_execution:
                message = "### refresh_mediacenters queued for later ! \n"
            else:
                message = "### refresh_mediacenters directly executed ! \n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == '/nfo_scan':
            _nfo_scan = ScriptRunner.get(refresh_all)
            _nfo_scan.resetargs(4)
            _nfo_scan.run()
            if _nfo_scan.queued_execution:
                message = "### nfo_generation queued for later ! \n"
            else:
                message = "### nfo_generation directly executed ! \n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

            '''
        elif url_path == '/kodi_alive':
            _kodi_alive = ScriptRunner.get(is_kodi_alive)
            _kodi_alive.run()
            if _kodi_alive.queued_execution:
                message = "### kodi alive queued for later ! \n"
            else:
                message = "### kodi alive directly executed ! \n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))
            '''

        elif url_path == '/nfo_send':
            _nfo_send = ScriptRunner.get(refresh_all)
            _nfo_send.resetargs(5)
            _nfo_send.run()
            if _nfo_send.queued_execution:
                message = "### nfo_send queued for later ! \n"
            else:
                message = "### nfo_send directly executed ! \n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == '/nfo_merge':
            _nfo_merge = ScriptRunner.get(refresh_all)
            _nfo_merge.resetargs(6)
            _nfo_merge.run()
            if _nfo_merge.queued_execution:
                message = "### nfo_merge queued for later ! \n"
            else:
                message = "### nfo_merge directly executed ! \n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == '/rd_progress':
            _rdprog_instance = ScriptRunner.get(jg_services.rd_progress)
            _rdprog_instance.run()
            if _rdprog_instance.queued_execution:
                message = "### rd_progress() queued for later ! (Checks Real-Debrid status)\n"
            else:
                message = "### rd_progress() directly executed ! (Checks Real-Debrid status)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))
            if(_rdprog_instance.get_output() == 'PLEASE_SCAN'):
                _scan_instance = ScriptRunner.get(refresh_all)
                _scan_instance.resetargs(1)
                _scan_instance.run()

        elif url_path == '/remotescan':
            _remoteScan_instance = ScriptRunner.get(jg_services.remoteScan)
            _remoteScan_instance.run()
            if _remoteScan_instance.queued_execution:
                message = "### remoteScan() queued for later ! (Checks for remote's new RD hashes)\n"
            else:
                message = "### remoteScan() directly executed ! (Checks for remote's new RD hashes)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))


        elif url_path == "/backup":
            _rdump_backup_instance = ScriptRunner.get(jg_services.rdump_backup)
            _rdump_backup_instance.run()
            if _rdump_backup_instance.queued_execution:
                message = "### rdump_backup() queued for later ! (backup the cur dump and dump)\n"
            else:
                message = "### rdump_backup() directly executed ! (backup the cur dump and dump)\n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

        elif url_path == "/restore":
            _rdump_restorelist_instance = ScriptRunner.get(jg_services.restoreList)
            _rdump_restorelist_instance.run()
            self.standard_headers()
            output = _rdump_restorelist_instance.get_output()
            self.wfile.write(bytes(output, "utf8"))
            # choice will go to /restoreitem?filename=&token=

        elif url_path == "/restoreitem":
            allparams = urllib.parse.urlparse(self.path).query
            params_dict = urllib.parse.parse_qs(allparams)
            if params_dict.get('filename') and params_dict.get('token'):
                fn = params_dict.get('filename')[0]
                tk = params_dict.get('token')[0]
                _restoritm_instance = ScriptRunner.get(jg_services.restoreitem)
                _restoritm_instance.resetargs(fn, tk)
                _restoritm_instance.run()
                self.standard_headers('application/json')
                output = _restoritm_instance.get_output()
                if not output.startswith("Wrong"):
                    self.wfile.write(bytes(output, "utf8"))
                else:
                    self.send_error(403, output)


        elif url_path.startswith("/getrdincrement/"):
            try:
                incr = int(url_path[len("/getrdincrement/"):].rstrip('/'))
                # self.filter_and_send_data(input_date)
            except ValueError:
                self.send_error(400, "Invalid increment format")
            else: 
                if 1 == 2: #TODO remove disable
                    _getrdincr_instance = ScriptRunner.get(jg_services.getrdincrement)
                    _getrdincr_instance.resetargs(incr)
                    _getrdincr_instance.run()
                    self.standard_headers('application/json')
                    output = _getrdincr_instance.get_output()
                    if output != '':
                        self.wfile.write(output)
                    else:
                        self.send_error(503, "Client triggered service, not yet available - pile file not yet created on server, please retry in few seconds")
        else:
            self.standard_headers()
            self.send_error(404, "> This is unknown command")


def is_kodi_alive_loop():
    global post_kodi_run_step

    while True:
        if is_kodi_alive():
            #logger.info("KODI-ALIVE/ ...Main kodi up again.")
            _refreshkodi_thread = ScriptRunner.get(refresh_all)
            _refreshkodi_thread.resetargs(post_kodi_run_step)
            _refreshkodi_thread.run()
            break
        time.sleep(15)

def refresh_all(step):

    global at_least_once_done # at least one run per day var
    global post_kodi_run_step

    retry_later = False

    nb_items = 1

    # reboot the post kodi steps to wanted step if possible 
    # at the beginning (1 or 2) -> ok anyway
    # partial (4) -> only if previously completed
    if step < 3:
        post_kodi_run_step = 12
    if step == 4 and post_kodi_run_step == 16:
        post_kodi_run_step = 15
    step_string = "            2--5"


    if step == 1: # triggered also with rd_progress_response == "PLEASE_SCAN":
        logger.info("         1| Main JG Scan...")
        #nb_items = multiScan() #TODO remove
        #if nb_items > 10: #if scan has added more than 10 items, we wait for full jellyfin scan + nfo generation before refereshing kodi (to avoid too many nfo refresh calls to kodi)
            #toomany = True

    
        logger.info(f"         1| ...Main JG Scan found {nb_items} new item(s)")


        # --unit test nb of items
        #nb_items = 11
        #logger.info(f"       ...| nbitems overriden with {nb_items} for testing")
        # ----


    if (step < 3 or (step > 10 and step < 13)): 
        if (not at_least_once_done[2] or nb_items > 0) and nb_items < INCR_KODI_REFR_MAX:
            if USE_KODI_ACTUALLY and False: #TODO remove                  
                if not refresh_kodi():
                    retry_later = True
                else:
                    at_least_once_done[2] = True
                    if post_kodi_run_step == 12:
                        post_kodi_run_step = 15
        elif(not nb_items < INCR_KODI_REFR_MAX):
            logger.info(f"         2| Kodi library refresh will be tried after Jellyfin refresh because there are more than {INCR_KODI_REFR_MAX-1} items")
        else:
            logger.info("         2| Kodi refresh bypassed")

    if step < 4:
        if not at_least_once_done[3] or nb_items > 0:
            if JF_WANTED_ACTUALLY:
                logger.info("         3| Jellyfin library refresh...")
                # refresh the jellyfin library and merge variants
                #lib_refresh_all() #TODO remove
                #wait_for_jfscan_to_finish() #TODO remove
                pass
            
            if USE_PLEX_ACTUALLY:
                logger.info("         3| Plex library refresh...")
                for plex_url in PLEX_URLS_ARRAY:
                    try:
                        requests.get(plex_url, timeout=10)
                    except Exception as e:
                        logger.error(f"   REFRESH~ Plex refresh API unavailable for {plex_url}")
            at_least_once_done[3] = True
        else:
            if JF_WANTED_ACTUALLY:
                logger.info("         3| Library refresh bypassed")
            if USE_PLEX_ACTUALLY:
                logger.info("         3| Plex refresh bypassed")

    if step < 5:
        if JF_WANTED_ACTUALLY:
            logger.info("         4| Generate Jellyfin NFOs *if any new items*...")
            if not nfo_loop_service():
                step = 9 # if jfwanted but nfo gen fails stop here but will do kodi scan and merge
                logger.error("         4| Generating NFOs from Jellyfin did not work, Kodi will refresh but without Jellyfin metadata")
        else:
            step = 9
            logger.warning("         4| Can't be done because JF_WANTED is not enabled in settings.env, Kodi will refresh but without Jellyfin metadata: In this case kodi sources should be configured for online metadata")

    # it's the alternative kodi refresh
    # if toomany, kodi refresh is done after jellyfin

    if USE_KODI_ACTUALLY:
        if (step < 3 or (step > 10 and step < 13) or step == 9):
            if not nb_items < INCR_KODI_REFR_MAX and False: #TODO remove
                    if not refresh_kodi():
                        retry_later = True
                    else:
                        at_least_once_done[2] = True
                        if post_kodi_run_step == 12:
                            post_kodi_run_step = 15


        # if step inferior or if specifically wanted with the webservice (6)
        if (step < 6 or (step > 10 and step < 16)) and retry_later == False:
                if JF_WANTED_ACTUALLY and False: #TODO remove
                    if not send_nfo_to_kodi():
                        retry_later = True
                    else:
                        if post_kodi_run_step == 15:
                            post_kodi_run_step = 16
                else:
                    if post_kodi_run_step == 15:
                        post_kodi_run_step = 16

    else:
        post_kodi_run_step = 16
        logger.warning(" Steps 2 (refresh) and 5 (nfo sync) can't be done because KODI_MAIN_URL is not defined in settings.env")

    # is step inferior or specifically wanted with the webservice (6 : nfo_merge)
    if (step < 7 or (step > 10 and step < 17) or step == 9):
        merge_kodi_versions()
    
    
    # 2 5 6 = 12 15 16 (>10)
    # potential refresh_all setup if run by kodi_alive_loop (if run by retry later or already run)
    # _prepare_kodi_dedicated_thread = ScriptRunner.get(refresh_all)
    # _prepare_kodi_dedicated_thread.resetargs(post_kodi_run_step)
    if retry_later == True: # and kodi_mysql_init_and_verify(just_verify=True):
        logger.warning(f" Steps {step_string[post_kodi_run_step:]} Will be retried when Main Kodi is up again (15s retry-loop enabled)...")
        _is_kodi_alive_loop_thread = ScriptRunner.get(is_kodi_alive_loop)
        _is_kodi_alive_loop_thread.run() # will run only if not running, no queue
        # toimprove : ne need to queue this job ?
        # will run refresh_all with arg 8



def run_server(server_class=HTTPServer, handler_class=RequestHandler, port=WEBSERVICE_INTERNAL_PORT):
    global httpd
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logger.info(f"      HTTP/ JellyGrail WebService running on port: {port} ~")
    httpd.serve_forever()


class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        self.inotify_run()
    def process_IN_DELETE(self, event):
        self.inotify_run()
    def process_IN_MODIFY(self, event):
        self.inotify_run()
    def process_IN_MOVED_FROM(self, event):
        self.inotify_run()
    def process_IN_MOVED_TO(self, event):
        self.inotify_run()
    def inotify_run(self):
        logger.debug(". inotify handler will call /scan in 30 minutes")
        time.sleep(1800) # tothink toimprove
        _scan_instance = ScriptRunner.get(refresh_all)
        _scan_instance.resetargs(1)
        _scan_instance.run()

# ---- included cron
        
# restart_jellygrail_at is in jfapi module

def guess_lan_ip():

    global LAN_IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        lip = s.getsockname()[0]
    except Exception as e:
        logger.error(f"Error when trying to guess LAN IP: {e}")
    else:
        LAN_IP = lip
        if LAN_IP != WEBDAV_LAN_HOST and USE_KODI_ACTUALLY:
            logger.warning(f"    CONFIG/ LAN IP ({LAN_IP}) is different from WEBDAV_LAN_HOST ({WEBDAV_LAN_HOST}), NFOs might not reference correct URLs")
    finally:
        s.close()


def ssdp_broadcast_daemon():

    # test in linux with nc -ul 6505

    # struct is : JGx|VERSION|LAN_IP|WEBSERVICE_INTERNAL_PORT|KODI_MYSQL_PORT|WEBDAV_INTERNAL_PORT
    #      0       1               2                  3                                     4                                              5                              6
    msg = "JGx|" + VERSION + "|" + LAN_IP + "|" + str(WEBSERVICE_INTERNAL_PORT) + "|" + str(KODI_MYSQL_CONFIG.get('port', '0')) + "|" + str(WEBDAV_INTERNAL_PORT) + "|" + SSDP_TOKEN

    encmsg = msg.encode("ascii")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    logger.info(f"      SSDP/ Broadcasting message {msg} on port {str(SSDP_PORT)} every 5sec~")
    while True:
        sock.sendto(encmsg, ("<broadcast>", SSDP_PORT))
        time.sleep(5)


def periodic_trigger(seconds=120):
    _rdprog_instance = ScriptRunner.get(jg_services.rd_progress)
    while True:
        time.sleep(seconds)
        _rdprog_instance.run()
        if(_rdprog_instance.get_output() == 'PLEASE_SCAN'):
            _scan_instance = ScriptRunner.get(refresh_all)
            _scan_instance.resetargs(1)
            _scan_instance.run()

def periodic_trigger_rs(seconds=350):
    _rs_instance = ScriptRunner.get(jg_services.remoteScan)
    while True:
        time.sleep(seconds)
        _rs_instance.run()

def periodic_trigger_nfo_gen(seconds=200):
    _nfogen_instance = ScriptRunner.get(refresh_all)
    while True:
        time.sleep(seconds)
        _nfogen_instance.resetargs(4)
        _nfogen_instance.run()

def inotify_deamon(to_watch):
    # ----- inotify 

    # Set up watch manager
    wm = pyinotify.WatchManager()

    for item2watch in to_watch:
        wm.add_watch(item2watch, pyinotify.ALL_EVENTS, rec=True, auto_add=True)
        logger.debug(f". inotify_deamon | Monitoring : {item2watch}")

    # Event handler
    event_handler = EventHandler()

    # Notifier
    notifier = pyinotify.Notifier(wm, event_handler)
    logger.info("   STORAGE/ Local drive(s) activity detector started ~")

    notifier.loop()
    # ----- inotify END

def restart_jgdocker_at(target_hour=6, target_minute=30):
    global httpd
    while True:
        # Get the current time
        now = datetime.datetime.now()
        next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if next_run < now:
            next_run += datetime.timedelta(days=1)
        sleep_time = (next_run - now).total_seconds()
        logger.info(f"  SCHEDULE/ JellyGrail next restart in {str(sleep_time/3600)[:4]} hours ~")
        time.sleep(sleep_time)
        if True:
            logger.warning(f"  SCHEDULE/ ~ JellyGrail will now shutdown for restart, beware '--restart unless-stopped' must be set in your docker run otherwise it won't restart !!")
            httpd.shutdown()


def handle_socket_request(connection, client_address, socket_type):
    if socket_type == "nfopath":
        logger.debug(f". {socket_type} socket OPEN [handle_socket_request]")
    try:
        if socket_type == "ffprobe":
            while True:
                data = connection.recv(1024)
                if data:
                    args = shlex.split(data.decode('utf-8'))
                    rkey = 3
                    for key, arg in enumerate(args):
                        if arg == "-i":
                            rkey = key + 1

                    messagein = args[rkey]
                    (stdout, stderr, returncode) = get_fastpass_ffprobe(messagein)
                    # Create a single message with lengths and data
                    messageout = (
                        struct.pack('!I', len(stdout)) + stdout +
                        struct.pack('!I', len(stderr)) + stderr +
                        struct.pack('!i', returncode)
                    )
                    # logger.warning(f"Message sent: {messageout}")
                    connection.sendall(messageout)
                else:
                    #logger.debug(f"~> main/socket | {socket_type} socket CLOSED.")
                    break
                
        if socket_type == "nfopath":
            while True:
                data = connection.recv(1024)
                if data:
                    
                    message = data.decode('utf-8')
                    response = fetch_nfo(message)
                    connection.sendall(response.encode('utf-8'))
                else:
                    logger.error(f"    SOCKET| {socket_type} socket disconnected (BindFS instance must have crashed !!)")
                    break
    finally:
        connection.close()

def socket_server_waiting(socket_type):
    global socket_started
    server_address = f'/tmp/jelly_{socket_type}_socket'
    
    # Make sure the socket does not already exist
    try:
        os.unlink(server_address)
    except OSError:
        if os.path.exists(server_address):
            raise

    # Create a UNIX socket
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    # Bind the socket to the address
    server_socket.bind(server_address)

    os.chmod(server_address, 0o777)

    # Listen for incoming connections
    server_socket.listen()
    if socket_type == "ffprobe":
        logger.info(f"    SOCKET| Waiting for any {socket_type} wrapper transaction ~")

    while True:
        #print(".", end="", flush=True)
        connection, client_address = server_socket.accept() # it waits here
        if socket_type == "nfopath":
            socket_started = True
            logger.info(f"    SOCKET| BindFS connected")
        _handle_client_thread = threading.Thread(target=handle_socket_request, args=(connection, client_address, socket_type))
        _handle_client_thread.daemon = True
        _handle_client_thread.start()

def bdd_install():

    dbinstance = jellyDB()
    #init_database() already in the object init
    # Play migrations
    dbinstance.jg_datamodel_migration()

    # create movies and shows parent folders
    dbinstance.insert_data("/movies", None, None, None, 'all')
    dbinstance.insert_data("/shows", None, None, None, 'all')
    #insert_data("/concerts", None, None, None, 'all')
    dbinstance.sqcommit()
    dbinstance.sqclose()
    
    del dbinstance

if __name__ == "__main__":

    full_run = True

    guess_lan_ip()

    print( """
""" + YELLOW + " ________________________ github.com/philamp/" + f"""
|
|       ___     _ _        ____          _ _
|      |_  |___| | |_   _ / __/ _ ____ _(_) |
|__   _  | / _ \ | | | | | |  _/ '_/ _` | | |  __
     / |_|   __/ |   |_|   |_| | |  (_| | | |    |
     \____/\___,_,_|\__, /\____,_| \__,_,_,_|    |
                     |__/                        |
                                    v{VERSION}    |
     {GREEN}__________________{YELLOW}_{GREEN}__{YELLOW}__{GREEN}_{YELLOW}____________________|""" + RESET)


    # Some info to reassure user
    logger.info(f"|")
    logger.info(f"|  - Prefered languages:             {os.getenv('INTERESTED_LANGUAGES')}")
    if JF_WANTED:
        logger.info(f"|  - Jellyfin Metadata:              Country: {os.getenv('JF_COUNTRY')}")
        logger.info(f"|                                    Language: {os.getenv('JF_LANGUAGE')}")
        logger.info(f"|  - Jellyfin host:                  http://localhost:8096 (login: {os.getenv('JF_LOGIN') or 'admin'})")
        logger.info(f"|  - Nginx WebDAV server:            http://{WEBDAV_HOST_PORT} (no auth, local access only! see README! don't expose it!)")
        logger.info(f"|  - JellyGrail WebService:          http://{LAN_IP}:{WEBSERVICE_INTERNAL_PORT} (no auth, local access only! see README! don't expose it!)")
        logger.info(f"|  - SSDP Broadcasting on port:      {SSDP_PORT} (for Kodi auto-discovery)")
    if USE_KODI_ACTUALLY:
        logger.info(f"|  - Kodi host:                      {KODI_MAIN_URL}")
        logger.info(f"|                                    (NFO sync: {'enabled' if JF_WANTED else 'disabled'})""")
    if REMOTE_RDUMP_BASE_LOCATION.startswith('http') or REMOTE_RDUMP_BASE_LOCATION != "http://hostname-or-ip:1234":
        logger.info(f"|  - Remote JellyGrail URL:          {REMOTE_RDUMP_BASE_LOCATION}")
    if RD_API_SET:  
        logger.info(f"|  - Real-Debrid API:                Enabled (token set)")
    if USE_PLEX_ACTUALLY:
        logger.info(f"|  - Plex refresh URL(s): {', '.join(PLEX_URLS_ARRAY)}")
    logger.info(f"|________________________________________ __ _")
    logger.info(f" ")


    # BDD INIT and close
    bdd_install()

    if JF_WANTED:
        if not jfconfig():
            logger.critical("  JELLYFIN| Config failed, please stop the container and fix the error. If login/password lost, you can reset Jellyfin by emptying /jellygrail/jellyfin/config and /jellygrail/jellyfin/cache folders but it will remove all your Jellyfin libraries, configuration and users.")
            JF_WANTED_ACTUALLY = False


    # one sqlite READ ONLY  thread for nforead and ffprobewrappe
    staticDB.sinit()

    thread_ssdp = threading.Thread(target=ssdp_broadcast_daemon)
    thread_ssdp.daemon = True  # exits when parent thread exits
    thread_ssdp.start()

    thread_ef = threading.Thread(target=socket_server_waiting, args=("ffprobe",))
    thread_ef.daemon = True  # exits when parent thread exits
    thread_ef.start()
    
    # Thread 0.1 - UNIX Socket (nfo path retriever socket : loop waiting thread) -- multithread requests ready but bindfs is not
    thread_e = threading.Thread(target=socket_server_waiting, args=("nfopath",))
    thread_e.daemon = True  # exits when parent thread exits
    thread_e.start()


    logger.info("    SOCKET| Waiting for BindFS ...")
    waitloop = 0
    while not socket_started:
        #print(".", end="", flush=True)
        waitloop += 1
        time.sleep(1)
        if(waitloop > 30):
            logger.critical("    SOCKET| BindFS is not connecting to socket !!!")
        if(waitloop > 32):
            # this is a workaround if docker logs contains : s6-sudoc: fatal: unable to get exit status from server: Operation timed out, docker restarts and usually works after. Weird error. Seems related to the way socket is instanciated
            full_run = False
            logger.critical(f"    SOCKET| JellyGrail now restarts if '--restart unless-stopped' was set, so please stop it manually to fix errors !!!")
            break

    # ----------------- INITs -----------------------------------------
    # Initialize the database connection, includes open() ----

    # walking in mounts and subwalk only in remote_* and local_* folders
    to_watch = init_mountpoints()
    # Config JF before starting threads and server threads


    kodi_mysql_init_and_verify(just_verify=True)

    if full_run == True:
        # ------------------- threads A + Ars, B, C, D, E  -----------------------
        
        # thread E
        if JF_WANTED:
            thread_e = threading.Thread(target=periodic_trigger_nfo_gen)
            thread_e.daemon = True  # 
            thread_e.start()
            logger.info("  SCHEDULE/ NFO Metadata delta generation will be triggered every 3mn ~")


        if RD_API_SET:

            logger.warning(f"REALDEBRID/ Premium days remaining: {str(premium_timeleft()/86400)[:4]}")

            # A: rd_progress called automatically every 2mn
            thread_a = threading.Thread(target=periodic_trigger)
            thread_a.daemon = True  # 
            thread_a.start()

            # Ars: remoteScan trigger every 7mn
            if REMOTE_RDUMP_BASE_LOCATION.startswith('http') or REMOTE_RDUMP_BASE_LOCATION != "http://hostname-or-ip:1234":
                thread_ars = threading.Thread(target=periodic_trigger_rs)
                thread_ars.daemon = True  # 
                thread_ars.start()
                logger.info("  SCHEDULE/ Real Debrid API remoteScan will be triggered every 7mn ~")
            else:
                logger.info("    MANUAL/ Real Debrid remoteScan skipped as REMOTE_RDUMP_BASE_LOCATION is not set. If needed, verify value in ./jellygrail/config/settings.env and restart container.")
            
            logger.info(f"  SCHEDULE/ Real Debrid API rd_progress will be triggered every 2mn ~ (+ writing dump every {str(RDUMP_STORE_INTERVAL/60)[:4]}mn)")
        else:
            logger.warning("    MANUAL/ Real Debrid API key not set, verify RD_APITOKEN in ./jellygrail/config/settings.env and restart container")


        # C: inotify deamon
        if len(to_watch) > 0:
            thread_c = threading.Thread(target=inotify_deamon, args=(to_watch,))
            thread_c.daemon = True  # exits when parent thread exits
            thread_c.start()
        
        # B: restart_jellygrail_at 6.30am
        thread_b = threading.Thread(target=restart_jgdocker_at)
        thread_b.daemon = True  # exits when parent thread exits
        thread_b.start()

        logger.warning("    MANUAL/ CTRL+C does not prevent restart. So if needed, stopping should be done with a docker stop command")

        # daily restart scan
        _scan_instance = ScriptRunner.get(refresh_all)
        _scan_instance.resetargs(1)
        _scan_instance.run()


        # D server thread
        run_server()
        #server_thread.join() 
        
    # ffprobe and nfo data dedicatede sqlite thread close
    staticDB.s.sqclose()
    #sqclose() each thread closes it connexion, no more global sqlite thread !!
    #mariadb_close()
