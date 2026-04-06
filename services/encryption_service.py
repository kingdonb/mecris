import os
import binascii
import logging
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("mecris.encryption")

class EncryptionService:
    """Provides AES-256-GCM encryption/decryption for multi-tenant PII.
    
    Compatible with the Rust implementation in sync-service/src/lib.rs.
    Format: [12-byte nonce][ciphertext][16-byte tag]
    """
    
    def __init__(self, key_hex: str = None):
        self.key_hex = key_hex or os.getenv("MASTER_ENCRYPTION_KEY")
        if not self.key_hex:
            logger.warning("MASTER_ENCRYPTION_KEY not set. Encryption/Decryption will fail.")
            self.aesgcm = None
        else:
            try:
                key_bytes = binascii.unhexlify(self.key_hex.strip())
                if len(key_bytes) != 32:
                    raise ValueError(f"Invalid key length: {len(key_bytes)} bytes (expected 32)")
                self.aesgcm = AESGCM(key_bytes)
            except Exception as e:
                logger.error(f"Failed to initialize EncryptionService: {e}")
                self.aesgcm = None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return as hex string [nonce][ciphertext+tag]."""
        if not self.aesgcm:
            raise RuntimeError("EncryptionService not initialized (missing key)")
        
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        return binascii.hexlify(nonce + ciphertext).decode()

    def decrypt(self, encrypted_hex: str) -> str:
        """Decrypt hex string [nonce][ciphertext+tag] and return plaintext."""
        if not self.aesgcm:
            raise RuntimeError("EncryptionService not initialized (missing key)")
        
        try:
            data = binascii.unhexlify(encrypted_hex.strip())
            if len(data) < 12:
                raise ValueError("Invalid encrypted data length")
            
            nonce = data[:12]
            ciphertext = data[12:]
            plaintext_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def try_encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Try to encrypt plaintext. If it fails or is unavailable, return original value."""
        if not plaintext or not self.aesgcm:
            return plaintext
            
        try:
            return self.encrypt(plaintext)
        except Exception as e:
            logger.warning(f"Encryption failed (non-fatal, returning plaintext): {e}")
            return plaintext
