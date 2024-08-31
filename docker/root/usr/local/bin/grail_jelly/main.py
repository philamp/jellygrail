#!/usr/bin/env python3
# coding: utf-8
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


# dotenv for RD API management
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')

KODI_MAIN_URL = os.getenv('KODI_MAIN_URL')

# dev reminder : this version should be aligned to version in PREPARE.SH (change both at the same time !!!!)
VERSION = "20240830"

RUNNING_VERSION = os.getenv('RUNNING_VERSION')

REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')

JF_WANTED = os.getenv('JF_WANTED') != "no"

PLEX_REFRESH_A = os.getenv('PLEX_REFRESH_A')
PLEX_REFRESH_B = os.getenv('PLEX_REFRESH_B')
PLEX_REFRESH_C = os.getenv('PLEX_REFRESH_C')

# check if api key is set
RD_API_SET = os.getenv('RD_APITOKEN') != "PASTE-YOUR-KEY-HERE"
JF_WANTED = os.getenv('JF_WANTED') != "no"
socket_started = False

# ------ Contact points
from jgscan import bdd_install, init_mountpoints, scan, get_fastpass_ffprobe
from jfconfig import jfconfig
from jgscan.jgsql import init_database, sqclose
from nfo_generator import nfo_loop_service, fetch_nfo
from kodi_services import refresh_kodi, send_nfo_to_kodi, is_kodi_alive, merge_kodi_versions
from kodi_services.sqlkodi import mariadb_close, kodi_mysql_init_and_verify
from jfapi import lib_refresh_all, wait_for_jfscan_to_finish

import jg_services

# setup the logger once
from base import logger_setup
logger = logger_setup.log_setup()


class RequestHandler(BaseHTTPRequestHandler):

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

        elif url_path == '/mc_scan':
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

        elif url_path == '/kodi_alive':
            _kodi_alive = ScriptRunner.get(is_kodi_alive)
            _kodi_alive.run()
            if _kodi_alive.queued_execution:
                message = "### kodi alive queued for later ! \n"
            else:
                message = "### kodi alive directly executed ! \n"
            self.standard_headers()
            self.wfile.write(bytes(message, "utf8"))

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

    logger.info("~ Kodi retrier loop ~")
    while True:
        if is_kodi_alive():
            logger.info("~> Kodi alive, proceed with library and NFO refresh <~")
            _refreshkodi_thread = ScriptRunner.get(refresh_all)
            _refreshkodi_thread.resetargs(8) 
            _refreshkodi_thread.run()
            break
        time.sleep(2)

def refresh_all(step):


    retry_later = False
    toomany = False

    if step == 1: # or rd_progress_response == "PLEASE_SCAN":
        if scan() > 10: #if scan has added more than 10 items, we wait for full jellyfin scan + nfo generation before refereshing kodi (to avoid too many nfo refresh calls to kodi)
            toomany = True
        logger.debug(". refresh_all PART 1 : scan")
    if (step < 3 or step == 8) and not toomany:
        if (KODI_MAIN_URL != "PASTE_KODIMAIN_URL_HERE" and KODI_MAIN_URL != ""):
            logger.debug(". refresh_all PART 2 : refresh kodi incremental mode")
            if not refresh_kodi():
                retry_later = True

    if step < 4:
        logger.debug(". refresh_all PART 3 : refresh jf or plex")
        if JF_WANTED:
            # refresh the jellyfin library and merge variants
            lib_refresh_all()
            wait_for_jfscan_to_finish()
        else:
            if PLEX_REFRESH_A != 'PASTE_A_REFRESH_URL_HERE':
                try:
                    requests.get(PLEX_REFRESH_A, timeout=10)
                except Exception as e:
                    logger.error("error with plex refresh")
            if PLEX_REFRESH_B != 'PASTE_B_REFRESH_URL_HERE':
                try:
                    requests.get(PLEX_REFRESH_B, timeout=10)
                except Exception as e:
                    logger.error("error with plex refresh")
            if PLEX_REFRESH_C != 'PASTE_C_REFRESH_URL_HERE':
                try:
                    requests.get(PLEX_REFRESH_C, timeout=10)
                except Exception as e:
                    logger.error("error with plex refresh")

    if step < 5:
        if JF_WANTED:
            logger.debug(". refresh_all PART 4 : refresh nfo (with jf)")
            if not nfo_loop_service():
                step = 9 # bypass the rest
                # ping externally before trigerring ?
                # script runner should check before ressting args: if queued true and current args < new args, keep current args (logic)

    # if toomany, kodi refresh is done after jellyfin 
    if toomany:
        if (KODI_MAIN_URL != "PASTE_KODIMAIN_URL_HERE" and KODI_MAIN_URL != ""):
            logger.debug(". refresh_all PART 2 shifted : refresh kodi shifted because in toomany mode")
            if not refresh_kodi():
                retry_later = True

    if (step < 6 or step == 8) and retry_later == False:
        if (KODI_MAIN_URL != "PASTE_KODIMAIN_URL_HERE" and KODI_MAIN_URL != "") and JF_WANTED:
            logger.debug(". refresh_all PART 5 : send new nfos to kodi")
            if not send_nfo_to_kodi():
                retry_later = True
            else:
                merge_kodi_versions()
        else:
            # since merging can be done without jellyfin or kodi rpc access
            merge_kodi_versions()

    if retry_later == True and kodi_mysql_init_and_verify():
        _is_kodi_alive_loop_thread = ScriptRunner.get(is_kodi_alive_loop)
        _is_kodi_alive_loop_thread.run()
        # launch the jobs that tests kodi alive in loop
            # this will then launch a new instance of refresh all wth special behavior



