#!/bin/bash

### CONSTANTS and declarations ###
declare -A FIELD_DESCRIPTIONS
declare -A FIELD_DEPENDENCIES
declare -A FIELD_REGEX
declare -A FIELD_FUNCS
declare -A VALUES
FIELDS=()
func_output=""
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'

#----- 
c_choices=("AF" "AL" "DZ" "AR" "AM" "AU" "AT" "AZ" "BH" "BD" "BY" "BE" "BZ" "VE" "BO" "BA" "BW" "BR" "BN" "BG" "KH" "CM" "CA" "029" "CL" "CO" "CD" "CR" "HR" "CZ" "DK" "DO" "EC" "EG" "SV" "ER" "EE" "ET" "FO" "FI" "FR" "GE" "DE" "GR" "GL" "GT" "HT" "HN" "HK" "HU" "IS" "IN" "ID" "IR" "IQ" "IE" "PK" "IL" "IT" "CI" "JM" "JP" "JO" "KZ" "KE" "KR" "KW" "KG" "LA" "419" "LV" "LB" "LY" "LI" "LT" "LU" "MO" "MK" "MY" "MV" "ML" "MT" "MX" "MN" "ME" "MA" "NP" "NL" "NZ" "NI" "NG" "NO" "OM" "PS" "PA" "PY" "CN" "PE" "PH" "PL" "PT" "MC" "PR" "QA" "MD" "RE" "RO" "RU" "RW" "SA" "SN" "RS" "CS" "SG" "SK" "SI" "SO" "ZA" "ES" "LK" "SE" "CH" "SY" "TW" "TJ" "TH" "TT" "TN" "TR" "TM" "AE" "UA" "GB" "US" "UY" "UZ" "VN" "YE" "ZW")
l_choices=("aa" "ab" "af" "ak" "sq" "am" "ar" "an" "hy" "as" "av" "ae" "ay" "az" "ba" "bm" "eu" "be" "bn" "bh" "bi" "bs" "br" "bg" "my" "ca" "ch" "ce" "zh" "zh-tw" "zh-hk" "cu" "cv" "kw" "co" "cr" "cs" "da" "dv" "nl" "dz" "en" "eo" "et" "ee" "fo" "fj" "fi" "fr" "fr-ca" "fy" "ff" "ka" "de" "gd" "ga" "gl" "gv" "el" "gn" "gu" "ht" "ha" "he" "hz" "hi" "ho" "hr" "hu" "ig" "is" "io" "ii" "iu" "ie" "ia" "id" "ik" "it" "jv" "ja" "kl" "kn" "ks" "kr" "kk" "km" "ki" "rw" "ky" "kv" "kg" "ko" "kj" "ku" "lo" "la" "lv" "li" "ln" "lt" "lb" "lu" "lg" "mk" "mh" "ml" "mi" "mr" "ms" "mg" "mt" "mn" "na" "nv" "nr" "nd" "ng" "ne" "nn" "nb" "no" "ny" "oc" "oj" "or" "om" "os" "pa" "fa" "pi" "pl" "pt" "pt-pt" "pt-br" "ps" "qu" "rm" "ro" "rn" "ru" "sg" "sa" "si" "sk" "sl" "se" "sm" "sn" "sd" "so" "st" "es-mx" "es" "sc" "sr" "ss" "su" "sw" "sv" "ty" "ta" "tt" "te" "tg" "tl" "th" "bo" "ti" "to" "tn" "ts" "tk" "tr" "tw" "ug" "uk" "ur" "uz" "ve" "vi" "vo" "cy" "wa" "wo" "xh" "yi" "yo" "za" "zu")
threechars_languages_codes=(aar abk ace ach ada ady afa afh afr ain aka akk alb sqi ale alg alt amh ang anp apa ara arc arg arm hye arn arp art arw asm ast ath aus ava ave awa aym aze bad bai bak bal bam ban baq eus bas bat bej bel bem ben ber bho bih bik bin bis bla bnt tib bod bos bra bre btk bua bug bul bur mya byn cad cai car cat cau ceb cel cze ces cha chb che chg chi zho chk chm chn cho chp chr chu chv chy cmc cnr cop cor cos cpe cpf cpp cre crh crp csb cus wel cym cze ces dak dan dar day del den ger deu dgr din div doi dra dsb dua dum dut nld dyu dzo efi egy eka gre ell elx eng enm epo est baq eus ewe ewo fan fao per fas fat fij fil fin fiu fon fre fra fre fra frm fro frr frs fry ful fur gaa gay gba gem geo kat ger deu gez gil gla gle glg glv gmh goh gon gor got grb grc gre ell grn gsw guj gwi hai hat hau haw heb her hil him hin hit hmn hmo hrv hsb hun hup arm hye iba ibo ice isl ido iii ijo iku ile ilo ina inc ind ine inh ipk ira iro ice isl ita jav jbo jpn jpr jrb kaa kab kac kal kam kan kar kas geo kat kau kaw kaz kbd kha khi khm kho kik kin kir kmb kok kom kon kor kos kpe krc krl kro kru kua kum kur kut lad lah lam lao lat lav lez lim lin lit lol loz ltz lua lub lug lui lun luo lus mac mkd mad mag mah mai mak mal man mao mri map mar mas may msa mdf mdr men mga mic min mis mac mkd mkh mlg mlt mnc mni mno moh mon mos mao mri may msa mul mun mus mwl mwr bur mya myn myv nah nai nap nau nav nbl nde ndo nds nep new nia nic niu dut nld nno nob nog non nor nqo nso nub nwc nya nym nyn nyo nzi oci oji ori orm osa oss ota oto paa pag pal pam pan pap pau peo per fas phi phn pli pol pon por pra pro pus qaa-qtz que raj rap rar roa roh rom rum ron rum ron run rup rus sad sag sah sai sal sam san sas sat scn sco sel sem sga sgn shn sid sin sio sit sla slo slk slo slk slv sma sme smi smj smn smo sms sna snd snk sog som son sot spa alb sqi srd srn srp srr ssa ssw suk sun sus sux swa swe syc syr tah tai tam tat tel tem ter tet tgk tgl tha tib bod tig tir tiv tkl tlh tli tmh tog ton tpi tsi tsn tso tuk tum tup tur tut tvl twi tyv udm uga uig ukr umb und urd uzb vai ven vie vol vot wak wal war was wel cym wen wln wol xal xho yao yap yid yor ypk zap zbl zen zgh zha chi zho znd zul zun zxx zza)
#-----

