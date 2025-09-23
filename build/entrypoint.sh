#!/bin/bash

function set_mailcow_token() {
  # Create API User for Mailcow
  if [ ! -f ${MAILCOW_PATH}/data/mailcow-token.conf ]; then
    if [ -z ${MAILCOW_API_TOKEN} ]; then
      echo "==== Generating API user for mailcow... ===="
      MAILCOW_API_TOKEN=$(openssl rand -hex 15 | awk '{printf "%s-%s-%s-%s-%s\n", substr($0,1,6), substr($0,7,6), substr($0,13,6), substr($0,19,6), substr($0,25,6)}')
    fi
    echo "MAILCOW_API_TOKEN=${MAILCOW_API_TOKEN}" > ${MAILCOW_PATH}/data/mailcow-token.conf
    source ${MAILCOW_PATH}/mailcow/.env
    
    # Wait for MySQL to be ready and api table to exist
    echo "Waiting for MySQL and api table to be ready..."
    while ! mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "DESCRIBE api" >/dev/null 2>&1; do
      echo "MySQL/api table not ready yet..."
      sleep 5
    done
    
    echo "MySQL and api table are ready, inserting API token..."
    
    # Insert API token
    if mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "INSERT INTO api (api_key, allow_from, skip_ip_check, created, access, active) VALUES ('${MAILCOW_API_TOKEN}', '172.16.0.0/12', '0', NOW(), 'rw', '1')" 2>/dev/null; then
      echo "API token successfully inserted into database"
    else
      # Check if token already exists
      if mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "SELECT api_key FROM api WHERE api_key='${MAILCOW_API_TOKEN}'" | grep -q "${MAILCOW_API_TOKEN}"; then
        echo "API token already exists in database"
      else
        echo "ERROR: Failed to insert API token into database"
      fi
    fi
  else
    source ${MAILCOW_PATH}/data/mailcow-token.conf
  fi

  export MAILCOW_API_TOKEN
}

function create_edulution_view() {
  echo "==== Creating edulution_gal view... ===="
  source ${MAILCOW_PATH}/mailcow/.env
  
  # Wait for MySQL to be ready
  echo "Waiting for MySQL to be ready..."
  while ! mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "SELECT 1" >/dev/null 2>&1; do
    echo "MySQL not ready yet..."
    sleep 5
  done
  
  echo "Creating edulution_gal view..."
  
  mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME <<'EOSQL'
CREATE OR REPLACE VIEW edulution_gal AS

-- Mailboxen mit allen eigenen Aliassen
SELECT
    m.username                        AS c_uid,
    m.username                        AS c_name,
    m.name                            AS c_cn,
    NULL                              AS givenname,
    NULL                              AS sn,
    CONCAT_WS(';',
        m.username,
        (
            SELECT GROUP_CONCAT(DISTINCT a.address ORDER BY a.address SEPARATOR ';')
            FROM alias a
            WHERE a.active = 1
              AND a.goto NOT LIKE '%,%'
              AND FIND_IN_SET(m.username, REPLACE(a.goto, ' ', '')) > 0
              AND a.address <> m.username
        )
    )                                 AS mail,
    NULL                              AS telephonenumber,
    NULL                              AS mobile,
    NULL                              AS homephone,
    NULL                              AS street,
    NULL                              AS l,
    NULL                              AS postalcode,
    NULL                              AS o,
    NULL                              AS title,
    NULL                              AS url,
    NULL                              AS note,
    GREATEST(
        IFNULL(m.modified, m.created),
        IFNULL((
            SELECT MAX(a.modified)
            FROM alias a
            WHERE a.active = 1
              AND a.goto NOT LIKE '%,%'
              AND FIND_IN_SET(m.username, REPLACE(a.goto, ' ', '')) > 0
              AND a.address <> m.username
        ), m.created)
    )                                 AS updated_at
FROM mailbox m
WHERE m.active = 1

UNION ALL

-- Verteilerlisten (Aliase mit mehreren Empfängern)
SELECT
    a.address                         AS c_uid,
    a.address                         AS c_name,
    CONCAT(
        a.address,
        ' (Verteiler, ',
        LENGTH(a.goto) - LENGTH(REPLACE(a.goto, ',', '')) + 1,
        ' Empfaenger)'
    )                                 AS c_cn,
    NULL                              AS givenname,
    NULL                              AS sn,
    a.address                         AS mail,
    NULL                              AS telephonenumber,
    NULL                              AS mobile,
    NULL                              AS homephone,
    NULL                              AS street,
    NULL                              AS l,
    NULL                              AS postalcode,
    NULL                              AS o,
    NULL                              AS title,
    NULL                              AS url,
    NULL                              AS note,
    a.modified                        AS updated_at
FROM alias a
WHERE a.active = 1
  AND a.goto LIKE '%,%';
EOSQL
  
  if [ $? -eq 0 ]; then
    echo "edulution_gal view created successfully"
  else
    echo "WARNING: Failed to create edulution_gal view, it may already exist"
  fi
}

