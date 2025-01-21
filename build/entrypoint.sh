#!/bin/bash

function on_stop() {
    echo "Container has been stopped! Stopping mailcow an cleanup system..."
    docker compose --project-directory ${MAILCOW_PATH}/mailcow/ down
    rm -rf ${MAILCOW_PATH}/mailcow
    echo "Finished!"
    exit 0
}

trap on_stop SIGTERM
trap on_stop SIGINT

cat <<EOF
  _____ ____  _   _ _    _   _ _____ ___ ___  _   _       __  __    _    ___ _     
 | ____|  _ \| | | | |  | | | |_   _|_ _/ _ \| \ | |     |  \/  |  / \  |_ _| |    
 |  _| | | | | | | | |  | | | | | |  | | | | |  \| |_____| |\/| | / _ \  | || |    
 | |___| |_| | |_| | |__| |_| | | |  | | |_| | |\  |_____| |  | |/ ___ \ | || |___ 
 |_____|____/ \___/|_____\___/  |_| |___\___/|_| \_|     |_|  |_/_/   \_\___|_____|

EOF

if [ -n $(docker compose --project-directory ${MAILCOW_PATH}/mailcow/ ps | grep mailcow) ]; then
  echo "! Mailcow is already running. Only starting api and sync..."
  source /app/venv/bin/activate
  python /app/api.py 2>&1 >> /app/log.log &
  python /app/sync.py
  exit
fi

echo "===== Preparing Mailcow Instance ====="
rm -rf ${MAILCOW_PATH}/mailcow
mkdir -p ${MAILCOW_PATH}/mailcow/data
cp -r /opt/mailcow/data ${MAILCOW_PATH}/mailcow/
cp -r /opt/mailcow/docker-compose.yml ${MAILCOW_PATH}/mailcow/
cp -r /opt/mailcow/generate_config.sh ${MAILCOW_PATH}/mailcow/

echo "==== Applying template files for the authentification... ===="

mkdir -p ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/
cp /templates/dovecot/edulution-sso.lua ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/edulution-sso.lua
cp /templates/dovecot/extra.conf ${MAILCOW_PATH}/mailcow/data/conf/dovecot/extra.conf
chown root:401 ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/edulution-sso.lua

mkdir -p ${MAILCOW_PATH}/mailcow/data/web/inc/
cp /templates/web/functions.inc.php ${MAILCOW_PATH}/mailcow/data/web/inc/functions.inc.php
cp /templates/web/sogo-auth.php ${MAILCOW_PATH}/mailcow/data/web/sogo-auth.php

mkdir -p ${MAILCOW_PATH}/mailcow/data/conf/sogo/
cp /templates/sogo/custom-theme.css ${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css
cp /templates/sogo/sogo-full.svg ${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg

cd ${MAILCOW_PATH}/mailcow

echo "==== Generating Mailcow config, if does not exist... ===="

export MAILCOW_TZ=${MAILCOW_TZ:-Europe/Berlin}
export MAILCOW_BRANCH=${MAILCOW_BRANCH:-master}

if [ ! -f ${MAILCOW_PATH}/data/mailcow.conf ]; then
    source ./generate_config.sh
    rm -f generate_config.sh
    mkdir -p ${MAILCOW_PATH}/data
    mv mailcow.conf ${MAILCOW_PATH}/data/
fi

ln -s ${MAILCOW_PATH}/data/mailcow.conf ${MAILCOW_PATH}/mailcow/.env

mkdir -p ${MAILCOW_PATH}/data/mail

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

echo "==== Downloading and starting mailcow... ===="

docker compose pull -q 2>&1 > /dev/null
docker compose up -d --quiet-pull 2>&1 > /dev/null

docker network connect --alias edulution mailcowdockerized_mailcow-network ${HOSTNAME}
docker network connect --alias edulution edulution-ui_default ${HOSTNAME}

docker network connect --alias edulution-traefik mailcowdockerized_mailcow-network edulution-traefik

# Create API User for Mailcow
if [ ! -f ${MAILCOW_PATH}/data/mailcow-token.conf ]; then
  echo "==== Generating API user for mailcow... ===="
  MAILCOW_API_TOKEN=$(openssl rand -hex 15 | awk '{printf "%s-%s-%s-%s-%s\n", substr($0,1,6), substr($0,7,6), substr($0,13,6), substr($0,19,6), substr($0,25,6)}')
  echo "MAILCOW_API_TOKEN=${MAILCOW_API_TOKEN}" > ${MAILCOW_PATH}/data/mailcow-token.conf
  source ${MAILCOW_PATH}/mailcow/.env
  mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "INSERT INTO api (api_key, allow_from, skip_ip_check, created, access, active) VALUES ('${MAILCOW_API_TOKEN}', '172.16.0.0/12', '0', NOW(), 'rw', '1')"
else
  source ${MAILCOW_PATH}/data/mailcow-token.conf
fi

export MAILCOW_API_TOKEN

echo "==== Waiting for mailcow to come up... ===="

while ! curl -s -k --head --request GET --max-time 2 "https://nginx/api/v1/get" | grep -q "HTTP/"; do
  echo "[...]"
  sleep 1
done

# Starting auth api
source /app/venv/bin/activate
python /app/api.py 2>&1 >> /app/log.log &
sleep 
python /app/sync.py