def run_server(server_class=HTTPServer, handler_class=RequestHandler, port=6502):
    global httpd
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logger.info(f"~ Server running on port {port}")
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
        logger.debug("inotify handler will call /scan in 30 minutes")
        time.sleep(1800) # todo to improve
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
            # logger.info("periodic trigger is working")
            _scan_instance = ScriptRunner.get(refresh_all)
            _scan_instance.resetargs(1)
            _scan_instance.run()

def periodic_trigger_rs(seconds=350):
    _rs_instance = ScriptRunner.get(jg_services.remoteScan)
    while True:
        time.sleep(seconds)
        _rs_instance.run()

def periodic_trigger_nfo_gen(seconds=70):
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
        logger.debug(f"~ inotify_deamon | Monitoring : {item2watch}")

    logger.info("~ inotify monitoring started [inotify_deamon] ~")
    # Event handler
    event_handler = EventHandler()

    # Notifier
    notifier = pyinotify.Notifier(wm, event_handler)

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
        logger.info(f"~ Jellyfin next restart in {sleep_time} seconds.")
        time.sleep(sleep_time)
        if True:
            logger.info(f"> JellyGrail will now shutdown for restart, beware '--restart unless-stopped' must be set in your docker run otherwise it won't restart !!")
            httpd.shutdown()

def handle_socket_request(connection, client_address, socket_type):
    if socket_type == "nfopath":
        logger.debug(f"> {socket_type} socket OPEN [handle_socket_request]")
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
                    logger.warning(f"~! main/socket | {socket_type} socket CLOSED. happens if nginx bindfs fails.")
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
    logger.info(f"~ Waiting for {socket_type} client.")
    while True:
        #print(".", end="", flush=True)
        connection, client_address = server_socket.accept() # it waits here
        if socket_type == "nfopath":
            socket_started = True
        _handle_client_thread = threading.Thread(target=handle_socket_request, args=(connection, client_address, socket_type))
        _handle_client_thread.daemon = True
        _handle_client_thread.start()


