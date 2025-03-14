#!/usr/bin/env python3
# coding: utf-8
# dotenv for RD API management
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')
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
from jg_services import premium_timeleft

KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

# !!!!!!!!!!!!! dev reminder : this version should be aligned to version in PREPARE.SH (change both at the same time !!!!)
VERSION = "20240915"

INCR_KODI_REFR_MAX = 8

CONFIG_VERSION = os.getenv('CONFIG_VERSION')

REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')

JF_WANTED = os.getenv('JF_WANTED') != "no"

PLEX_REFRESH_A = os.getenv('PLEX_REFRESH_A')
PLEX_REFRESH_B = os.getenv('PLEX_REFRESH_B')
PLEX_REFRESH_C = os.getenv('PLEX_REFRESH_C')

# dotenv gathering
RD_API_SET = os.getenv('RD_APITOKEN') != "PASTE-YOUR-KEY-HERE"
JF_WANTED = os.getenv('JF_WANTED') != "no"
KODI_MAIN_WANTED = True if (KODI_MAIN_URL != "PASTE_KODIMAIN_URL_HERE" and KODI_MAIN_URL != "") else False


socket_started = False
at_least_once_done = [False, False, False, False, False, False, False, False]
post_kodi_run_step = 12

# ------ Contact points
from jgscan import bdd_install, init_mountpoints, scan, get_fastpass_ffprobe
from jfconfig import jfconfig
from jgscan.jgsql import init_database, sqclose
from nfo_generator import nfo_loop_service, fetch_nfo
from kodi_services import refresh_kodi, send_nfo_to_kodi, is_kodi_alive, merge_kodi_versions
from kodi_services.sqlkodi import kodi_mysql_init_and_verify
from jfapi import lib_refresh_all, wait_for_jfscan_to_finish

import jg_services

# setup the logger once
from base import logger_setup
logger = logger_setup.log_setup()


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

        if url_path == '/scan':
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


        elif url_path == '/test':
            _test_instance = ScriptRunner.get(jg_services.test)
            _test_instance.run()
            dumped_data = _test_instance.get_output()
            self.standard_headers()
            self.wfile.write(bytes(dumped_data, "utf8"))


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
        nb_items = scan()
        #if nb_items > 10: #if scan has added more than 10 items, we wait for full jellyfin scan + nfo generation before refereshing kodi (to avoid too many nfo refresh calls to kodi)
            #toomany = True

    
        logger.info(f"         1| ...Main JG Scan found {nb_items} new item(s)")


        # --unit test nb of items
        #nb_items = 11
        #logger.info(f"       ...| nbitems overriden with {nb_items} for testing")
        # ----


    if (step < 3 or (step > 10 and step < 13)): 
        if (not at_least_once_done[2] or nb_items > 0) and nb_items < INCR_KODI_REFR_MAX:
            if KODI_MAIN_WANTED:                   
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
            
            if JF_WANTED:
                logger.info("         3| Jellyfin library refresh...")
                # refresh the jellyfin library and merge variants
                lib_refresh_all()
                wait_for_jfscan_to_finish()
                pass
            else:
                logger.info("         3| Plex library refresh...")
                if PLEX_REFRESH_A != 'PASTE_A_REFRESH_URL_HERE':
                    try:
                        requests.get(PLEX_REFRESH_A, timeout=10)
                    except Exception as e:
                        logger.error("   REFRESH~ Plex refresh API unavailable")
                else:
                    logger.info("         3| Plex library can't be done because at least PLEX_REFRESH_A is not defined in setings.env")
                if PLEX_REFRESH_B != 'PASTE_B_REFRESH_URL_HERE':
                    try:
                        requests.get(PLEX_REFRESH_B, timeout=10)
                    except Exception as e:
                        logger.error("   REFRESH~ Plex refresh API unavailable")
                if PLEX_REFRESH_C != 'PASTE_C_REFRESH_URL_HERE':
                    try:
                        requests.get(PLEX_REFRESH_C, timeout=10)
                    except Exception as e:
                        logger.error("   REFRESH~ Plex refresh API unavailable")
            at_least_once_done[3] = True
        else:
            if JF_WANTED:
                logger.info("         3| Library refresh bypassed")
            else:
                logger.info("         3| Plex refresh bypassed")

    if step < 5:
        if JF_WANTED:
            if not nfo_loop_service():
                step = 9 # if jfwanted but nfo gen fails stop here but will do kodi scan and merge
                logger.warning("         4| Generating NFOs from Jellyfin does not work, refresh will stop there. Open jellyfin on your browser to create the primary user")
        else:
            logger.warning(" Step 4 Can't be done because JF_WANTED is not enabled in settings.env | But kodi refresh and merging can work: In this case kodi sources should be configured for online metadata")

    # it's the alternative kodi refresh
    # if toomany, kodi refresh is done after jellyfin

    if KODI_MAIN_WANTED:
        if (step < 3 or (step > 10 and step < 13) or step == 9):
            if not nb_items < INCR_KODI_REFR_MAX:
                    if not refresh_kodi():
                        retry_later = True
                    else:
                        at_least_once_done[2] = True
                        if post_kodi_run_step == 12:
                            post_kodi_run_step = 15


        # if step inferior or if specifically wanted with the webservice (6)
        if (step < 6 or (step > 10 and step < 16)) and retry_later == False:
                if JF_WANTED:
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



