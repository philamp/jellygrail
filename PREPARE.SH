#!/bin/bash

c_choices=("AF" "AL" "DZ" "AR" "AM" "AU" "AT" "AZ" "BH" "BD" "BY" "BE" "BZ" "VE" "BO" "BA" "BW" "BR" "BN" "BG" "KH" "CM" "CA" "029" "CL" "CO" "CD" "CR" "HR" "CZ" "DK" "DO" "EC" "EG" "SV" "ER" "EE" "ET" "FO" "FI" "FR" "GE" "DE" "GR" "GL" "GT" "HT" "HN" "HK" "HU" "IS" "IN" "ID" "IR" "IQ" "IE" "PK" "IL" "IT" "CI" "JM" "JP" "JO" "KZ" "KE" "KR" "KW" "KG" "LA" "419" "LV" "LB" "LY" "LI" "LT" "LU" "MO" "MK" "MY" "MV" "ML" "MT" "MX" "MN" "ME" "MA" "NP" "NL" "NZ" "NI" "NG" "NO" "OM" "PS" "PA" "PY" "CN" "PE" "PH" "PL" "PT" "MC" "PR" "QA" "MD" "RE" "RO" "RU" "RW" "SA" "SN" "RS" "CS" "SG" "SK" "SI" "SO" "ZA" "ES" "LK" "SE" "CH" "SY" "TW" "TJ" "TH" "TT" "TN" "TR" "TM" "AE" "UA" "GB" "US" "UY" "UZ" "VN" "YE" "ZW")

l_choices=("aa" "ab" "af" "ak" "sq" "am" "ar" "an" "hy" "as" "av" "ae" "ay" "az" "ba" "bm" "eu" "be" "bn" "bh" "bi" "bs" "br" "bg" "my" "ca" "ch" "ce" "zh" "zh-tw" "zh-hk" "cu" "cv" "kw" "co" "cr" "cs" "da" "dv" "nl" "dz" "en" "eo" "et" "ee" "fo" "fj" "fi" "fr" "fr-ca" "fy" "ff" "ka" "de" "gd" "ga" "gl" "gv" "el" "gn" "gu" "ht" "ha" "he" "hz" "hi" "ho" "hr" "hu" "ig" "is" "io" "ii" "iu" "ie" "ia" "id" "ik" "it" "jv" "ja" "kl" "kn" "ks" "kr" "kk" "km" "ki" "rw" "ky" "kv" "kg" "ko" "kj" "ku" "lo" "la" "lv" "li" "ln" "lt" "lb" "lu" "lg" "mk" "mh" "ml" "mi" "mr" "ms" "mg" "mt" "mn" "na" "nv" "nr" "nd" "ng" "ne" "nn" "nb" "no" "ny" "oc" "oj" "or" "om" "os" "pa" "fa" "pi" "pl" "pt" "pt-pt" "pt-br" "ps" "qu" "rm" "ro" "rn" "ru" "sg" "sa" "si" "sk" "sl" "se" "sm" "sn" "sd" "so" "st" "es-mx" "es" "sc" "sr" "ss" "su" "sw" "sv" "ty" "ta" "tt" "te" "tg" "tl" "th" "bo" "ti" "to" "tn" "ts" "tk" "tr" "tw" "ug" "uk" "ur" "uz" "ve" "vi" "vo" "cy" "wa" "wo" "xh" "yi" "yo" "za" "zu")

#-----

