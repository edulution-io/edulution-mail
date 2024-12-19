import requests
import logging

class Mailcow:

    def __init__(self):
        self._url = "nginx"
        self._apiToken = "c6baf8-ba41dd-a814af-d8ba9b-0b3c76"

        requests.packages.urllib3.util.connection.HAS_IPV6 = False

    def _getRequest(self, url) -> dict:
        requestUrl = "https://" + self._url + "/" + url
        headers = {'X-API-Key': self._apiToken, 'Content-type': 'application/json'}

        req = requests.get(requestUrl, headers=headers, verify=False)
        if req.status_code != 200:
            logging.error("  * ERROR! Could not connect to mailcow api!")
            logging.error("  * " + req.text)
            return False
        
        return req.json()
    
    def getDomains(self) -> list:
        logging.info("  * Downloading list of domains from mailcow...")
        requestQuery = "/api/v1/get/domain/all"
        return self._getRequest(requestQuery)
    
    def getMailboxes(self) -> list:
        logging.info("  * Downloading list of mailboxes from mailcow...")
        requestQuery = "/api/v1/get/mailbox/all"
        return self._getRequest(requestQuery)
