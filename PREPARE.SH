#!/bin/bash
cd "$(dirname "$0")"
# TODO put back docker stop start commands in place
VERSION="20240715"

SETTINGS_PATH="./jellygrail/config/settings.env"
SETTINGS_EXAMPLE_PATH="./jellygrail/config/settings.env.example"

if [ -f "$SETTINGS_PATH" ]; then
    source $SETTINGS_PATH
    echo "Found previous settings values, loading them as default."
    if [ "$1" = "change" ] && [ "$RUNNING_VERSION" = "$VERSION" ]; then
        echo "If you have a running jellygrail container: "
        echo " - named something else than 'jellygrail'" 
        echo " - or managed with systemd" 
        echo "-> please manually stop it"
        if [ "$(docker ps -a --filter "name=^jellygrail$" --format '{{.Names}}')" == "jellygrail" ]; then
            read -p $'\nYou want to change settings, It\'s mandatory to stop current container to take new settings into account.\nWould you like to stop the already running jellygrail container ? (yes/no) :\n>' upyesnochange
            if [ $upyesnochange = "yes" ]; then
                docker stop jellygrail 2> /dev/null
                echo "Container stopped"
                $HASTORESTART="yes"
            fi
        fi
    fi
    if [ "$RUNNING_VERSION" != "$VERSION" ]; then
        echo "If you have a running jellygrail container: "
        echo " - named something else than 'jellygrail'" 
        echo " - or managed with systemd"
        echo "-> maybe you'll need to stop it and remove it manually"
        ONE="change"
        if [ "$(docker ps -a --filter "name=^jellygrail$" --format '{{.Names}}')" == "jellygrail" ]; then
            read -p $'\nIt\'s recommanded that you stop and remove your current container as you have pulled a new version of JellyGrail.\nWould you like to stop and remove the already running jellygrail container ? (yes/no) :\n>' upyesno
            if [ $upyesno = "yes" ]; then
                docker stop jellygrail 2> /dev/null
                docker rm jellygrail 2> /dev/null
                echo "Container stopped and deleted"
            fi
        fi
        read -p $'\nWould you like to DELETE your current virtual-renaming database ? Read this version release note ('"$VERSION"$') to know if it\'s recommanded (yes/no):\n>' dbdelyesno
        if [ $dbdelyesno = "yes" ]; then
            cp ./jellygrail/.bindfs_jelly.db ./jellygrail/bindfs_jelly.$(db.date +"%Y%m%d-%H%M%S").backup
            rm ./jellygrail/.bindfs_jelly.db
            echo "A datestamped backup has been created in ./jellygrail folder."
        fi
        echo "Will now upgrade settings from version $RUNNING_VERSION to version $VERSION"
    fi
fi



#----- 

c_choices=("AF" "AL" "DZ" "AR" "AM" "AU" "AT" "AZ" "BH" "BD" "BY" "BE" "BZ" "VE" "BO" "BA" "BW" "BR" "BN" "BG" "KH" "CM" "CA" "029" "CL" "CO" "CD" "CR" "HR" "CZ" "DK" "DO" "EC" "EG" "SV" "ER" "EE" "ET" "FO" "FI" "FR" "GE" "DE" "GR" "GL" "GT" "HT" "HN" "HK" "HU" "IS" "IN" "ID" "IR" "IQ" "IE" "PK" "IL" "IT" "CI" "JM" "JP" "JO" "KZ" "KE" "KR" "KW" "KG" "LA" "419" "LV" "LB" "LY" "LI" "LT" "LU" "MO" "MK" "MY" "MV" "ML" "MT" "MX" "MN" "ME" "MA" "NP" "NL" "NZ" "NI" "NG" "NO" "OM" "PS" "PA" "PY" "CN" "PE" "PH" "PL" "PT" "MC" "PR" "QA" "MD" "RE" "RO" "RU" "RW" "SA" "SN" "RS" "CS" "SG" "SK" "SI" "SO" "ZA" "ES" "LK" "SE" "CH" "SY" "TW" "TJ" "TH" "TT" "TN" "TR" "TM" "AE" "UA" "GB" "US" "UY" "UZ" "VN" "YE" "ZW")

