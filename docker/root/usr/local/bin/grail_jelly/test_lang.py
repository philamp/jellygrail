import pycountry
import re

INTERESTED_LANGUAGES = "fre eng fra" #todo: put that in PREPARE.SH and SETTINGS EXAMPLE

# Preprocess: Create a set of all language names for quick lookup

languages = [
    "Afrikaans",
    "Arabic",
    "Bengali",
    "Bulgarian",
    "Catalan",
    "Cantonese",
    "Croatian",
    "Czech",
    "Danish",
    "Dutch",
    "Lithuanian",
    "Malay",
    "Malayalam",
    "Panjabi",
    "Tamil",
    "English",
    "Finnish",
    "French",
    "German",
    "Greek",
    "Hebrew",
    "Hindi",
    "Hungarian",
    "Indonesian",
    "Italian",
    "Japanese",
    "Javanese",
    "Korean",
    "Norwegian",
    "Polish",
    "Portuguese",
    "Romanian",
    "Russian",
    "Serbian",
    "Slovak",
    "Slovene",
    "Spanish",
    "Swedish",
    "Telugu",
    "Thai",
    "Turkish",
    "Ukrainian",
    "Vietnamese",
    "Welsh",
    "Sign language",
    "Algerian",
    "Aramaic",
    "Armenian",
    "Berber",
    "Burmese",
    "Bosnian",
    "Brazilian",
    "Bulgarian",
    "Cypriot",
    "Corsica",
    "Creole",
    "Scottish",
    "Egyptian",
    "Esperanto",
    "Estonian",
    "Finn",
    "Flemish",
    "Georgian",
    "Hawaiian",
    "Indonesian",
    "Inuit",
    "Irish",
    "Icelandic",
    "Latin",
    "Mandarin",
    "Nepalese",
    "Sanskrit",
    "Tagalog",
    "Tahitian",
    "Tibetan",
    "Gypsy",
]



language_names = [lang.lower() for lang in languages] # under 3 chars, it would be too common


# Create a single regex pattern to match any language name
# language_pattern = re.compile(r'\b(' + '|'.join(re.escape(name) for name in language_names) + r')\b', re.IGNORECASE)

def find_language_in_string(input_string):
    instrlower = input_string.lower()
    #logger.info(f"---{language_names}")
    for language in language_names:
        if re.search(rf'[ \._\-(\[]{language}[ \._\-)\]]', instrlower):
            return f" {{{language}}}"
    return ""

    # Search for any language in the input string
    #match = language_pattern.search(input_string)
    #if match:
    #    return f" {match.group(0).capitalize()}"  # Return the matched language
    #return ""

if __name__ == "__main__":
    print(find_language_in_string("The Night Manager Season 1 (S01) 1080p 10bit DS4K DSNP WEBRip x265 HEVC [HIndi] DDP Atmos 5.1 ESub ~ TsS [PMZ]"))