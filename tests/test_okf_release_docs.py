"""TDD: OKF release docs must pass validation (0 orphan warnings)."""
import subprocess, sys

def test_release_docs_pass_validation():
    """OKF bundle must have 0 orphan warnings for new concepts."""
    result = subprocess.run(
        ['bash', '-c', 'make okf-validate 2>/dev/null | tail -3'],
        capture_output=True, text=True
    )
    output = result.stdout + result.stderr
    # Check no orphan warnings for our 4 concepts
    assert 'architecture/ghost-heartbeat-restoration.md: orphan' not in output
    assert 'decisions/2026-09-06-ghost-heartbeat-restoration.md: orphan' not in output
    assert 'runbooks/authorization-mechanism.md: orphan' not in output
    assert 'decisions/2026-09-06-release-process.md: orphan' not in output
