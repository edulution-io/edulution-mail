from .ListStorage import ListStorage
from .DomainListStorage import DomainListStorage

class AliasListStorage(ListStorage):

    primaryKey = "address"

    def __init__(self, domainList: DomainListStorage):
        super().__init__()
        self._domainList = domainList

    def _checkElementValidity(self, element):
        return element["address"].split("@")[-1] in self._domainList._managed