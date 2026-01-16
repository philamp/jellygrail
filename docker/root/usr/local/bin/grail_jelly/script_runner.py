# CONSTANTS EVERYWHERE + stop event
from base.constants import *

# LIBS
import threading
import queue

# JG MODULES
from base import * # loads common libs
from jgscan import multiScan
from kodi_services import refresh_kodi


# plug to same logging instance as main
logger = logging.getLogger('jellygrail')

# REFRESHER instance return codes:
# 0 = at least one kodi missing
# 1 = no kodi missing or queued execution so we don't know

#### DEPRECATED #######

'''
class refreshByStep:
    _num_items = 0
    _steps = [
        multiScan, #0
        refresh_kodi, #1
        self.step_jf_refresh, #2
        self.step_nfogen, #3
        refresh_kodi, #4
        self.step_send_nfos, #5
        self.step_sqlops #6
    ]
    _static_bypass_conditions = [ # = already completed = we dont do if
        False,
        not USE_KODI_ACTUALLY,
        not JF_WANTED_ACTUALLY,
        not JF_WANTED_ACTUALLY,
        not USE_KODI_ACTUALLY,
        not USE_KODI_ACTUALLY or not JF_WANTED_ACTUALLY,
        not USE_KODI_ACTUALLY
    ]

    _completed = [True] * len(_steps)
    _last_completed = None
    _running = False
    _queued_execution = False
    _at_least_once_done = [False] * len(_steps)
    _started = [False] * len(_steps)

    @classmethod
    def onthefly_bypass_conditions(cls, step): # = already completed = we dont do if
        if step == 1:
            if cls._num_items > INCR_KODI_REFR_MAX or (cls._num_items == 0 and cls._at_least_once_done[step]): # CUSTOM CASE : if 0 items but at least once done, we skip
                return True
            
        if step == 4:
            if cls._num_items <= INCR_KODI_REFR_MAX or (cls._num_items == 0 and cls._at_least_once_done[step]):
                return True
            
        if step == 2:
            if cls._num_items == 0 and cls._at_least_once_done[step]:
                return True

        #default = we do
        return False

    @classmethod
    def once_done_set(cls, step):
        # CUSTOM CASE : set for 1 -> set for 4 also and vice versa
        if step in [1,4]:
            cls._at_least_once_done[1] = True
            cls._at_least_once_done[4] = True 
        else:
            cls._at_least_once_done[step] = True

    @classmethod
    def completed_set(cls, step):
        # CUSTOM CASE : set for 1 -> set for 4 also and vice versa
        if step in [1,4]:
            cls._completed[1] = True
            cls._completed[4] = True 
        else:
            cls._completed[step] = True

    @classmethod
    def started_set(cls, step):
        # CUSTOM CASE : set for 1 -> set for 4 also and vice versa
        if step in [1,4]:
            cls._started[1] = True
            cls._started[4] = True 
        else:
            cls._started[step] = True

    @classmethod
    def runfunc(cls, step):
        if cls._runfunc(cls, step):
            cls.once_done_set(step)
            #cls.at_least_once_done[step] = True

    @classmethod
    def _runfunc(cls, step):
        if step == 0: #special case
            cls._num_items = cls._steps[step]()
            return True
        else:
            if cls._steps[step]():
                return True
        return False

    @classmethod
    def runEachStep(cls):
        cls._running = True
        for i, _ in enumerate(cls._completed):
            # CUSTOM - play dynamic bypass if last_completed was True, otherwise, they won't be bypassed (= we want to try them again if they were not done in last run, even if onthefly_bypass_conditions say so)
            if cls._last_completed[i]:
                cls._completed[i] = cls.onthefly_bypass_conditions(i)
            if not cls._completed[i]:
                cls.started_set(i)

                logger.info(f" REFRESHER| 🚀 Launching S{i} : {cls._steps[i].__name__}")
                if cls.runfunc(i):
                    cls.completed_set(i)
                #cls._completed[i] = cls.runfunc(i)

                # launch here the threaded kodi availabilty checker if step is kodi related and kodi is not available
                if not cls._completed[i] and i in [1,4,5]:
                    logger.warning(f" REFRESHER| S{i} could not be completed, likely due to device unavailability")
                    
                    
        # CUSTOM - reset started flags
        cls._started = [False] * len(cls._steps)
        cls._running = False



    # --- run driver ---
    @classmethod
    def run(cls, start_at=None, steps_to_run=None):

        # CUSTOM CASE : if step 1 is asked, force step 4 also
        if steps_to_run is not None and 1 in steps_to_run:
            steps_to_run.append(4)

        steps_to_run = list(set(steps_to_run)) if steps_to_run is not None else None

            
        
        total = len(cls._steps)

        has_to_queue = False

        # Ways to specify which steps to run start_at = index OR steps_to_run = [indices]
        if steps_to_run is not None:
            indices = steps_to_run
        elif start_at is not None:
            indices = range(start_at, total)
        else:
            indices = range(total)

        
        
        # queue if in steps asked at least one is already marked as completed
        # = for i in indices if cls.completed[i]
        # Mark indicated steps as not completed

        # memorize the last completed status before we change the current one
        cls._last_completed = cls._completed.copy()

        # Apply current run request, so apply "uncompleted" only to indicated steps
        for i in range(total):
            if i in indices:
                cls._completed[i] = False
                
                if not has_to_queue and (cls._started[i] == True and not cls._static_bypass_conditions[i]):
                    has_to_queue = True

        # play static bypass conditions // these always apply anyway
        for i in enumerate(cls._static_bypass_conditions):
            cls._completed[i] = cls._static_bypass_conditions[i]
        
        
        if not cls._running:
            cls.runEachStep()
            # ...then
            if cls._queued_execution:
                cls._queued_execution = False
                cls.runEachStep()

            if not all(cls._completed):
                logger.info(" REFRESHER| 🔁 Some incomplete steps, retried upon devices availability")
                return 0
            else:
                logger.info(" REFRESHER| ✅ All steps complete.") 
                return 1

        elif has_to_queue: # CUSTOM - if running and at least one of the steps to run is already started
            cls._queued_execution = True
            logger.info(" REFRESHER| ↘ Queued.") 
            return 1
'''   


'''
if self.running:
    self.queued_execution = True
    logger.info("⏳ Refresh already running, queuing this request")
else:
    self.running = True
    self.queued_execution = False
    logger.info(f"🚀 Starting refresh from step {start_at if start_at is not None else 0}")
    try:
        self.runEachStep()
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