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
        
        # 1. Start with the most explicit ID we have
        target_id = provided_user_id
        
        if not target_id:
            # Check local credentials file
            creds = self.load_credentials()
            target_id = creds.get("user_id")

        if not target_id:
            # Check explicit DEFAULT_USER_ID env var
            target_id = os.getenv("DEFAULT_USER_ID")

        # 2. Return None if nothing found (no more generating random 'local-' IDs)
        if not target_id:
            return None

        # 3. Resolve familiar_id (e.g. 'yebyen') to pocket_id_sub (UUID) if needed
        if target_id and not self._is_uuid(target_id) and not target_id.startswith("local-"):
            resolved = self.resolve_familiar_id(target_id)
            if resolved:
                return resolved

        return target_id

    def _is_uuid(self, val: str) -> bool:
        """Check if a string is a UUID."""
        if not val or len(val) < 32:
            return False
        import re
        return bool(re.match(r'^[0-9a-f-]{32,36}$', val.lower()))

    def resolve_familiar_id(self, familiar_id: str) -> Optional[str]:
        """Query Neon DB to map a familiar_id to a pocket_id_sub."""
        db_url = os.getenv("NEON_DB_URL")
        if not db_url:
            return None

        try:
            import psycopg2
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pocket_id_sub FROM users WHERE familiar_id = %s", (familiar_id,))
                    row = cur.fetchone()
                    if row:
                        return row[0]
        except Exception as e:
            # We don't log an error here to avoid noise if DB is unavailable
            pass
        return None

# Singleton instance
credentials_manager = CredentialsManager()
