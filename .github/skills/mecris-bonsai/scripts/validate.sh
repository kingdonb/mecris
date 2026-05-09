#!/bin/bash

###########################################
# Part of Kingdon Skills - mecris-bonsai
###########################################
# Validates project health and context hygiene

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Mecris Bonsai Health Validation ==="
echo ""

# Step 1: Check Context Hygiene
echo "Step 1: Checking Context Hygiene in TDG.md..."
if grep -q "\-v" TDG.md; then
    echo -e "${RED}✗ FAILURE: Verbose flag (-v) found in TDG.md. High risk of context burn.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ No verbose flags found in test commands.${NC}"
fi

# Step 2: Check Backlog Consolidation
echo "Step 2: Checking Backlog Consolidation..."
if [ -f "ACTIVE_BACKLOG.md" ]; then
    echo -e "${GREEN}✓ ACTIVE_BACKLOG.md exists.${NC}"
else
    echo -e "${YELLOW}! WARNING: ACTIVE_BACKLOG.md missing. Project trunk may be unshaped.${NC}"
fi

# Step 3: Verify Android Build Environment
echo "Step 3: Verifying Android Build Environment..."
export PATH="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin:$PATH"
if command -v java >/dev/null 2>&1; then
    JAVA_VER=$(java -version 2>&1 | head -n 1)
    echo -e "${GREEN}✓ Java found: $JAVA_VER${NC}"
else
    echo -e "${RED}✗ FAILURE: Android Studio JBR not found in expected path.${NC}"
    exit 1
fi

echo ""
echo "=== Summary ==="
echo -e "${GREEN}✓ Workspace satisfies Bonsai Shaping standards.${NC}"
exit 0
