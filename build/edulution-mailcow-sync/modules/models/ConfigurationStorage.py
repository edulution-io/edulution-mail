import os
import logging

class ConfigurationStorage:

    def importFromEnvironment(self):
        self.DEFAULT_USER_QUOTA = os.environ.get("DEFAULT_USER_QUOTA", 1000)

        self.GROUPS_TO_SYNC = os.environ.get("GROUPS_TO_SYNC", "role-schooladministrator,role-teacher,role-student")
        self.GROUPS_TO_SYNC = self.GROUPS_TO_SYNC.split(",") if "," in self.GROUPS_TO_SYNC else [ self.GROUPS_TO_SYNC ]

        self.DOMAIN_QUOTA = os.environ.get("DOMAIN_QUOTA", 10 * 1024)
        self.ENABLE_GAL = os.environ.get("ENABLE_GAL", 1)

        self.SYNC_INTERVAL = os.environ.get("SYNC_INTERVAL", 60)

        self.MAILCOW_API_TOKEN = os.environ.get("MAILCOW_API_TOKEN", False) # entrypoint.sh set this as environment variable
        self.KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "edu-mailcow-sync")
        self.KEYCLOAK_SECRET_KEY = os.environ.get("KEYCLOAK_SECRET_KEY", False)
        self.KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", "https://edulution-traefik/auth/")

        if not self.KEYCLOAK_SECRET_KEY:
            logging.error("!!! ERROR !!!")
            logging.error("Environment variables for mailcow or keycloak are not set! Please refere the documentation!")
            exit(1)