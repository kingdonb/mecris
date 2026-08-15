#!/usr/bin/env bash
# Mecris Akamai Deployment Script
# Single command deployment with ALL required variables.
# Source this from the project root: ./mecris-go-spin/sync-service/deploy-akamai.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}=== Mecris Akamai Deployment ===${NC}"
echo "Project root: $PROJECT_ROOT"

# Load environment from project .env
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    echo "Loading $PROJECT_ROOT/.env"
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo -e "${RED}ERROR: $PROJECT_ROOT/.env not found${NC}"
    exit 1
fi

# Validate required variables
REQUIRED_VARS=(
    "NEON_DB_URL"
    "MASTER_ENCRYPTION_KEY"
    "CLOZEMASTER_EMAIL"
    "CLOZEMASTER_PASSWORD"
    "TWILIO_ACCOUNT_SID"
    "TWILIO_AUTH_TOKEN"
    "OPENWEATHER_API_KEY"
)

echo -e "${YELLOW}Validating required environment variables...${NC}"
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo -e "${RED}ERROR: $var is not set${NC}"
        exit 1
    else
        echo "  ✓ $var"
    fi
done

# Encrypt Twilio auth token
echo -e "${YELLOW}Encrypting Twilio auth token...${NC}"
cd "$PROJECT_ROOT"
TWILIO_AUTH_TOKEN_ENCRYPTED=$(python3 -c "
import os
from services.encryption_service import EncryptionService
es = EncryptionService(os.getenv('MASTER_ENCRYPTION_KEY'))
print(es.encrypt(os.getenv('TWILIO_AUTH_TOKEN')))
")
echo "  ✓ Encrypted"

# Pocket ID JWKS (from private network - metnoom.urmanac.com on Tailscale)
OIDC_JWKS_JSON='{"keys":[{"alg":"RS256","e":"AQAB","kid":"tmUpnrhx6gk","kty":"RSA","n":"vqLb33vkC8oZ7NDdlcBfBztPOAue3ZWrMDNhk9fBU2xrX6WTiAofqGDe_JJDCywJfEyDY-ecfQEXc5pph4v9R5xRiGhel4hLfcdcUTV7FH6MehaufcTREh_khCuAhyMOvUNlhw63mTY0yDpmaHubkh8vyhJUvmzBxr1ZR2snnrbas9q_ASvhKBeinFiAwXYH7Jf8I6C7E5LjP4BO4_ft4P2KBdspKSSREgln_i-ntZCt0UgLgDcS5coNGrz8hw-3NLUKAgHG_5GFXKSuibTV86Esk6MSYSgtKdHLM4O59Hgyz4CPFI8s47jtsLbbpuo8nq-WHU1PtQoTE1IayAD0tQ","use":"sig"}]}'

# Twilio WhatsApp Template SID (Default to approved urgency alert v2 if unset)
TWILIO_WHATSAPP_TEMPLATE_SID="${TWILIO_WHATSAPP_TEMPLATE_SID:-HX638b7f9403e04c8fa880370f1b7a9ba1}"

# Deploy
echo -e "${YELLOW}Deploying to Akamai (Production WhatsApp Delivery Mode)...${NC}"
cd "$SCRIPT_DIR"

spin aka deploy --build --no-confirm --skip-readiness-check \
  --variable db_url="$NEON_DB_URL" \
  --variable neon_db_url="$NEON_DB_URL" \
  --variable master_encryption_key="$MASTER_ENCRYPTION_KEY" \
  --variable internal_api_key="test-internal-key" \
  --variable clozemaster_email="$CLOZEMASTER_EMAIL" \
  --variable clozemaster_password="$CLOZEMASTER_PASSWORD" \
  --variable twilio_account_sid="$TWILIO_ACCOUNT_SID" \
  --variable twilio_auth_token_encrypted="$TWILIO_AUTH_TOKEN_ENCRYPTED" \
  --variable twilio_from_number="+15744757115" \
  --variable twilio_whatsapp_template_sid="$TWILIO_WHATSAPP_TEMPLATE_SID" \
  --variable openweather_api_key="$OPENWEATHER_API_KEY" \
  --variable oidc_jwks_json="$OIDC_JWKS_JSON" \
  --variable cloud_provider="akamai"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo "Test with: curl -H \"Authorization: Bearer \$TOKEN\" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/health"