#!/usr/bin/env python3

import random
import string
import time
import logging
import os

from modules import Keycloak, Mailcow, DomainListStorage, MailboxListStorage, ConfigurationStorage

logging.basicConfig(format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)

class EdulutionMailcowSync:

    def __init__(self):
        self._config = self._readConfig()

        self.keycloak = Keycloak()
        self.mailcow = Mailcow()

    def start(self):
        logging.info("===== Edulution-Mailcow-Sync =====")
        while True:
            if not self._sync():
                logging.error("!!! Sync failed, see above errors !!!")
                exit(1)
            else:
                logging.info("=== Sync finished successfully ===")
                time.sleep(60)

    def _sync(self) -> bool:
        logging.info("=== Starting Edulution-Mailcow-Sync ===")

        domainList = DomainListStorage()
        mailboxList = MailboxListStorage()

        logging.info("* 1. Loading data from mailcow and keycloak")

        domainList.loadRawData(self.mailcow.getDomains())
        mailboxList.loadRawData(self.mailcow.getMailboxes())
        users = self.keycloak.getUsers()

        logging.info("* 2. Calculation deltas between keycloak and mailcow")

        for user in users:
            mail = user["email"]
            maildomain = mail.split("@")[-1]

            if not self._addDomain(maildomain, domainList):
                continue

            self._addMailbox(user, mailboxList)
        
        logging.info("  * " + domainList.getQueueCountsString("domain(s)"))
        logging.info("  * " + mailboxList.getQueueCountsString("mailbox(es)"))

        return True
    
    def _readConfig(self) -> ConfigurationStorage:
        config = ConfigurationStorage()
        config.importFromEnvironment()
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
        #active = 0 if user["sophomorixStatus"] in ["L", "D", "R", "K", "F"] else 1
        return mailboxList.addElement({
            "domain": domain,
            "local_part": localPart,
            "active": 1, #active,
            "quota": 1000, #user["sophomorixMailQuotaCalculated"],
            "password": password,
            "password2": password,
            "name": user["firstName"] + " " + user["lastName"]
        }, mail)

if __name__ == "__main__":
    try:
        syncer = EdulutionMailcowSync()
        syncer.start()
    except KeyboardInterrupt:
        pass