l_choices=("aa" "ab" "af" "ak" "sq" "am" "ar" "an" "hy" "as" "av" "ae" "ay" "az" "ba" "bm" "eu" "be" "bn" "bh" "bi" "bs" "br" "bg" "my" "ca" "ch" "ce" "zh" "zh-tw" "zh-hk" "cu" "cv" "kw" "co" "cr" "cs" "da" "dv" "nl" "dz" "en" "eo" "et" "ee" "fo" "fj" "fi" "fr" "fr-ca" "fy" "ff" "ka" "de" "gd" "ga" "gl" "gv" "el" "gn" "gu" "ht" "ha" "he" "hz" "hi" "ho" "hr" "hu" "ig" "is" "io" "ii" "iu" "ie" "ia" "id" "ik" "it" "jv" "ja" "kl" "kn" "ks" "kr" "kk" "km" "ki" "rw" "ky" "kv" "kg" "ko" "kj" "ku" "lo" "la" "lv" "li" "ln" "lt" "lb" "lu" "lg" "mk" "mh" "ml" "mi" "mr" "ms" "mg" "mt" "mn" "na" "nv" "nr" "nd" "ng" "ne" "nn" "nb" "no" "ny" "oc" "oj" "or" "om" "os" "pa" "fa" "pi" "pl" "pt" "pt-pt" "pt-br" "ps" "qu" "rm" "ro" "rn" "ru" "sg" "sa" "si" "sk" "sl" "se" "sm" "sn" "sd" "so" "st" "es-mx" "es" "sc" "sr" "ss" "su" "sw" "sv" "ty" "ta" "tt" "te" "tg" "tl" "th" "bo" "ti" "to" "tn" "ts" "tk" "tr" "tw" "ug" "uk" "ur" "uz" "ve" "vi" "vo" "cy" "wa" "wo" "xh" "yi" "yo" "za" "zu")

#-----

prompt_for_c_choice() {
    echo "Start typing your country code (case insensitive, 2 chars max.) and press Enter to autocomplete: (leave empty to keep default/current: $JF_COUNTRY )"
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
            f_c_input=""
            return
        fi


    done
}

prompt_for_l_choice() {
    echo "Start typing your language code (case insensitive, 2 chars max.) and press Enter to autocomplete: (leave empty to keep default/current: $JF_LANGUAGE )"
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
            f_l_input=""
            return
        fi

    done
}

#----


