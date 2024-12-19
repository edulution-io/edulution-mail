from .ListStorage import ListStorage

class DomainListStorage(ListStorage):

    primaryKey = "domain_name"
    validityCheckDescription = "#### managed by linuxmuster ####"

    def _checkElementValidity(self, element):
        return element["description"] == self.validityCheckDescription



    
    
    