def run_server(server_class=HTTPServer, handler_class=RequestHandler, port=6502):
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
        logger.info(f"    SOCKET/ Waiting for any {socket_type} wrapper transaction ~")

    while True:
        #print(".", end="", flush=True)
        connection, client_address = server_socket.accept() # it waits here
        if socket_type == "nfopath":
            socket_started = True
            logger.info(f"    SOCKET/ BindFS connected")
        _handle_client_thread = threading.Thread(target=handle_socket_request, args=(connection, client_address, socket_type))
        _handle_client_thread.daemon = True
        _handle_client_thread.start()


if __name__ == "__main__":

    full_run = True

    init_database()

    bdd_install() # before jfconfig so that 1/ base folders are for sure created and 2/ databases has played migrations

    # Thread 0.2 - UNIX Socket (ffprobe bash wrapper responder)
    thread_ef = threading.Thread(target=socket_server_waiting, args=("ffprobe",))
    thread_ef.daemon = True  # exits when parent thread exits
    thread_ef.start()
    
    # Thread 0.1 - UNIX Socket (nfo path retriever socket : loop waiting thread) -- multithread requests ready but bindfs is not
    thread_e = threading.Thread(target=socket_server_waiting, args=("nfopath",))
    thread_e.daemon = True  # exits when parent thread exits
    thread_e.start()


    logger.info("    SOCKET/ Waiting for BindFS ...")
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
    if JF_WANTED:
        jf_config_result = jfconfig()
        '''
        if jf_config_result == "FIRST_RUN":
            _scan_instance = ScriptRunner.get(refresh_all)
            _scan_instance.resetargs(1)
            _scan_instance.run()
        '''
        if jf_config_result == "ZERO-RUN":
            logger.warning(f"   RESTART/ JellyGrail now restarts if '--restart unless-stopped' was set, otherwise please start it manually.")
            full_run = False

    # config checkups
    if VERSION != CONFIG_VERSION:
        logger.error("    MANUAL/ Config version is different from app version, please STOP or CTRL-C the container, rerun PREPARE.SH or fix directly in settings.env (vs. settings.env.example)")
    else:
        if not KODI_MAIN_WANTED:
            logger.warning("    MANUAL/ Kodi main url is not set up, maybe ignored intentionnaly ? Otherwise please rerun PREPARE.SH and restart container.")
        else:
            if not JF_WANTED:
                logger.warning("    MANUAL/ Kodi main url defined, but embedded Jellyfin disabled, Kodi can work without NFO sync from jellyfin, however make sure not to use the Local NFO data scrapper in Kodi video sources configuration.")

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
            if REMOTE_RDUMP_BASE_LOCATION.startswith('http'):
                thread_ars = threading.Thread(target=periodic_trigger_rs)
                thread_ars.daemon = True  # 
                thread_ars.start()
                logger.info("  SCHEDULE/ Real Debrid API remoteScan will be triggered every 7mn ~")
            
            logger.info("  SCHEDULE/ Real Debrid API rd_progress will be triggered every 2mn ~")
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
        
    sqclose()
    #mariadb_close()