function configure_sogo_gal() {
  echo "==== Configuring SOGo Global Address List... ===="
  source ${MAILCOW_PATH}/mailcow/.env
  
  SOGO_CONF="${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo.conf"
  
  # Wait for sogo.conf to exist
  while [ ! -f "$SOGO_CONF" ]; do
    echo "Waiting for sogo.conf to be created..."
    sleep 5
  done
  
  echo "Checking SOGo configuration for GAL settings..."
  
  # Check if edulution GAL is already configured
  if grep -q "id = \"edulution\"" "$SOGO_CONF"; then
    echo "edulution GAL is already configured in SOGo"
  else
    echo "Adding edulution GAL configuration to SOGo..."
    
    # Create the GAL configuration
    GAL_CONFIG="  SOGoUserSources = (
    {
      type = sql;
      id = \"edulution\";
      isAddressBook = YES;
      canAuthenticate = NO;
      displayName = \"GAL edulution\";

      viewURL = \"mysql://${DBUSER}:${DBPASS}@mysql/${DBNAME}/edulution_gal\";

      UIDFieldName   = \"c_uid\";
      CNFieldName    = \"c_cn\";
      IDFieldName    = \"c_uid\";
      MailFieldNames = (\"mail\");

      listRequiresDot = NO; // necessary for show contacts in list!
    }
  );"
    
    # Check if SOGoUserSources exists
    if grep -q "SOGoUserSources" "$SOGO_CONF"; then
      echo "SOGoUserSources already exists, needs manual configuration"
      echo "Please add the edulution GAL configuration manually to the existing SOGoUserSources"
    else
      # Add before the closing brace of the main configuration
      # First, backup the original file
      cp "$SOGO_CONF" "${SOGO_CONF}.bak.$(date +%Y%m%d%H%M%S)"
      
      # Insert the configuration before the last closing brace
      awk -v config="$GAL_CONFIG" '
        /^}$/ && !done {
          print config
          print ""
          done=1
        }
        {print}
      ' "$SOGO_CONF" > "${SOGO_CONF}.tmp"
      
      if [ $? -eq 0 ]; then
        mv "${SOGO_CONF}.tmp" "$SOGO_CONF"
        echo "edulution GAL configuration added successfully"
        
        # Restart SOGo container to apply changes
        echo "Restarting SOGo container to apply configuration..."
        docker restart mailcowdockerized-sogo-mailcow-1 2>/dev/null || true
      else
        echo "ERROR: Failed to add GAL configuration"
        rm -f "${SOGO_CONF}.tmp"
      fi
    fi
  fi
  
  echo "SOGo GAL configuration check completed"
}

function start() {
  source /app/venv/bin/activate
  python /app/api.py 2>&1 >> /app/log.log &
  sleep 5
  python /app/sync.py
}

function init() {
  echo "===== Preparing Mailcow Instance ====="
  
  mkdir -p ${MAILCOW_PATH}/mailcow/data
  
  if [ ! -f ${MAILCOW_PATH}/mailcow/docker-compose.yml ]; then
      cp -r /opt/mailcow/. ${MAILCOW_PATH}/mailcow/
  fi
  
  cd ${MAILCOW_PATH}/mailcow

  echo "==== Generating Mailcow config, if does not exist... ===="

  export MAILCOW_TZ=${MAILCOW_TZ:-Europe/Berlin}
  export MAILCOW_BRANCH=${MAILCOW_BRANCH:-legacy}

  if [ ! -f ${MAILCOW_PATH}/data/mailcow.conf ]; then
      source ./generate_config.sh
      rm -f generate_config.sh
      mkdir -p ${MAILCOW_PATH}/data
      mv mailcow.conf ${MAILCOW_PATH}/data/
  fi

  rm -rf ${MAILCOW_PATH}/mailcow/.env
  ln -s ${MAILCOW_PATH}/data/mailcow.conf ${MAILCOW_PATH}/mailcow/.env
  ln -s ${MAILCOW_PATH}/data/mailcow.conf ${MAILCOW_PATH}/mailcow/mailcow.conf

  mkdir -p ${MAILCOW_PATH}/data/mail
}

function pull_and_start_mailcow() {
  echo "==== Downloading and starting mailcow... ===="
  
  # Always ensure SOGo files exist before starting containers
  ensure_sogo_files
  
  docker compose pull -q 2>&1 > /dev/null
  docker compose up -d --quiet-pull 2>&1 > /dev/null
}

function apply_docker_network() {
  docker network connect --alias edulution mailcowdockerized_mailcow-network ${HOSTNAME}
  docker network connect --alias edulution edulution-ui_default ${HOSTNAME}
  docker network connect --alias edulution-traefik mailcowdockerized_mailcow-network edulution-traefik
  # Add nginx alias for backward compatibility
  docker network connect --alias nginx mailcowdockerized_mailcow-network mailcowdockerized-nginx-mailcow-1 2>/dev/null || true
}

