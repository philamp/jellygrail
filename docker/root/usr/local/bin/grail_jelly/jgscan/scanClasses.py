import threading

class jgScan:
    
    i_scanned = 0
    lock_incr = threading.Lock()

    present_virtual_folders = []
    lock_m = threading.Lock()

    present_virtual_folders_shows = []
    lock_s = threading.Lock()



    @classmethod
    def add_to_pvm(cls, item):
        with cls.lock_m:
            cls.present_virtual_folders.append(item)

    @classmethod
    def add_to_pvs(cls, item):
        with cls.lock_s:
            cls.present_virtual_folders_shows.append(item)

    @classmethod
    def itemincr(cls):
        with cls.lock_incr:
            cls.i_scanned += 1