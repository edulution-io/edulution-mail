#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${GREEN}==>${NC} $1"
}

# Wait for MySQL with timeout
wait_for_mysql() {
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "SELECT 1" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        log_info "Waiting for MySQL... ($attempt/$max_attempts)"
        sleep 2
    done
    
    log_error "MySQL not available after $max_attempts attempts"
    return 1
}

# Set Mailcow API Token
set_mailcow_token() {
    log_step "Setting up Mailcow API token"
    
    if [ ! -f ${MAILCOW_PATH}/data/mailcow-token.conf ]; then
        if [ -z ${MAILCOW_API_TOKEN} ]; then
            log_info "Generating new API token"
            MAILCOW_API_TOKEN=$(openssl rand -hex 15 | awk '{printf "%s-%s-%s-%s-%s\n", substr($0,1,6), substr($0,7,6), substr($0,13,6), substr($0,19,6), substr($0,25,6)}')
        fi
        echo "MAILCOW_API_TOKEN=${MAILCOW_API_TOKEN}" > ${MAILCOW_PATH}/data/mailcow-token.conf
        source ${MAILCOW_PATH}/mailcow/.env
        
        # Wait for MySQL and api table
        # log_info "Waiting for MySQL and api table"
        # local attempt=0
        # while ! mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "DESCRIBE api" >/dev/null 2>&1; do
        #     attempt=$((attempt + 1))
        #     if [ $attempt -gt 60 ]; then
        #         log_error "MySQL api table not available after 60 attempts"
        #         break
        #     fi
        #     sleep 5
        # done

        # Wait for MySQL
        if ! wait_for_mysql; then
            log_error "Cannot read/create API token - MySQL unavailable"
            return 1
        fi
        
        # Insert API token
        if mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "INSERT INTO api (api_key, allow_from, skip_ip_check, created, access, active) VALUES ('${MAILCOW_API_TOKEN}', '172.16.0.0/12', '0', NOW(), 'rw', '1')" 2>/dev/null; then
            log_success "API token inserted into database"
        else
            if mysql -h mysql -u $DBUSER -p$DBPASS $DBNAME -e "SELECT api_key FROM api WHERE api_key='${MAILCOW_API_TOKEN}'" | grep -q "${MAILCOW_API_TOKEN}"; then
                log_info "API token already exists in database"
            else
                log_error "Failed to insert API token into database"
            fi
        fi
    else
        source ${MAILCOW_PATH}/data/mailcow-token.conf
        log_info "Using existing API token"
    fi
    
    export MAILCOW_API_TOKEN
}

# Create edulution_gal view
create_edulution_view() {
    log_step "Creating edulution GAL database view"
    source ${MAILCOW_PATH}/mailcow/.env
    
    # Wait for MySQL
    if ! wait_for_mysql; then
        log_error "Cannot create view - MySQL unavailable"
        return 1
    fi
    
    log_info "Creating edulution_gal view"
    
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
        log_success "edulution_gal view created"
    else
        log_warning "Failed to create edulution_gal view (may already exist)"
    fi
}

# Configure SOGo GAL
configure_sogo_gal() {
    log_step "Configuring SOGo Global Address List"
    source ${MAILCOW_PATH}/mailcow/.env
    
    SOGO_CONF="${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo.conf"
    
    # Wait for sogo.conf
    local attempt=0
    while [ ! -f "$SOGO_CONF" ]; do
        attempt=$((attempt + 1))
        if [ $attempt -gt 60 ]; then
            log_error "sogo.conf not found after 60 attempts"
            return 1
        fi
        log_info "Waiting for sogo.conf... ($attempt/60)"
        sleep 5
    done
    
    # Check if already configured
    if grep -q "id = \"edulution\"" "$SOGO_CONF" 2>/dev/null; then
        log_info "edulution GAL already configured"
        return 0
    fi
    
    log_info "Adding edulution GAL configuration"
    
    # Create GAL configuration
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

      listRequiresDot = NO;
    }
  );"
    
    # Check if SOGoUserSources already exists
    if grep -q "SOGoUserSources" "$SOGO_CONF"; then
        log_warning "SOGoUserSources already exists - manual configuration needed"
        return 1
    fi
    
    # Backup and modify configuration
    cp "$SOGO_CONF" "${SOGO_CONF}.bak.$(date +%Y%m%d%H%M%S)"
    
    # Insert configuration before last closing brace
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
        log_success "GAL configuration added"
    else
        log_error "Failed to add GAL configuration"
        rm -f "${SOGO_CONF}.tmp"
        return 1
    fi
}

