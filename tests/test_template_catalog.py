"""The committed WhatsApp template catalog matches what the senders fill (#363).

Every approved SID in data/approved_templates.json needs a body file in
data/templates/, and mecris_status_v2 must have exactly the 5 slots Spin and
Python fill (mecris-go-spin/sync-service/src/lib.rs, slots()).

The body files come from scripts/fetch_template_bodies.py, a read-only Twilio
Content API fetch that needs the owner's credentials and OK. Until it has run,
this test is skipped rather than failed.
"""
from pathlib import Path

import pytest

from scripts.fetch_template_bodies import catalog_problems

REPO_ROOT = Path(__file__).resolve().parent.parent
APPROVED = REPO_ROOT / "data" / "approved_templates.json"
TEMPLATES = REPO_ROOT / "data" / "templates"


def test_every_approved_template_has_a_matching_body_file():
    if not TEMPLATES.is_dir() or not any(TEMPLATES.glob("*.json")):
        pytest.skip("data/templates/ not fetched yet: run scripts/fetch_template_bodies.py (needs owner OK)")
    assert catalog_problems(APPROVED, TEMPLATES) == []
