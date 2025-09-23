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
        self.deactivationTracker = DeactivationTracker(storage_path=self._config.MAILCOW_PATH + "/data")

        self.keycloak.initKeycloakAdmin()

    def start(self):
        logging.info("===== Edulution-Mailcow-Sync =====")
        while True:
            if not self._sync():
                logging.error("!!! Sync failed, see above errors !!!")
                exit(1)
            else:
                logging.info("=== Sync finished successfully ===")
                logging.info("")
                logging.info(f"=== Waiting {self._config.SYNC_INTERVAL} seconds before next sync ===")
                logging.info("")
                time.sleep(self._config.SYNC_INTERVAL)

    def _sync(self) -> bool:
        logging.info("=== Starting Edulution-Mailcow-Sync ===")

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
            groups = self.keycloak.getGroups()
        except Exception as e:
            logging.error(f"Failed to load data from keycloak: {e}")
            return False

        logging.info("* 2. Calculation deltas between keycloak and mailcow")

        for user in users:
            mail = user["email"]
            maildomain = mail.split("@")[-1]

            if self.keycloak.checkGroupMembershipForUser(user["id"], self._config.GROUPS_TO_SYNC):
                if not self._addDomain(maildomain, domainList):
                    continue
                
                self._addMailbox(user, mailboxList)
                self._addAliasesFromProxyAddresses(user, mail, aliasList)
        
        for group in groups:
            mail = group["attributes"]["mail"][0]
            maildomain = mail.split("@")[-1]
            
            membermails = []
            for member in group["members"]:
                if self.keycloak.checkGroupMembershipForUser(member["id"], self._config.GROUPS_TO_SYNC):
                    if "email" not in member:
                        logging.error(f"    -> Member {member['id']} ({member.get('username', 'n/a')}) has not email attribute!")
                        continue
                    membermails.append(member["email"])

            if not self._addDomain(maildomain, domainList):
                continue

            if len(membermails) == 0:
                logging.warning(f"    -> Mailinglist {mail} has no members, skipping!")
                continue

            self._addAlias(mail, membermails, aliasList)
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
        self._processDeactivationsAndDeletions(domainList, mailboxList, aliasList, filterList)

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
        
        # Process immediate deletions for aliases and filters
        for alias in aliasList.disableQueue():
            alias_id = alias.get('id') or alias.get('address')
            if alias_id:
                self.mailcow.deleteAlias(alias_id)
                logging.info(f"  * Deleted alias {alias_id}")
        
        for filter in filterList.disableQueue():
            filter_id = filter.get('id')
            if filter_id:
                self.mailcow.deleteFilter(filter_id)
                logging.info(f"  * Deleted filter {filter_id}")
        
        if soft_delete_enabled:
            # Process deactivations for mailboxes
            for mailbox in mailboxList.disableQueue():
                username = mailbox.get('username')
                if username:
                    # Check if already marked for deactivation
                    if not self.deactivationTracker.isMarkedForDeactivation("mailboxes", username):
                        # First deactivation: disable and mark with deletion date
                        self.deactivationTracker.markForDeactivation("mailboxes", username, grace_period)
                        description = self.deactivationTracker.formatDescriptionWithDeletionDate(
                            mailbox.get('name', ''), "mailboxes", username
                        )
                        # Extract local_part and domain for the update
                        local_part, domain = username.split('@')
                        self.mailcow.updateMailbox({
                            "attr": {
                                "active": 0,
                                "name": description,
                                "local_part": local_part,
                                "domain": domain
                            },
                            "items": [username]
                        })
                        logging.info(f"  * Deactivated mailbox {username}")
            
            # Process deactivations for domains
            for domain in domainList.disableQueue():
                domain_name = domain.get('domain_name')
                if domain_name:
                    # Check if already marked for deactivation
                    if not self.deactivationTracker.isMarkedForDeactivation("domains", domain_name):
                        # First deactivation: disable and mark with deletion date
                        self.deactivationTracker.markForDeactivation("domains", domain_name, grace_period)
                        description = self.deactivationTracker.formatDescriptionWithDeletionDate(
                            domain.get('description', ''), "domains", domain_name
                        )
                        self.mailcow.updateDomain({
                            "attr": {
                                "active": 0,
                                "description": description,
                                "domain": domain_name
                            },
                            "items": [domain_name]
                        })
                        logging.info(f"  * Deactivated domain {domain_name}")
            
            # Check for items to permanently delete
            for mailbox_id in self.deactivationTracker.getItemsToDelete("mailboxes"):
                if self.mailcow.deleteMailbox(mailbox_id):
                    self.deactivationTracker.removeDeleted("mailboxes", mailbox_id)
                    logging.info(f"  * Permanently deleted mailbox {mailbox_id}")
            
            for domain_id in self.deactivationTracker.getItemsToDelete("domains"):
                if self.mailcow.deleteDomain(domain_id):
                    self.deactivationTracker.removeDeleted("domains", domain_id)
                    logging.info(f"  * Permanently deleted domain {domain_id}")
            
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
            # Soft delete disabled - delete immediately
            for mailbox in mailboxList.disableQueue():
                username = mailbox.get('username')
                if username:
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

    def _addAlias(self, alias: str, goto: str | list, aliasList: AliasListStorage) -> bool:
        goto_targets = ",".join(goto) if isinstance(goto, list) else goto
        return aliasList.addElement({
            "address": alias,
            "goto": goto_targets,
            "active": 1,
            "sogo_visible": 1
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
