from .ListStorage import ListStorage

class MailboxListStorage(ListStorage):

    primaryKey = "username"
    validityCheckDescription = "#### managed by linuxmuster ####"

    def _checkElementValidity(self, element):
        if "tags" in element:
            if self.validityCheckDescription in element["tags"]:
                return True
        return False



    
    
    