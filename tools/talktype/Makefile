# Makefile for TalkType
# Located in mecris/tools/talktype/

.PHONY: all server client stop-server status help setup logs clean check-deps sync-upstream

# Variables
TALKTYPE_REPO := talktype-repo
VENV_DIR := .venv
VENV_ACTIVATE := $(VENV_DIR)/bin/activate
VENV_PYTHON := $(VENV_DIR)/bin/python
WHISPER_SERVER_PY := whisper_server.py
TALKTYPE_PY := talktype.py

# Default configuration
WHISPER_MODEL ?= medium
WHISPER_DEVICE ?= auto
WHISPER_PORT ?= 8002
WHISPER_COMPUTE ?= auto

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[39m

# Default target
all: help

help:
	@echo "$(BLUE)TalkType Management Commands$(RESET)"
	@echo ""
	@echo "  $(GREEN)setup$(RESET)         - Initialize venv and install dependencies"
	@echo "  $(GREEN)server$(RESET)        - Start the Whisper API server in the background"
	@echo "                   Set WHISPER_MODEL=medium/large-v3, WHISPER_DEVICE=cpu/cuda to override."
	@echo "                   Example: make server WHISPER_MODEL=medium WHISPER_DEVICE=auto"
	@echo "  $(GREEN)client$(RESET)        - Run the TalkType client (connects to local server)"
	@echo "                   Use --setup flag for interactive configuration."
	@echo "  $(GREEN)stop-server$(RESET)   - Stop the Whisper API server"
	@echo "  $(GREEN)status$(RESET)        - Check if the Whisper API server is running"
	@echo "  $(GREEN)logs$(RESET)          - Tail the whisper server logs"
	@echo "  $(GREEN)clean$(RESET)         - Remove PID files and logs"
	@echo "  $(GREEN)sync-upstream$(RESET) - Sync talktype-repo with upstream main"
	@echo "  $(GREEN)help$(RESET)          - Show this help message"
	@echo ""
	@echo "$(YELLOW)Note: For macOS, ensure Accessibility permissions are granted to your terminal. $(RESET)"
	@echo "$(YELLOW)First run of 'make server' will download the chosen Whisper model. $(RESET)"

check-deps:
	@command -v uv >/dev/null 2>&1 || { echo "$(RED)Error: 'uv' is not installed. $(RESET)"; exit 1; }
	@command -v ffmpeg >/dev/null 2>&1 || { echo "$(RED)Error: 'ffmpeg' is not installed. (Required for audio processing)$(RESET)"; exit 1; }

setup: check-deps
	@echo "$(GREEN)Initializing virtual environment...$(RESET)"
	@uv venv $(VENV_DIR)
	@echo "$(GREEN)Installing dependencies from $(TALKTYPE_REPO)/requirements.txt...$(RESET)"
	@uv add -r $(TALKTYPE_REPO)/requirements.txt
	@echo "$(GREEN)Setup complete.$(RESET)"

server:
	@echo "$(GREEN)Starting Whisper API server (model: $(WHISPER_MODEL), device: $(WHISPER_DEVICE), compute: $(WHISPER_COMPUTE)) on port $(WHISPER_PORT)...$(RESET)"
	@echo "$(YELLOW)Output is redirected to talktype_whisper_server.log$(RESET)"
	@cd $(TALKTYPE_REPO) && { \
		nohup ../$(VENV_PYTHON) $(WHISPER_SERVER_PY) --model $(WHISPER_MODEL) --device $(WHISPER_DEVICE) --port $(WHISPER_PORT) --compute $(WHISPER_COMPUTE) &> ../talktype_whisper_server.log & \
		echo $$! > ../talktype_whisper_server.pid; \
	}
	@sleep 2
	@echo "$(GREEN)Whisper server started. Check talktype_whisper_server.log for details. $(RESET)"
	@PID=$$(cat talktype_whisper_server.pid); echo "$(YELLOW)PID: $$PID$(RESET)"

client:
	@echo "$(GREEN)Running TalkType client, connecting to server on port $(WHISPER_PORT)...$(RESET)"
	@cd $(TALKTYPE_REPO) && \
	../$(VENV_PYTHON) $(TALKTYPE_PY) --api http://localhost:$(WHISPER_PORT)/transcribe --minimal

sync-upstream:
	@echo "$(YELLOW)Syncing talktype-repo with upstream...$(RESET)"
	@cd $(TALKTYPE_REPO) && git fetch upstream && git checkout main && git reset --hard upstream/main
	@echo "$(GREEN)Sync complete. New HEAD: $$(cd $(TALKTYPE_REPO) && git rev-parse HEAD)$(RESET)"

logs:
	@tail -f talktype_whisper_server.log

stop-server:
	@echo "$(YELLOW)Attempting to stop Whisper API server...$(RESET)"
	@if [ -f "talktype_whisper_server.pid" ]; then \
		PID=$$(cat talktype_whisper_server.pid); \
		if ps -p $$PID > /dev/null; then \
			echo "$(GREEN)Stopping Whisper API server (PID: $$PID)...$(RESET)"; \
			kill $$PID; \
			rm talktype_whisper_server.pid; \
			echo "$(GREEN)Whisper API server stopped.$(RESET)"; \
		else \
			echo "$(YELLOW)PID file found, but no matching process is running. Removing stale PID file.$(RESET)"; \
			rm talktype_whisper_server.pid; \
		fi; \
	else \
		echo "$(YELLOW)No PID file found. Checking for running processes...$(RESET)"; \
		if pgrep -f "whisper_server.py" > /dev/null; then \
			pkill -f "whisper_server.py"; \
			echo "$(YELLOW)Attempted to kill any running whisper_server.py processes directly.$(RESET)"; \
		else \
			echo "$(GREEN)No running whisper_server.py process found.$(RESET)"; \
		fi; \
	fi

status:
	@echo "$(BLUE)Checking Whisper API server status...$(RESET)"
	@if [ -f "talktype_whisper_server.pid" ]; then \
		PID=$$(cat talktype_whisper_server.pid); \
		if ps -p $$PID > /dev/null; then \
			echo "$(GREEN)Whisper API server is running (PID: $$PID).$(RESET)"; \
		else \
			echo "$(RED)Whisper API server PID file found, but process not running. Removing PID file.$(RESET)"; \
			rm talktype_whisper_server.pid; \
		fi; \
	else \
		echo "$(YELLOW)No PID file found. Checking actively running processes...$(RESET)"; \
		if pgrep -f "whisper_server.py" > /dev/null; then \
			echo "$(GREEN)A whisper_server.py process is running (PID: $$(pgrep -f "whisper_server.py")).$(RESET)"; \
		else \
			echo "$(RED)Whisper API server is NOT running.$(RESET)"; \
		fi; \
	fi; \
	if curl -s http://localhost:$(WHISPER_PORT)/health > /dev/null; then \
		echo "$(GREEN)Whisper API server health endpoint is responsive.$(RESET)" && \
		curl -s http://localhost:$(WHISPER_PORT)/health | grep -o '\"device\":\"[^\"]*\"'; \
	else \
		echo "$(RED)Whisper API server health endpoint is NOT responsive.$(RESET)"; \
	fi

clean:
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	@rm -f talktype_whisper_server.pid talktype_whisper_server.log
	@echo "$(GREEN)Cleanup complete.$(RESET)"

