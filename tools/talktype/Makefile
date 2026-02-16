# Makefile for TalkType
# Located in mecris/tools/talktype/

.PHONY: all server client stop-server status help

# Variables
TALKTYPE_REPO := talktype-repo
VENV_ACTIVATE := ./.venv/bin/activate
WHISPER_SERVER_PY := whisper_server.py
TALKTYPE_PY := talktype.py
VENV_PYTHON := ./.venv/bin/python
WHISPER_MODEL ?= small
WHISPER_DEVICE ?= cpu
WHISPER_PORT ?= 8002

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
	@echo "  $(GREEN)server$(RESET)       - Start the Whisper API server in the background (model: $(WHISPER_MODEL), device: $(WHISPER_DEVICE))"
	@echo "                   Set WHISPER_MODEL=medium/large-v3, WHISPER_DEVICE=mps/cpu/cuda to override."
	@echo "                   Example: make server WHISPER_MODEL=medium WHISPER_DEVICE=mps"
	@echo "  $(GREEN)client$(RESET)       - Run the TalkType client (connects to local server)"
	@echo "  $(GREEN)stop-server$(RESET)  - Stop the Whisper API server"
	@echo "  $(GREEN)status$(RESET)       - Check if the Whisper API server is running"
	@echo "  $(GREEN)help$(RESET)         - Show this help message"
	@echo ""
	@echo "$(YELLOW)Note: For macOS, ensure Accessibility permissions are granted to your terminal. $(RESET)"
	@echo "$(YELLOW)First run of 'make server' will download the chosen Whisper model. $(RESET)"

server:
	@echo "$(GREEN)Starting Whisper API server (model: $(WHISPER_MODEL), device: $(WHISPER_DEVICE)) on port $(WHISPER_PORT)...$(RESET)"
	@echo "$(YELLOW)Output is redirected to talktype_whisper_server.log$(RESET)"
	@cd $(TALKTYPE_REPO) && { \
		nohup $(VENV_PYTHON) $(WHISPER_SERVER_PY) --model $(WHISPER_MODEL) --device $(WHISPER_DEVICE) --port $(WHISPER_PORT) &> ../talktype_whisper_server.log & \
		echo $$! > ../talktype_whisper_server.pid; \
	}
	@sleep 2
	@echo "$(GREEN)Whisper server started. Check talktype_whisper_server.log for details. $(RESET)"
	@echo "$(YELLOW)PID: $$(cat ../talktype_whisper_server.pid)$(RESET)"

client:
	@echo "$(GREEN)Running TalkType client, connecting to server on port $(WHISPER_PORT)...$(RESET)"
	@cd $(TALKTYPE_REPO) && \
	source $(VENV_ACTIVATE) && \
	python $(TALKTYPE_PY) --api http://localhost:$(WHISPER_PORT)/transcribe

stop-server:
	@echo "$(YELLOW)Attempting to stop Whisper API server...$(RESET)"
	@if [ -f "talktype_whisper_server.pid" ]; then 
		kill $$(cat talktype_whisper_server.pid); 
		rm talktype_whisper_server.pid; 
		echo "$(GREEN)Whisper API server stopped.$(RESET)"; 
	else 
		echo "$(YELLOW)No PID file found. Server might not be running or PID file is missing.$(RESET)"; 
		pkill -f "whisper_server.py"; 
		echo "$(YELLOW)Attempted to kill any running whisper_server.py processes directly.$(RESET)"; 
	fi

status:
	@echo "$(BLUE)Checking Whisper API server status...$(RESET)"
	@if [ -f "talktype_whisper_server.pid" ]; then 
		PID=$$(cat talktype_whisper_server.pid); 
		if ps -p $$PID > /dev/null; then 
			echo "$(GREEN)Whisper API server is running (PID: $$PID).$(RESET)"; 
		else 
			echo "$(RED)Whisper API server PID file found, but process not running. Removing PID file.$(RESET)"; 
			rm talktype_whisper_server.pid; 
		fi; 
	else 
		echo "$(YELLOW)No PID file found. Checking actively running processes...$(RESET)"; 
		if pgrep -f "whisper_server.py" > /dev/null; then 
			echo "$(GREEN)A whisper_server.py process is running (PID: $$(pgrep -f "whisper_server.py")).$(RESET)"; 
		else 
			echo "$(RED)Whisper API server is NOT running.$(RESET)"; 
		fi; 
	fi
	@if curl -s http://localhost:$(WHISPER_PORT)/health > /dev/null; then 
		echo "$(GREEN)Whisper API server health endpoint is responsive.$(RESET)"; 
	else 
		echo "$(RED)Whisper API server health endpoint is NOT responsive.$(RESET)"; 
	fi
