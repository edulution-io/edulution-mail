from .ListStorage import ListStorage
from .DomainListStorage import DomainListStorage

class AliasListStorage(ListStorage):

    primaryKey = "address"
    validityCheckMarker = "#### managed-by-edulution-sync ####"

    def __init__(self, domainList: DomainListStorage):
        super().__init__()
        self._domainList = domainList

    def _checkElementValidity(self, element):
        # Check if domain is managed
        if element["address"].split("@")[-1] not in self._domainList._managed:
            return False

        # Check if alias has the management marker
        if "private_comment" in element:
            return self.validityCheckMarker in element["private_comment"]

        # No marker = not managed by sync (manual alias)
        return False