prompt_for_c_choice() {
    echo "Start typing your country code (case insensitive, 2 chars max.) and press Enter to autocomplete: (default:US;leave empty to keep default)"
    while read -e -p "> " c_input; do
        # Use compgen to generate a list of matches

        if [ ! -z "$c_input" ]; then

            c_input=${c_input^^}

            for choice in "${c_choices[@]}"; do
                if [[ "$c_input" == "$choice" ]]; then
                    echo "Exact country match found: $choice"
                    f_c_input=$choice
                    return  # Exit the function
                fi
            done

            c_matches=($(compgen -W "${c_choices[*]}" -- "$c_input"))
            
            # Check the number of matches
            if [[ ${#c_matches[@]} -eq 1 ]]; then
                # If there's exactly one match, select it
                echo "Nearest country found: ${c_matches[0]}"
                f_c_input=${c_matches[0]}
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
            f_c_input="US"
            return
        fi


    done
}

prompt_for_l_choice() {
    echo "Start typing your language code (case insensitive, 2 chars max.) and press Enter to autocomplete: (default:en;leave empty to keep default)"
    while read -e -p "> " l_input; do

        if [ ! -z "$l_input" ]; then
            # Use compgen to generate a list of matches
            l_input=${l_input,,}

            for choice in "${l_choices[@]}"; do
                if [[ "$l_input" == "$choice" ]]; then
                    echo "Exact language match found: $choice"
                    f_l_input=$choice
                    return  # Exit the function
                fi
            done

            l_matches=($(compgen -W "${l_choices[*]}" -- "$l_input"))


            
            # Check the number of matches
            if [[ ${#l_matches[@]} -eq 1 ]]; then
                # If there's exactly one match, select it
                echo "Nearest language found: ${l_matches[0]}"
                f_l_input=${l_matches[0]}
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
            f_l_input="en"
            return
        fi

    done
}

#----

# Path to the rclone configuration file and its example

CONF_PATH="./mounts/remote_realdebrid/rclone.conf"
CONF_EXAMPLE_PATH="./mounts/remote_realdebrid/rclone.conf.example"

SETTINGS_PATH="./jellygrail/config/settings.env"
SETTINGS_EXAMPLE_PATH="./jellygrail/config/settings.env.example"

if [ "$1" = "upgrade" ]; then
    read -p $'\nWould you like to stop and remove the already running JellyGrail container ? (yes/no) (needed for running a new one):\n>' upyesno
    if [ $upyesno = "yes" ]; then
        docker stop jellygrail
        docker rm jellygrail
    fi
fi 

# Check if the configuration file already exists
if [ ! -f "$CONF_PATH"  ] || [ ! -f "$SETTINGS_PATH"  ] || [ "$1" = "upgrade" ]; then

    # Copy the example configuration file to the new configuration file
    if [ -f "$SETTINGS_EXAMPLE_PATH" ]; then
        cp -f "$SETTINGS_EXAMPLE_PATH" "$SETTINGS_PATH"
    fi
        
    # Prompt the user for the API key
    echo "-- Upgrade or creation of config files: $CONF_PATH and $SETTINGS_PATH will be created --"
    echo ""
    read -p $'\nPlease enter your Real-Debrid API key (leave empty to ignore):\n> ' api_key
    read -p $'\nPlease enter the remote JellyGrail instance location (ex: http://10.6.0.1:6502 ; leave empty to ignore):\n> ' remote_loc

    if [ ! -z "$remote_loc" ]; then
        read -p $'\nPlease enter the initial increment from which you want to synchronize remote torrents. \nIt does not apply if /jellygrail/data/rd_incr.txt already exists. \n(default: 0 ; leave empty to keep default):\n> ' default_incr
        read -p $'\nFrom the remote JellyGrail instance, do you want to take the whole content of torrents, including folders ? yes/no (default: yes ; leave empty to keep default):\n> ' whole_content
    fi

    read -p $'\nDo you want to use integrated Jellyfin ? \nyes/no (default: yes ; leave empty to keep default)\n> ' jf_wanted

    if [ "$jf_wanted" = "no" ]; then

        sed -i "s/JF_WANTED=\"yes\"/JF_WANTED=\"no\"/" "$SETTINGS_PATH"

        echo "...so we assume Plex might be used, you might need help from this web page to find your Plex Token : https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/"
        echo "...then list your librairies sections ids (xx) : http://your_nas_ip:32400/library/sections?X-Plex-Token=YOUR_PLEX_TOKEN"
        echo "...then build your refresh URLs like that (replace xx) : http://your_nas_ip:32400/library/sections/xx/refresh?X-Plex-Token=YOUR_PLEX_TOKEN"
        read -p "...build all refresh urls and submit them in next prompt, press enter to continue" dummy
        read -p $'\n1st Plex refresh URL (leave empty to ignore):\n> ' plex_refresh_a
        read -p $'\n2nd Plex refresh URL (leave empty to ignore):\n> ' plex_refresh_b
        read -p $'\n3rd Plex refresh URL (leave empty to ignore):\n> ' plex_refresh_c

        if [ ! -z "$plex_refresh_a" ]; then
            sed -i "s|PLEX_REFRESH_A=\"PASTE_A_REFRESH_URL_HERE\"|PLEX_REFRESH_A=\"$plex_refresh_a\"|" "$SETTINGS_PATH"
        fi
        if [ ! -z "$plex_refresh_b" ]; then
            sed -i "s|PLEX_REFRESH_B=\"PASTE_B_REFRESH_URL_HERE\"|PLEX_REFRESH_B=\"$plex_refresh_b\"|" "$SETTINGS_PATH"
        fi
        if [ ! -z "$plex_refresh_c" ]; then
            sed -i "s|PLEX_REFRESH_C=\"PASTE_C_REFRESH_URL_HERE\"|PLEX_REFRESH_C=\"$plex_refresh_c\"|" "$SETTINGS_PATH"
        fi

    else
        echo ""
        prompt_for_c_choice
        echo ""
        prompt_for_l_choice
        sed -i "s/JF_COUNTRY=\"CH\"/JF_COUNTRY=\"$f_c_input\"/" "$SETTINGS_PATH"
        sed -i "s/JF_LANGUAGE=\"fr\"/JF_LANGUAGE=\"$f_l_input\"/" "$SETTINGS_PATH"
    fi

    read -p $'\nIf an additional custom host mount folder is needed type the full desired path here\n(leave empty to ignore)\n> ' add_host_mount
    if [ ! -z "$add_host_mount" ]; then
        sed -i "s|ADD_HOST_MOUNT=\"\"|ADD_HOST_MOUNT=\"$add_host_mount\"|" "$SETTINGS_PATH"
    fi 

    # Check if the user input is empty
    if [ ! -z "$api_key" ]; then
        # Make sure the example configuration file exists
        if [ -f "$CONF_EXAMPLE_PATH" ]; then
            # Copy the example configuration file to the new configuration file
            cp -f "$CONF_EXAMPLE_PATH" "$CONF_PATH"
    
            # Replace the placeholder with the user-provided API key
            sed -i "s/PASTE-YOUR-KEY-HERE/$api_key/" "$CONF_PATH"
    
            echo "The RD rclone configuration file has been created and the API key has been inserted."
        else
            echo "The RD rclone example configuration file does not exist. Please check the path."
        fi

        # Make sure the example configuration file exists
        if [ -f "$SETTINGS_EXAMPLE_PATH" ]; then

            # Replace the placeholder with the user-provided API key
            sed -i "s/PASTE-YOUR-KEY-HERE/$api_key/" "$SETTINGS_PATH"
            if [ ! -z "$remote_loc" ]; then
                sed -i "s|PASTE-REMOTE-ADDR-HERE|$remote_loc|" "$SETTINGS_PATH"
            fi
            if [ ! -z "$default_incr" ]; then
                sed -i "s/DEFAULT_INCR=\"0\"/DEFAULT_INCR=\"$default_incr\"/" "$SETTINGS_PATH"
            fi
            if [ ! -z "$whole_content" ]; then
                sed -i "s/ALL_FILES_INCLUDING_STRUCTURE=\"yes\"/ALL_FILES_INCLUDING_STRUCTURE=\"$whole_content\"/" "$SETTINGS_PATH"
            fi

        else
            echo "The jellygrail example settings file does not exist. Please check the path."
        fi

    else
        echo "No API key entered. The configuration file will not be created. Real-Debrid implementation will not work"
    fi

else
    echo "The configuration file already exists."
fi

echo "Proceeding with the script (creation of jf config folders and rshare mounting of Video_Library folder)"
echo "------------------------------------------------------------------------------------------------------"
./_MOUNT.SH mount
echo "SCRIPT COMPLETED"
echo "----------------"
