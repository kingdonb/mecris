import pytest
import re
import base64
import hashlib
from services.auth_utils import generate_code_verifier, generate_code_challenge

def test_generate_code_verifier_properties():
    """Verifier must be 43-128 chars and use unreserved characters."""
    verifier = generate_code_verifier()
    assert 43 <= len(verifier) <= 128
    # Regex for unreserved characters: [A-Z], [a-z], [0-9], "-", ".", "_", "~"
    assert re.match(r'^[A-Za-z0-9._~-]+$', verifier)

def test_generate_code_challenge_is_base64url():
    """Challenge must be a base64url encoded SHA256 hash of the verifier."""
    verifier = "test_verifier_string_of_sufficient_length_1234567890"
    challenge = generate_code_challenge(verifier)
    
    # Manually compute expected challenge
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    expected = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').replace('=', '')
    
    assert challenge == expected
    # Challenge should not contain padding chars
    assert '=' not in challenge

def test_verifiers_are_unique():
    v1 = generate_code_verifier()
    v2 = generate_code_verifier()
    assert v1 != v2
