#!/usr/bin/env python3
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

def bump_version(new_version, version_code=None):
    root = Path(__file__).parent.parent
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Update VERSION_MANIFEST.json
    manifest_path = root / "VERSION_MANIFEST.json"
    if manifest_path.exists():
        print(f"Updating {manifest_path}...")
        data = json.loads(manifest_path.read_text())
        data["total_version"] = new_version
        data["release_date"] = today
        for component in data["components"].values():
            component["version"] = new_version
        manifest_path.write_text(json.dumps(data, indent=2) + "\n")

    # 2. Update Android build.gradle.kts
    android_gradle = root / "mecris-go-project/app/build.gradle.kts"
    if android_gradle.exists():
        print(f"Updating {android_gradle}...")
        content = android_gradle.read_text()
        content = re.sub(r'versionName = ".*?"', f'versionName = "{new_version}"', content)
        if version_code:
            content = re.sub(r'versionCode = \d+', f'versionCode = {version_code}', content)
        android_gradle.write_text(content)

    # 3. Update Spin manifests
    spin_manifests = [
        root / "boris-fiona-walker/spin.toml",
        root / "mecris-go-spin/sync-service/spin.toml"
    ]
    for spin_toml in spin_manifests:
        if spin_toml.exists():
            print(f"Updating {spin_toml}...")
            content = spin_toml.read_text()
            content = re.sub(r'version\s*=\s*".*?"', f'version = "{new_version}"', content)
            spin_toml.write_text(content)

    # 4. Update pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        print(f"Updating {pyproject}...")
        content = pyproject.read_text()
        content = re.sub(r'^version\s*=\s*".*?"', f'version = "{new_version}"', content, flags=re.MULTILINE)
        pyproject.write_text(content)

    # 5. Update web/package.json
    web_pkg = root / "web/package.json"
    if web_pkg.exists():
        print(f"Updating {web_pkg}...")
        data = json.loads(web_pkg.read_text())
        data["version"] = new_version
        web_pkg.write_text(json.dumps(data, indent=2) + "\n")

    # 6. Update ROADMAP.md version label
    roadmap = root / "ROADMAP.md"
    if roadmap.exists():
        print(f"Updating {roadmap}...")
        content = roadmap.read_text()
        content = re.sub(r'- \*\*Version\*\*: v.*? \(.*?\)', f'- **Version**: v{new_version} ({today})', content)
        roadmap.write_text(content)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py <new_version> [version_code]")
        sys.exit(1)
    
    v = sys.argv[1]
    vc = sys.argv[2] if len(sys.argv) > 2 else None
    bump_version(v, vc)
    print(f"Successfully bumped all components to {v}")
