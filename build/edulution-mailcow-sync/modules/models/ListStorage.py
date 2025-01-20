import math


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
            if self._checkElementValidity(element):
                self._addQueue[elementId] = element

        return True
    
    def queuesAreEmpty(self) -> bool:
        return len(self._addQueue) == 0 and len(self._updateQueue) == 0 and len(self._disableQueue) == 0 and len(self._killQueue) == 0

    def getQueueCountsString(self, descriptor: str) -> str:
        return f"Going to add {len(self._addQueue)} {descriptor}, update {len(self._updateQueue)} {descriptor} and disable {len(self._disableQueue)} {descriptor}"
    
    def addQueue(self) -> list:
        return self._getQueueAsList(self._addQueue)
    
    def updateQueue(self) -> list:
        queue = []
        for key, value in self._updateQueue.items():
            queue.append({
            "attr": value,
            "items": [key]
        })
        return queue

    def _checkElementChanges(self, element: dict, elementId: str):
        currentElement = self._managed[elementId]

        for key, value in element.items():
            if self._checkElementValueDelta(key, currentElement, value):
                return True

        return False

    def _checkElementValueDelta(self, key: str, currentElement: dict, newValue: str) -> bool:
        return key not in currentElement or currentElement[key] != newValue

    def _getQueueAsList(self, queue: dict) -> list:
        elementList = []
        for key, value in queue.items():
            elementList.append(value)
        return elementList

    def _checkElementValidity(self, element) -> bool:
        return True
    
    def _convertBytesToMebibytes(self, byteSize):
        byteSize = int(byteSize)
        if byteSize == 0:
            return 0

        p = math.pow(1024, 2) # 2 stands for mebibyte
        s = round(byteSize / p, 2)
        return int(s)