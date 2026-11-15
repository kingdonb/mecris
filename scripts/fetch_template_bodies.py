#!/usr/bin/env python3
"""Fetch approved WhatsApp template bodies from the Twilio Content API (#363 step 1).

Read-only: it issues GET requests to content.twilio.com and nothing else. For
every SID in data/approved_templates.json it reads the body, sample variables,
category and approval status, and writes data/templates/<name>.json.

Today the repo holds only name-to-SID pairs, so the wording Meta approved is
not reviewable here. Committing the bodies lets tests check that the slots the
senders fill match the approved text (tests/test_template_catalog.py).

Usage (needs TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env, and the owner's OK):
    python scripts/fetch_template_bodies.py            # write data/templates/*.json
    python scripts/fetch_template_bodies.py --dry-run  # fetch and report, write nothing

Output names SIDs, template names and HTTP status codes only. Credentials are
never printed.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

CONTENT_HOST = "content.twilio.com"
CONTENT_URL = f"https://{CONTENT_HOST}/v1/Content/{{sid}}"
APPROVAL_URL = f"https://{CONTENT_HOST}/v1/Content/{{sid}}/ApprovalRequests"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APPROVED = REPO_ROOT / "data" / "approved_templates.json"
DEFAULT_OUT = REPO_ROOT / "data" / "templates"

# Slots each sender fills, per template (lib.rs slots(); Python reminder paths).
EXPECTED_SLOTS = {"mecris_status_v2": 5}

SAFE_NAME = re.compile(r"[a-z0-9_]+")
PLACEHOLDER = re.compile(r"\{\{\s*(\d+)\s*\}\}")
PREFERRED_TYPES = ("twilio/text", "whatsapp/card", "twilio/quick-reply", "twilio/call-to-action")


def placeholders(body):
    """Unique {{n}} slot numbers in a template body, sorted."""
    return sorted({int(n) for n in PLACEHOLDER.findall(body or "")})


def load_approved(path=DEFAULT_APPROVED):
    """Return {sid: name} from data/approved_templates.json."""
    with open(path, encoding="utf-8") as f:
        return dict(json.load(f)["approved_templates"])


def _bodies(types):
    return {t: {"body": spec["body"]} for t, spec in (types or {}).items()
            if isinstance(spec, dict) and isinstance(spec.get("body"), str)}


def _primary_body(bodies):
    for t in PREFERRED_TYPES:
        if t in bodies:
            return bodies[t]["body"]
    return next(iter(bodies.values()), {}).get("body", "")


def build_record(sid, name, content, approval):
    """The committed shape of one template. Leaves out account identifiers."""
    whatsapp = (approval or {}).get("whatsapp") or {}
    bodies = _bodies(content.get("types"))
    body = _primary_body(bodies)
    return {
        "sid": sid,
        "name": name,
        "friendly_name": content.get("friendly_name"),
        "language": content.get("language"),
        "category": whatsapp.get("category"),
        "approval_status": whatsapp.get("status"),
        "rejection_reason": whatsapp.get("rejection_reason") or None,
        "body": body,
        "placeholders": placeholders(body),
        "variables": content.get("variables") or {},
        "types": bodies,
        "source": "Twilio Content API (scripts/fetch_template_bodies.py)",
    }


def fetch_template(sid, name, get_json):
    """Return (record, None) or (None, status). get_json(url) -> (status, dict)."""
    status, content = get_json(CONTENT_URL.format(sid=sid))
    if status != 200:
        return None, status
    status, approval = get_json(APPROVAL_URL.format(sid=sid))
    if status != 200:
        return None, status
    return build_record(sid, name, content, approval), None


def write_record(record, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record['name']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path


def fetch_all(approved, get_json, out_dir=DEFAULT_OUT, dry_run=False):
    """Fetch every approved template. Returns (written paths, [(sid, status or reason)])."""
    written, failures = [], []
    for sid, name in sorted(approved.items(), key=lambda kv: kv[1]):
        if not SAFE_NAME.fullmatch(name or ""):
            failures.append((sid, "bad-name"))
            continue
        record, status = fetch_template(sid, name, get_json)
        if record is None:
            failures.append((sid, status))
            continue
        if not dry_run:
            written.append(write_record(record, Path(out_dir)))
    return written, failures


def catalog_problems(approved_path, templates_dir, expected_slots=EXPECTED_SLOTS):
    """Human-readable problems with the committed catalog; empty when it is complete."""
    templates_dir = Path(templates_dir)
    problems = []
    for sid, name in sorted(load_approved(approved_path).items(), key=lambda kv: kv[1]):
        path = templates_dir / f"{name}.json"
        if not path.is_file():
            problems.append(f"{name} ({sid}): body file missing")
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("sid") != sid:
            problems.append(f"{name}: body file is for a different SID")
        want = expected_slots.get(name)
        got = len(placeholders(record.get("body", "")))
        if want is not None and got != want:
            problems.append(f"{name}: body has {got} placeholders, senders fill {want}")
    return problems


def make_twilio_get(account_sid, auth_token, timeout=20):
    """A GET-only client for the Content API. Errors surface as status codes, never URLs or keys."""
    import requests
    from requests.auth import HTTPBasicAuth

    session = requests.Session()
    session.auth = HTTPBasicAuth(account_sid, auth_token)

    def get_json(url):
        if not url.startswith(f"https://{CONTENT_HOST}/"):
            raise ValueError("refusing a non-Content-API URL")
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            return type(exc).__name__, {}
        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, {}

    return get_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    parser.add_argument("--approved", type=Path, default=DEFAULT_APPROVED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        print("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set (.env).", file=sys.stderr)
        return 2

    approved = load_approved(args.approved)
    written, failures = fetch_all(approved, make_twilio_get(account_sid, auth_token), args.out, args.dry_run)
    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    for sid, status in failures:
        print(f"FAILED {sid} ({approved.get(sid, '?')}): {status}", file=sys.stderr)
    if args.dry_run:
        print(f"dry run: {len(approved) - len(failures)} of {len(approved)} fetched, nothing written")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
