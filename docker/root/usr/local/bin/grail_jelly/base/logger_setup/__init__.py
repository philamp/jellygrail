import logging
from colorlog import ColoredFormatter
import time
'''
class LevelLetterFilter(logging.Filter):
    def filter(self, record):
        record.levelletter = record.levelname[:1].upper()
        return True
'''

class NoRepeatPrefixFilter(logging.Filter):
    """ 
    - Suppresses identical messages within `ttl` seconds.
    - Replaces first 10 chars with spaces if prefix matches previous message.
    """

    def __init__(self, ttl=1800, prefix_len=10):
        super().__init__()
        self.ttl = ttl
        self.prefix_len = prefix_len
        self.last_msg = None
        self.last_time = 0.0
        self.last_prefix = None

    def filter(self, record):
        msg = record.getMessage()
        now = time.time()

        # suppress exact duplicate within TTL
        if msg == self.last_msg and now - self.last_time < self.ttl:
            return False

        prefix = msg[:self.prefix_len]

        # replace prefix if same as previous
        if prefix == self.last_prefix:
            msg = " " * self.prefix_len + msg[self.prefix_len:]
            record.msg = msg
            record.args = ()  # ensure logging doesn't reformat

        self.last_msg = msg
        self.last_time = now
        self.last_prefix = prefix
        return True
        
def log_setup():
        # ---- Create or get the logger
    logger = logging.getLogger("jellygrail")
    # Set the lowest level to log messages; this can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Create file handler which logs even debug messages
    # fh = logging.FileHandler('/jellygrail/log/jelly_update.log')
    #fh.setLevel(logging.INFO)  # Set the level for the file handler

    # Create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)  # Set the level for the stream handler; adjust as needed
    ch.addFilter(NoRepeatPrefixFilter(ttl=1800,prefix_len=10)) #30mn no-repeat
    #ch.addFilter(LevelLetterFilter()) 

    # Create formatter and add it to the handlers
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') -- updated for below to add colors
    #formatterfh = ColoredFormatter("%(asctime)s %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
    formatterch = ColoredFormatter("%(log_color)s%(levelname).1s%(reset)s | %(log_color)s%(message)s%(reset)s")
    #fh.setFormatter(formatterfh)
    ch.setFormatter(formatterch)

    # Add the handlers to the logger
    #logger.addHandler(fh)
    logger.addHandler(ch)

    return logger