def ticks_to_minutes(ticks):
    """
    Convert runtime ticks to minutes.

    """
    ticks_per_second = 10000000
    minutes = (ticks / ticks_per_second) / 60
    return round(minutes)