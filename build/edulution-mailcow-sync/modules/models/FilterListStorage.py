from .ListStorage import ListStorage
from .DomainListStorage import DomainListStorage

class FilterListStorage(ListStorage):

    primaryKey = "username"

    def __init__(self, domainList: DomainListStorage):
        super().__init__()
        self._domainList = domainList

    def updateQueue(self):
        queue = []
        for key, value in self._updateQueue.items():
            filterId = self._managed[key]["id"]
            queue.append({
            "attr": value,
            "items": [filterId]
        })
        return queue

    def _checkElementValidity(self, element):
        return element["username"].split("@")[-1] in self._domainList._managed