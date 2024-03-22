import logging
import threading
import queue
# plug to same logging instance as main
logger = logging.getLogger('jellygrail')

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
        self.args = args
        self.kwargs = kwargs

    def run(self):
        # async bahavior parameters pre-check and set queud execution only if running
        if self.is_running:
            self.queued_execution = True

        self.is_running = True
        self.queued_execution = False
        # async is instanciated here
        self.thread = threading.Thread(target=self._execute)
        self.thread.start()

    def _execute(self):
        # sync
        try:
            if self.func:
                self.manytimes += 1
                # TODO: pass it to debug when ok
                logger.info(f"ASYNC CALL: {self.func.__name__} | TIMES CALLED (since last restart): {self.manytimes}")
                result = self.func(*self.args, **self.kwargs)
                self.output_queue.put(result if result is not None else f"Func: {self.func.__name__} -> does not return any value (issue or actually no need to call get_output!)")
            else:
                raise ValueError("No function has been set to run in the async ScriptRunner.")
        except Exception as e:
            logger.critical(f"An error occurred in thread: {self.func.__name__} error is: {e}", exc_info=True)
        finally:
            # async bahavior parameters management post-set
            # TODO: pass it to debug when ok
            logger.info(f"ASYNC CALL: {self.func.__name__} FINISHED")
            self.is_running = False
            if self.queued_execution:
                self.queued_execution = False # set it to False ASAP right after flag was interrogated
                self.run_it()

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