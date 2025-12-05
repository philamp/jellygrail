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
    - Supprime les messages dupliqués s'ils sont apparus dans les `max_recent`
      derniers messages, et dans la fenêtre `ttl` (en secondes).
    - Fait du prefix blanking (remplace les `prefix_len` premiers caractères
      par des espaces si le préfixe est identique au message précédent).
    """

    def __init__(self, ttl=1800, max_recent=10, prefix_len=10):
        super().__init__()
        self.ttl = ttl
        self.max_recent = max_recent
        self.prefix_len = prefix_len
        # On stocke le message *brut* comme clé de dédup
        self.recent = deque(maxlen=max_recent)  # (timestamp, raw_msg)
        self.last_prefix = None

    def filter(self, record: logging.LogRecord) -> bool:
        now = time.time()

        # 1) Message brut (clé de dédup) : on appelle getMessage AVANT toute modif
        raw_msg = record.getMessage()

        # 2) Purge des entrées trop anciennes
        self.recent = deque(
            [(t, m) for t, m in self.recent if now - t < self.ttl],
            maxlen=self.max_recent,
        )

        # 3) Silencing si déjà vu récemment (sur le *message brut*)
        #if any(m == raw_msg for _, m in self.recent):
        #    return False

        # 4) Prefix blanking (uniquement pour l’affichage)
        display_msg = raw_msg
        prefix = raw_msg[:self.prefix_len]

        if prefix == self.last_prefix:
            display_msg = " " * self.prefix_len + raw_msg[self.prefix_len:]
            record.msg = display_msg
            record.args = ()  # pour éviter que logging essaie de reformater

        # 5) Mise à jour de l’état
        self.last_prefix = prefix
        # On enregistre le *message brut* pour la dédup, pas la version blankée
        self.recent.append((now, raw_msg))

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
    ch.addFilter(RecentDedupFilter(ttl=900, max_recent=20, prefix_len=10)) #15mn no-repeat on the last 20 items
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