import os
import logging
import json

class ConfigurationStorage:

    def load(self):
        self.importFromEnvironment()
        self.importFromOverrideFile()

    def importFromEnvironment(self):
        self.DEFAULT_USER_QUOTA = os.environ.get("DEFAULT_USER_QUOTA", 1000)

        self.GROUPS_TO_SYNC = os.environ.get("GROUPS_TO_SYNC", "role-schooladministrator,role-teacher,role-student")
        self.GROUPS_TO_SYNC = self.GROUPS_TO_SYNC.split(",") if "," in self.GROUPS_TO_SYNC else [ self.GROUPS_TO_SYNC ]

        self.DOMAIN_QUOTA = os.environ.get("DOMAIN_QUOTA", 10 * 1024)
        self.ENABLE_GAL = os.environ.get("ENABLE_GAL", 1)

        self.SYNC_INTERVAL = os.environ.get("SYNC_INTERVAL", 300)
        self.RETRY_INTERVAL = int(self.SYNC_INTERVAL) // 5 if int(self.SYNC_INTERVAL) >= 60 else 10
        
        self.SOFT_DELETE_ENABLED = int(os.environ.get("SOFT_DELETE_ENABLED", 1))
        self.SOFT_DELETE_GRACE_PERIOD = int(os.environ.get("SOFT_DELETE_GRACE_PERIOD", 2592000))  # 30 days default
        self.SOFT_DELETE_MARK_COUNT = int(os.environ.get("SOFT_DELETE_MARK_COUNT", 10))  # Number of marks before deactivation
        self.PERMANENT_DELETE_ENABLED = int(os.environ.get("PERMANENT_DELETE_ENABLED", 1))  # Enable permanent deletion after grace period

        self.MAILCOW_API_TOKEN = os.environ.get("MAILCOW_API_TOKEN", False) # entrypoint.sh set this as environment variable
        self.KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "edu-mailcow-sync")
        self.KEYCLOAK_SECRET_KEY = os.environ.get("KEYCLOAK_SECRET_KEY", False)
        self.KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", "https://edulution-traefik/auth/")

        self.MAILCOW_PATH = os.environ.get("MAILCOW_PATH", "/srv/docker/edulution-mail")

        self.IGNORE_MAILBOXES = os.environ.get("IGNORE_MAILBOXES", "")
        self.IGNORE_MAILBOXES = self.IGNORE_MAILBOXES.split(",") if "," in self.IGNORE_MAILBOXES else [ self.IGNORE_MAILBOXES ]

        if not self.KEYCLOAK_SECRET_KEY:
            logging.error("!!! ERROR !!!")
            logging.error("Environment variables for mailcow or keycloak are not set! Please refere the documentation!")
            exit(1)

    def importFromOverrideFile(self):
        """
        Some variables for the mailcow sync can be overwritten by an override file:

        - DEFAULT_USER_QUOTA
        - GROUPS_TO_SYNC
        - DOMAIN_QUOTA
        - ENABLE_GAL
        - SYNC_INTERVAL
        - SOFT_DELETE_ENABLED
        - SOFT_DELETE_GRACE_PERIOD
        - SOFT_DELETE_MARK_COUNT
        - PERMANENT_DELETE_ENABLED
        - IGNORE_MAILBOXES
        """

        OVERRIDE_FILE = os.environ.get("MAILCOW_PATH", "/srv/docker/edulution-mail") + "/mail.override.config"

        if os.path.exists(OVERRIDE_FILE):
            logging.info("==========================================================")
            logging.info(f"OVERRIDE FILE FOUND: {OVERRIDE_FILE}")

            try:
                with open(OVERRIDE_FILE, "r") as f:
                    override_config = json.load(f)
            except Exception as e:
                logging.error(f"[!] Failed to load override file: {e}")
                return

            if "DEFAULT_USER_QUOTA" in override_config:
                logging.info(f"* OVERRIDE DEFAULT_USER_QUOTA: {self.DEFAULT_USER_QUOTA} with {override_config['DEFAULT_USER_QUOTA']}")
                self.DEFAULT_USER_QUOTA = int(override_config["DEFAULT_USER_QUOTA"])

            if "GROUPS_TO_SYNC" in override_config:
                new_groups = override_config["GROUPS_TO_SYNC"]
                new_groups = new_groups.split(",") if "," in new_groups else [ new_groups ]
                logging.info(f"* OVERRIDE GROUPS_TO_SYNC: {self.GROUPS_TO_SYNC} with {new_groups}")
                self.GROUPS_TO_SYNC = new_groups
            
            if "DOMAIN_QUOTA" in override_config:
                logging.info(f"* OVERRIDE DOMAIN_QUOTA: {self.DOMAIN_QUOTA} with {override_config['DOMAIN_QUOTA']}")
                self.DOMAIN_QUOTA = int(override_config["DOMAIN_QUOTA"])

            if "ENABLE_GAL" in override_config:
                logging.info(f"* OVERRIDE ENABLE_GAL: {self.ENABLE_GAL} with {override_config['ENABLE_GAL']}")
                self.ENABLE_GAL = int(override_config["ENABLE_GAL"])

            if "SYNC_INTERVAL" in override_config:
                logging.info(f"* OVERRIDE SYNC_INTERVAL: {self.SYNC_INTERVAL} with {override_config['SYNC_INTERVAL']}")
                self.SYNC_INTERVAL = int(override_config["SYNC_INTERVAL"])
            
            if "SOFT_DELETE_ENABLED" in override_config:
                logging.info(f"* OVERRIDE SOFT_DELETE_ENABLED: {self.SOFT_DELETE_ENABLED} with {override_config['SOFT_DELETE_ENABLED']}")
                self.SOFT_DELETE_ENABLED = int(override_config["SOFT_DELETE_ENABLED"])
            
            if "SOFT_DELETE_GRACE_PERIOD" in override_config:
                logging.info(f"* OVERRIDE SOFT_DELETE_GRACE_PERIOD: {self.SOFT_DELETE_GRACE_PERIOD} with {override_config['SOFT_DELETE_GRACE_PERIOD']}")
                self.SOFT_DELETE_GRACE_PERIOD = int(override_config["SOFT_DELETE_GRACE_PERIOD"])
            
            if "SOFT_DELETE_MARK_COUNT" in override_config:
                logging.info(f"* OVERRIDE SOFT_DELETE_MARK_COUNT: {self.SOFT_DELETE_MARK_COUNT} with {override_config['SOFT_DELETE_MARK_COUNT']}")
                self.SOFT_DELETE_MARK_COUNT = int(override_config["SOFT_DELETE_MARK_COUNT"])
            
            if "PERMANENT_DELETE_ENABLED" in override_config:
                logging.info(f"* OVERRIDE PERMANENT_DELETE_ENABLED: {self.PERMANENT_DELETE_ENABLED} with {override_config['PERMANENT_DELETE_ENABLED']}")
                self.PERMANENT_DELETE_ENABLED = int(override_config["PERMANENT_DELETE_ENABLED"])

            if "IGNORE_MAILBOXES" in override_config:
                new_ignore_mailboxes = override_config["IGNORE_MAILBOXES"]
                new_ignore_mailboxes = new_ignore_mailboxes.split(",") if "," in new_ignore_mailboxes else [ new_ignore_mailboxes ]
                logging.info(f"* OVERRIDE IGNORE_MAILBOXES: {self.IGNORE_MAILBOXES} with {new_ignore_mailboxes}")
                self.IGNORE_MAILBOXES = new_ignore_mailboxes

            logging.info("==========================================================")
            

            