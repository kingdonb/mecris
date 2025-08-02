#!/bin/bash
"""
Mecris MCP Server Shutdown Script
Graceful server shutdown with cleanup
"""

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mecris.pid"
LOG_FILE="$SCRIPT_DIR/mecris.log"
HEALTH_URL="http://127.0.0.1:8000/health"

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

# Check if server is running
check_running() {
    if [ ! -f "$PID_FILE" ]; then
        log "No PID file found - server may not be running"
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    if ! kill -0 "$pid" 2>/dev/null; then
        warn "Process $pid not found - removing stale PID file"
        rm -f "$PID_FILE"
        return 1
    fi
    
    return 0
}

# Graceful shutdown
shutdown_server() {
    if ! check_running; then
        log "Server is not running"
        return 0
    fi
    
    local pid=$(cat "$PID_FILE")
    log "Shutting down Mecris MCP Server (PID: $pid)..."
    
    # Send SIGTERM for graceful shutdown
    if kill -TERM "$pid" 2>/dev/null; then
        log "Sent SIGTERM to process $pid"
        
        # Wait for graceful shutdown (up to 15 seconds)
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 15 ]; do
            sleep 1
            ((count++))
            echo -n "."
        done
        echo
        
        # Check if process is still running
        if kill -0 "$pid" 2>/dev/null; then
            warn "Process did not shut down gracefully, sending SIGKILL..."
            if kill -KILL "$pid" 2>/dev/null; then
                log "Process forcefully terminated"
            else
                error "Failed to kill process $pid"
                return 1
            fi
        else
            log "Server shut down gracefully"
        fi
    else
        error "Failed to send SIGTERM to process $pid"
        return 1
    fi
    
    # Clean up PID file
    rm -f "$PID_FILE"
    log "Cleanup completed"
    return 0
}

# Force kill all related processes
force_cleanup() {
    log "Performing force cleanup..."
    
    # Kill any python processes running our server
    local pids=$(pgrep -f "start_server.py" || true)
    if [ -n "$pids" ]; then
        warn "Force killing remaining server processes: $pids"
        echo "$pids" | xargs -r kill -KILL
    fi
    
    # Kill any uvicorn processes on our port
    local uvicorn_pids=$(lsof -ti:8000 || true)
    if [ -n "$uvicorn_pids" ]; then
        warn "Force killing processes on port 8000: $uvicorn_pids"
        echo "$uvicorn_pids" | xargs -r kill -KILL
    fi
    
    # Remove PID file
    rm -f "$PID_FILE"
    log "Force cleanup completed"
}

# Main execution
main() {
    case "${1:-}" in
        --force|-f)
            force_cleanup
            ;;
        --status|-s)
            if check_running; then
                local pid=$(cat "$PID_FILE")
                log "Server is running with PID: $pid"
                if curl -s -f "$HEALTH_URL" >/dev/null 2>&1; then
                    log "Health check: OK"
                else
                    warn "Health check: FAILED"
                fi
            else
                log "Server is not running"
            fi
            ;;
        *)
            shutdown_server
            ;;
    esac
}

# Help text
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Mecris MCP Server Shutdown Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  (no args)     Graceful shutdown"
    echo "  --force, -f   Force kill all server processes"
    echo "  --status, -s  Check server status"
    echo "  --help, -h    Show this help"
    exit 0
fi

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi