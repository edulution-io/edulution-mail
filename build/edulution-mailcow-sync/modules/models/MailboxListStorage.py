from .ListStorage import ListStorage
from .DomainListStorage import DomainListStorage

class MailboxListStorage(ListStorage):

    primaryKey = "username"
    validityCheckTag = "not-managed"

    def __init__(self, domainList: DomainListStorage):
        super().__init__()
        self._domainList = domainList

    def _checkElementValidity(self, element):
        if "tags" in element:
            if self.validityCheckTag in element["tags"]:
                return False
        return element["domain"] in self._domainList._managed

    def _checkElementValueDelta(self, key, currentElement, newValue):
        ignoreKeys = ["password", "password2"]

        if key in ignoreKeys:
            return False
        elif key not in currentElement:
            return True
        elif key == "quota":
            currentQuota = self._convertBytesToMebibytes(currentElement[key])
            newQuota = int(newValue)
            return currentQuota != newQuota
        else:
            return super()._checkElementValueDelta(key, currentElement, newValue)