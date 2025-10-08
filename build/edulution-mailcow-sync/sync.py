#!/usr/bin/env python3

import random
import string
import time
import logging
import os

from modules import Keycloak, Mailcow, DomainListStorage, MailboxListStorage, ConfigurationStorage, AliasListStorage, FilterListStorage, DeactivationTracker

logging.basicConfig(format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)

class EdulutionMailcowSync:

    def __init__(self):
        self._config = self._readConfig()

        self.keycloak = Keycloak(server_url=self._config.KEYCLOAK_SERVER_URL, client_id=self._config.KEYCLOAK_CLIENT_ID, client_secret_key=self._config.KEYCLOAK_SECRET_KEY)
        self.mailcow = Mailcow(apiToken=self._config.MAILCOW_API_TOKEN)
        self.deactivationTracker = DeactivationTracker(
            storage_path=self._config.MAILCOW_PATH + "/data",
            mark_count_threshold=self._config.SOFT_DELETE_MARK_COUNT
        )

        self.keycloak.initKeycloakAdmin()

    def start(self):
        logging.info("===== Edulution-Mailcow-Sync =====")
        while True:
            try:
                if not self._sync():
                    logging.error("!!! Sync failed, see above errors !!!")
                    # Don't exit on sync failure, wait and retry
                    logging.info(f"=== Retrying in {self._config.RETRY_INTERVAL} seconds ===")
                    time.sleep(self._config.RETRY_INTERVAL)
                else:
                    logging.info("=== Sync finished successfully ===")
                    logging.info("")
                    logging.info(f"=== Waiting {self._config.SYNC_INTERVAL} seconds before next sync ===")
                    logging.info("")
                    time.sleep(self._config.SYNC_INTERVAL)
            except KeyboardInterrupt:
                logging.info("Sync interrupted by user")
                break
            except Exception as e:
                logging.exception(f"Unexpected error during sync: {e}")
                logging.info(f"=== Retrying in {self._config.RETRY_INTERVAL} seconds ===")
                time.sleep(self._config.RETRY_INTERVAL)

    def _sync(self) -> bool:
        logging.info("=== Starting Edulution-Mailcow-Sync ===")
        logging.info("")

        if os.path.exists(self._config.MAILCOW_PATH + "/DISABLE_SYNC"):
            logging.info("")
            logging.info("========================================================")
            logging.info("* Sync disabled by DISABLE_SYNC file in mailcow path!")
            logging.info("========================================================")
            logging.info("")
            return True

        domainList = DomainListStorage()
        mailboxList = MailboxListStorage(domainList)
        aliasList = AliasListStorage(domainList)
        filterList = FilterListStorage(domainList)

        logging.info("* 1. Loading data from mailcow and keycloak")

        # Load Mailcow data with retry logic
        try:
            domainList.loadRawData(self.mailcow.getDomains())
            mailboxList.loadRawData(self.mailcow.getMailboxes())
            aliasList.loadRawData(self.mailcow.getAliases())
            filterList.loadRawData(self.mailcow.getFilters())
        except Exception as e:
            logging.error(f"Failed to load data from mailcow: {e}")
            return False
        
        try:
            users = self.keycloak.getUsers()                    
        except Exception as e:
            logging.exception(f"Failed to load user from keycloak: {e}")
            return False  # Users are essential, fail completely
        
        try:
            groups = self.keycloak.getGroups()
        except Exception as e:
            logging.exception(f"Failed to load groups from keycloak: {e}")
            return False  # Groups are essential, fail completely

        logging.info("* 2. Calculation deltas between keycloak and mailcow")

        for user in users:
            if "email" not in user:
                continue
            
            mail = user["email"]
            
            # Skip ignored mailboxes
            if mail in self._config.IGNORE_MAILBOXES:
                logging.debug(f"  * Skipping ignored mailbox: {mail}")
                continue
            
            maildomain = mail.split("@")[-1]

            if self.keycloak.checkGroupMembershipForUser(user["id"], self._config.GROUPS_TO_SYNC):
                if not self._addDomain(maildomain, domainList):
                    continue
                
                self._addMailbox(user, mailboxList)
                self._addAliasesFromProxyAddresses(user, mail, aliasList)
        
        for group in groups:
            mail = group["attributes"]["mail"][0]
            maildomain = mail.split("@")[-1]

            description = mail
            if "description" in group["attributes"]:
                description = group["attributes"]["description"][0]
            
            membermails = []
            for member in group["members"]:
                if "id" not in member:
                    logging.warning(f"    -> Member {member} without ID in group {mail}, skipping!")
                    continue
                if self.keycloak.checkGroupMembershipForUser(member["id"], self._config.GROUPS_TO_SYNC):
                    if "email" not in member:
                        logging.error(f"    -> Member {member['id']} ({member.get('username', 'n/a')}) has not email attribute!")
                        continue
                    # Skip ignored mailboxes from group membership
                    if member["email"] not in self._config.IGNORE_MAILBOXES:
                        membermails.append(member["email"])

            if not self._addDomain(maildomain, domainList):
                continue

            if len(membermails) == 0:
                logging.debug(f"    -> Mailinglist {mail} has no members, skipping!")
                continue

            self._addAlias(mail, membermails, aliasList, sogo_visible = 0, alias_description = description)
            self._addAliasesFromProxyAddresses(group, mail, aliasList)

        if domainList.queuesAreEmpty() and mailboxList.queuesAreEmpty() and aliasList.queuesAreEmpty() and filterList.queuesAreEmpty():
            logging.info("  * Everything is up-to-date!")
            return True
        else:
            logging.info("  * " + domainList.getQueueCountsString("domain(s)"))
            logging.info("  * " + mailboxList.getQueueCountsString("mailbox(es)"))
            logging.info("  * " + aliasList.getQueueCountsString("alias(es)"))
            logging.info("  * " + filterList.getQueueCountsString("filter(s)"))

        logging.info("* 3. Syncing deltas to mailcow")

        # 1. Process deactivations and deletions
        #self._processDeactivationsAndDeletions(domainList, mailboxList, aliasList, filterList)

        # 2. Domain(s) add and update

        for domain in domainList.addQueue():
            self.mailcow.addDomain(domain)

        for domain in domainList.updateQueue():
            self.mailcow.updateDomain(domain)

        # 3. Mailbox(es) add and update

        for mailbox in mailboxList.addQueue():
            self.mailcow.addMailbox(mailbox)

        for mailbox in mailboxList.updateQueue():
            self.mailcow.updateMailbox(mailbox)

        # 4. Alias(es) add and update

        for alias in aliasList.addQueue():
            self.mailcow.addAlias(alias)

        for alias in aliasList.updateQueue():
            self.mailcow.updateAlias(alias)

        # 5. Filter(s) add and update

        for filter in filterList.addQueue():
            self.mailcow.addFilter(filter)

        for filter in filterList.updateQueue():
            self.mailcow.updateFilter(filter)

        return True
    
    def _readConfig(self) -> ConfigurationStorage:
        config = ConfigurationStorage()
        config.load()
        return config

    def _addDomain(self, domainName: str, domainList: DomainListStorage) -> bool:
        return domainList.addElement({
            "domain": domainName,
            "defquota": 1,
            "maxquota": self._config.DOMAIN_QUOTA,
            "quota": self._config.DOMAIN_QUOTA,
            "description": DomainListStorage.validityCheckDescription,
            "active": 1,
            "restart_sogo": 1,
            "mailboxes": 10000,
            "aliases": 10000,
            "gal": self._config.ENABLE_GAL
        }, domainName)
    
    def _processDeactivationsAndDeletions(self, domainList: DomainListStorage, mailboxList: MailboxListStorage, aliasList: AliasListStorage, filterList: FilterListStorage):
        grace_period = self._config.SOFT_DELETE_GRACE_PERIOD
        soft_delete_enabled = self._config.SOFT_DELETE_ENABLED
        
        # Process deletions for filters (always immediate)
        for filter in filterList.disableQueue():
            filter_id = filter.get('id')
            if filter_id:
                self.mailcow.deleteFilter(filter_id)
                logging.info(f"  * Deleted filter {filter_id}")
        
        if soft_delete_enabled:
            # Process deactivations for aliases with mark counting
            for alias in aliasList.disableQueue():
                alias_id = alias.get('id') or alias.get('address')
                if alias_id:
                    # Mark for deactivation (will only delete after threshold marks)
                    if self.deactivationTracker.markForDeactivation("aliases", alias_id, grace_period):
                        # Threshold reached - actually delete
                        self.mailcow.deleteAlias(alias_id)
                        logging.info(f"  * Deleted alias {alias_id} after {self._config.SOFT_DELETE_MARK_COUNT} marks")
            
            # Process deactivations for mailboxes - with missing count check
            for mailbox in mailboxList.disableQueue():
                # Get username from mailbox data
                username = None
                if 'username' in mailbox:
                    username = mailbox['username']
                elif 'local_part' in mailbox and 'domain' in mailbox:
                    username = mailbox['local_part'] + '@' + mailbox['domain']
                
                if username:
                    # Skip ignored mailboxes
                    if username in self._config.IGNORE_MAILBOXES:
                        logging.debug(f"  * Skipping ignored mailbox from deletion: {username}")
                        continue
                    
                    # Mark for deactivation (will only deactivate after threshold marks)
                    if self.deactivationTracker.markForDeactivation("mailboxes", username, grace_period):
                        # Third mark reached - actually deactivate
                        # Extract local_part and domain for the update
                        local_part, domain = username.split('@')
                        self.mailcow.updateMailbox({
                            "attr": {
                                "active": 0,
                                "local_part": local_part,
                                "domain": domain
                            },
                            "items": [username]
                        })
                        logging.info(f"  * Deactivated mailbox {username} after {self._config.SOFT_DELETE_MARK_COUNT} marks")
            
            # Process deactivations for domains
            for domain in domainList.disableQueue():
                domain_name = domain.get('domain_name')
                if domain_name:
                    # Mark for deactivation (will only deactivate after 3 marks)
                    if self.deactivationTracker.markForDeactivation("domains", domain_name, grace_period):
                        # Third mark reached - actually deactivate
                        self.mailcow.updateDomain({
                            "attr": {
                                "active": 0,
                                "domain": domain_name
                            },
                            "items": [domain_name]
                        })
                        logging.info(f"  * Deactivated domain {domain_name} after {self._config.SOFT_DELETE_MARK_COUNT} marks")
            
            # Check for items to permanently delete (if enabled)
            if self._config.PERMANENT_DELETE_ENABLED:
                for mailbox_id in self.deactivationTracker.getItemsToDelete("mailboxes"):
                    # Skip ignored mailboxes from permanent deletion
                    if mailbox_id in self._config.IGNORE_MAILBOXES:
                        continue
                    if self.mailcow.deleteMailbox(mailbox_id):
                        self.deactivationTracker.removeDeleted("mailboxes", mailbox_id)
                        logging.info(f"  * Permanently deleted mailbox {mailbox_id}")
                
                for domain_id in self.deactivationTracker.getItemsToDelete("domains"):
                    if self.mailcow.deleteDomain(domain_id):
                        self.deactivationTracker.removeDeleted("domains", domain_id)
                        logging.info(f"  * Permanently deleted domain {domain_id}")
                
                # Also check for aliases to permanently delete
                for alias_id in self.deactivationTracker.getItemsToDelete("aliases"):
                    self.deactivationTracker.removeDeleted("aliases", alias_id)
                    # Aliases are already deleted when deactivated, just clean up tracker
            
            # Reactivate items that reappeared in Keycloak
            for mailbox in mailboxList.addQueue() + mailboxList.updateQueue():
                username = mailbox.get('local_part') + '@' + mailbox.get('domain') if 'local_part' in mailbox else mailbox.get('attr', {}).get('local_part') + '@' + mailbox.get('attr', {}).get('domain')
                if username and self.deactivationTracker.isMarkedForDeactivation("mailboxes", username):
                    self.deactivationTracker.reactivate("mailboxes", username)
                    logging.info(f"  * Reactivated mailbox {username} (found in Keycloak again)")
            
            for domain in domainList.addQueue() + domainList.updateQueue():
                domain_name = domain.get('domain') if 'domain' in domain else domain.get('attr', {}).get('domain')
                if domain_name and self.deactivationTracker.isMarkedForDeactivation("domains", domain_name):
                    self.deactivationTracker.reactivate("domains", domain_name)
                    logging.info(f"  * Reactivated domain {domain_name} (found in Keycloak again)")
        else:
            # Soft delete disabled - immediate deletion
            for alias in aliasList.disableQueue():
                alias_id = alias.get('id') or alias.get('address')
                if alias_id:
                    self.mailcow.deleteAlias(alias_id)
                    logging.info(f"  * Deleted alias {alias_id}")
            
            for mailbox in mailboxList.disableQueue():
                # Get username from mailbox data
                username = None
                if 'username' in mailbox:
                    username = mailbox['username']
                elif 'local_part' in mailbox and 'domain' in mailbox:
                    username = mailbox['local_part'] + '@' + mailbox['domain']
                
                if username:
                    # Skip ignored mailboxes
                    if username in self._config.IGNORE_MAILBOXES:
                        logging.debug(f"  * Skipping ignored mailbox from deletion: {username}")
                        continue
                    self.mailcow.deleteMailbox(username)
                    logging.info(f"  * Deleted mailbox {username}")
            
            for domain in domainList.disableQueue():
                domain_name = domain.get('domain_name')
                if domain_name:
                    self.mailcow.deleteDomain(domain_name)
                    logging.info(f"  * Deleted domain {domain_name}")
    
    def _addMailbox(self, user: dict, mailboxList: MailboxListStorage) -> bool:
        mail = user["email"]
        domain = mail.split("@")[-1]
        localPart = mail.split("@")[0]
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        quota = self._config.DEFAULT_USER_QUOTA
        if "attributes" in user:
            if "sophomorixMailQuotaCalculated" in user["attributes"]:
                quota = user["attributes"]["sophomorixMailQuotaCalculated"][0] 
        active = 0 if user["attributes"]["sophomorixStatus"] in ["L", "D", "R", "K", "F"] else 1
        return mailboxList.addElement({
            "domain": domain,
            "local_part": localPart,
            "active": active,
            "quota": quota,
            "password": password,
            "password2": password,
            "name": user["firstName"] + " " + user["lastName"]
        }, mail)
    
    def _addAliasesFromProxyAddresses(self, user: dict, mail: str, mailcowAliases: str | list) -> bool:
        aliases = []

        if "proxyAddresses" in user["attributes"]:
            if isinstance(user["attributes"]["proxyAddresses"], list):
                aliases = user["attributes"]["proxyAddresses"]
            else:
                aliases = [user["attributes"]["proxyAddresses"]]

        if len(aliases) > 0:
            for alias in aliases:
                self._addAlias(alias, mail, mailcowAliases)

        return True

    def _addAlias(self, alias: str, goto: str | list, aliasList: AliasListStorage, sogo_visible: int = 1, alias_description: str = "") -> bool:
        goto_targets = ",".join(goto) if isinstance(goto, list) else goto
        return aliasList.addElement({
            "address": alias,
            "goto": goto_targets,
            "active": 1,
            "sogo_visible": sogo_visible,
            "private_comment": alias_description
        }, alias)

    # def _addListFilter(self, listAddress: str, memberAddresses: list, filterList: FilterListStorage):
    #     scriptData = "### Auto-generated mailinglist filter by linuxmuster ###\r\n\r\n"
    #     scriptData += "require \"copy\";\r\n\r\n"
    #     for memberAddress in memberAddresses:
    #         scriptData += f"redirect :copy \"{memberAddress}\";\r\n"
    #     scriptData += "\r\ndiscard;stop;"
    #     return filterList.addElement({
    #         'active': 1,
    #         'username': listAddress,
    #         'filter_type': 'prefilter',
    #         'script_data': scriptData,
    #         'script_desc': f"Auto-generated mailinglist filter for {listAddress}"
    #     }, listAddress)

if __name__ == "__main__":
    try:
        syncer = EdulutionMailcowSync()
        syncer.start()
    except KeyboardInterrupt:
        pass
