#!/bin/bash

# Privacy-Preserving Multi-Agent Negotiation Framework
# Start all services script

set -e

echo "=========================================="
echo "  Starting Negotiation Services"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Function to check if a port is in use
check_port() {
    lsof -i :$1 >/dev/null 2>&1
    return $?
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1

    echo -n "  Waiting for $name..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url/api/health" > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready${NC}"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}Failed${NC}"
    return 1
}

# Kill existing processes on our ports
echo "Checking for existing processes..."
for port in 8000 8001 8002 3000; do
    if check_port $port; then
        echo -e "  ${YELLOW}Port $port in use - killing process${NC}"
        lsof -ti :$port | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
done

echo ""
echo "Starting backends..."
echo ""

# Start Agent A Backend (port 8001)
echo -e "${GREEN}[1/4]${NC} Starting Agent A Backend on port 8001..."
cd "$SCRIPT_DIR/agent-backend"
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
AGENT_ID=A PORT=8001 uvicorn app.main:app --host 0.0.0.0 --port 8001 &
AGENT_A_PID=$!
deactivate

# Start Agent B Backend (port 8002)
echo -e "${GREEN}[2/4]${NC} Starting Agent B Backend on port 8002..."
cd "$SCRIPT_DIR/agent-backend"
source venv/bin/activate
AGENT_ID=B PORT=8002 uvicorn app.main:app --host 0.0.0.0 --port 8002 &
AGENT_B_PID=$!
deactivate

# Start Arena Backend (port 8000)
echo -e "${GREEN}[3/4]${NC} Starting Arena Backend on port 8000..."
cd "$SCRIPT_DIR/arena-backend"
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
ARENA_PID=$!
deactivate

# Start Frontend (port 3000)
echo -e "${GREEN}[4/4]${NC} Starting Next.js Frontend on port 3000..."
cd "$SCRIPT_DIR/frontend-next"
if [ ! -d "node_modules" ]; then
    echo "  Installing npm dependencies..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Waiting for services to be ready..."
echo ""

# Wait for services
sleep 3
wait_for_service "http://localhost:8001" "Agent A"
wait_for_service "http://localhost:8002" "Agent B"
wait_for_service "http://localhost:8000" "Arena"

echo ""
echo "=========================================="
echo -e "  ${GREEN}All Services Started!${NC}"
echo "=========================================="
echo ""
echo "  Open these URLs in separate browser tabs:"
echo ""
echo -e "  ${GREEN}Arena (Public View):${NC}"
echo "    http://localhost:3000/arena"
echo ""
echo -e "  ${GREEN}Partner A (Alex - Private View):${NC}"
echo "    http://localhost:3000/agent-a"
echo ""
echo -e "  ${GREEN}Partner B (Jordan - Private View):${NC}"
echo "    http://localhost:3000/agent-b"
echo ""
echo "  API Documentation:"
echo "    http://localhost:8000/docs"
echo ""
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C to cleanup
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $AGENT_A_PID $AGENT_B_PID $ARENA_PID $FRONTEND_PID 2>/dev/null || true
    echo "All services stopped."
    exit 0
}

trap cleanup INT TERM

# Wait for any process to exit
wait
