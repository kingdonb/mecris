# Boris & Fiona Walk Reminder Makefile
# 
# This Makefile provides convenient shortcuts for all development tasks.
# Environment variables are managed by direnv (.envrc file).
#
# Prerequisites:
# - Rust installed: https://rustup.rs/
# - Spin CLI installed: https://developer.fermyon.com/spin/install
# - direnv installed: https://direnv.net/

.PHONY: help dev test build clean deploy status stop watch install-deps check-env

# Default target
.DEFAULT_GOAL := help

# Colors for pretty output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

## Help: Show this help message
help:
	@echo "$(BLUE)🐕 Boris & Fiona Walk Reminder - Development Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  make dev          - Start Spin app for development (with auto-reload)"
	@echo "  make run          - Start Spin app (simple, blocks terminal)"
	@echo "  make watch        - Start Spin watch (background process with &)"
	@echo "  make stop         - Stop any running Spin processes"
	@echo ""
	@echo "$(GREEN)Testing:$(RESET)"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-int     - Run integration tests only"
	@echo "  make test-watch   - Run tests in watch mode (re-run on changes)"
	@echo ""
	@echo "$(GREEN)API Testing:$(RESET)"
	@echo "  make api-test     - Test the /check endpoint"
	@echo "  make web-test     - Open web frontend in browser"
	@echo "  make status       - Show current system status"
	@echo ""
	@echo "$(GREEN)Build & Deploy:$(RESET)"
	@echo "  make build        - Build the WASM component"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make deploy       - Deploy to Spin Cloud (requires setup)"
	@echo ""
	@echo "$(GREEN)Setup & Maintenance:$(RESET)"
	@echo "  make install-deps - Install development dependencies"
	@echo "  make check-env    - Verify environment setup"
	@echo "  make lint         - Run code formatting and linting"
	@echo ""
	@echo "$(YELLOW)💡 Environment variables are managed by direnv (.envrc)$(RESET)"
	@echo "   Run 'direnv allow' to load them automatically"

## Development: Start Spin app with watch mode (recommended)
dev: check-env
	@echo "$(GREEN)🚀 Starting Boris & Fiona Walk Reminder (development mode)$(RESET)"
	@echo "   Web Frontend: http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/"
	@echo "   API Endpoint: http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/check"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	spin watch --listen $(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT) --clear

## Development: Start Spin app (simple)
run: check-env
	@echo "$(GREEN)🚀 Starting Boris & Fiona Walk Reminder$(RESET)"
	spin up --listen $(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)

## Development: Start Spin watch in background
watch: check-env
	@echo "$(GREEN)🚀 Starting Boris & Fiona Walk Reminder (background)$(RESET)"
	@echo "   Web Frontend: http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/"
	@echo "   API Endpoint: http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/check"
	@echo "   Use 'make stop' to terminate"
	spin watch --listen $(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT) --clear &
	@sleep 2
	@echo "$(GREEN)✅ Server started in background$(RESET)"

## Development: Stop any running Spin processes
stop:
	@echo "$(YELLOW)🛑 Stopping Spin processes...$(RESET)"
	@pkill -f "spin watch" || echo "No spin watch processes found"
	@pkill -f "spin up" || echo "No spin up processes found"
	@echo "$(GREEN)✅ Stopped$(RESET)"

## Testing: Run all tests
test:
	@echo "$(GREEN)🧪 Running all tests$(RESET)"
	cargo test

## Testing: Run unit tests only
test-unit:
	@echo "$(GREEN)🧪 Running unit tests$(RESET)"
	cargo test --lib

## Testing: Run integration tests only  
test-int:
	@echo "$(GREEN)🧪 Running integration tests$(RESET)"
	cargo test --test integration_tests

## Testing: Run tests in watch mode
test-watch:
	@echo "$(GREEN)🧪 Running tests in watch mode$(RESET)"
	@echo "   Tests will re-run when files change"
	@echo "   Press Ctrl+C to stop"
	@if command -v cargo-watch >/dev/null 2>&1; then \
		cargo watch -x test; \
	else \
		echo "$(YELLOW)⚠️  cargo-watch not installed. Install with: cargo install cargo-watch$(RESET)"; \
		echo "   Falling back to regular test run..."; \
		cargo test; \
	fi

## API Testing: Test the /check endpoint
api-test: check-env
	@echo "$(GREEN)🔧 Testing /check API endpoint$(RESET)"
	@if curl -s --connect-timeout 5 http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/check >/dev/null 2>&1; then \
		echo "$(GREEN)✅ Server is running$(RESET)"; \
		echo ""; \
		echo "$(BLUE)API Response:$(RESET)"; \
		curl -s -X POST http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/check | jq . || curl -X POST http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/check; \
	else \
		echo "$(RED)❌ Server not running. Start with 'make dev' or 'make watch'$(RESET)"; \
		exit 1; \
	fi

