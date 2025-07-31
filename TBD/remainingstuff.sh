#---





#--------new / old






PLEX_REFRESH_1="PASTE_A_REFRESH_URL_HERE"
PLEX_REFRESH_2="PASTE_B_REFRESH_URL_HERE"
PLEX_REFRESH_3="PASTE_C_REFRESH_URL_HERE"

ADD_HOST_MOUNT=""

MYSQL_ROOT_PASSWORD=temporary_nothing #toimprove soon !
MYSQL_USER=kodi
MYSQL_PASSWORD=kodi


----


# Function to generate a secure CGI web form
generate_html_form() {
    echo "Content-type: text/html"
    echo ""

    echo "<!DOCTYPE html>"
    echo "<html lang='en'>"
    echo "<head><title>Env Setup Wizard</title></head>"
    echo "<body><h2>Configure Your Environment</h2>"
    echo "<form action='hybrid_setup.sh' method='post'>"

    for VAR in "${FIELDS[@]}"; do
        DEP="${FIELD_DEPENDENCIES[$VAR]}"
        if [[ -n "$DEP" ]]; then
            DEP_VAR="${DEP%=*}"
            DEP_VALUE="${DEP#*=}"
            if [[ "${VALUES[$DEP_VAR]}" != "$DEP_VALUE" ]]; then
                continue  # Skip field if dependency is not met
            fi
        fi

        CLEAN_DESCRIPTION=$(echo "${FIELD_DESCRIPTIONS[$VAR]}" | tr '\n' ' ' | sed 's/  */ /g')
        echo "<label>$CLEAN_DESCRIPTION: <input type='text' name='$VAR' value='$(sanitize_input "${VALUES[$VAR]}")'></label><br>"
    done

    echo "<button type='submit'>Save</button>"
    echo "</form></body></html>"
}

# Function to securely handle CGI form submission
handle_web_submission() {
    # Read POST data properly
    if [[ "$REQUEST_METHOD" == "POST" && -n "$CONTENT_LENGTH" ]]; then
        read -r -n "$CONTENT_LENGTH" QUERY_STRING
    else
        QUERY_STRING="$QUERY_STRING"  # Fallback for GET requests (if applicable)
    fi

    # Decode URL-encoded values (replace + with space, and decode %XX)
    QUERY_STRING=$(echo "$QUERY_STRING" | sed 's/+/ /g' | sed 's/%\(..\)/\\x\1/g' | xargs -0 printf '%b')

    # Only update the .env file if data exists
    if [[ -n "$QUERY_STRING" ]]; then
        > "$ENV_FILE"  # Clear the file before writing new values

        # Parse form data
        for VAR in "${FIELDS[@]}"; do
            SAFE_VALUE=$(echo "$QUERY_STRING" | grep -oE "$VAR=[^&]+" | cut -d '=' -f2)
            SAFE_VALUE=$(sanitize_input "$SAFE_VALUE")

            if [[ -n "$SAFE_VALUE" ]]; then
                VALUES["$VAR"]="$SAFE_VALUE"
                echo "$VAR=$SAFE_VALUE" >> "$ENV_FILE"
            fi
        done
    fi

    echo "Content-type: text/html"
    echo ""
    echo "<!DOCTYPE html>"
    echo "<html lang='en'>"
    echo "<head><meta http-equiv='refresh' content='2;url=hybrid_setup.sh'><title>Env Setup Wizard</title></head>"
    echo "<body><h2>✅ Configuration Saved Securely!</h2>"
    echo "<p>Redirecting in 2 seconds...</p>"
    echo "<a href='setup.sh'>Back</a></body></html>"
}