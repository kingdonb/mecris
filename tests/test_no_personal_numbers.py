"""No personal phone numbers in tracked files (#358).

kingdonb/mecris is public. This scan reads every tracked text file and looks
for E.164-shaped strings (+ and 10 to 15 digits), the same with '+' URL-encoded
as %2B (Twilio form bodies), and bare 11-digit NANP strings (1NXXNXXXXXX, for
example a JSON key), which are checked as if written with a '+'. A match is
allowed when it:

- is a Twilio magic test number (+1500555xxxx);
- is a NANP fiction number (NXX-555-0100 to 0199);
- cannot be a dialable NANP number (+1 without exactly 10 national digits,
  an area code or exchange starting with 0 or 1, or area code 555);
- or its SHA-256 is listed in tests/fixtures/phone_allowlist_sha256.txt, which
  is how already-public business numbers pass without being repeated here.

Failures report file and line only. The scan never prints a number, so its
output is safe to paste into an issue or CI log.
"""
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO_ROOT / "tests" / "fixtures" / "phone_allowlist_sha256.txt"

E164 = re.compile(r"(?<![\w+])\+[1-9]\d{9,14}(?!\w)")
PCT_E164 = re.compile(r"%2[Bb]([1-9]\d{9,14})(?!\w)")
BARE_NANP = re.compile(r"(?<![\w+.])1[2-9]\d{2}[2-9]\d{6}(?![\w.])")
TWILIO_MAGIC = re.compile(r"1500555\d{4}")


def load_allowlist(path=ALLOWLIST):
    hashes = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        hashes.add(line.split()[0].lower())
    return hashes


def allowed_by_rule(number):
    """True when the E.164 string cannot belong to a person (see module doc)."""
    digits = number[1:]
    if TWILIO_MAGIC.fullmatch(digits):
        return True
    if digits.startswith("1"):
        national = digits[1:]
        if len(national) != 10:
            return True
        npa, nxx, line = national[:3], national[3:6], national[6:]
        if npa[0] in "01" or nxx[0] in "01" or npa == "555":
            return True
        if nxx == "555" and line.startswith("01"):
            return True
    return False


def is_allowed(number, allowlist):
    if allowed_by_rule(number):
        return True
    return hashlib.sha256(number.encode("utf-8")).hexdigest() in allowlist


def _tracked_files():
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    result = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True)
    if result.returncode != 0:
        pytest.skip("not running inside a git checkout")
    names = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [REPO_ROOT / n for n in names if n]


def candidate_numbers(line):
    """Every phone-shaped string on the line, normalised to E.164 with a '+'."""
    found = [m.group(0) for m in E164.finditer(line)]
    found += ["+" + m.group(1) for m in PCT_E164.finditer(line)]
    found += ["+" + m.group(0) for m in BARE_NANP.finditer(line)]
    return found


def find_unlisted_numbers(files, allowlist):
    """Return 'path:line' for every E.164 match that is not allowed. Never the number."""
    locations = []
    for path in files:
        try:
            data = path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            continue
        if b"\0" in data[:8192]:
            continue  # binary
        text = data.decode("utf-8", "replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(not is_allowed(n, allowlist) for n in candidate_numbers(line)):
                locations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    return locations


def test_allowlist_entries_are_sha256_hashes():
    for entry in load_allowlist():
        assert re.fullmatch(r"[0-9a-f]{64}", entry), "allowlist entries must be SHA-256 hex digests"


def test_rules_allow_test_and_fiction_numbers():
    assert allowed_by_rule("+1" + "500555" + "0006")      # Twilio magic number
    assert allowed_by_rule("+1" + "202" + "555" + "0143")  # NANP fiction range
    assert allowed_by_rule("+1" + "555" + "1234567")       # area code 555
    assert allowed_by_rule("+1" + "234567890")             # 9 national digits


def test_rules_reject_a_dialable_number():
    # Built at runtime so this file holds no dialable literal.
    candidate = "+1" + "2" * 10
    assert not allowed_by_rule(candidate)
    assert not is_allowed(candidate, set())
    assert is_allowed(candidate, {hashlib.sha256(candidate.encode()).hexdigest()})


def test_no_personal_numbers_in_tracked_files():
    locations = find_unlisted_numbers(_tracked_files(), load_allowlist())
    assert locations == [], (
        f"{len(locations)} line(s) hold a phone number that is not a test, fiction or "
        "allowlisted number. Replace it with a Twilio magic number (+1500555xxxx), or, for an "
        "already-public business number, add its SHA-256 to tests/fixtures/phone_allowlist_sha256.txt."
    )


def _scan_one(tmp_path, monkeypatch, text):
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", tmp_path)
    f = tmp_path / "sample.txt"
    f.write_text(text, encoding="utf-8")
    return find_unlisted_numbers([f], set())


def test_scan_catches_percent_encoded_plus(tmp_path, monkeypatch):
    # Twilio form bodies and webhook vectors carry '+' as %2B.
    dialable = "1" + "2" * 10
    assert _scan_one(tmp_path, monkeypatch, "From=%2B" + dialable + "&Body=hi\n") == ["sample.txt:1"]
    assert _scan_one(tmp_path, monkeypatch, "To=whatsapp%3A%2b" + dialable + "\n") == ["sample.txt:1"]


def test_scan_catches_bare_nanp_digits(tmp_path, monkeypatch):
    # The bare 1NXXNXXXXXX form, e.g. a JSON key, with no '+' in front.
    dialable = "1" + "2" * 10
    assert _scan_one(tmp_path, monkeypatch, '{"' + dialable + '": {"sent": 1}}\n') == ["sample.txt:1"]


def test_scan_ignores_bare_digits_that_are_not_dialable(tmp_path, monkeypatch):
    lines = [
        "ts=1700000000000",              # epoch millis, 13 digits
        "id 1" + "0" * 10,                # exchange starts with 0
        "v=1.2" + "2" * 10,               # part of a decimal
        "magic " + "1500555" + "0006",    # Twilio magic number
        "fiction " + "1202555" + "0143",  # NANP fiction range
    ]
    assert _scan_one(tmp_path, monkeypatch, "\n".join(lines) + "\n") == []