## API Testing: Open web frontend
web-test: check-env
	@echo "$(GREEN)🌐 Opening web frontend$(RESET)"
	@if curl -s --connect-timeout 5 http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/ >/dev/null 2>&1; then \
		open http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/; \
	else \
		echo "$(RED)❌ Server not running. Start with 'make dev' or 'make watch'$(RESET)"; \
		exit 1; \
	fi

## Status: Show current system status
status: check-env
	@echo "$(BLUE)📊 Boris & Fiona Walk Reminder Status$(RESET)"
	@echo ""
	@echo "$(GREEN)Environment:$(RESET)"
	@echo "  Twilio Account: $(SPIN_VARIABLE_TWILIO_ACCOUNT_SID)"
	@echo "  Weather API Key: $(SPIN_VARIABLE_OPENWEATHER_API_KEY)"
	@echo "  Local Server: http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)"
	@echo ""
	@echo "$(GREEN)Processes:$(RESET)"
	@if pgrep -f "spin watch" >/dev/null 2>&1; then \
		echo "  ✅ Spin watch running (PID: $$(pgrep -f 'spin watch'))"; \
	elif pgrep -f "spin up" >/dev/null 2>&1; then \
		echo "  ✅ Spin up running (PID: $$(pgrep -f 'spin up'))"; \
	else \
		echo "  ❌ No Spin processes running"; \
	fi
	@echo ""
	@echo "$(GREEN)Server Health:$(RESET)"
	@if curl -s --connect-timeout 5 http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/ >/dev/null 2>&1; then \
		echo "  ✅ Server responding on port $(SPIN_LOCAL_PORT)"; \
	else \
		echo "  ❌ Server not responding"; \
	fi

## Build: Build the WASM component
build:
	@echo "$(GREEN)🏗️  Building WASM component$(RESET)"
	spin build

## Build: Clean build artifacts
clean:
	@echo "$(YELLOW)🧹 Cleaning build artifacts$(RESET)"
	cargo clean
	@rm -rf .spin/logs/ 2>/dev/null || true
	@echo "$(GREEN)✅ Cleaned$(RESET)"

## Deploy: Deploy to Spin Cloud
deploy: check-env build
	@echo "$(GREEN)🚀 Deploying to Spin Cloud$(RESET)"
	@if [ -z "$(SPIN_CLOUD_APP_NAME)" ]; then \
		echo "$(RED)❌ SPIN_CLOUD_APP_NAME not set in .envrc$(RESET)"; \
		echo "   Add 'export SPIN_CLOUD_APP_NAME=\"your-app-name\"' to .envrc"; \
		exit 1; \
	fi
	@echo "   App Name: $(SPIN_CLOUD_APP_NAME)"
	spin deploy

## Setup: Install development dependencies
install-deps:
	@echo "$(GREEN)📦 Installing development dependencies$(RESET)"
	@echo ""
	@echo "$(BLUE)Checking Rust...$(RESET)"
	@if command -v rustc >/dev/null 2>&1; then \
		echo "  ✅ Rust $(shell rustc --version)"; \
	else \
		echo "  ❌ Rust not installed. Install from https://rustup.rs/"; \
		exit 1; \
	fi
	@echo ""
	@echo "$(BLUE)Checking Spin CLI...$(RESET)"
	@if command -v spin >/dev/null 2>&1; then \
		echo "  ✅ Spin CLI $(shell spin --version)"; \
	else \
		echo "  ❌ Spin CLI not installed. Install from https://developer.fermyon.com/spin/install"; \
		exit 1; \
	fi
	@echo ""
	@echo "$(BLUE)Checking direnv...$(RESET)"
	@if command -v direnv >/dev/null 2>&1; then \
		echo "  ✅ direnv $(shell direnv version)"; \
	else \
		echo "  ❌ direnv not installed. Install with: brew install direnv"; \
		echo "     Then add to shell: echo 'eval \"\$$(direnv hook zsh)\"' >> ~/.zshrc"; \
		exit 1; \
	fi
	@echo ""
	@echo "$(BLUE)Installing Rust tools...$(RESET)"
	@cargo install cargo-watch 2>/dev/null || echo "  ℹ️  cargo-watch already installed"
	@echo ""
	@echo "$(GREEN)✅ Dependencies ready!$(RESET)"
	@echo "   Run 'direnv allow' to load environment variables"

## Setup: Check environment setup
check-env:
	@if [ -z "$(SPIN_VARIABLE_TWILIO_ACCOUNT_SID)" ] || [ "$(SPIN_VARIABLE_TWILIO_ACCOUNT_SID)" = "test" ]; then \
		echo "$(YELLOW)⚠️  Using test Twilio credentials$(RESET)"; \
		echo "   Update .envrc with real values for SMS sending"; \
	fi

## Lint: Format and lint code
lint:
	@echo "$(GREEN)✨ Formatting and linting code$(RESET)"
	cargo fmt
	cargo clippy -- -D warnings

# Internal: Check if server is running
_check-server:
	@curl -s --connect-timeout 5 http://$(SPIN_LOCAL_HOST):$(SPIN_LOCAL_PORT)/ >/dev/null 2>&1