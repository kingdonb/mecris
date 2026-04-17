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
	cd mecris-go-spin/sync-service && spin cloud deploy --build

deploy-akamai:
	@echo "☁️ Deploying to Akamai Functions..."
	cd mecris-go-spin/sync-service && spin aka deploy --build --no-confirm

deploy-all: deploy-fermyon deploy-akamai
	@echo "✅ Deployment to both clouds complete"
