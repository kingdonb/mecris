import os
import json
from typing import Optional, Dict
from pathlib import Path

class CredentialsManager:
    """Manages local user credentials and token lifecycle."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".mecris"
        self.credentials_file = self.config_dir / "credentials.json"
        self.mode = os.getenv("MECRIS_MODE", "standalone")

    def ensure_config_dir(self):
        """Ensure the .mecris directory exists."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_credentials(self) -> Dict:
        """Load credentials from the config file."""
        if not self.credentials_file.exists():
            return {}
        try:
            with open(self.credentials_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_credentials(self, data: Dict):
        """Save credentials to the config file."""
        self.ensure_config_dir()
        with open(self.credentials_file, "w") as f:
            json.dump(data, f, indent=2)

    def resolve_user_id(self, provided_user_id: Optional[str] = None) -> Optional[str]:
        """Resolve the current user ID based on provided ID, local config, or mode."""
        
        # 1. Trust explicit provided ID (e.g. from JWT)
        if provided_user_id:
            return provided_user_id

        # 2. Check explicit DEFAULT_USER_ID env var for backward compatibility
        default_id = os.getenv("DEFAULT_USER_ID")
        if default_id:
            return default_id

        # 3. Check local credentials file
        creds = self.load_credentials()
        if "user_id" in creds:
            return creds["user_id"]

        # 3. Mode-based fallbacks
        if self.mode == "standalone":
            # Generate a persistent local ID if none exists
            import uuid
            new_id = f"local-{uuid.uuid4().hex[:8]}"
            self.save_credentials({"user_id": new_id})
            return new_id
        
        # In multi-tenant mode, we do NOT fall back to DEFAULT_USER_ID automatically.
        # The user must log in.
        return None

# Singleton instance
credentials_manager = CredentialsManager()
