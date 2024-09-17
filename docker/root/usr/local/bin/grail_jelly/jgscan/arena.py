from base import *
from base.littles import *
import pycountry
# for similarity
# from thefuzz import fuzz
from thefuzz import process
from base.constants import *

def get_bit_depth(pix_fmt):
    bit_depth_map = {
        'yuv420p': '8',
        'yuv422p': '8',
        'yuv444p': '8',
        'yuv420p10le': '10',
        'yuv422p10le': '10',
        'yuv444p10le': '10',
        'yuv420p12le': '12',
        'yuv422p12le': '12',
        'yuv444p12le': '12',
        # Add other mappings as needed
    }
    
    return bit_depth_map.get(pix_fmt, 'Unknown')

def parse_ffprobe(stdout, filepathnotice):

    hdrtpl = ""
    bitratetpl = ""
    resolutiontpl = ""
    codectpl = ""
    audiotpla = ""
    audiotplb = ""

    slang_tpl = ""
    alang_tpl = ""

    slang_arr = []
    alang_arr = []

    _dvprofile = None
    if stdout is not None:
        try:
            info = json.loads(stdout.decode("utf-8"))
    
            for stream in info.get('streams', []):
                if codec_name := stream.get('codec_name'):
                    if stream.get('codec_type') == "video" and codec_name != "mjpeg" and codec_name != "png":
                        if stream.get('color_transfer') == "smpte2084":
                            hdrtpl = " hdr10"
                        else:
                            hdrtpl = f" sdr{get_bit_depth(stream.get('pix_fmt', 'yuv420p'))}"
    
                        # hdrtpl == " sdr8" or 
                        if codec_name not in "h264 hevc":
                            codectpl = f" {codec_name}"
                                    
                        if( sideinfo := stream.get('side_data_list') ):
                            if(_dvprofile := sideinfo[0].get('dv_profile')):
                                hdrtpl = f" DVp{_dvprofile}"
    
                        if resx := stream.get('width'):
                            if resy := stream.get('height'):
                                if resx/resy >= 16/9:
                                    resolutiontpl = f" {str(round(resx * 9/16))}p"
                                else:
                                    resolutiontpl = f" {str(resy)}p"
                        
                    ####
                    elif stream.get('codec_type') == "audio":
                        if alang := (stream.get('tags') or {}).get('language', '').lower():
                            if alang in "fre eng fra ang": #toimprove : pur here the prefered languages of the user +eng
                                alang_arr.append(f"{alang[:2].upper()}")

                        if codec_name in ['eac3', 'mlp']:
                            channel_layout = stream.get('channel_layout', "")
                        # eac3 (Enhanced AC-3) is often used for Atmos
                        # mlp (Meridian Lossless Packing) is used for TrueHD (which can carry Atmos)
                            if ('atmos' in (stream.get('tags') or {}).get('title', '').lower()) or (codec_name == 'eac3' and '7.1' in channel_layout) or (codec_name == 'mlp' and 'object_based' in channel_layout):
                                audiotpla = " Atmos"
        
                        elif codec_name in ['dts', 'dts_hd']:
                            dtitle = (stream.get('tags') or {}).get('title', '').lower()
                        # Additional check in the 'title' metadata if available
                            if 'dts:x' in dtitle or 'dtsx' in dtitle:
                                audiotplb = " DTSx"

                    ####
                    elif stream.get('codec_type') == "subtitle":
                        if slang := (stream.get('tags') or {}).get('language', '').lower():
                            if slang in "fre eng fra ang": 
                                slang_arr.append(f"{slang[:2].upper()}")
    
    
    
            if(info.get('format')):
                if bitrate := info.get("format").get("bit_rate"):
                    bitrate = str(round(int(info.get("format").get("bit_rate")) / 1000000))
                    bitratetpl = f" {bitrate}Mbps"
    
        except (KeyError, IndexError, json.JSONDecodeError):
            logger.error(f"jgscan/caching | Fail to extract stream details on {filepathnotice}")

    if slang_arr:
        slang_arr = list(set(slang_arr))
        slang_tpl = f" s{'s'.join(slang_arr)}"
    if alang_arr:
        alang_arr = list(set(alang_arr))
        alang_tpl = f" v{'v'.join(alang_arr)}"

    return (f"{bitratetpl}{alang_tpl}{slang_tpl}{resolutiontpl}{hdrtpl}{codectpl}{audiotpla}{audiotplb}", _dvprofile)

def find_most_similar(input_str, string_list):
    # This returns the best match, its score and index
    best_match = process.extractOne(input_str, string_list)
    return best_match

'''
def tpl(str_value, preffix = ''):
    if str_value is not None:
        return f" {preffix}{str_value}"
    return ''
'''
    

def ytpl(value):
    if value is not None:
        return f" ({str(value)})"
    return ''

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
