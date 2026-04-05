import pytest
import re
import base64
import hashlib
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
from services.auth_utils import generate_code_verifier, generate_code_challenge, build_auth_url, exchange_code_for_tokens, exchange_refresh_token

@patch('requests.post')
def test_exchange_code_for_tokens(mock_post):
    """Function must send correct POST request to token endpoint."""
    mock_post.return_value.json.return_value = {"access_token": "abc", "refresh_token": "def"}
    mock_post.return_value.status_code = 200
    
    code = "fake_code"
    verifier = "fake_verifier"
    port = 1234
    
    with patch.dict('os.environ', {
        'POCKET_ID_CLIENT_ID': 'test_client',
        'POCKET_ID_TOKEN_ENDPOINT': 'https://auth.example.com/token'
    }):
        tokens = exchange_code_for_tokens(code, verifier, port)
        
    assert tokens == {"access_token": "abc", "refresh_token": "def"}
    
    # Verify request
    args, kwargs = mock_post.call_args
    assert args[0] == 'https://auth.example.com/token'
    data = kwargs['data']
    assert data['grant_type'] == 'authorization_code'
    assert data['code'] == code
    assert data['code_verifier'] == verifier
    assert data['client_id'] == 'test_client'
    assert data['redirect_uri'] == f'http://localhost:{port}'

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

@patch('requests.post')
def test_exchange_refresh_token(mock_post):
    """exchange_refresh_token must POST refresh_token grant without code_verifier or redirect_uri."""
    mock_post.return_value.json.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_in": 3600
    }
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status = lambda: None

    with patch.dict('os.environ', {
        'POCKET_ID_CLIENT_ID': 'test_client',
        'POCKET_ID_TOKEN_ENDPOINT': 'https://auth.example.com/token'
    }):
        tokens = exchange_refresh_token("old_refresh_token")

    assert tokens["access_token"] == "new_access"
    assert tokens["refresh_token"] == "new_refresh"

    args, kwargs = mock_post.call_args
    assert args[0] == 'https://auth.example.com/token'
    data = kwargs['data']
    assert data['grant_type'] == 'refresh_token'
    assert data['refresh_token'] == 'old_refresh_token'
    assert data['client_id'] == 'test_client'
    assert 'code_verifier' not in data
    assert 'redirect_uri' not in data
