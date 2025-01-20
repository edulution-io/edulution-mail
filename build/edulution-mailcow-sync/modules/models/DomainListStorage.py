from .ListStorage import ListStorage

class DomainListStorage(ListStorage):

    primaryKey = "domain_name"
    validityCheckDescription = "#### managed by linuxmuster ####"

    def _checkElementValidity(self, element):
        return element["description"] == self.validityCheckDescription

    def _checkElementValueDelta(self, key, currentElement, newValue):
        ignoreKeys = ["domain", "restart_sogo"]

        getKeyNames = {
            "maxquota": "max_quota_for_mbox",
            "defquota": "def_quota_for_mbox",
            "quota": "max_quota_for_domain",
            "mailboxes": "max_num_mboxes_for_domain",
            "aliases": "max_num_aliases_for_domain"
        }
        quotaKeyNames = ["max_quota_for_mbox", "def_quota_for_mbox", "max_quota_for_domain"]

        if key in getKeyNames:
            key = getKeyNames[key]

        if key in ignoreKeys:
            return False
        elif key in quotaKeyNames:
            currentQuota = self._convertBytesToMebibytes(currentElement[key])
            newQuota = int(newValue)
            return currentQuota != newQuota
        else:
            return super()._checkElementValueDelta(key, currentElement, newValue)

    
    
    