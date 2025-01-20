import logging

from keycloak import KeycloakAdmin, KeycloakOpenID

import urllib3
urllib3.disable_warnings()

class Keycloak:

    def __init__(self, server_url: str, client_id: str, client_secret_key: str):
        self.server_url = server_url
        self.client_id = client_id
        self.client_secret_key = client_secret_key

    def initKeycloakOpenID(self) -> None:
        self.keycloak_openid = KeycloakOpenID(
            server_url=self.server_url,
            client_id=self.client_id,
            client_secret_key=self.client_secret_key,
            realm_name="edulution",
            verify=False
        )

    def initKeycloakAdmin(self) -> None:
        self.keycloak_admin = KeycloakAdmin(
            server_url=self.server_url,
            client_id=self.client_id,
            client_secret_key=self.client_secret_key,
            realm_name="edulution",
            verify=False
        )

    def authenticate(self, username: str, password: str) -> bool:
        try:
            token = self.keycloak_openid.token(username, password)
            if "access_token" in token:
                return True
            return False
        except:
            return False
        
    def checkToken(self, token: str) -> str | bool:
        try:
            result = self.keycloak_openid.decode_token(token)
            return str(result.get("email"))
        except:
            return False

    def getUsers(self) -> list:
        logging.info("  * Downloading list of users from keycloak...")
        result = []
        users = self.keycloak_admin.get_users()
        for user in users:
            if "email" in user:
                result.append(user)
        return result
    
    def getGroups(self) -> list:
        logging.info("  * Downloading list of groups from keycloak...")
        result = []
        groups = self.keycloak_admin.get_groups()
        for group in groups:
            group_details = self.keycloak_admin.get_group(group["id"])
            if "attributes" in group_details and "mail" in group_details["attributes"] and "sophomorixMaillist" in group_details["attributes"]:
                if group_details["attributes"]["sophomorixMaillist"][0] == "TRUE":
                    group_details["members"] = self.getGroupMembers(group_details)
                    result.append(group_details)
        return result
    
    def getGroupMembers(self, group: dict) -> list:
        logging.info(f"    -> Loading members for group {group['name']}")
        return self.keycloak_admin.get_group_members(group['id'])
    
    def checkGroupMembershipForUser(self, userid: str, validGroups: list) -> bool:
        groups = self.keycloak_admin.get_user_groups(userid)
        for group in groups:
            if group["name"] in validGroups:
                return True
        return False