if __name__ == "__main__":

    full_run = True

    init_database()

    bdd_install() # before jfconfig so that 1/ base folders are for sure created and 2/ databases has played migrations

    
    # Thread 0.1 - UNIX Socket (nfo path retriever socket : loop waiting thread) -- multithread requests ready but bindfs is not
    thread_e = threading.Thread(target=socket_server_waiting, args=("nfopath",))
    thread_e.daemon = True  # exits when parent thread exits
    thread_e.start()

    # Thread 0.2 - UNIX Socket (ffprobe bash wrapper responder)
    thread_ef = threading.Thread(target=socket_server_waiting, args=("ffprobe",))
    thread_ef.daemon = True  # exits when parent thread exits
    thread_ef.start()

    logger.info("~ Waiting for nginx-bindfs to open NFO socket ...")
    waitloop = 0
    while not socket_started:
        #print(".", end="", flush=True)
        waitloop += 1
        time.sleep(1)
        if(waitloop > 30):
            logger.critical("!!! BindFS is not connecting to socket, BindFS service is probably not working properly thus JellyGrail won't start ... ")

    # ----------------- INITs -----------------------------------------
    # Initialize the database connection, includes open() ----

    # walking in mounts and subwalk only in remote_* and local_* folders
    to_watch = init_mountpoints()

    # Config JF before starting threads and server threads, trigger a first scan if it's first use (rd_progress potentially does it as well and daily restart scan)      
    if JF_WANTED:
        #jf_config_result = jfconfig()
        # if jf_config_result == "FIRST_RUN":
            # _scan_instance = ScriptRunner.get(refresh_all)
            # _scan_instance.resetargs(1)
            # _scan_instance.run()
        if jfconfig() == "ZERO-RUN":
            logger.warning(f"! JellyGrail will now shutdown for restart in deamon mode, beware '--restart unless-stopped' must be set in your docker run otherwise it won't restart !!")
            full_run = False

    # config checkups
    if VERSION != RUNNING_VERSION:
        logger.critical("!!! Config version is different from app version, please STOP or CTRL-C the container and rerun PREPARE.SH")
    else:
        if KODI_MAIN_URL == "PASTE_KODIMAIN_URL_HERE" or KODI_MAIN_URL == "":
            logger.warning("! Kodi main url is not set up, maybe ignored intentionnaly, else please rerun PREPARE.SH")
        else:
            if not JF_WANTED:
                logger.warning("! Kodi main url set up, but embedded jellyfin disabled, Kodi can work without NFO sync from jellyfin. But when adding the webdav movie/show source to Kodi, you must not use the NFO scraper.")

    kodi_mysql_init_and_verify()

    if full_run == True:
        # ------------------- threads A + Ars, B, C, D, E  -----------------------
        
        # thread E
        if JF_WANTED:
            thread_e = threading.Thread(target=periodic_trigger_nfo_gen)
            thread_e.daemon = True  # 
            thread_e.start()


        if RD_API_SET:
            # A: rd_progress called automatically every 2mn
            thread_a = threading.Thread(target=periodic_trigger)
            thread_a.daemon = True  # 
            thread_a.start()

            # Ars: remoteScan trigger every 7mn
            if REMOTE_RDUMP_BASE_LOCATION.startswith('http'):
                thread_ars = threading.Thread(target=periodic_trigger_rs)
                thread_ars.daemon = True  # 
                thread_ars.start()
                logger.info("~ Real Debrid API remoteScan will be triggered every 7mn")
            
            logger.info("~ Real Debrid API rd_progress will be triggered every 2mn")
        else:
            logger.warning("! Real Debrid API key not set, verify RD_APITOKEN in ./jellygrail/config/settings.env")


        # C: inotify deamon
        if len(to_watch) > 0:
            thread_c = threading.Thread(target=inotify_deamon, args=(to_watch,))
            thread_c.daemon = True  # exits when parent thread exits
            thread_c.start()
        
        # B: restart_jellygrail_at 6.30am
        thread_b = threading.Thread(target=restart_jgdocker_at)
        thread_b.daemon = True  # exits when parent thread exits
        thread_b.start()

        # restart scan
        logger.info("> Daily scan triggered")
        _scan_instance = ScriptRunner.get(refresh_all)
        _scan_instance.resetargs(1)
        _scan_instance.run()

        # D: server thread
        # server_thread = threading.Thread(target=run_server)
        # server_thread.daemon = False
        # server_thread.start()

        logger.warning("! if you have run the container in -it mode (interactive) to check for errors, you can now CTRL+C it, fix errors if any, and run 'sudo docker start jellygrail'")

        run_server()
        #server_thread.join() 
        
    sqclose()
    mariadb_close()