# a function that computes for each domain from a number
# ex : 22 means Download HD and in preferred language and download 4k in preferred language
# ex : 10 means Download HD and any language and don't download 4
# it should return a dict like {'fhd': 0, 'uhd': 2} where 0 means don't download, 1 means download any language, 2 means download preferred language
def compute_domain_prefs(num: int) -> dict:
    



def compute_domain_prefs(num: int) -> dict:
    prefs = {}
    # HD part
    hd_part = num % 10
    if hd_part == 0:
        prefs['fhd'] = (False, None)
    elif hd_part == 1:
        prefs['fhd'] = (True, 'any')
    elif hd_part == 2:
        prefs['fhd'] = (True, 'preferred')
    else:
        prefs['fhd'] = (False, None)  # default fallback

    # 4K part
    k4_part = (num // 10) % 10
    if k4_part == 0:
        prefs['uhd'] = (False, None)
    elif k4_part == 1:
        prefs['uhd'] = (True, 'any')
    elif k4_part == 2:
        prefs['uhd'] = (True, 'preferred')
    else:
        prefs['uhd'] = (False, None)  # default fallback

    return prefs