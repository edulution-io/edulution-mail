import os

class ConfigurationStorage:

    def importFromEnvironment(self):
        self.DOMAIN_QUOTA = os.environ.get("DOMAIN_QUOTA", 5000)
        self.ENABLE_GAL = os.environ.get("ENABLE_GAL", 1)