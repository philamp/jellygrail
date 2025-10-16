import logging
import threading
import queue

# all computed constants + stop event
from base.constants import *

from jgscan import multiScan

KODI_MAIN_URL = os.getenv('KODI_MAIN_URL') or ""
USE_KODI = (os.getenv('USE_KODI') or "y") != "n"
USE_KODI_ACTUALLY = USE_KODI and (KODI_MAIN_URL != "PASTE_KODIMAIN_URL_HERE" and KODI_MAIN_URL != "" and KODI_MAIN_URL != "your-player-ip-or-hostname")
JF_WANTED = (os.getenv('JF_WANTED') or "y") != "n"
JF_WANTED_ACTUALLY = JF_WANTED

# plug to same logging instance as main
logger = logging.getLogger('jellygrail')

# declare all global instances here

class refreshByStep:
    def __init__(self):
        self.steps = [
            self.step1_scan, #0
            self.step2_kodi_refresh, #1
            self.step3_jf_refresh, #2
            self.step4_report, #3
            self.step2_kodi_refresh, #4
            self.step5_send_nfos, #5
        ]
        self.completed = [False] * len(self.steps)
        self.running = False
        self.queued_execution = False

        if not JF_WANTED_ACTUALLY:

            if not USE_KODI_ACTUALLY:
                self.completed[5] = True
            

    # --- steps (chaque fonction retourne True/False) ---
    def step1_scan(self):
        #nb_items = multiScan()
        
        return True

    def step2_kodi_refresh(self):

        return True

    def step3_jf_refresh(self):

        return True

    def step4_report(self):

        return True
    
    def step5_send_nfos(self):

        return True

    def subrun(self):
        self.running = True
        for i, _ in enumerate(self.completed):
            if not self.completed[i]:
                logger.info(f" REFRESHER| Launching {self.steps[i].__name__}")
                self.completed[i] = self.steps[i]()
        if not all(self.completed):
            logger.info(" REFRESHER| 🔁 Some incomplete steps, retried upon kodi devices \n")
        else:
            logger.info(" REFRESHER| ✅ All steps complete.")
        self.running = False
    # --- run driver ---
    def run(self, start_at=None, steps_to_run=None):
        
        total = len(self.steps)

        # Ways to specify which steps to run start_at = index OR steps_to_run = [indices]
        if steps_to_run is not None:
            indices = steps_to_run
        elif start_at is not None:
            indices = range(start_at, total)
        else:
            indices = range(total)

        # Marque les steps concernés comme non complétés
        for i in range(total):
            if i in indices:
                self.completed[i] = False
        
        if not self.running:
            self.subrun()
            if self.queued_execution:
                self.queued_execution = False
                self.subrun()
        else:
            self.queued_execution = True
            return 




        '''
        if self.running:
            self.queued_execution = True
            logger.info("⏳ Refresh already running, queuing this request")
        else:
            self.running = True
            self.queued_execution = False
            logger.info(f"🚀 Starting refresh from step {start_at if start_at is not None else 0}")
            try:
                self.subrun()
            except Exception as e:
                logger.critical(f" Error occurred during refresh: {e}", exc_info=True)
            finally:
                self.running = False
                if self.queued_execution:
                    self.queued_execution = False
                    logger.info("🔁 Queued refresh request detected, starting it now")
                    self.run(start_at=start_at, steps_to_run=steps_to_run)
        '''




class ScriptRunnerSub:
    def __init__(self, func=None, *args, **kwargs):
        # default 
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.manytimes = 0
        self.is_running = False
        self.queued_execution = False

        # managing async ddata
        self.thread = None
        self.output_queue = queue.Queue() #dumped encoded data only !! (ex :json.dumps(data).encode())

    def resetargs(self, *args, **kwargs):
        #self.func = func
        if (self.func.__name__ == "refresh_all"):

            

            # if the next queued execution has higher step value, don't take it, as it would bypass some jobs
            if self.queued_execution == True:
                cmp_newargs = args[0] if args[0] > 10 else args[0] + 10
                cmp_curargs = self.args[0] if self.args[0] > 10 else self.args[0] + 10

                if cmp_curargs < cmp_newargs: 
                    logger.debug(". refresh_all requested with higher step value, won't be applied")
                    return
        self.args = args
        self.kwargs = kwargs

    def run(self):
        # async bahavior parameters pre-check and set queud execution only if running
        if self.is_running:
            self.queued_execution = True if self.func.__name__ != "is_kodi_alive_loop" else False # this task does not need a queue
        else: 
            self.is_running = True
            self.queued_execution = False
            # async is instanciated here
            self.thread = threading.Thread(target=self._execute)
            self.thread.daemon = True
            self.thread.start()

    def _execute(self):
        # sync
        try:
            if self.func:
                self.manytimes += 1
                if self.func.__name__ == "refresh_all":
                    if len(self.args) < 1:
                        self.args[0] = 1
                    logger.info(f"[[  Step@{self.args[0]}~~n{self.manytimes}")
                else:
                    logger.debug(f"[Threadrun/ {self.func.__name__} #{self.manytimes}")
                result = self.func(*self.args, **self.kwargs)
                if result is not None:
                    self.output_queue.put(result)
            else:
                raise ValueError("> No function set to run as thread")
        except Exception as e:
            logger.critical(f" Threadrun| Error occurred in thread: {self.func.__name__}; error is: {e}", exc_info=True)
        finally:
            # async bahavior parameters management post-set
            if self.func.__name__ == "refresh_all" and len(self.args):
                logger.info(f"          ~~n{self.manytimes} ]]")
            else:
                logger.info(f"[Threadrun/ {self.func.__name__} #{self.manytimes} done]")
            self.is_running = False
            if self.queued_execution:
                self.queued_execution = False # set it to False ASAP right after flag was interrogated
                self.run()

    def get_output(self):
        # Wait for the function to complete and get its output
        if self.thread:
            self.thread.join()
        return self.output_queue.get()

class ScriptRunner:
    _instances = {}

    @staticmethod
    def get(target_function, *args, **kwargs):
        func_name = target_function.__name__
        if func_name not in ScriptRunner._instances:
            ScriptRunner._instances[func_name] = ScriptRunnerSub(target_function, *args, **kwargs)
        return ScriptRunner._instances[func_name]