# Start API and sync services
start_services() {
    log_step "Starting API and sync services"
    
    source /app/venv/bin/activate
    
    log_info "Starting API service"
    python /app/api.py 2>&1 >> /app/log.log &
    
    sleep 5
    
    log_info "Starting sync service"
    python /app/sync.py
}

# Initialize Mailcow
init_mailcow() {
    log_step "Initializing Mailcow instance"
    
    mkdir -p ${MAILCOW_PATH}/mailcow/data
    
    if [ ! -f ${MAILCOW_PATH}/mailcow/docker-compose.yml ]; then
        log_info "Copying Mailcow files"
        cp -r /opt/mailcow/. ${MAILCOW_PATH}/mailcow/
    fi
    
    cd ${MAILCOW_PATH}/mailcow
    
    # Generate config if needed
    export MAILCOW_TZ=${MAILCOW_TZ:-Europe/Berlin}
    export MAILCOW_BRANCH=${MAILCOW_BRANCH:-legacy}
    
    if [ ! -f ${MAILCOW_PATH}/data/mailcow.conf ]; then
        log_info "Generating Mailcow configuration"
        source ./generate_config.sh
        rm -f generate_config.sh
        mkdir -p ${MAILCOW_PATH}/data
        mv mailcow.conf ${MAILCOW_PATH}/data/
    fi
    
    # Create symlinks
    rm -rf ${MAILCOW_PATH}/mailcow/.env
    ln -s ${MAILCOW_PATH}/data/mailcow.conf ${MAILCOW_PATH}/mailcow/.env
    ln -s ${MAILCOW_PATH}/data/mailcow.conf ${MAILCOW_PATH}/mailcow/mailcow.conf
    
    mkdir -p ${MAILCOW_PATH}/data/mail
    
    log_success "Mailcow initialized"
}