function ensure_sogo_files() {
  echo "==== Ensuring SOGo theme files exist... ===="
  
  mkdir -p ${MAILCOW_PATH}/mailcow/data/conf/sogo/
  
  # Force remove any existing directories with same names
  [ -d "${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css" ] && rm -rf ${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css
  [ -d "${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg" ] && rm -rf ${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg
  
  # Always copy fresh files to ensure they exist as FILES
  cp /templates/sogo/custom-theme.css ${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css
  cp /templates/sogo/sogo-full.svg ${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg
  
  # Verify files were created as files, not directories
  if [ ! -f "${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css" ]; then
    echo "ERROR: custom-theme.css is not a file!"
    exit 1
  fi
  if [ ! -f "${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg" ]; then
    echo "ERROR: sogo-full.svg is not a file!"
    exit 1
  fi
  
  echo "SOGo theme files verified as files"
}

function apply_templates() {
  echo "==== Applying template files for the authentification... ===="

  mkdir -p ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/
  cp /templates/dovecot/edulution-sso.lua ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/edulution-sso.lua
  cp /templates/dovecot/extra.conf ${MAILCOW_PATH}/mailcow/data/conf/dovecot/extra.conf
  chown root:401 ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/edulution-sso.lua

  mkdir -p ${MAILCOW_PATH}/mailcow/data/web/inc/
  cp /templates/web/functions.inc.php ${MAILCOW_PATH}/mailcow/data/web/inc/functions.inc.php
  cp /templates/web/sogo-auth.php ${MAILCOW_PATH}/mailcow/data/web/sogo-auth.php

  # Use the dedicated function to ensure SOGo files
  ensure_sogo_files

  echo "==== Add docker override for mailcow... ===="

  cat <<EOF > ${MAILCOW_PATH}/mailcow/docker-compose.override.yml
services:
  nginx-mailcow:
    ports: !override
      - 8443:443
  sogo-mailcow:
    volumes:
      - ./data/conf/sogo/custom-theme.css:/usr/lib/GNUstep/SOGo/WebServerResources/css/theme-default.css:z
      - ./data/conf/sogo/sogo-full.svg:/usr/lib/GNUstep/SOGo/WebServerResources/img/sogo-full.svg:z

volumes:
  vmail-vol-1:
    driver_opts:
      type: none
      device: ${MAILCOW_PATH}/data/mail
      o: bind
EOF
}

cat <<EOF
  _____ ____  _   _ _    _   _ _____ ___ ___  _   _       __  __    _    ___ _     
 | ____|  _ \| | | | |  | | | |_   _|_ _/ _ \| \ | |     |  \/  |  / \  |_ _| |    
 |  _| | | | | | | | |  | | | | | |  | | | | |  \| |_____| |\/| | / _ \  | || |    
 | |___| |_| | |_| | |__| |_| | | |  | | |_| | |\  |_____| |  | |/ ___ \ | || |___ 
 |_____|____/ \___/|_____\___/  |_| |___\___/|_| \_|     |_|  |_/_/   \_\___|_____|

EOF

if docker compose --project-directory "${MAILCOW_PATH}/mailcow/" ps | grep -q 'mailcow'; then
  echo "! Mailcow is already running. Only starting api and sync..."
  
  # Always ensure SOGo files exist even when mailcow is already running
  ensure_sogo_files
  
  set_mailcow_token
  create_edulution_view
  configure_sogo_gal
  apply_docker_network
  start
  exit
fi

init

apply_templates

configure_sogo_gal

pull_and_start_mailcow

apply_docker_network

echo "==== Waiting for mailcow to come up... ===="

# First connect to mailcow network to reach nginx
echo "Connecting to mailcow network..."
docker network connect mailcowdockerized_mailcow-network ${HOSTNAME} 2>/dev/null || true

# Wait for nginx to be ready
while ! curl -s -k --head --request GET --max-time 2 "https://nginx-mailcow/" 2>/dev/null | grep -q "HTTP/"; do
  echo "Waiting for nginx-mailcow to be ready..."
  sleep 2
done

echo "Nginx is ready, checking if mailcow is fully initialized..."

set_mailcow_token

create_edulution_view

# Wait for mailcow API to be ready (not just nginx)
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  API_RESPONSE=$(curl -s -k --max-time 5 -H "X-API-Key: ${MAILCOW_API_TOKEN}" --ipv4 "https://nginx-mailcow/api/v1/get/domain/all" 2>/dev/null || echo "")
  
  # Check if we get a proper JSON response (not the preparing page)
  if echo "$API_RESPONSE" | grep -q "mailbox"; then
    echo "Mailcow API is ready!"
    break
  elif echo "$API_RESPONSE" | grep -q "Preparing"; then
    echo "Mailcow is still preparing..."
  else
    echo "Waiting for mailcow API to be ready..."
  fi
  
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "WARNING: Mailcow did not become ready within timeout period, trying to set token anyway..."
fi

start
