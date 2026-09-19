"""Unit tests for the Helix billing reader lever (task 588, C1a).

No live network calls: the recorded M1 wallet shape is a fixture and the
HTTP layer is mocked. Run: pytest tests/test_helix_billing.py
"""
import os
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import helix_billing  # noqa: E402

# Shape recorded verbatim from the M1 door-trace, 2026-09-19.
WALLET_FIXTURE = {
    "id": "wal_01kkyy4qavm7x76t9xrn683ks4",
    "created_at": "2026-03-17T22:19:56.635147Z",
    "updated_at": "2026-09-19T20:44:42.296064773Z",
    "stripe_customer_id": "cus_TEST",
    "stripe_subscription_id": "sub_TEST",
    "subscription_status": "active",
    "subscription_current_period_start": 1789683683,
    "subscription_current_period_end": 1792275683,
    "subscription_created": 1773786083,
    "subscription_cancel_at_period_end": False,
    "user_id": "",
    "org_id": "org_01kkyy4pvta650945vn727sasy",
    "balance": 498.333376936,
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else WALLET_FIXTURE
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("HELIX_BILLING_API_TOKEN", "hl-test-token")
    monkeypatch.delenv("USER_API_TOKEN", raising=False)
    monkeypatch.setenv("HELIX_BILLING_ORG_ID", "mecris")
    helix_billing.clear_cache()
    yield
    helix_billing.clear_cache()


def _fake_http(response=None, side_effect=None):
    fake = mock.MagicMock()
    fake.get.return_value = response or FakeResponse()
    if side_effect:
        fake.get.side_effect = side_effect
    return fake


def test_parses_live_recorded_shape():
    with mock.patch.object(helix_billing, "requests", _fake_http()):
        assert helix_billing.get_balance() == pytest.approx(498.333376936)


def test_wallet_exposes_period_dates_for_allowance_math():
    with mock.patch.object(helix_billing, "requests", _fake_http()):
        wallet = helix_billing.get_wallet()
    assert wallet["period_end"] == 1792275683  # 2026-10-17T22:21Z (D5)
    assert wallet["period_start"] == 1789683683
    assert wallet["subscription_status"] == "active"


def test_zero_balance_stays_zero_not_none():
    payload = dict(WALLET_FIXTURE, balance=0.0)
    with mock.patch.object(helix_billing, "requests", _fake_http(FakeResponse(200, payload))):
        assert helix_billing.get_balance() == 0.0


def test_missing_balance_key_is_none():
    payload = {k: v for k, v in WALLET_FIXTURE.items() if k != "balance"}
    with mock.patch.object(helix_billing, "requests", _fake_http(FakeResponse(200, payload))):
        assert helix_billing.get_balance() is None


def test_cloudflare_403_is_none_not_crash():
    with mock.patch.object(helix_billing, "requests", _fake_http(FakeResponse(403))):
        assert helix_billing.get_balance() is None


def test_network_exception_is_none():
    with mock.patch.object(helix_billing, "requests",
                           _fake_http(side_effect=ConnectionError("boom"))):
        assert helix_billing.get_balance() is None


def test_missing_token_skips_fetch_entirely():
    fake = _fake_http()
    with mock.patch.dict(os.environ, {"HELIX_BILLING_API_TOKEN": "", "USER_API_TOKEN": ""}):
        with mock.patch.object(helix_billing, "requests", fake):
            assert helix_billing.get_balance() is None
    fake.get.assert_not_called()


def test_user_api_token_sandbox_fallback():
    with mock.patch.dict(os.environ, {"HELIX_BILLING_API_TOKEN": "",
                                      "USER_API_TOKEN": "hl-sandbox"}):
        with mock.patch.object(helix_billing, "requests", _fake_http()) as fake:
            assert helix_billing.get_balance() is not None


def test_cache_dedupes_within_ttl_and_force_bypasses():
    fake = _fake_http()
    with mock.patch.object(helix_billing, "requests", fake):
        helix_billing.get_balance()
        helix_billing.get_balance()
        assert fake.get.call_count == 1  # 5-min cache held
        helix_billing.get_balance(force=True)
        assert fake.get.call_count == 2


def test_cache_expires_after_ttl():
    fake = _fake_http()
    # get_wallet() consumes exactly one monotonic() tick per call:
    # first read cached at t=0; second read at t=400 (> 300 TTL) refetches.
    with mock.patch.object(helix_billing, "requests", fake):
        with mock.patch("time.monotonic", side_effect=[0.0, 400.0]):
            helix_billing.get_balance()
            helix_billing.get_balance()
        assert fake.get.call_count == 2


def test_headers_bearer_cloudflare_safe():
    fake = _fake_http()
    with mock.patch.object(helix_billing, "requests", fake):
        helix_billing.get_balance()
    kwargs = fake.get.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer hl-test-token"
    assert "Python" not in kwargs["headers"]["User-Agent"]
    assert kwargs["headers"]["Accept"] == "application/json"
    assert kwargs["params"] == {"org_id": "mecris"}
    assert kwargs["timeout"] == 5
