"""
Unit tests for scripts/bump_version.py

Covers:
  - VERSION_MANIFEST.json update
  - Android build.gradle.kts update (versionName and versionCode)
  - spin.toml updates
  - pyproject.toml update
  - web/package.json update
  - ROADMAP.md version label update
  - Skips gracefully when files are absent
  - CLI __main__ guard (missing args → exit 1)
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# The script lives in scripts/ — import via sys.path manipulation
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import bump_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def root(tmp_path, monkeypatch):
    """Make bump_version see tmp_path as the repo root."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(bump_version, "__file__", str(scripts_dir / "bump_version.py"))
    return tmp_path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# ---------------------------------------------------------------------------
# VERSION_MANIFEST.json
# ---------------------------------------------------------------------------

class TestVersionManifest:
    def test_updates_total_version_and_components(self, root):
        manifest = root / "VERSION_MANIFEST.json"
        _write(manifest, json.dumps({
            "total_version": "0.0.1",
            "release_date": "2020-01-01",
            "components": {
                "python": {"version": "0.0.1"},
                "android": {"version": "0.0.1"},
            }
        }))
        bump_version.bump_version("1.2.3")
        data = json.loads(manifest.read_text())
        assert data["total_version"] == "1.2.3"
        assert data["components"]["python"]["version"] == "1.2.3"
        assert data["components"]["android"]["version"] == "1.2.3"

    def test_updates_release_date(self, root):
        manifest = root / "VERSION_MANIFEST.json"
        _write(manifest, json.dumps({
            "total_version": "0.0.1",
            "release_date": "2000-01-01",
            "components": {}
        }))
        bump_version.bump_version("2.0.0")
        data = json.loads(manifest.read_text())
        # date must be a valid YYYY-MM-DD string (today)
        from datetime import datetime
        expected = datetime.now().strftime("%Y-%m-%d")
        assert data["release_date"] == expected

    def test_skips_when_absent(self, root):
        # no manifest file — should not raise
        bump_version.bump_version("9.9.9")


# ---------------------------------------------------------------------------
# Android build.gradle.kts
# ---------------------------------------------------------------------------

class TestAndroidGradle:
    _GRADLE_TEMPLATE = (
        'versionName = "0.1.0"\n'
        'versionCode = 10\n'
        'someOtherField = "untouched"\n'
    )

    def _gradle_path(self, root: Path) -> Path:
        return root / "mecris-go-project" / "app" / "build.gradle.kts"

    def test_updates_version_name(self, root):
        path = self._gradle_path(root)
        _write(path, self._GRADLE_TEMPLATE)
        bump_version.bump_version("1.5.0")
        content = path.read_text()
        assert 'versionName = "1.5.0"' in content

    def test_updates_version_code_when_provided(self, root):
        path = self._gradle_path(root)
        _write(path, self._GRADLE_TEMPLATE)
        bump_version.bump_version("1.5.0", version_code=42)
        content = path.read_text()
        assert "versionCode = 42" in content

    def test_does_not_update_version_code_when_omitted(self, root):
        path = self._gradle_path(root)
        _write(path, self._GRADLE_TEMPLATE)
        bump_version.bump_version("1.5.0")
        content = path.read_text()
        assert "versionCode = 10" in content

    def test_leaves_other_fields_untouched(self, root):
        path = self._gradle_path(root)
        _write(path, self._GRADLE_TEMPLATE)
        bump_version.bump_version("1.5.0")
        content = path.read_text()
        assert 'someOtherField = "untouched"' in content

    def test_skips_when_absent(self, root):
        bump_version.bump_version("1.5.0")


# ---------------------------------------------------------------------------
# spin.toml files
# ---------------------------------------------------------------------------

