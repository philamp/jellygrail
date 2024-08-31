import logging
import threading
import queue
# plug to same logging instance as main
logger = logging.getLogger('jellygrail')

# declare all global instances here

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
            if self.queued_execution == True and self.args[0] < args[0]: #if the queud execution has set stronger refresh_all call (with lower step value than requested), don't change the step value
                logger.debug(". refresh_all requested with higher step value, won't be applied")
                return
        self.args = args
        self.kwargs = kwargs

    def run(self):
        # async bahavior parameters pre-check and set queud execution only if running
        if self.is_running:
            self.queued_execution = True
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
                if self.func.__name__ == "refresh_all" and len(self.args):
                    logger.debug(f"~ THREAD {self.func.__name__} triggered @ step {self.args[0]} ~")
                else:
                    logger.debug(f"~ THREAD {self.func.__name__} triggered ~")
                result = self.func(*self.args, **self.kwargs)
                if result is not None:
                    self.output_queue.put(result)
            else:
                raise ValueError("> No function set to run as thread")
        except Exception as e:
            logger.critical(f"> Error occurred in thread: {self.func.__name__}; error is: {e}", exc_info=True)
        finally:
            # async bahavior parameters management post-set
            if self.func.__name__ == "refresh_all" and len(self.args):
                logger.info(f"~> THREAD {self.func.__name__} @ step {self.args[0]} COMPLETED [{self.manytimes}] <~")
            else:
                logger.info(f"~> THREAD {self.func.__name__} COMPLETED [{self.manytimes}] <~")
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