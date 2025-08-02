#!/bin/bash
# """
# Mecris MCP Server Launch Script
# Safe server startup with process management
# """

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
VENV_PATH="$PYTHON_DIR/venv"
PID_FILE="$SCRIPT_DIR/mecris.pid"
LOG_FILE="$SCRIPT_DIR/mecris.log"
HEALTH_URL="http://127.0.0.1:8000/health"
MAX_WAIT_TIME=30  # seconds

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Check if server is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log "Server already running with PID $pid"
            return 0
        else
            warn "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi
    return 1
}

# Health check with retry
wait_for_health() {
    log "Waiting for server to be healthy..."
    local attempts=0
    while [ $attempts -lt $MAX_WAIT_TIME ]; do
        if curl -s -f "$HEALTH_URL" >/dev/null 2>&1; then
            log "Server is healthy and ready!"
            return 0
        fi
        sleep 1
        ((attempts++))
        echo -n "."
    done
    echo
    error "Server failed to become healthy within ${MAX_WAIT_TIME}s"
    return 1
}

# Cleanup function
cleanup() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log "Stopping server (PID: $pid)..."
            kill -TERM "$pid"
            # Wait for graceful shutdown
            local count=0
            while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
                sleep 1
                ((count++))
            done
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                warn "Force killing server..."
                kill -KILL "$pid"
            fi
        fi
        rm -f "$PID_FILE"
    fi
}

# Set trap for cleanup
#trap cleanup EXIT INT TERM

# Main execution
main() {
    log "Starting Mecris MCP Server..."
    
    # Check if already running
    if check_running; then
        exit 0
    fi
    
    # Validate environment
    if [ ! -d "$VENV_PATH" ]; then
        error "Virtual environment not found at $VENV_PATH"
        error "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
    
    if [ ! -f "$PYTHON_DIR/start_server.py" ]; then
        error "start_server.py not found in $PYTHON_DIR"
        exit 1
    fi
    
    # Activate virtual environment and start server
    log "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    
    # Start server in background
    log "Starting server process..."
    export SKIP_HEALTH_PROMPT=true  # Skip interactive health check prompt
    python "$PYTHON_DIR/start_server.py" >> "$LOG_FILE" 2>&1 &
    local server_pid=$!
    
    # Save PID
    echo "$server_pid" > "$PID_FILE"
    log "Server started with PID: $server_pid"
    
    # Wait for health check
    if wait_for_health; then
        log "Mecris MCP Server is running successfully!"
        log "Health endpoint: $HEALTH_URL"
        log "PID file: $PID_FILE"
        log "Log file: $LOG_FILE"
        return 0
    else
        error "Server startup failed"
        cleanup
        return 1
    fi
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
