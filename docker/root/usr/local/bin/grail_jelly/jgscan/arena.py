from base import *
import pycountry
# for similarity
# from thefuzz import fuzz
from thefuzz import process
from jgscan.constants import *

def find_most_similar(input_str, string_list):
    # This returns the best match, its score and index
    best_match = process.extractOne(input_str, string_list)
    return best_match

def tpl(str_value, preffix = ''):
    if str_value is not None:
        return f" {preffix}{str_value}"
    return ''

def ytpl(value):
    if value is not None:
        return f" ({str(value)})"
    return ''

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

def clean_string(s):
    s = s.replace(".", " ")
    s = s.replace("-", "")
    s = s.strip()
    s = s.capitalize()
    s = remove_brackets(s)
    return s

def remove_brackets(text):
    return re.sub(r'\[.*?\]', '', text)

def subtitle_extension(file_name):
    _attribs = []
    special_attribs = {"default", "sdh", "forced", "foreign"}
    patterns = r'[\.\[\]_()]'

    # Check if the filename ends with .srt
    if not file_name.lower().endswith(SUB_EXTS):
        return None  # Return None if the file is not an .srt file

    base_name, ext = get_tuple(file_name)

    # splitting using pattern and not taking empty parts
    parts = list(filter(None, re.split(patterns, base_name.lower())))
    parts = parts[-4:] if len(parts) >= 4 else parts
    
    for part in parts:
        # If the part is a recognized special attribute, append it to other_attribs
        if part in special_attribs:
            if part == "foreign":
                _attribs.append("forced")
            else:
                _attribs.append(part)
        else:
            # Check if it's a valid 2 or 3-char language code or a full language name
            lang = pycountry.languages.get(alpha_2=part) or pycountry.languages.get(alpha_3=part) or pycountry.languages.get(name=part.capitalize())
            if lang:
                lang_code = getattr(lang, 'alpha_2', None)
                if lang_code:
                    _attribs.append(lang_code)
                else:
                    lang_code = getattr(lang, 'name', None)
                    if lang_code:
                        _attribs.append(lang_code.lower())

    # if there is really nothing return the only last split found
    if(len(_attribs) < 1):
        _attribs.append(parts[-1])

    # fix if original filenames kind-of-mentionned same language 2 times (fr.french for example)
    if len(_attribs) > 1 and (_attribs[-1] == _attribs[-2]):
        _attribs.pop(-1)
        
    if(len(_attribs) > 0):
        return "."+".".join(_attribs) + ext
    else:
        return ext