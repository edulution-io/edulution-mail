from .ListStorage import ListStorage
from .DomainListStorage import DomainListStorage

class AliasListStorage(ListStorage):

    primaryKey = "address"
    validityCheckMarker = "#### managed-by-edulution-sync ####"

    def __init__(self, domainList: DomainListStorage, force_marker_update: bool = False):
        super().__init__()
        self._domainList = domainList
        self._force_marker_update = force_marker_update

    def _checkElementValidity(self, element):
        # Check if domain is managed
        if element["address"].split("@")[-1] not in self._domainList._managed:
            return False

        # In force marker update mode: treat all domain-matched aliases as managed
        if self._force_marker_update:
            # All aliases in managed domain = managed (for migration)
            return True

        # Normal mode: Check if alias has the management marker
        if "private_comment" in element and element["private_comment"] is not None:
            return self.validityCheckMarker in element["private_comment"]

        # No marker = not managed by sync (manual alias)
        return False

    def _checkElementValueDelta(self, key, currentElement, newValue):
        import logging
        # Update private_comment if it doesn't have the marker (for migration)
        if key == "private_comment":
            current_comment = currentElement.get("private_comment", "")
            if current_comment is None:
                current_comment = ""

            # Debug logging
            if self._force_marker_update and logging.getLogger().level == logging.DEBUG:
                logging.debug(f"  * [ALIAS DEBUG] Checking {currentElement.get('address')}: current_comment='{current_comment[:50] if current_comment else 'EMPTY'}...', newValue='{newValue[:50]}...', has_marker={self.validityCheckMarker in current_comment}")

            # If migration mode is enabled or current comment doesn't have marker, force update
            if self._force_marker_update or self.validityCheckMarker not in current_comment:
                return True
            # If it has marker, check if value changed
            return current_comment != newValue

        # For all other keys, use default behavior
        return super()._checkElementValueDelta(key, currentElement, newValue)