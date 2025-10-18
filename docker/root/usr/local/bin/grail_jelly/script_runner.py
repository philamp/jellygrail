# CONSTANTS EVERYWHERE + stop event
from base.constants import *

# LIBS
from base import * # loads common libs
import threading
import queue

# JG MODULES
from jgscan import multiScan



# plug to same logging instance as main
logger = logging.getLogger('jellygrail')

# declare all global instances here

class refreshByStep:
    def __init__(self):
        self.num_items = 0
        self.steps = [
            self.step_scan, #0
            self.step_kodi_refresh, #1
            self.step_jf_refresh, #2
            self.step_nfogen, #3
            self.step_kodi_refresh, #4
            self.step_send_nfos, #5
            self.step_sqlops #6
        ]
        self.static_bypass_conditions = [ # = already completed = we dont do if
            False,
            not USE_KODI_ACTUALLY,
            not JF_WANTED_ACTUALLY,
            not JF_WANTED_ACTUALLY,
            not USE_KODI_ACTUALLY,
            not USE_KODI_ACTUALLY or not JF_WANTED_ACTUALLY,
            not USE_KODI_ACTUALLY
        ]

        self.completed = [True] * len(self.steps)
        self.running = False
        self.queued_execution = False
        self.at_least_once_done = [False] * len(self.steps)

    def onthefly_bypass_conditions(self, step): # = already completed = we dont do if
        if step == 1:
            if self.num_items > INCR_KODI_REFR_MAX or (self.num_items == 0 and self.at_least_once_done[step]): # CUSTOM CASE : if 0 items but at least once done, we skip
                return True
            
        if step == 4:
            if self.num_items <= INCR_KODI_REFR_MAX or (self.num_items == 0 and self.at_least_once_done[step]):
                return True
            
        if step == 2:
            if self.num_items == 0 and self.at_least_once_done[step]:
                return True

        #default = we do
        return False

    def once_done_set(self, step):
        # CUSTOM CASE : set for 1 -> set for 4 also and vice versa
        if step in [1,4]:
            self.at_least_once_done[1] = True
            self.at_least_once_done[4] = True 
        else:
            self.at_least_once_done[step] = True
    
    def runfunc(self, step):
        if self._runfunc(self, step):
            self.once_done_set(step)
            #self.at_least_once_done[step] = True

    def _runfunc(self, step):
        if step == 0: #special case
            self.num_items = self.steps[step]()
            return True
        else:
            if self.steps[step]():
                return True
        return False

    def subrun(self):
        self.running = True
        for i, _ in enumerate(self.completed):
            # play dynamic bypass
            self.completed[i] = self.onthefly_bypass_conditions(i)
            if not self.completed[i]:
                logger.info(f" REFRESHER| 🚀 Launching S{i} : {self.steps[i].__name__}")
                self.completed[i] = self.runfunc(i)
        if not all(self.completed):
            logger.info(" REFRESHER| 🔁 Some incomplete steps, retried upon devices availability \n")
        else:
            logger.info(" REFRESHER| ✅ All steps complete.")
        self.running = False

    # --- run driver ---
    def run(self, start_at=None, steps_to_run=None):

        # CUSTOM CASE : if step 1 is asked, force step 4 also
        if steps_to_run is not None and 1 in steps_to_run:
            steps_to_run.append(4)

        steps_to_run = list(set(steps_to_run)) if steps_to_run is not None else None

        # CUSTOM CASE TODO : if not step not totally completed, self.num_items should not bet set, let it previous value
        # CUSTOM TODO: have "started_step"
            
        
        total = len(self.steps)

        has_to_queue = False

        # Ways to specify which steps to run start_at = index OR steps_to_run = [indices]
        if steps_to_run is not None:
            indices = steps_to_run
        elif start_at is not None:
            indices = range(start_at, total)
        else:
            indices = range(total)

        
        
        # queue if in steps asked at least one is already marked as completed
        # = for i in indices if self.completed[i]
        # Mark indicated steps as not completed
        for i in range(total):
            if i in indices:
                if self.completed[i] == True and not self.static_bypass_conditions[i]:
                    has_to_queue = True
                self.completed[i] = False

        # play static bypass conditions
        for i in enumerate(self.static_bypass_conditions):
            self.completed[i] = self.static_bypass_conditions[i]
        
        
        if not self.running:
            self.subrun()
            # ...then
            if self.queued_execution:
                self.queued_execution = False
                self.subrun()
        elif has_to_queue:
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