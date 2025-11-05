from .ListStorage import ListStorage
from .DomainListStorage import DomainListStorage

class MailboxListStorage(ListStorage):

    primaryKey = "username"
    validityCheckTag = "not-managed"  # Legacy: for backwards compatibility
    managedTag = "edulution-sync-managed"  # New: identifies sync-managed mailboxes

    def __init__(self, domainList: DomainListStorage):
        super().__init__()
        self._domainList = domainList

    def _checkElementValidity(self, element):
        # Check if domain is managed
        if element["domain"] not in self._domainList._managed:
            return False

        # Check tags
        if "tags" in element:
            # Legacy: Backwards compatibility - respect "not-managed" tag
            if self.validityCheckTag in element["tags"]:
                return False

            # New: Only manage mailboxes with our management tag
            if self.managedTag in element["tags"]:
                return True

        # No tags or no management tag = not managed by sync (manual mailbox)
        return False

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