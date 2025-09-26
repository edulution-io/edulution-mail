import logging
import time

from keycloak import KeycloakAdmin, KeycloakOpenID

import urllib3
urllib3.disable_warnings()

class Keycloak:

    def __init__(self, server_url: str, client_id: str, client_secret_key: str):
        self.server_url = server_url
        self.client_id = client_id
        self.client_secret_key = client_secret_key
        self.page_size = 100  # Number of users per page

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
        """Get all users with pagination and retry logic"""
        logging.info("  * Downloading list of users from keycloak...")
        result = []
        first = 0  # Starting position
        max_retries = 6
        
        while True:
            users_batch = None
            
            # Retry logic for each batch
            for attempt in range(max_retries):
                try:
                    # Get users with pagination parameters
                    # first: starting position, max: number of users to retrieve
                    users_batch = self.keycloak_admin.get_users({
                        "first": first,
                        "max": self.page_size
                    })
                    
                    if users_batch is not None:
                        break
                        
                except Exception as e:
                    logging.warning(f"    -> Failed to get users batch starting at {first} (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        logging.warning(f"    -> Waiting {(attempt + 1) * 10} seconds before retrying...")
                        time.sleep((attempt + 1) * 10)
                    else:
                        logging.error(f"    -> Failed to retrieve users batch after {max_retries} attempts")
                        raise
            
            # Process the batch
            if users_batch:
                users_with_email = [user for user in users_batch if "email" in user]
                result.extend(users_with_email)
                logging.debug(f"    -> Retrieved batch: {len(users_batch)} users, {len(users_with_email)} with email (total so far: {len(result)})")
                
                # Check if we got fewer users than requested (indicates last page)
                if len(users_batch) < self.page_size:
                    break
                    
                # Move to next page
                first += self.page_size
            else:
                # No more users
                break
        
        logging.info(f"    -> Successfully retrieved {len(result)} users")
        return result
    
    def getGroups(self) -> list:
        """Get all groups with pagination and retry logic"""
        logging.info("  * Downloading list of groups from keycloak...")
        result = []
        first = 0  # Starting position
        max_retries = 6
        
        while True:
            groups_batch = None
            
            # Retry logic for each batch
            for attempt in range(max_retries):
                try:
                    # Get groups with pagination parameters
                    groups_batch = self.keycloak_admin.get_groups({
                        "first": first,
                        "max": self.page_size
                    })
                    
                    if groups_batch is not None:
                        break
                        
                except Exception as e:
                    logging.warning(f"    -> Failed to get groups batch starting at {first} (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        logging.warning(f"    -> Waiting {(attempt + 1) * 10} seconds before retrying...")
                        time.sleep((attempt + 1) * 10)
                    else:
                        logging.error(f"    -> Failed to retrieve groups batch after {max_retries} attempts")
                        raise
            
            # Process the batch
            if groups_batch:
                for group in groups_batch:
                    try:
                        group_details = self.keycloak_admin.get_group(group["id"])
                        if "attributes" in group_details and "mail" in group_details["attributes"] and "sophomorixMaillist" in group_details["attributes"]:
                            if group_details["attributes"]["sophomorixMaillist"][0] == "TRUE":
                                group_details["members"] = self.getGroupMembers(group_details)
                                result.append(group_details)
                    except Exception as e:
                        logging.warning(f"    -> Failed to get details for group {group.get('name', 'unknown')}: {e}")
                        raise
                
                logging.debug(f"    -> Retrieved batch: {len(groups_batch)} groups (mailing lists found: {len(result)})")
                
                # Check if we got fewer groups than requested (indicates last page)
                if len(groups_batch) < self.page_size:
                    break
                    
                # Move to next page
                first += self.page_size
            else:
                # No more groups
                break
        
        logging.info(f"    -> Successfully retrieved {len(result)} groups")
        return result
    
    def getGroupMembers(self, group: dict) -> list:
        """Get group members with pagination and retry logic"""
        logging.info(f"    -> Loading members for group {group['name']}")
        members = []
        first = 0
        max_retries = 6
        
        while True:
            members_batch = None
            
            for attempt in range(max_retries):
                try:
                    # Get members with pagination
                    members_batch = self.keycloak_admin.get_group_members(
                        group_id=group['id'],
                        query={
                            "first": first,
                            "max": self.page_size
                        }
                    )
                    
                    if members_batch is not None:
                        break
                        
                except Exception as e:
                    logging.warning(f"       -> Failed to get members batch for group {group['name']} (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        logging.warning(f"       -> Waiting {(attempt + 1) * 10} seconds before retrying...")
                        time.sleep((attempt + 1) * 10)
                    else:
                        logging.error(f"       -> Failed to retrieve members after {max_retries} attempts")
                        raise
            
            if members_batch:
                members.extend(members_batch)
                
                # Check if we got fewer members than requested
                if len(members_batch) < self.page_size:
                    break
                    
                first += self.page_size
            else:
                break
        
        logging.debug(f"       -> Retrieved {len(members)} members for group {group['name']}")
        return members
    
    def checkGroupMembershipForUser(self, userid: str, validGroups: list) -> bool:
        try:
            groups = self.keycloak_admin.get_user_groups(userid)
            for group in groups:
                if group["name"] in validGroups:
                    return True
            return False
        except:
            return False