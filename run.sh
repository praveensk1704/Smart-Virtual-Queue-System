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
echo "  Open in browser: http://localhost:8000"
echo ""
echo "  Pages:"
echo "    Dashboard:      http://localhost:8000/"
echo "    Register User:  http://localhost:8000/register"
echo "    Gate Simulator: http://localhost:8000/gate"
echo ""
echo "  Press Ctrl+C to stop the server"
echo "============================================================"
echo ""

python3 server.py
