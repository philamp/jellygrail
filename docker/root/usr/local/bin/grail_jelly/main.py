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
import struct
from nfo_generator import nfo_loop_service, fetch_nfo

# dotenv for RD API management
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')

REMOTE_RDUMP_BASE_LOCATION = os.getenv('REMOTE_RDUMP_BASE_LOCATION')

# check if api key is set
RD_API_SET = os.getenv('RD_APITOKEN') != "PASTE-YOUR-KEY-HERE"
JF_WANTED = os.getenv('JF_WANTED') != "no"
socket_started = False

# ------ Contact points
from jgscan import bdd_install, init_mountpoints, scan, get_fastpass_ffprobe
from jfconfig import jfconfig
from jgscan.jgsql import init_database, sqclose

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
            _scan_instance = ScriptRunner.get(scan)
            _scan_instance.run()
            if _scan_instance.queued_execution:
                message = "### scan() queued for later ! (Forces a library scan)\n"
            else:
                message = "### scan() directly executed ! (Forces a library scan)\n"
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
                _scan_instance = ScriptRunner.get(scan)
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
            self.send_error(404, "You cannot ask that, that is foolish and rude")


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
        _scan_instance = ScriptRunner.get(scan)
        _scan_instance.run()

# ---- included cron
        
# restart_jellygrail_at is in jfapi module

def periodic_trigger(seconds=800):
    _rdprog_instance = ScriptRunner.get(jg_services.rd_progress)
    while True:
        time.sleep(seconds)
        _rdprog_instance.run()
        if(_rdprog_instance.get_output() == 'PLEASE_SCAN'):
            # logger.info("periodic trigger is working")
            _scan_instance = ScriptRunner.get(scan)
            _scan_instance.run()

def periodic_trigger_rs(seconds=350):
    _rs_instance = ScriptRunner.get(jg_services.remoteScan)
    while True:
        time.sleep(seconds)
        _rs_instance.run()

def inotify_deamon(to_watch):
    # ----- inotify 

    # Set up watch manager
    wm = pyinotify.WatchManager()

    for item2watch in to_watch:
        wm.add_watch(item2watch, pyinotify.ALL_EVENTS, rec=True, auto_add=True)
        logger.debug(f"~ inotify_deamon | Monitoring : {item2watch}")

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
    logger.debug(f"~> main/socket | {socket_type} socket OPEN.")
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
                    # todo remove
                    # stdout = f"4321out\n1234"
                    # stdout = stdout.encode('utf-8')
                    # stderr = f"4321err\n1234"
                    # stderr = stderr.encode('utf-8')
                    # returncode = 12
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
                    # logger.info(f"Message received from BindFS: {message}")

                    #logger.info(f"Socket type is: {socket_type}")
                    # TODO toremove
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
    logger.info(f"main/socket | Waiting for {socket_type} client.")
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
    
    # Thread 0.1 - UNIX Socket (nfo path retriever socket : loop waiting thread) -- multithread requests ready but bindfs is not
    thread_e = threading.Thread(target=socket_server_waiting, args=("nfopath",))
    thread_e.daemon = True  # exits when parent thread exits
    thread_e.start()

    # Thread 0.2 - UNIX Socket (ffprobe bash wrapper responder)
    thread_ef = threading.Thread(target=socket_server_waiting, args=("ffprobe",))
    thread_ef.daemon = True  # exits when parent thread exits
    thread_ef.start()

    # todo : do we need NFO socket if user does not need nginx-webdav powered kodi ?
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
    init_database() 

    bdd_install() # before jfconfig so that 1/ base folders are for sure created and 2/ databases has played migrations

    # walking in mounts and subwalk only in remote_* and local_* folders
    to_watch = init_mountpoints()

    # Config JF before starting threads and server threads, trigger a first scan if it's first use (rd_progress potentially does it as well but RD may not be used TODO fix with regular scan as well)        
    if JF_WANTED:
        jf_config_result = jfconfig()
        if jf_config_result == "FIRST_RUN":
            _scan_instance = ScriptRunner.get(scan)
            _scan_instance.daemon = True 
            _scan_instance.run()
        elif jf_config_result == "ZERO-RUN":
            logger.info(f"JellyGrail will now shutdown for restart in deamon mode, beware '--restart unless-stopped' must be set in your docker run otherwise it won't restart !!")
            full_run = False
    else:
        _scan_instance = ScriptRunner.get(scan)
        _scan_instance.daemon = True 
        _scan_instance.run()

    # TODO test toremove
    nfo_loop_service()


    if full_run == True:
        # ------------------- threads A + Ars, B, C, D  -----------------------
        
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

        # D: server thread
        # server_thread = threading.Thread(target=run_server)
        # server_thread.daemon = False
        # server_thread.start()
        run_server()
        #server_thread.join() 
        
    sqclose()
