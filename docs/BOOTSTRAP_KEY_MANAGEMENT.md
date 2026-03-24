# 🔐 Bootstrap Key Management & Encryption

This document outlines the secure "Dark-Pipe" workflow for initializing the Mecris Master Encryption Key and securing user credentials. This process ensures that sensitive keys never touch the terminal screen or shell history by using subshell expansion.

## 1. Prerequisites
- `op` (1Password CLI v2.x)
- `openssl`
- `spin` (Fermyon Spin CLI)
- Access to the Neon Database

## 2. Key Generation & 1Password Storage
Generate a 32-byte hex key and store it directly in a 1Password "Mecris Master Key" item.

```bash
op item create --category "Password" --title "Mecris Master Key" --vault "Private" "password=$(openssl rand -hex 32 | tr -d '\n')"
```

## 3. Provisioning the Cloud Environment
Fetch the key from 1Password and set it as a Spin Cloud variable. Use `tr -d '\n'` to ensure no trailing newline is included in the secret value.

```bash
spin cloud variables set master_encryption_key="$(op item get "Mecris Master Key" --fields label=password --reveal | tr -d '\n')" --app mecris-sync-v2
```

## 4. Local Environment Setup
Append the key to your local `.env` file for the Python MCP and local diagnostics.

```bash
printf "\nMASTER_ENCRYPTION_KEY=%s\n" "$(op item get "Mecris Master Key" --fields label=password --reveal | tr -d '\n')" >> .env
```

## 5. Encrypting User Credentials
Once the environment has the `MASTER_ENCRYPTION_KEY`, run the repair script to migrate plaintext credentials in the database to the secure encrypted format.

```python
# Run this script via: PYTHONPATH=. .venv/bin/python << 'EOF' ...
import os
import binascii
import psycopg2
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

def encrypt(plaintext, key_hex):
    key = binascii.unhexlify(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return binascii.hexlify(nonce + ciphertext).decode()

key = os.getenv("MASTER_ENCRYPTION_KEY")
email = os.getenv("CLOZEMASTER_EMAIL")
password = os.getenv("CLOZEMASTER_PASSWORD")
db_url = os.getenv("NEON_DB_URL")

if not all([key, email, password, db_url]):
    print("❌ Error: Missing required environment variables in .env")
    exit(1)

email_enc = encrypt(email, key)
pass_enc = encrypt(password, key)

with psycopg2.connect(db_url) as conn:
    with conn.cursor() as cur:
        # Update user with the specific UUID
        cur.execute("""
            UPDATE users 
            SET clozemaster_email_encrypted = %s, 
                clozemaster_password_encrypted = %s 
            WHERE pocket_id_sub = 'c0a81a4b-115a-4eb6-bc2c-40908c58bf64'
        """, (email_enc, pass_enc))
        conn.commit()
        print("✅ Production user repaired with encrypted credentials!")
```

## 6. Verification & Troubleshooting
Trigger a "FORCE SYNC" in the Android app. Check the Spin Cloud logs to verify:
1. `MASTER_ENCRYPTION_KEY` is successfully loaded.
2. Credentials are successfully decrypted.
3. Clozemaster login succeeds.
4. Beeminder push succeeds.

### Common Pitfalls
- **Odd number of digits:** This usually indicates a trailing newline in the `master_encryption_key` or encrypted DB field. Rust's `hex::decode` is very strict. Always use `tr -d '\n'` when setting cloud variables via subshell.
- **Unauthorized (401):** Ensure the `beeminder_token_encrypted` field is actually encrypted. The system now refuses plaintext tokens.
- **Last Sync Timestamp False Positives:** Ensure the system propagates errors correctly so `beeminder_last_sync` isn't updated on a failed push.
