import json
import os
import time
import logging
from datetime import datetime, timedelta

class DeactivationTracker:
    
    def __init__(self, storage_path="/srv/docker/edulution-mail/data"):
        self.storage_path = storage_path
        self.storage_file = os.path.join(storage_path, "deactivation_tracker.json")
        self.data = {
            "domains": {},
            "mailboxes": {},
            "aliases": {},
            "filters": {}
        }
        self.load()
    
    def load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    self.data = json.load(f)
                logging.info(f"  * Loaded deactivation tracker from {self.storage_file}")
            except Exception as e:
                logging.error(f"  * Failed to load deactivation tracker: {e}")
    
    def save(self):
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            with open(self.storage_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"  * Failed to save deactivation tracker: {e}")
    
    def markForDeactivation(self, item_type: str, item_id: str, grace_period_seconds: int):
        if item_type not in self.data:
            return False
        
        delete_at = time.time() + grace_period_seconds
        delete_at_readable = datetime.fromtimestamp(delete_at).strftime('%Y-%m-%d %H:%M:%S')
        
        self.data[item_type][item_id] = {
            "deactivated_at": time.time(),
            "delete_at": delete_at,
            "delete_at_readable": delete_at_readable
        }
        
        logging.info(f"  * Marked {item_type} {item_id} for deletion at {delete_at_readable}")
        self.save()
        return True
    
    def reactivate(self, item_type: str, item_id: str):
        if item_type in self.data and item_id in self.data[item_type]:
            del self.data[item_type][item_id]
            logging.info(f"  * Reactivated {item_type} {item_id}")
            self.save()
            return True
        return False
    
    def getItemsToDelete(self, item_type: str) -> list:
        if item_type not in self.data:
            return []
        
        items_to_delete = []
        current_time = time.time()
        
        for item_id, info in self.data[item_type].items():
            if info["delete_at"] <= current_time:
                items_to_delete.append(item_id)
        
        return items_to_delete
    
    def removeDeleted(self, item_type: str, item_id: str):
        if item_type in self.data and item_id in self.data[item_type]:
            del self.data[item_type][item_id]
            self.save()
    
    def isMarkedForDeactivation(self, item_type: str, item_id: str) -> bool:
        return item_type in self.data and item_id in self.data[item_type]
    
    def getDeactivationInfo(self, item_type: str, item_id: str) -> dict:
        if self.isMarkedForDeactivation(item_type, item_id):
            return self.data[item_type][item_id]
        return None
    
    def formatDescriptionWithDeletionDate(self, original_description: str, item_type: str, item_id: str) -> str:
        info = self.getDeactivationInfo(item_type, item_id)
        if info:
            deletion_marker = f"[DEACTIVATED - DELETE AT: {info['delete_at_readable']}]"
            if original_description and deletion_marker not in original_description:
                return f"{deletion_marker} {original_description}"
            elif not original_description:
                return deletion_marker
        return original_description