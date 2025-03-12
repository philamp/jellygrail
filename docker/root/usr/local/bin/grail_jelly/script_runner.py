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