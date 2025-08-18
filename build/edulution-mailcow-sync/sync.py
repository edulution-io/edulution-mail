#!/usr/bin/env python3

import random
import string
import time
import logging
import os

from modules import Keycloak, Mailcow, DomainListStorage, MailboxListStorage, ConfigurationStorage, AliasListStorage, FilterListStorage

logging.basicConfig(format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)

class EdulutionMailcowSync:

    def __init__(self):
        self._config = self._readConfig()

        self.keycloak = Keycloak(server_url=self._config.KEYCLOAK_SERVER_URL, client_id=self._config.KEYCLOAK_CLIENT_ID, client_secret_key=self._config.KEYCLOAK_SECRET_KEY)
        self.mailcow = Mailcow(apiToken=self._config.MAILCOW_API_TOKEN)

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
                    if "email"  not in member:
                        logging.error(f"    -> Member {member['id']} ({member.get('username', 'n/a')}) has not email attribute!")
                        continue
                    membermails.append(member["email"])

            if not self._addDomain(maildomain, domainList):
                continue

            # self._addMailbox({
            #     "email": mail,
            #     "firstName": group["name"],
            #     "lastName": "(list)",
            #     "attributes": {
            #         "sophomorixMailQuotaCalculated": [ 1 ],
            #         "sophomorixStatus": "G"
            #     }
            # }, mailboxList)

            self._addAlias(mail, membermails, aliasList)
            self._addAliasesFromProxyAddresses(group, mail, aliasList)

            # self._addListFilter(mail, membermails, filterList)

        if domainList.queuesAreEmpty() and mailboxList.queuesAreEmpty() and aliasList.queuesAreEmpty() and filterList.queuesAreEmpty():
            logging.info("  * Everything is up-to-date!")
            return True
        else:
            logging.info("  * " + domainList.getQueueCountsString("domain(s)"))
            logging.info("  * " + mailboxList.getQueueCountsString("mailbox(es)"))
            logging.info("  * " + aliasList.getQueueCountsString("alias(es)"))
            logging.info("  * " + filterList.getQueueCountsString("filter(s)"))

        logging.info("* 3. Syncing deltas to mailcow")

        # 1. Delete items

        # self.mailcow.killElementsOfType(
        #     "filter", mailcowFilters.killQueue())
        # self.mailcow.killElementsOfType(
        #     "alias", mailcowAliases.killQueue())
        # self.mailcow.killElementsOfType(
        #     "mailbox", mailcowMailboxes.killQueue())
        # self.mailcow.killElementsOfType(
        #     "domain", mailcowDomains.killQueue())

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
