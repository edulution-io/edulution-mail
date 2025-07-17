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

        self.MAILCOW_API_TOKEN = os.environ.get("MAILCOW_API_TOKEN", False) # entrypoint.sh set this as environment variable
        self.KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "edu-mailcow-sync")
        self.KEYCLOAK_SECRET_KEY = os.environ.get("KEYCLOAK_SECRET_KEY", False)
        self.KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", "https://edulution-traefik/auth/")

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
        """

        OVERRIDE_FILE = os.environ.get("MAILCOW_PATH", "/srv/docker/edulution-mail") + "/mail.override.config"

        if os.path.exists(OVERRIDE_FILE):
            logging.info("==========================================================")
            logging.info(f"OVERRIDE FILE FOUND: {OVERRIDE_FILE}")

            with open(OVERRIDE_FILE, "r") as f:
                override_config = json.load(f)

            if "DEFAULT_USER_QUOTA" in override_config:
                logging.info(f"* OVERRIDE DEFAULT_USER_QUOTA: {self.DEFAULT_USER_QUOTA} with {override_config['DEFAULT_USER_QUOTA']}")
                self.DEFAULT_USER_QUOTA = int(override_config["DEFAULT_USER_QUOTA"])

            if "GROUPS_TO_SYNC" in override_config:
                logging.info(f"* OVERRIDE GROUPS_TO_SYNC: {self.GROUPS_TO_SYNC} with {override_config['GROUPS_TO_SYNC']}")
                self.GROUPS_TO_SYNC = override_config["GROUPS_TO_SYNC"]
                self.GROUPS_TO_SYNC = self.GROUPS_TO_SYNC.split(",") if "," in self.GROUPS_TO_SYNC else [ self.GROUPS_TO_SYNC ]
            
            if "DOMAIN_QUOTA" in override_config:
                logging.info(f"* OVERRIDE DOMAIN_QUOTA: {self.DOMAIN_QUOTA} with {override_config['DOMAIN_QUOTA']}")
                self.DOMAIN_QUOTA = int(override_config["DOMAIN_QUOTA"])

            if "ENABLE_GAL" in override_config:
                logging.info(f"* OVERRIDE ENABLE_GAL: {self.ENABLE_GAL} with {override_config['ENABLE_GAL']}")
                self.ENABLE_GAL = int(override_config["ENABLE_GAL"])

            if "SYNC_INTERVAL" in override_config:
                logging.info(f"* OVERRIDE SYNC_INTERVAL: {self.SYNC_INTERVAL} with {override_config['SYNC_INTERVAL']}")
                self.SYNC_INTERVAL = int(override_config["SYNC_INTERVAL"])

            logging.info("==========================================================")
            

            