# Ensure SOGo theme files exist
ensure_sogo_files() {
    log_info "Ensuring SOGo theme files"
    
    mkdir -p ${MAILCOW_PATH}/mailcow/data/conf/sogo/
    
    # Remove directories if they exist
    [ -d "${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css" ] && rm -rf ${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css
    [ -d "${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg" ] && rm -rf ${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg
    
    # Copy theme files
    cp /templates/sogo/custom-theme.css ${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css
    cp /templates/sogo/sogo-full.svg ${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg
    
    # Verify files
    if [ ! -f "${MAILCOW_PATH}/mailcow/data/conf/sogo/custom-theme.css" ]; then
        log_error "custom-theme.css is not a file!"
        exit 1
    fi
    if [ ! -f "${MAILCOW_PATH}/mailcow/data/conf/sogo/sogo-full.svg" ]; then
        log_error "sogo-full.svg is not a file!"
        exit 1
    fi
    
    log_success "SOGo theme files ready"
}

# Apply template files
apply_templates() {
    log_step "Applying template files"
    
    # Dovecot templates
    log_info "Copying Dovecot authentication templates"
    mkdir -p ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/
    cp /templates/dovecot/edulution-sso.lua ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/edulution-sso.lua
    cp /templates/dovecot/extra.conf ${MAILCOW_PATH}/mailcow/data/conf/dovecot/extra.conf
    chown root:401 ${MAILCOW_PATH}/mailcow/data/conf/dovecot/lua/edulution-sso.lua
    
    # Web templates
    log_info "Copying web authentication templates"
    mkdir -p ${MAILCOW_PATH}/mailcow/data/web/inc/
    cp /templates/web/functions.inc.php ${MAILCOW_PATH}/mailcow/data/web/inc/functions.inc.php
    cp /templates/web/sogo-auth.php ${MAILCOW_PATH}/mailcow/data/web/sogo-auth.php
    
    # SOGo files
    ensure_sogo_files
    
    # Docker override
    log_info "Creating Docker Compose override"
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
    
    log_success "Templates applied"
}

# Pull and start Mailcow containers
pull_and_start_mailcow() {
    log_step "Starting Mailcow containers"
    
    ensure_sogo_files
    
    log_info "Pulling Docker images"
    docker compose pull -q 2>&1 > /dev/null
    
    log_info "Starting containers"
    docker compose up -d --quiet-pull 2>&1 > /dev/null
    
    log_success "Mailcow containers started"
}

# Apply Docker network connections
apply_docker_network() {
    log_step "Configuring Docker networks"
    
    log_info "Connecting to mailcow network"
    docker network connect --alias edulution mailcowdockerized_mailcow-network ${HOSTNAME} 2>/dev/null || true
    
    log_info "Connecting to UI network"
    docker network connect --alias edulution edulution-ui_default ${HOSTNAME} 2>/dev/null || true
    
    log_info "Connecting Traefik"
    docker network connect --alias edulution-traefik mailcowdockerized_mailcow-network edulution-traefik 2>/dev/null || true
    
    # Backward compatibility
    docker network connect --alias nginx mailcowdockerized_mailcow-network mailcowdockerized-nginx-mailcow-1 2>/dev/null || true
    
    log_success "Networks configured"
}

# Wait for Mailcow to be ready
wait_for_mailcow() {
    log_step "Waiting for Mailcow to be ready"
    
    # Connect to network first
    log_info "Connecting to Mailcow network"
    docker network connect mailcowdockerized_mailcow-network ${HOSTNAME} 2>/dev/null || true
    
    # Wait for nginx
    local attempt=0
    while ! curl -s -k --head --request GET --max-time 2 "https://nginx-mailcow/" 2>/dev/null | grep -q "HTTP/"; do
        attempt=$((attempt + 1))
        if [ $attempt -gt 60 ]; then
            log_error "Nginx not ready after 60 attempts"
            break
        fi
        log_info "Waiting for Nginx... ($attempt/60)"
        sleep 2
    done
    
    log_success "Nginx is ready"
    
    # Wait for API
    log_info "Checking Mailcow API"
    attempt=0
    while [ $attempt -lt 60 ]; do
        API_RESPONSE=$(curl -s -k --max-time 5 -H "X-API-Key: ${MAILCOW_API_TOKEN}" --ipv4 "https://nginx-mailcow/api/v1/get/status/containers" 2>/dev/null || echo "")
        
        if echo "$API_RESPONSE" | grep -q "running"; then
            log_success "Mailcow API is ready"
            break
        elif echo "$API_RESPONSE" | grep -q "Preparing"; then
            log_info "Mailcow is still preparing..."
        else
            log_info "Waiting for API... ($attempt/60)"
        fi
        
        attempt=$((attempt + 1))
        sleep 5
    done
    
    if [ $attempt -eq 60 ]; then
        log_warning "Mailcow API timeout - continuing anyway"
    fi
}

# Main execution
main() {
    # Banner
    cat <<EOF

  _____ ____  _   _ _    _   _ _____ ___ ___  _   _       __  __    _    ___ _     
 | ____|  _ \| | | | |  | | | |_   _|_ _/ _ \| \ | |     |  \/  |  / \  |_ _| |    
 |  _| | | | | | | | |  | | | | | |  | | | | |  \| |_____| |\/| | / _ \  | || |    
 | |___| |_| | |_| | |__| |_| | | |  | | |_| | |\  |_____| |  | |/ ___ \ | || |___ 
 |_____|____/ \___/|_____\___/  |_| |___\___/|_| \_|     |_|  |_/_/   \_\___|_____|

EOF
    
    # Check if Mailcow is already running
    if docker compose --project-directory "${MAILCOW_PATH}/mailcow/" ps | grep -q 'mailcow'; then
        log_warning "Mailcow is already running - only starting API and sync services"
        
        ensure_sogo_files
        set_mailcow_token
        create_edulution_view
        configure_sogo_gal
        apply_docker_network
        start_services
        exit 0
    fi
    
    # Full initialization
    init_mailcow
    apply_templates
    configure_sogo_gal
    pull_and_start_mailcow
    set_mailcow_token
    create_edulution_view
    apply_docker_network
    wait_for_mailcow
    start_services
}

# Run main function
main