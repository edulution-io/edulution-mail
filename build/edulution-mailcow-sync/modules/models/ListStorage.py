class ListStorage:

    primaryKey = "INVALID"

    def __init__(self):
        self._all = {}
        self._managed = {}
        self._addQueue = {}
        self._updateQueue = {}
        self._disableQueue = {}
        self._killQueue = {}

        self._primaryKey = self.primaryKey

    def loadRawData(self, rawData: list) -> bool:
        for element in rawData:
            self._all[element[self.primaryKey]] = element
            if self._checkElementValidity(element):
                self._managed[element[self.primaryKey]] = element
                self._disableQueue[element[self.primaryKey]] = element

    def addElement(self, element: dict, elementId: str) -> bool:
        if elementId in self._managed:
            if elementId in self._disableQueue:
                # Remove element from disable queue if its managed
                del self._disableQueue[elementId]
            if self._checkElementChanges(element, elementId):
                # Add element to update queue if its manages an changed
                self._updateQueue[elementId] = element
        elif elementId in self._all:
            # Else return false if element is not managed
            return False
        elif elementId not in self._addQueue:
            # Add element to add queue if its a new element
            self._addQueue[elementId] = element

        return True
    
    def getQueueCountsString(self, descriptor: str) -> str:
        return f"Going to add {len(self._addQueue)} {descriptor}, update {len(self._updateQueue)} {descriptor} and disable {len(self._disableQueue)} {descriptor}"
            
    def _checkElementChanges(self, element, elementId) -> bool:
        return False

    def _checkElementValidity(self, element) -> bool:
        return True
    
    def countManagedDomains(self) -> int:
        return len(self._managed)