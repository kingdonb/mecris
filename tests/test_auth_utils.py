import pytest
import re
import base64
import hashlib
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
from services.auth_utils import generate_code_verifier, generate_code_challenge, build_auth_url

def test_build_auth_url_contains_required_params():
    """Build URL must contain all OIDC and PKCE parameters."""
    challenge = "fake_challenge"
    state = "fake_state"
    port = 54321
    
    with patch.dict('os.environ', {
        'POCKET_ID_CLIENT_ID': 'test_client',
        'POCKET_ID_AUTH_ENDPOINT': 'https://auth.example.com/authorize'
    }):
        url = build_auth_url(challenge, state, port)
        
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.example.com"
    assert parsed.path == "/authorize"
    
    params = parse_qs(parsed.query)
    assert params['client_id'] == ['test_client']
    assert params['redirect_uri'] == [f'http://localhost:{port}']
    assert params['response_type'] == ['code']
    assert 'openid' in params['scope'][0]
    assert 'offline_access' in params['scope'][0]
    assert params['code_challenge'] == [challenge]
    assert params['code_challenge_method'] == ['S256']
    assert params['state'] == [state]

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
