"""Tests for JWKS-based JWT signature verification in auth_service."""
import time
import pytest
import jwt
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

import services.auth_service as auth_service_module
from services.auth_service import verify_token


def _make_rsa_key():
    """Generate a fresh RSA private key for testing."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


def _make_token(private_key, iss="https://metnoom.urmanac.com", sub="user-abc", exp_offset=3600):
    """Sign a JWT with the given private key."""
    return jwt.encode(
        {"sub": sub, "iss": iss, "exp": int(time.time()) + exp_offset},
        private_key,
        algorithm="RS256",
    )


def _mock_jwks_client(public_key):
    """Return a mock PyJWKClient whose get_signing_key_from_jwt returns public_key."""
    signing_key = MagicMock()
    signing_key.key = public_key
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = signing_key
    return mock_client


class TestVerifyTokenCloudMode:
    """Signature verification tests run with MECRIS_MODE=cloud."""

    def test_valid_token_passes(self):
        """Token signed with correct key should decode successfully."""
        private_key = _make_rsa_key()
        public_key = private_key.public_key()
        token = _make_token(private_key)

        mock_client = _mock_jwks_client(public_key)
        with patch.dict("os.environ", {"MECRIS_MODE": "cloud", "OIDC_ISSUER": "https://metnoom.urmanac.com"}):
            with patch.object(auth_service_module, "_get_jwks_client", return_value=mock_client):
                payload = verify_token(token)

        assert payload["sub"] == "user-abc"

    def test_wrong_signing_key_raises_401(self):
        """Token signed with a different RSA key must be rejected with 401."""
        signer_key = _make_rsa_key()
        wrong_key = _make_rsa_key()  # different key — public key won't match signature
        token = _make_token(signer_key)

        # JWKS returns the *wrong* public key
        mock_client = _mock_jwks_client(wrong_key.public_key())
        with patch.dict("os.environ", {"MECRIS_MODE": "cloud", "OIDC_ISSUER": "https://metnoom.urmanac.com"}):
            with patch.object(auth_service_module, "_get_jwks_client", return_value=mock_client):
                with pytest.raises(HTTPException) as exc_info:
                    verify_token(token)

        assert exc_info.value.status_code == 401

    def test_expired_token_raises_401(self):
        """Expired token must be rejected even if signature is valid."""
        private_key = _make_rsa_key()
        public_key = private_key.public_key()
        token = _make_token(private_key, exp_offset=-10)  # already expired

        mock_client = _mock_jwks_client(public_key)
        with patch.dict("os.environ", {"MECRIS_MODE": "cloud", "OIDC_ISSUER": "https://metnoom.urmanac.com"}):
            with patch.object(auth_service_module, "_get_jwks_client", return_value=mock_client):
                with pytest.raises(HTTPException) as exc_info:
                    verify_token(token)

        assert exc_info.value.status_code == 401

    def test_issuer_mismatch_raises_401(self):
        """Token with wrong issuer must be rejected after signature verification."""
        private_key = _make_rsa_key()
        public_key = private_key.public_key()
        token = _make_token(private_key, iss="https://evil.example.com")

        mock_client = _mock_jwks_client(public_key)
        with patch.dict("os.environ", {"MECRIS_MODE": "cloud", "OIDC_ISSUER": "https://metnoom.urmanac.com"}):
            with patch.object(auth_service_module, "_get_jwks_client", return_value=mock_client):
                with pytest.raises(HTTPException) as exc_info:
                    verify_token(token)

        assert exc_info.value.status_code == 401
        assert "issuer" in exc_info.value.detail.lower()


class TestVerifyTokenStandaloneMode:
    """In standalone mode JWKS is not called; only expiry is checked."""

    def test_unsigned_token_passes_in_standalone(self):
        """Standalone mode must accept tokens without RSA signature."""
        # Encode with a simple secret — no RSA
        token = jwt.encode(
            {"sub": "local-user", "iss": "anyone", "exp": int(time.time()) + 3600},
            "any-secret",
            algorithm="HS256",
        )
        with patch.dict("os.environ", {"MECRIS_MODE": "standalone"}):
            payload = verify_token(token)
        assert payload["sub"] == "local-user"

    def test_expired_token_rejected_in_standalone(self):
        """Standalone mode must still reject expired tokens."""
        token = jwt.encode(
            {"sub": "local-user", "exp": int(time.time()) - 10},
            "any-secret",
            algorithm="HS256",
        )
        with patch.dict("os.environ", {"MECRIS_MODE": "standalone"}):
            with pytest.raises(HTTPException) as exc_info:
                verify_token(token)
        assert exc_info.value.status_code == 401

    def test_jwks_client_not_called_in_standalone(self):
        """Standalone mode must not call the JWKS endpoint."""
        token = jwt.encode(
            {"sub": "local-user", "exp": int(time.time()) + 3600},
            "any-secret",
            algorithm="HS256",
        )
        with patch.dict("os.environ", {"MECRIS_MODE": "standalone"}):
            with patch.object(auth_service_module, "_get_jwks_client") as mock_get:
                verify_token(token)
                mock_get.assert_not_called()
