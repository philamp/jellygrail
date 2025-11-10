import logging
from colorlog import ColoredFormatter
import time
from collections import deque
'''
class LevelLetterFilter(logging.Filter):
    def filter(self, record):
        record.levelletter = record.levelname[:1].upper()
        return True
'''

class RecentDedupFilter(logging.Filter):
    """
    - Suppresses duplicate messages if they appeared in the last 10 messages within 30 min.
    - Replaces the first 10 chars with spaces if they match the prefix of the last message.
    """

    def __init__(self, ttl=1800, max_recent=10, prefix_len=10):
        super().__init__()
        self.ttl = ttl
        self.max_recent = max_recent
        self.prefix_len = prefix_len
        self.recent = deque(maxlen=max_recent)  # (timestamp, message)
        self.last_prefix = None

    def filter(self, record):
        now = time.time()
        msg = record.getMessage()

        # purge old entries
        self.recent = deque(
            [(t, m) for t, m in self.recent if now - t < self.ttl],
            maxlen=self.max_recent,
        )

        # suppress if seen recently
        #if any(m == msg for _, m in self.recent):
        #    return False

        # prefix blanking (compare only to last message)
        prefix = msg[:self.prefix_len]
        if prefix == self.last_prefix:
            msg = " " * self.prefix_len + msg[self.prefix_len:]
            record.msg = msg
            record.args = ()  # prevent reformatting issues

        # update state
        self.last_prefix = prefix
        self.recent.append((now, msg))
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
    ch.addFilter(RecentDedupFilter(ttl=1800, max_recent=10, prefix_len=10)) #30mn no-repeat on the last 10 items
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