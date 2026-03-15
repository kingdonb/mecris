#!/bin/bash
# Mecris Release Suite Verification Script
# Automates checks across Android, Spin, and Python components.

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 Starting Mecris Suite Verification..."

# 1. Python Components
echo -e "\n🔍 Checking Python MCP & Scrapers..."
uv run python usage_tracker.py > /dev/null
echo -e "${GREEN}✅ UsageTracker: NEON CONNECTED${NC}"
uv run python groq_odometer_tracker.py > /dev/null
echo -e "${GREEN}✅ GroqOdometer: NEON CONNECTED${NC}"

# 2. Rust/Spin Component
echo -e "\n🔍 Checking Spin Backend..."
cd boris-fiona-walker
cargo test --quiet
echo -e "${GREEN}✅ Spin Backend: TESTS PASSED${NC}"
cd ..

# 3. Android Component
echo -e "\n🔍 Checking Android Build..."
export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$PATH"
cd mecris-go-project
./gradlew assembleDebug -q
echo -e "${GREEN}✅ Android: BUILD SUCCESSFUL${NC}"
cd ..

# 4. Version Sync
echo -e "\n🔍 Verifying Version Manifest..."
if [ -f "VERSION_MANIFEST.json" ]; then
    VERSION=$(grep "total_version" VERSION_MANIFEST.json | cut -d '"' -f 4)
    echo -e "${GREEN}✅ Manifest Found: Version $VERSION${NC}"
else
    echo -e "${RED}❌ Manifest Missing!${NC}"
    exit 1
fi

echo -e "\n${GREEN}✨ ALL SYSTEMS NOMINAL. READY FOR RELEASE. ✨${NC}"
