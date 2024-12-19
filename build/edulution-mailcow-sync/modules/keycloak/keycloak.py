import logging

from keycloak import KeycloakAdmin

import urllib3
urllib3.disable_warnings()

class Keycloak:

    def __init__(self):
        self.keycloak_admin = KeycloakAdmin(
            server_url="https://demo.edulution.io/auth/",
            client_id="edu-api",
            client_secret_key="BAUNWYgAqdHf9jrNkiniByJBAfhWLJxd",
            realm_name="edulution",
            verify=False
        )

    def getUsers(self) -> list:
        logging.info("  * Downloading list of users from keycloak...")
        result = []
        users = self.keycloak_admin.get_users({"max": 100})
        for user in users:
            if "email" in user:
                result.append(user)
        return result
    
    def checkGroupMembershipForUser(self, userid: str, validGroups: list) -> bool:
        groups = self.keycloak_admin.get_user_groups(userid)
        for group in groups:
            if group["name"] in validGroups:
                return True
        return False