#!/usr/bin/env python3
# coding: utf-8
import time
import threading
import pyinotify
from http.server import BaseHTTPRequestHandler, HTTPServer
from script_runner import ScriptRunner
import urllib

# import script_runner threading class (ScriptRunnerSub) and its smart instanciator (ScriptRunner)
from script_runner import ScriptRunner


# dotenv for RD API management
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')


# ------ Contact points
from jgscan import init_bdd, init_mountpoints, scan
from jfapi import restart_jellygrail_at
from jfconfig import jfconfig

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
                    self.send_error(503, "Client triggered service, not yet available - rd dump file not yet created on server, please retry in few seconds")



def run_server(server_class=HTTPServer, handler_class=RequestHandler, port=6502):
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
        _scan_instance = ScriptRunner.get(scan)
        _scan_instance.run()

# ---- included cron
        
# restart_jellygrail_at is in jfapi module

def periodic_trigger(seconds=120):
    global thrdinsts
    _rdprog_instance = ScriptRunner.get(jg_services.rd_progress)
    while True:
        time.sleep(seconds)
        _rdprog_instance.run()
        if(_rdprog_instance.get_output() == 'PLEASE_SCAN'):
            # logger.info("periodic trigger is working")
            _scan_instance = ScriptRunner.get(scan)
            _scan_instance.run()

def inotify_deamon(to_watch):
    # ----- inotify 

    # Set up watch manager
    wm = pyinotify.WatchManager()

    for item2watch in to_watch:
        wm.add_watch(item2watch, pyinotify.ALL_EVENTS, rec=True, auto_add=True)
        logger.info(f"~ Activity monitored on : {item2watch}")

    # Event handler
    event_handler = EventHandler()

    # Notifier
    notifier = pyinotify.Notifier(wm, event_handler)

    notifier.loop()
    # ----- inotify END

if __name__ == "__main__":

    init_bdd() # before jfconfig so that base folders are for sure created

    jfconfig()

    # walking in mounts and subwalk only in remote_* and local_* folders
    to_watch = init_mountpoints()

    # threads A B C

    # rd_progress called automatically
    thread_a = threading.Thread(target=periodic_trigger)
    thread_a.daemon = True  # exists when parent thread exits
    thread_a.start()

    # restart_jellygrail_at
    thread_b = threading.Thread(target=restart_jellygrail_at)
    thread_b.daemon = True  # exists when parent thread exits
    thread_b.start()

    # inotify deamon
    if len(to_watch) > 0:
        thread_c = threading.Thread(target=inotify_deamon, args=(to_watch,))
        thread_c.daemon = True  # exists when parent thread exits
        thread_c.start()

    #thread D, server
    run_server()


