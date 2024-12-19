#!/bin/bash

# function on_stop() {
#     echo "Container has been stopped! Stopping mailcow an cleanup system..."
#     docker compose --project-directory ${MAILCOW_PATH}/mailcow/ down
#     rm -rf ${MAILCOW_PATH}/mailcow
#     echo "Finished!"
#     exit 0
# }

# trap on_stop SIGTERM
# trap on_stop SIGINT

rm -rf ${MAILCOW_PATH}/mailcow
mkdir -p ${MAILCOW_PATH}/mailcow/data
cp -vr /opt/mailcow/data ${MAILCOW_PATH}/mailcow/
cp -vr /opt/mailcow/docker-compose.yml ${MAILCOW_PATH}/mailcow/
cp -vr /opt/mailcow/generate_config.sh ${MAILCOW_PATH}/mailcow/

cd ${MAILCOW_PATH}/mailcow

if [ ! -f ${MAILCOW_PATH}/data/mailcow.conf ]; then
    source ./generate_config.sh
    rm -f generate_config.sh
    mkdir -p ${MAILCOW_PATH}/data
    mv mailcow.conf ${MAILCOW_PATH}/data/
fi

ln -s ${MAILCOW_PATH}/data/mailcow.conf ${MAILCOW_PATH}/mailcow/.env

mkdir -p ${MAILCOW_PATH}/data/mail

cat <<EOF > ${MAILCOW_PATH}/mailcow/docker-compose.override.yml
volumes:
  vmail-vol-1:
    driver_opts:
      type: none
      device: ${MAILCOW_PATH}/mailcow/data/mail
      o: bind
EOF

docker compose pull
docker compose up -d

docker network connect --alias edulution mailcowdockerized_mailcow-network ${HOSTNAME}

# Create API User for Mailcow
if [ ! -f ${MAILCOW_PATH}/data/mailcow-token.conf ]; then
    MAILCOW_API_TOKEN=$(openssl rand -hex 15 | awk '{printf "%s-%s-%s-%s-%s\n", substr($0,1,6), substr($0,7,6), substr($0,13,6), substr($0,19,6), substr($0,25,6)}')
    echo "MAILCOW_API_TOKEN=${MAILCOW_API_TOKEN}" > ${MAILCOW_PATH}/data/mailcow-token.conf
    source ${MAILCOW_PATH}/mailcow/.env
    mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "INSERT INTO api (api_key, allow_from, skip_ip_check, created, access, active) VALUES ('${MAILCOW_API_TOKEN}', '172.16.0.0/12', '0', NOW(), 'rw', '1')"
else
    source ${MAILCOW_PATH}/data/mailcow-token.conf
fi

# TEST API
# curl -4 -k -X 'GET'   'https://nginx/api/v1/get/status/version'   -H 'accept: application/json'   -H 'X-API-Key: c6baf8-ba41dd-a814af-d8ba9b-0b3c76'



tail -f