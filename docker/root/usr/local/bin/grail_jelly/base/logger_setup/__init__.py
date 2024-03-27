import logging
from colorlog import ColoredFormatter

def log_setup():
        # ---- Create or get the logger
    logger = logging.getLogger("jellygrail")
    # Set the lowest level to log messages; this can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Create file handler which logs even debug messages
    fh = logging.FileHandler('/jellygrail/log/jelly_update.log')
    fh.setLevel(logging.DEBUG)  # Set the level for the file handler

    # Create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)  # Set the level for the stream handler; adjust as needed

    # Create formatter and add it to the handlers
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') -- updated for below to add colors
    formatterfh = ColoredFormatter("%(asctime)s %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
    formatterch = ColoredFormatter("%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
    fh.setFormatter(formatterfh)
    ch.setFormatter(formatterch)

    # Add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger