import requests
import logging

class Mailcow:

    def __init__(self, apiToken: str):
        self._url = "nginx"
        self._apiToken = apiToken

        requests.packages.urllib3.util.connection.HAS_IPV6 = False

    def _getRequest(self, url: str) -> dict:
        requestUrl = "https://" + self._url + "/" + url
        headers = {'X-API-Key': self._apiToken, 'Content-type': 'application/json'}

        req = requests.get(requestUrl, headers=headers, verify=False)
        if req.status_code != 200:
            logging.error("  * ERROR! Could not connect to mailcow api!")
            logging.error("  * " + req.text)
            return False
        
        return req.json()
    
    def _postRequest(self, url: str, data: dict) -> dict:
        requestUrl = "https://" + self._url + "/" + url
        headers = {'X-API-Key': self._apiToken, 'Content-type': 'application/json'}

        req = requests.post(requestUrl, json=data, headers=headers, verify=False)
        if req.status_code != 200:
            logging.error("  * ERROR! Could not connect to mailcow api!")
            logging.error("  * " + req.text)
            return False
        
        res = req.json()
        if isinstance(res, list):
            res = res[0]
        
        if res["type"] != "success":
            logging.error("  * ERROR! API Request failed!")
            logging.error("  * Message: " + str(res["msg"]))
            return False

        return True
    
    # ========================================================================================

    def getDomains(self) -> list:
        logging.info("  * Downloading list of domains from mailcow...")
        requestQuery = "/api/v1/get/domain/all"
        return self._getRequest(requestQuery)
    
    def addDomain(self, domain: dict) -> bool:
        logging.info(f"  * Adding domain {domain['domain']} to mailcow...")
        requestQuery = "/api/v1/add/domain"
        return self._postRequest(requestQuery, domain)
    
    def updateDomain(self, domain: dict) -> bool:
        logging.info(f"  * Edit domain {domain['attr']['domain']} on mailcow...")
        requestQuery = "/api/v1/edit/domain"
        return self._postRequest(requestQuery, domain)
    
    # ========================================================================================

    def getMailboxes(self) -> list:
        logging.info("  * Downloading list of mailboxes from mailcow...")
        requestQuery = "/api/v1/get/mailbox/all"
        return self._getRequest(requestQuery)
    
    def addMailbox(self, mailbox: dict) -> bool:
        logging.info(f"  * Adding mailbox {mailbox['local_part']}@{mailbox['domain']} to mailcow...")
        requestQuery = "/api/v1/add/mailbox"
        return self._postRequest(requestQuery, mailbox)

    def updateMailbox(self, mailbox: dict) -> bool:
        logging.info(f"  * Edit mailbox {mailbox['attr']['local_part']}@{mailbox['attr']['domain']} on mailcow...")
        requestQuery = "/api/v1/edit/mailbox"
        return self._postRequest(requestQuery, mailbox)
    
    # ========================================================================================

    def getAliases(self) -> list:
        logging.info("  * Downloading list of aliases from mailcow...")
        requestQuery = "/api/v1/get/alias/all"
        return self._getRequest(requestQuery)
    
    def addAlias(self, alias: dict) -> bool:
        logging.info(f"  * Adding alias {alias['address']} to mailcow...")
        requestQuery = "/api/v1/add/alias"
        return self._postRequest(requestQuery, alias)

    def updateAlias(self, alias: dict) -> bool:
        logging.info(f"  * Edit alias {alias['attr']['address']} on mailcow...")
        requestQuery = "/api/v1/edit/alias"
        return self._postRequest(requestQuery, alias)
    
    # ========================================================================================

    def getFilters(self) -> list:
        logging.info("  * Downloading list of filters from mailcow...")
        requestQuery = "/api/v1/get/filters/all"
        return self._getRequest(requestQuery)
    
    def addFilter(self, filter: dict) -> bool:
        logging.info(f"  * Adding filters {filter['username']} to mailcow...")
        requestQuery = "/api/v1/add/filter"
        return self._postRequest(requestQuery, filter)

    def updateFilter(self, filter: dict) -> bool:
        logging.info(f"  * Edit filters {filter['attr']['username']} on mailcow...")
        requestQuery = "/api/v1/edit/filter"
        return self._postRequest(requestQuery, filter)
    
    # ========================================================================================
    # Delete functions for cleanup
    
    def deleteDomain(self, domain: str) -> bool:
        logging.info(f"  * Deleting domain {domain} from mailcow...")
        requestQuery = "/api/v1/delete/domain"
        return self._postRequest(requestQuery, [domain])
    
    def deleteMailbox(self, mailbox: str) -> bool:
        logging.info(f"  * Deleting mailbox {mailbox} from mailcow...")
        requestQuery = "/api/v1/delete/mailbox"
        return self._postRequest(requestQuery, [mailbox])
    
    def deleteAlias(self, alias_id: str) -> bool:
        logging.info(f"  * Deleting alias {alias_id} from mailcow...")
        requestQuery = "/api/v1/delete/alias"
        return self._postRequest(requestQuery, [alias_id])
    
    def deleteFilter(self, filter_id: str) -> bool:
        logging.info(f"  * Deleting filter {filter_id} from mailcow...")
        requestQuery = "/api/v1/delete/filter"
        return self._postRequest(requestQuery, [filter_id])