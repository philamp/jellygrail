def ticks_to_minutes(ticks):
    """
    Convert runtime ticks to minutes.

    """
    ticks_per_second = 10000000
    minutes = (ticks / ticks_per_second) / 60
    return round(minutes)

def get_ext(filename):
    last_dot_index = filename.rfind('.')
    if last_dot_index == -1:
        return ""
    return filename[last_dot_index:]

def get_wo_ext(filename):
    last_dot_index = filename.rfind('.')
    if last_dot_index == -1:
        return filename
    return filename[:last_dot_index]

def get_tuple(filename):
    last_dot_index = filename.rfind('.')
    if last_dot_index == -1:
        return (filename, "")
    return (filename[:last_dot_index], filename[last_dot_index:])