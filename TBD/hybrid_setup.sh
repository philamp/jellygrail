#!/bin/bash

ENV_FILE="hybrid.env"
TEMPLATE_FILE="hybrid.env.template"

# Ensure .env exists and set secure permissions
touch "$ENV_FILE"
#chmod 600 "$ENV_FILE"

# Function to load existing values from .env
load_env() {
    if [ -f "$ENV_FILE" ]; then
        while IFS='=' read -r key value; do
            key=$(echo "$key" | tr -d ' ')
            value=$(echo "$value" | tr -d ' ')
            if [[ -n "$key" && "$key" != "#"* ]]; then
                VALUES["$key"]="$value"
            fi
        done < "$ENV_FILE"
    fi
}

# Function to sanitize input (Only allows alphanumeric, dots, dashes, and underscores)
sanitize_input() {
    echo "$1" | sed 's/[^a-zA-Z0-9._-]//g'
}

# Function to parse .env.template and extract fields & dependencies
parse_template() {
    declare -Ag FIELD_DESCRIPTIONS
    declare -Ag FIELD_DEPENDENCIES

    COMMENT=""
    if [ ! -f "$TEMPLATE_FILE" ] || [ ! -r "$TEMPLATE_FILE" ]; then
        echo "Error: Template file $TEMPLATE_FILE not found or not readable"
        exit 1
    fi

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^# ]]; then
            COMMENT=$(echo "$line" | sed 's/^# *//')
        elif [[ "$line" =~ ^([A-Z_]+)=(.*) ]]; then
            VAR="${BASH_REMATCH[1]}"
            DEFAULT="${BASH_REMATCH[2]//[[:space:]]/}"
            FIELD_DESCRIPTIONS["$VAR"]="${COMMENT:-Enter value for $VAR:}"
            FIELDS+=("$VAR")

            # Use existing value from hybrid.env or default from template
            if [[ -z "${VALUES[$VAR]}" ]]; then
                VALUES["$VAR"]="$DEFAULT"
            fi

            if [[ "$COMMENT" =~ required\ if\ ([A-Z_]+)=([a-zA-Z0-9_]+) ]]; then
                FIELD_DEPENDENCIES["$VAR"]="${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
            fi
            COMMENT=""
        fi
    done < "$TEMPLATE_FILE"

    declare -p FIELD_DESCRIPTIONS FIELD_DEPENDENCIES > /dev/null
}

# Function to show the Whiptail UI (CLI Mode)
prompt_terminal() {
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
        if [[ -z "$CLEAN_DESCRIPTION" ]]; then
            CLEAN_DESCRIPTION="Enter value for $VAR:"
        fi

        # Use previous value as default
        VALUE=$(whiptail --inputbox "$CLEAN_DESCRIPTION" 8 50 "$(sanitize_input "${VALUES[$VAR]}")" --title "Setup Wizard" 3>&1 1>&2 2>&3)
        VALUES["$VAR"]="$(sanitize_input "$VALUE")"
    done

    # Save securely to .env
    > "$ENV_FILE"
    for VAR in "${FIELDS[@]}"; do
        echo "$VAR=${VALUES[$VAR]}" >> "$ENV_FILE"
    done
    #chmod 600 "$ENV_FILE"  # Secure file
    whiptail --msgbox "✅ Configuration Saved!" 8 50
}

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

### MAIN EXECUTION ###
declare -A VALUES
FIELDS=()
load_env
parse_template

if [[ -t 1 ]]; then
    prompt_terminal
else
    if [[ "$REQUEST_METHOD" == "POST" ]]; then
        handle_web_submission
    else
        generate_html_form
    fi
fi