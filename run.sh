#!/bin/bash
# ============================================================
#  Smart Virtual Queue - Crowd Control System
#  One-command setup & run script
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  🚦 Smart Virtual Queue - Crowd Control System"
echo "  Hackathon Demo Setup"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Install with: sudo apt install python3 python3-pip"
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --quiet fastapi uvicorn python-multipart numpy Pillow jinja2 2>/dev/null

# Try to install face_recognition (may need dlib which needs cmake)
echo "📦 Installing OpenCV..."
pip install --quiet opencv-python-headless 2>/dev/null || true

echo ""
echo "📦 Trying to install face_recognition (optional, needs cmake + dlib)..."
pip install --quiet face-recognition 2>/dev/null && echo "✅ face_recognition installed" || {
    echo "⚠️  face_recognition not installed (needs cmake + dlib)."
    echo "   The system will use OpenCV Haar cascade fallback."
    echo "   To install: sudo apt install cmake && pip install face-recognition"
}

echo ""
echo "============================================================"
echo "  🚀 Starting Server..."
echo "  Local: http://localhost:8000"
echo "============================================================"
echo ""

# Start FastAPI server in background
python3 server.py &
SERVER_PID=$!

# Start Cloudflare quick tunnel to expose server publicly
echo "🌐 Starting public tunnel (Cloudflare)..."
rm -f /tmp/cf_tunnel.log
cloudflared tunnel --url http://localhost:8000 --no-autoupdate 2>/tmp/cf_tunnel.log &
CF_PID=$!

# Wait for tunnel URL to appear (up to 30 seconds)
TUNNEL_URL=""
for i in $(seq 1 30); do
    sleep 1
    TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' /tmp/cf_tunnel.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    printf "."
done
echo ""

GITHUB_PAGES="https://praveensk1704.github.io/Smart-Virtual-Queue-System"

if [ -n "$TUNNEL_URL" ]; then
    echo ""
    echo "============================================================"
    echo "  ✅ TUNNEL ACTIVE — Share these links with users:"
    echo ""
    echo "  📝 Register:   ${GITHUB_PAGES}/register.html?api=${TUNNEL_URL}"
    echo "  🚪 Gate:       ${GITHUB_PAGES}/gate.html?api=${TUNNEL_URL}"
    echo "  📊 Dashboard:  ${GITHUB_PAGES}/index.html?api=${TUNNEL_URL}"
    echo ""
    echo "  🔗 Direct backend: ${TUNNEL_URL}"
    echo "  💾 Images saved to: $(pwd)/face_images/"
    echo "============================================================"
else
    echo "⚠️  Tunnel URL not found. Use local: http://localhost:8000"
fi

echo ""
echo "  Press Ctrl+C to stop"
echo ""

# Keep running until Ctrl+C
trap "kill $SERVER_PID $CF_PID 2>/dev/null; echo 'Server stopped.'; exit 0" INT TERM
wait $SERVER_PID