# Change dir to the script's directory 
cd "$(dirname "$0")"

# Ensure .env exists and set secure permissions
ENV_FILE="hybrid.env"
TEMPLATE_FILE="settings.env.template"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"


### PROMPTING FUNCTIONS ###FIELD_FUNCS

prompt_for_c_choice() {
    #echo "Start typing your country code (case insensitive, 2 chars max.) and press Enter to autocomplete: (leave empty to keep default/current: $JF_COUNTRY )"
    while read -e -p "▶ " c_input; do
        # Use compgen to generate a list of matches

        if [ ! -z "$c_input" ]; then

            c_input=${c_input^^}

            for choice in "${c_choices[@]}"; do
                if [[ "$c_input" == "$choice" ]]; then
                    echo "Exact country match found: $choice"
                    func_output=$choice
                    return  # Exit the function
                fi
            done

            c_matches=($(compgen -W "${c_choices[*]}" -- "$c_input"))
            
            # Check the number of matches
            if [[ ${#c_matches[@]} -eq 1 ]]; then
                # If there's exactly one match, select it
                echo "Nearest country found: ${c_matches[0]}"
                func_output=${c_matches[0]}
                break
            elif [[ ${#c_matches[@]} -gt 1 ]]; then
                # If there are multiple matches, show them
                echo "Multiple matches: ${c_matches[*]}"
                echo "Type one country code among above matches or another one"
            else
                # No matches found
                echo "No country code match, try again..."
            fi

        else
            func_output=""
            return
        fi


    done
}

prompt_for_l_choice() {
    #echo "Start typing your language code (case insensitive, 2 chars max.) and press Enter to autocomplete: (leave empty to keep default/current: $JF_LANGUAGE )"
    while read -e -p "▶ " l_input; do

        if [ ! -z "$l_input" ]; then
            # Use compgen to generate a list of matches
            l_input=${l_input,,}

            for choice in "${l_choices[@]}"; do
                if [[ "$l_input" == "$choice" ]]; then
                    echo "Exact language match found: $choice"
                    func_output=$choice
                    return  # Exit the function
                fi
            done

            l_matches=($(compgen -W "${l_choices[*]}" -- "$l_input"))


            
            # Check the number of matches
            if [[ ${#l_matches[@]} -eq 1 ]]; then
                # If there's exactly one match, select it
                echo "Nearest language found: ${l_matches[0]}"
                func_output=${l_matches[0]}
                break
            elif [[ ${#l_matches[@]} -gt 1 ]]; then
                # If there are multiple matches, show them
                echo "Multiple matches: ${l_matches[*]}"
                echo "Type one language code among above matches or another one"
            else
                # No matches found
                echo "No language code match, try again..."
            fi

        else
            func_output=""
            return
        fi

    done
}



### LOAD EXISTING ###
load_env() {
    if [ -f "$ENV_FILE" ]; then
        while IFS='=' read -r key value; do
            key=$(echo "$key" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
            value=$(echo "$value" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
            if [[ -n "$key" && "$key" != "#"* && "$key" != "CONFIG_VERSION" ]]; then
                VALUES["$key"]="$value"
            fi
        done < "$ENV_FILE"
    fi
}



### PARSING TPL ###
parse_template() {
    if [ ! -f "$TEMPLATE_FILE" ] || [ ! -r "$TEMPLATE_FILE" ]; then
        echo "Error: Template file $TEMPLATE_FILE not found or not readable"
        exit 1
    fi

    # loop through comment+assignation 2-lines pairs
    while IFS= read -r line || [[ -n "$line" ]]; do

        if [[ "$line" =~ ^# ]]; then
            # Regex validation handling: look for regex:... in comment
            if [[ "$line" =~ @(.*) ]]; then
                CUR_FUNC="${BASH_REMATCH[1]}"
            fi
            if [[ "$line" =~ regex:([^\#]+) ]]; then
                CUR_REGEX="${BASH_REMATCH[1]}"
            fi
            # Remove leading # and any 'regex:...' part from the comment
            COMMENT="$COMMENT$(echo "$line" | sed -E 's/^# *//' | sed -E 's/regex:.*//' | sed -E 's/@[^ ]*//g' | sed 's/  */ /g' | sed 's/ *$//')"$'\n'
        elif [[ "$line" =~ ^([A-Z0-9_]+)=(.*) ]]; then
            VAR="${BASH_REMATCH[1]}"
            DEFAULT="$(echo "${BASH_REMATCH[2]}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            FIELD_DESCRIPTIONS["$VAR"]="${COMMENT:-Enter value for $VAR:}"$'\n'
            FIELDS+=("$VAR")

            # Fill missing previous values with tpl values (aka default)
            if [[ -z "${VALUES[$VAR]}" ]]; then
                VALUES["$VAR"]="$DEFAULT"
            fi

            # Dependency handling
            if [[ "$COMMENT" =~ required\ if\ ([A-Z0-9_]+)=([a-zA-Z0-9_]+) ]]; then
                FIELD_DEPENDENCIES["$VAR"]="${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
            fi

            #put the regex found eearlier
            if [[ -n "$CUR_REGEX" ]]; then
                FIELD_REGEX["$VAR"]="$CUR_REGEX"
            fi
            if [[ -n "$CUR_FUNC" ]]; then
                FIELD_FUNCS["$VAR"]="$CUR_FUNC"
            fi

            # Reset for next comment+assignation portion
            CUR_REGEX=""
            COMMENT=""
            CUR_FUNC=""
        fi
    done < "$TEMPLATE_FILE"
}

### PROMPTING ROOT ###
prompt_terminal() {
    for VAR in "${FIELDS[@]}"; do

        # Skip fields marked as (not-prompted) in description
        if [[ "${FIELD_DESCRIPTIONS[$VAR]}" == *"(not-prompted)"* ]]; then
            continue
        fi

        DEP="${FIELD_DEPENDENCIES[$VAR]}"
        if [[ -n "$DEP" ]]; then
            DEP_VAR="${DEP%=*}"
            DEP_VALUE="${DEP#*=}"
            if [[ "${VALUES[$DEP_VAR]}" != "$DEP_VALUE" ]]; then
                continue  # Skip field if dependency is not met
            fi
        fi

        CLEAN_DESCRIPTION=$(echo "${FIELD_DESCRIPTIONS[$VAR]}")

        # If a function is defined for this field, call it
        FUNC_NAME="${FIELD_FUNCS[$VAR]}"
        if [[ -n "$FUNC_NAME" ]]; then
            func_output=""
            if declare -f "$FUNC_NAME" &>/dev/null; then
                echo ""
                echo -e "$CLEAN_DESCRIPTION [${CYAN}${VALUES[$VAR]}${NC}] "
                "$FUNC_NAME"  # Call the function
                if [[ -n "$func_output" ]]; then    
                    VALUES["$VAR"]="$func_output"
                fi
            else
                echo "Warning: Function '$FUNC_NAME' not defined, skipping..."
            fi
            continue
        fi   


        # Regex validation if present
        REGEX="${FIELD_REGEX[$VAR]}"
        while true; do
            echo ""
            echo -e "$CLEAN_DESCRIPTION [${CYAN}${VALUES[$VAR]}${NC}] "
            read -rp "▶ " INPUT
            if [[ -z "$INPUT" ]]; then
                INPUT="${VALUES[$VAR]}"
            fi
            # echo "Entered: $INPUT"
            # echo "Validating with regex: $REGEX"
            if [[ -n "$REGEX" ]] && ! echo "$INPUT" | grep -Eq "$REGEX"; then
                echo "Invalid input for $VAR. Must match regex: $REGEX"
                continue
            fi
            VALUES["$VAR"]="$INPUT"
            break
        done

    done

    # Save securely to .env
    > "$ENV_FILE"
    for VAR in "${FIELDS[@]}"; do
        echo "$VAR=${VALUES[$VAR]}" >> "$ENV_FILE"
    done
    echo " "
    echo "✅ Configuration Saved!"
    echo "💡 You can re-run this script to verify your settings or edit the .env file directly."
}



### MAIN EXECUTION ###
load_env
parse_template

### FIGLET ###

echo -e "${YELLOW}"
cat <<'EOF'
     _      _ _        ____           _ _ 
    | | ___| | |_   _ / ___|_ __ __ _(_) |
 _  | |/ _ \ | | | | | |  _| '__/ _` | | |
| |_| |  __/ | | |_| | |_| | | | (_| | | |
 \___/ \___|_|_|\__, |\____|_|  \__,_|_|_|
                |___/       
                             
                      Config Setup Wizard.
EOF
echo -e "${NC}"

# Launch the terminal prompt if running in a terminal
if [[ -t 1 ]]; then
    prompt_terminal
else
    # if not terminal, throw an error
    echo "This script must be run in a terminal"
    exit 1
fi