class TestSpinToml:
    _SPIN_TEMPLATE = 'name = "mecris"\nversion = "0.0.1"\ndescription = "test"\n'

    def test_updates_boris_fiona_spin_toml(self, root):
        path = root / "boris-fiona-walker" / "spin.toml"
        _write(path, self._SPIN_TEMPLATE)
        bump_version.bump_version("3.0.0")
        content = path.read_text()
        assert 'version = "3.0.0"' in content

    def test_updates_mecris_go_spin_toml(self, root):
        path = root / "mecris-go-spin" / "sync-service" / "spin.toml"
        _write(path, self._SPIN_TEMPLATE)
        bump_version.bump_version("3.0.0")
        content = path.read_text()
        assert 'version = "3.0.0"' in content

    def test_skips_absent_spin_tomls(self, root):
        bump_version.bump_version("3.0.0")

    def test_spin_toml_with_spaces_around_equals(self, root):
        path = root / "boris-fiona-walker" / "spin.toml"
        _write(path, 'version  =  "0.1.0"\n')
        bump_version.bump_version("4.0.0")
        content = path.read_text()
        assert 'version = "4.0.0"' in content


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------

class TestPyprojectToml:
    def test_updates_version_line(self, root):
        pyproject = root / "pyproject.toml"
        _write(pyproject, '[tool.poetry]\nname = "mecris"\nversion = "0.1.0"\n')
        bump_version.bump_version("5.0.0")
        content = pyproject.read_text()
        assert 'version = "5.0.0"' in content

    def test_does_not_match_mid_line_version(self, root):
        # only the line-start `version = "..."` should match
        pyproject = root / "pyproject.toml"
        _write(pyproject, '# version = "old"\nversion = "0.2.0"\n')
        bump_version.bump_version("6.0.0")
        content = pyproject.read_text()
        assert 'version = "6.0.0"' in content
        # comment line should be untouched (re.MULTILINE anchors ^)
        assert '# version = "old"' in content

    def test_skips_when_absent(self, root):
        bump_version.bump_version("5.0.0")


# ---------------------------------------------------------------------------
# web/package.json
# ---------------------------------------------------------------------------

class TestWebPackageJson:
    def test_updates_version_field(self, root):
        pkg = root / "web" / "package.json"
        _write(pkg, json.dumps({"name": "mecris-web", "version": "0.0.1"}, indent=2) + "\n")
        bump_version.bump_version("7.0.0")
        data = json.loads(pkg.read_text())
        assert data["version"] == "7.0.0"

    def test_preserves_other_fields(self, root):
        pkg = root / "web" / "package.json"
        _write(pkg, json.dumps({"name": "mecris-web", "version": "0.0.1", "private": True}, indent=2) + "\n")
        bump_version.bump_version("7.1.0")
        data = json.loads(pkg.read_text())
        assert data["name"] == "mecris-web"
        assert data["private"] is True

    def test_skips_when_absent(self, root):
        bump_version.bump_version("7.0.0")


# ---------------------------------------------------------------------------
# ROADMAP.md
# ---------------------------------------------------------------------------

class TestRoadmapMd:
    def test_updates_version_label(self, root):
        roadmap = root / "ROADMAP.md"
        _write(roadmap, "# Roadmap\n\n- **Version**: v0.1.0 (2020-01-01)\n\nSome text.\n")
        bump_version.bump_version("8.0.0")
        content = roadmap.read_text()
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"- **Version**: v8.0.0 ({today})" in content

    def test_skips_when_absent(self, root):
        bump_version.bump_version("8.0.0")


# ---------------------------------------------------------------------------
# CLI (__main__)
# ---------------------------------------------------------------------------

class TestCli:
    _script = str(Path(__file__).parent.parent / "scripts" / "bump_version.py")

    def test_no_args_exits_1(self):
        result = subprocess.run(
            [sys.executable, self._script],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "Usage" in result.stdout

    def test_version_arg_exits_0(self, tmp_path):
        # Run the script with a version arg in an empty tmp dir so no real files
        # are modified.  Redirect __file__ via a symlink so root resolves to
        # tmp_path rather than the real repo root.
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "bump_version.py"
        fake_script.symlink_to(self._script)
        result = subprocess.run(
            [sys.executable, str(fake_script), "9.9.9"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "Successfully bumped" in result.stdout
