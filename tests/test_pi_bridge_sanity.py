"""
Sanity tests for the Pi + Mecris bridge integration.
"""
import pytest


class TestPiBridgeSanity:
    """Basic smoke tests that the Pi extension is properly structured."""

    def test_extension_file_exists(self):
        """Verify the Pi extension TypeScript file exists."""
        import os
        ext_path = ".pi/extensions/mecris/index.ts"
        assert os.path.exists(ext_path), f"Extension file not found at {ext_path}"

    def test_extension_has_required_patterns(self):
        """Verify the extension contains expected implementation patterns."""
        with open(".pi/extensions/mecris/index.ts") as f:
            content = f.read()
        
        required_patterns = [
            "mecris_load_tools",
            "registerTool",
            "STDIO_SCRIPT",
            "session_shutdown",
        ]
        
        for pattern in required_patterns:
            assert pattern in content, f"Extension missing expected pattern: {pattern}"

    def test_extension_package_json_valid(self):
        """Verify package.json is valid JSON and has required fields."""
        import json
        with open(".pi/extensions/mecris/package.json") as f:
            pkg = json.load(f)
        
        assert "name" in pkg, "package.json missing 'name'"
        assert "dependencies" in pkg, "package.json missing 'dependencies'"
        assert "@modelcontextprotocol/sdk" in pkg["dependencies"], \
            "MCP SDK not in dependencies"

    def test_e2e_test_script_executable(self):
        """Verify the E2E test script exists and is executable."""
        import os
        import stat
        script = "tests/e2e_pi_mecris.sh"
        assert os.path.exists(script), f"E2E test script not found: {script}"
        assert os.access(script, os.X_OK), f"E2E test script not executable: {script}"

    def test_pi_bridge_docs_exist(self):
        """Verify documentation files exist."""
        import os
        docs = [
            "docs/PI_MECRIS_GUIDE.md",
            "docs/PI_HARNESS_ROADMAP.md",
            ".pi/extensions/mecris/README.md",
        ]
        for doc in docs:
            assert os.path.exists(doc), f"Documentation file not found: {doc}"

    def test_ci_workflow_configured(self):
        """Verify GitHub Actions workflow is configured."""
        import os
        workflow = ".github/workflows/e2e-pi-mecris.yml"
        assert os.path.exists(workflow), f"CI workflow not found: {workflow}"
        
        with open(workflow) as f:
            content = f.read()
        
        assert "mecris_load_tools" in content or "e2e-pi-mecris" in content, \
            "Workflow doesn't reference Pi + Mecris bridge"