# Check if the configuration file already exists
if [ ! -f "$SETTINGS_PATH"  ] || [ "$1" = "change" ] || [ "$ONE" = "change" ]; then

    # Copy the example configuration file to the new configuration file
    if [ -f "$SETTINGS_EXAMPLE_PATH" ] ; then
        cp -f "$SETTINGS_EXAMPLE_PATH" "$SETTINGS_PATH"
    fi
        
    # Prompt the user for the API key
    echo ""
    read -p $'\nPlease enter your Real-Debrid API key (leave empty to keep default/current: '"$RD_APITOKEN"$' ):\n> ' api_key
    read -p $'\nPlease enter the remote JellyGrail instance location, including protocol (ex: http://10.6.0.1:6502 ; leave empty to keep default/current: '"$REMOTE_RDUMP_BASE_LOCATION"$' ):\n> ' remote_loc
    read -p $'\nPlease enter this docker webdav host:port as seen by an external device on the network, excluding protocol \n(ex: your-nas-ip:8085 ; leave empty to keep default/current: '"$WEBDAV_LAN_HOST"$' ):\n> ' webdav_lan

    if [ ! -z "$remote_loc" ]; then
        read -p $'\nPlease enter the default increment from which you want to synchronize remote torrents. \nIt does not apply if /jellygrail/data/rd_incr.txt already exists BUT applies if the remote has changed a lot \n(leave empty to keep default/current: '"$DEFAULT_INCR"$' ):\n> ' default_incr
        read -p $'\nFrom the remote JellyGrail instance, do you want to take the whole content of torrents, including folders ? yes/no (default: yes ; leave empty to keep default):\n> ' whole_content
    fi




    read -p $'\nDo you want to use integrated Jellyfin ? \nyes/no (leave empty to keep default/current: '"$JF_WANTED"$')\n> ' jf_wanted

    if [ ! -z "$JF_WANTED" ] && [ -z "$jf_wanted" ]; then
        jf_wanted="$JF_WANTED"
    fi

    if [ "$jf_wanted" = "no" ]; then

        sed -i "s/JF_WANTED=\"yes\"/JF_WANTED=\"no\"/" "$SETTINGS_PATH"

        echo "...so we assume Plex might be used, you might need help from this web page to find your Plex Token : https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/"
        echo "...then list your librairies sections ids (xx) : http://your_nas_ip:32400/library/sections?X-Plex-Token=YOUR_PLEX_TOKEN"
        echo "...then build your refresh URLs like that (replace xx) : http://your_nas_ip:32400/library/sections/xx/refresh?X-Plex-Token=YOUR_PLEX_TOKEN"
        read -p "...build all refresh urls and submit them in next prompt, press enter to continue" dummy
        read -p $'\n1st Plex refresh URL (leave empty to keep default/current):\n> ' plex_refresh_a
        read -p $'\n2nd Plex refresh URL (leave empty to keep default/current):\n> ' plex_refresh_b
        read -p $'\n3rd Plex refresh URL (leave empty to keep default/current):\n> ' plex_refresh_c

        # prefill 

        if [ ! -z "$PLEX_REFRESH_A" ] && [ -z "$plex_refresh_a" ]; then
            plex_refresh_a="$PLEX_REFRESH_A"
        fi

        if [ ! -z "$PLEX_REFRESH_B" ] && [ -z "$plex_refresh_b" ]; then
            plex_refresh_b="$PLEX_REFRESH_B"
        fi

        if [ ! -z "$PLEX_REFRESH_C" ] && [ -z "$plex_refresh_c" ]; then
            plex_refresh_c="$PLEX_REFRESH_C"
        fi

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
        echo "Now configuring country and language. Please note that these settings can't be effective anymore after the first initialization of Jellyfin: In this case use the JF web interface instead"
        echo ""
        prompt_for_c_choice
        echo ""
        prompt_for_l_choice

        # prefill

        if [ ! -z "$JF_COUNTRY" ] && [ -z "$f_c_input" ]; then
            f_c_input="$JF_COUNTRY"
        fi

        if [ ! -z "$JF_LANGUAGE" ] && [ -z "$f_l_input" ]; then
            f_l_input="$JF_LANGUAGE"
        fi

        # defaults already taken into account in prompting part
        if [ ! -z "$f_c_input" ]; then
            sed -i "s/JF_COUNTRY=\"CH\"/JF_COUNTRY=\"$f_c_input\"/" "$SETTINGS_PATH"
        fi
        if [ ! -z "$f_l_input" ]; then
            sed -i "s/JF_LANGUAGE=\"fr\"/JF_LANGUAGE=\"$f_l_input\"/" "$SETTINGS_PATH"
        fi

    fi

    read -p $'\nIf an additional custom host mount folder is needed type the full desired path here\n(It should be a new path or empty folder !!)\n(leave empty to keep empty/current: '"$ADD_HOST_MOUNT"$' )\n> ' add_host_mount

    if [ ! -z "$ADD_HOST_MOUNT" ] && [ -z "$add_host_mount" ]; then
        add_host_mount="$ADD_HOST_MOUNT"
    fi

    if [ ! -z "$add_host_mount" ]; then
        sed -i "s|ADD_HOST_MOUNT=\"\"|ADD_HOST_MOUNT=\"$add_host_mount\"|" "$SETTINGS_PATH"
    fi 

    # prefill with existing values (webdav for kodi)

    if [ ! -z "$WEBDAV_LAN_HOST" ] && [ -z "$webdav_lan" ]; then
        webdav_lan="$WEBDAV_LAN_HOST"
    fi

    if [ ! -z "$webdav_lan" ]; then
        sed -i "s|PASTE-WEBDAV-LAN-HOST-HERE|$webdav_lan|" "$SETTINGS_PATH"
    fi

    # prefill with existing values (RD part)

    if [ ! -z "$RD_APITOKEN" ] && [ -z "$api_key" ]; then
        api_key="$RD_APITOKEN"
    fi

    if [ ! -z "$REMOTE_RDUMP_BASE_LOCATION" ] && [ -z "$remote_loc" ]; then
        remote_loc="$REMOTE_RDUMP_BASE_LOCATION"
    fi

    if [ ! -z "$DEFAULT_INCR" ] && [ -z "$default_incr" ]; then
        default_incr="$DEFAULT_INCR"
    fi

    # Check if the user input is empty
    if [ ! -z "$api_key" ]; then

        # Make sure the configuration file exists
        if [ -f "$SETTINGS_PATH" ]; then

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

    sed -i "s/RUNNING_VERSION=/RUNNING_VERSION=$VERSION/" "$SETTINGS_PATH"

else
    echo "The configuration file already exists, you have not prompted for a change and you have not pulled any new version."
    echo "However if you want to force a change of settings, please rerun this script with parameter 'change'."
fi

if [ "$(docker ps -a --filter "name=^jellygrail$" --format '{{.Names}}')" != "jellygrail" ]; then
    read -p $'It seems that a jellygrail container is not instanciated (could be wrong if your renamed it), Would you like to prepare the rshared mounted folders ? (yes/no ; recommanded:yes) :\n>' mountingrshared
    if [ "$mountingrshared" = "yes" ]; then
        ./_MOUNT.SH mount
    fi
    echo "You now have to instanciate the jellygrail container with 'docker run etc...' (explained in README)"
else
    echo "Your jellygrail instance seems to be running already, so _MOUNT.SH script won't be triggered automatically"
fi  
if [ "$HASTORESTART" = "yes" ]; then
    read -p $'Would you like to restart the container now ? (yes/no ; if you manage it through systemd or renamed it, please do it manually and answer no) :\n>' restartcontainer
    if [ "$restartcontainer" = "yes" ]; then
        docker start jellygrail 2> /dev/null
        echo "Existing jellygrail container has been started, it will load new settings"
    fi
fi
echo "----------------"
echo "SCRIPT COMPLETED"
echo "----------------"
