import json
import os
import time
import logging
from datetime import datetime

class DeactivationTracker:
    
    def __init__(self, storage_path="/srv/docker/edulution-mail/data", mark_count_threshold=3):
        self.storage_path = storage_path
        self.storage_file = os.path.join(storage_path, "deactivation_tracker.json")
        self.mark_count_threshold = mark_count_threshold
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
        
        # Initialize or increment counter
        if item_id not in self.data[item_type]:
            self.data[item_type][item_id] = {
                "mark_count": 1,
                "first_marked_at": time.time(),
                "last_marked_at": time.time(),
                "deactivated": False
            }
            logging.info(f"  * First mark for {item_type} {item_id} (1/{self.mark_count_threshold})")
        else:
            # If already deactivated, don't increment counter
            if self.data[item_type][item_id].get("deactivated", False):
                return True
            
            current_count = self.data[item_type][item_id].get("mark_count", 0)
            if current_count < self.mark_count_threshold:
                self.data[item_type][item_id]["mark_count"] = current_count + 1
                self.data[item_type][item_id]["last_marked_at"] = time.time()
                logging.info(f"  * Mark {current_count + 1}/{self.mark_count_threshold} for {item_type} {item_id}")
            
            # On threshold mark, set for actual deactivation
            if self.data[item_type][item_id]["mark_count"] >= self.mark_count_threshold and not self.data[item_type][item_id].get("deactivated", False):
                delete_at = time.time() + grace_period_seconds
                delete_at_readable = datetime.fromtimestamp(delete_at).strftime('%Y-%m-%d %H:%M:%S')
                
                self.data[item_type][item_id]["deactivated"] = True
                self.data[item_type][item_id]["deactivated_at"] = time.time()
                self.data[item_type][item_id]["delete_at"] = delete_at
                self.data[item_type][item_id]["delete_at_readable"] = delete_at_readable
                
                logging.info(f"  * {item_type} {item_id} marked for deletion at {delete_at_readable} after {self.mark_count_threshold} marks")
        
        self.save()
        return self.data[item_type][item_id].get("mark_count", 0) >= self.mark_count_threshold
    
    def reactivate(self, item_type: str, item_id: str):
        if item_type in self.data and item_id in self.data[item_type]:
            # Reset counter instead of deleting completely
            self.data[item_type][item_id] = {
                "mark_count": 0,
                "deactivated": False
            }
            logging.info(f"  * Reset counter for {item_type} {item_id} (found in Keycloak again)")
            self.save()
            return True
        return False
    
    def getItemsToDelete(self, item_type: str) -> list:
        if item_type not in self.data:
            return []
        
        items_to_delete = []
        current_time = time.time()
        
        for item_id, info in self.data[item_type].items():
            if info.get("deactivated", False) and "delete_at" in info:
                if info["delete_at"] <= current_time:
                    items_to_delete.append(item_id)
        
        return items_to_delete
    
    def removeDeleted(self, item_type: str, item_id: str):
        if item_type in self.data and item_id in self.data[item_type]:
            del self.data[item_type][item_id]
            self.save()
    
    def isMarkedForDeactivation(self, item_type: str, item_id: str) -> bool:
        if item_type in self.data and item_id in self.data[item_type]:
            return self.data[item_type][item_id].get("deactivated", False)
        return False
    
    def getMarkCount(self, item_type: str, item_id: str) -> int:
        if item_type in self.data and item_id in self.data[item_type]:
            return self.data[item_type][item_id].get("mark_count", 0)
        return 0
    
    def getDeactivationInfo(self, item_type: str, item_id: str) -> dict:
        if self.isMarkedForDeactivation(item_type, item_id):
            return self.data[item_type][item_id]
        return None
    
    def formatDescriptionWithDeletionDate(self, original_description: str, item_type: str, item_id: str) -> str:
        info = self.getDeactivationInfo(item_type, item_id)
        if info and info.get("deactivated", False) and "delete_at_readable" in info:
            deletion_marker = f"[DEACTIVATED - DELETE AT: {info['delete_at_readable']}]"
            if original_description and deletion_marker not in original_description:
                return f"{deletion_marker} {original_description}"
            elif not original_description:
                return deletion_marker
        return original_description