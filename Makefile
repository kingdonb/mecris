.PHONY: test test-python test-rust test-all deploy-fermyon deploy-akamai deploy-all

test: test-python test-rust
	@echo "✅ All tests complete"

test-python:
	@echo "🐍 Running Python tests (pytest)"
	PYTHONPATH=. .venv/bin/pytest

test-rust:
	@echo "🦀 Running Rust tests (Boris & Fiona)"
	$(MAKE) -C boris-fiona-walker test
	@echo "🦀 Running Rust tests (Sync Service)"
	cd mecris-go-spin/sync-service && cargo test

test-all: test

deploy-fermyon:
	@echo "☁️ Deploying to Fermyon Cloud..."
	$(eval JWKS_JSON := $(shell curl -s https://metnoom.urmanac.com/.well-known/openid-configuration | jq -r .jwks_uri | xargs curl -s | jq -c .))
	cd mecris-go-spin/sync-service && spin cloud deploy --build \
		--variable cloud_provider=fermyon \
		--variable oidc_jwks_json='$(JWKS_JSON)'

deploy-akamai:
	@echo "☁️ Deploying to Akamai Functions..."
	$(eval JWKS_JSON := $(shell curl -s https://metnoom.urmanac.com/.well-known/openid-configuration | jq -r .jwks_uri | xargs curl -s | jq -c .))
	cd mecris-go-spin/sync-service && spin aka deploy --build --no-confirm \
		--variable db_url=$${NEON_DB_URL} \
		--variable neon_db_url=$${NEON_DB_URL} \
		--variable master_encryption_key=$${MASTER_ENCRYPTION_KEY} \
		--variable clozemaster_email=$${CLOZEMASTER_EMAIL} \
		--variable clozemaster_password=$${CLOZEMASTER_PASSWORD} \
		--variable twilio_account_sid=$${TWILIO_ACCOUNT_SID} \
		--variable twilio_auth_token_encrypted=$${TWILIO_AUTH_TOKEN_ENCRYPTED} \
		--variable twilio_from_number=$${TWILIO_FROM_NUMBER} \
		--variable openweather_api_key=$${OPENWEATHER_API_KEY} \
		--variable oidc_discovery_url="https://metnoom.urmanac.com/.well-known/openid-configuration" \
		--variable oidc_jwks_json='$(JWKS_JSON)' \
		--variable cloud_provider=akamai

deploy-all: deploy-fermyon deploy-akamai
	@echo "✅ Deployment to both clouds complete"
