"""
Smart Virtual Queue Crowd Control System - Backend Server
FastAPI REST API Server

Endpoints:
  POST /api/register         - Register a user with face image
  GET  /api/users             - List all registered users
  GET  /api/groups            - Get group statistics
  POST /api/set_active_group  - Set the currently active group (ADMIN)
  POST /api/verify            - Verify a face at the gate
  GET  /api/stats             - System statistics
  GET  /api/gate_logs         - Gate access logs
  POST /api/reset             - Reset the system (ADMIN)
  POST /api/configure         - Configure groups (ADMIN)
  POST /api/admin/login       - Admin login
  GET  /                      - Web dashboard
"""

import os
import re
import time
import base64
import hashlib
import secrets
import html
from collections import defaultdict
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import database as db
import face_engine

app = FastAPI(title="Smart Virtual Queue - Crowd Control System")

# ─────────────────────────────────────────────
# SECURITY: Admin password & session tokens
# ─────────────────────────────────────────────
ADMIN_PASSWORD_HASH = None
ADMIN_TOKENS = {}  # token -> expiry timestamp
TOKEN_EXPIRY = 3600 * 8  # 8 hours

def _init_admin_password():
    """Load or create admin password."""
    global ADMIN_PASSWORD_HASH
    pw_file = os.path.join(os.path.dirname(__file__), ".admin_password")
    if os.path.exists(pw_file):
        with open(pw_file, "r") as f:
            ADMIN_PASSWORD_HASH = f.read().strip()
    else:
        # Default password on first run - user MUST change it
        default_pw = "admin123"
        ADMIN_PASSWORD_HASH = hashlib.sha256(default_pw.encode()).hexdigest()
        with open(pw_file, "w") as f:
            f.write(ADMIN_PASSWORD_HASH)
        os.chmod(pw_file, 0o600)
        print(f"⚠️  Default admin password set: {default_pw}")
        print(f"   Change it via POST /api/admin/change_password")

_init_admin_password()

def verify_admin_token(request: Request) -> bool:
    """Check if request has a valid admin token."""
    token = request.headers.get("X-Admin-Token", "")
    if not token:
        # Also check query param for SSE/websocket
        token = request.query_params.get("token", "")
    if token in ADMIN_TOKENS:
        if ADMIN_TOKENS[token] > time.time():
            return True
        else:
            del ADMIN_TOKENS[token]  # expired
    return False

def require_admin(request: Request):
    """Returns error response if not admin, or None if authorized."""
    if not verify_admin_token(request):
        return JSONResponse({"error": "Unauthorized. Admin login required."}, status_code=401)
    return None

# ─────────────────────────────────────────────
# SECURITY: Rate limiting
# ─────────────────────────────────────────────
_rate_limits = defaultdict(list)  # ip -> [timestamps]
RATE_LIMIT_REGISTER = 10       # max registrations per IP per minute
RATE_LIMIT_VERIFY = 30         # max verifications per IP per minute
RATE_LIMIT_GENERAL = 120       # max general requests per IP per minute

def check_rate_limit(ip: str, limit: int) -> bool:
    """Returns True if rate limit exceeded."""
    now = time.time()
    _rate_limits[ip] = [t for t in _rate_limits[ip] if t > now - 60]
    if len(_rate_limits[ip]) >= limit:
        return True
    _rate_limits[ip].append(now)
    return False

# ─────────────────────────────────────────────
# SECURITY: Input sanitization
# ─────────────────────────────────────────────
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB max for base64 images
MAX_NAME_LENGTH = 100
NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s\.\-\']+$')

def sanitize_name(name: str) -> str:
    """Sanitize user name to prevent XSS and injection."""
    name = name.strip()[:MAX_NAME_LENGTH]
    name = html.escape(name)
    return name

def validate_name(name: str) -> str | None:
    """Returns error message if name is invalid, None if valid."""
    if not name or len(name.strip()) < 2:
        return "Name must be at least 2 characters"
    if len(name) > MAX_NAME_LENGTH:
        return f"Name must be under {MAX_NAME_LENGTH} characters"
    if not NAME_PATTERN.match(name):
        return "Name can only contain letters, numbers, spaces, dots, hyphens, and apostrophes"
    return None

# Allow requests from GitHub Pages, local dev, and Cloudflare tunnels
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://praveensk1704.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

# ─── Request size limit middleware ───
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
        return JSONResponse({"error": "Request too large"}, status_code=413)
    # Rate limit general requests
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip, RATE_LIMIT_GENERAL):
        return JSONResponse({"error": "Too many requests. Slow down."}, status_code=429)
    return await call_next(request)

# Static files & templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACE_IMAGES_DIR = os.path.join(BASE_DIR, "face_images")
os.makedirs(FACE_IMAGES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Initialize database on startup
db.init_db()


# ─────────────────────────────────────────────
# Web Dashboard
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.get("/gate", response_class=HTMLResponse)
async def gate_page(request: Request):
    return templates.TemplateResponse(request, "gate.html")


# ─────────────────────────────────────────────
# Admin Authentication
# ─────────────────────────────────────────────

@app.post("/api/admin/login")
async def admin_login(request: Request):
    """Admin login - returns a session token."""
    data = await request.json()
    password = data.get("password", "")

    if not password:
        return JSONResponse({"error": "Password required"}, status_code=400)

    # Rate limit login attempts
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip + "_login", 5):  # 5 attempts per minute
        return JSONResponse({"error": "Too many login attempts. Wait 1 minute."}, status_code=429)

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != ADMIN_PASSWORD_HASH:
        return JSONResponse({"error": "Wrong password"}, status_code=403)

    token = secrets.token_hex(32)
    ADMIN_TOKENS[token] = time.time() + TOKEN_EXPIRY
    return JSONResponse({"success": True, "token": token, "expires_in": TOKEN_EXPIRY})


@app.post("/api/admin/change_password")
async def admin_change_password(request: Request):
    """Change admin password. Requires current admin token."""
    auth_err = require_admin(request)
    if auth_err:
        return auth_err

    data = await request.json()
    new_password = data.get("new_password", "")

    if len(new_password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    global ADMIN_PASSWORD_HASH
    ADMIN_PASSWORD_HASH = hashlib.sha256(new_password.encode()).hexdigest()
    pw_file = os.path.join(os.path.dirname(__file__), ".admin_password")
    with open(pw_file, "w") as f:
        f.write(ADMIN_PASSWORD_HASH)
    os.chmod(pw_file, 0o600)

    # Invalidate all existing tokens
    ADMIN_TOKENS.clear()

    return JSONResponse({"success": True, "message": "Password changed. All sessions logged out."})


@app.get("/api/admin/check")
async def admin_check(request: Request):
    """Check if the current token is valid."""
    is_admin = verify_admin_token(request)
    return JSONResponse({"authenticated": is_admin})


# ─────────────────────────────────────────────
# REST API Endpoints
# ─────────────────────────────────────────────

@app.post("/api/register")
async def api_register(request: Request):
    """Register a new user with face image (base64)."""
    # Rate limit registrations
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip + "_reg", RATE_LIMIT_REGISTER):
        return JSONResponse({"error": "Too many registrations. Wait 1 minute."}, status_code=429)

    data = await request.json()
    name = data.get("name", "").strip()
    image_b64 = data.get("image", "")

    # Validate name
    name_err = validate_name(name)
    if name_err:
        return JSONResponse({"error": name_err}, status_code=400)
    name = sanitize_name(name)

    if not image_b64:
        return JSONResponse({"error": "Face image is required"}, status_code=400)

    # Check image size (prevent huge uploads)
    if len(image_b64) > MAX_IMAGE_SIZE:
        return JSONResponse({"error": "Image too large (max 5MB)"}, status_code=400)

    # Extract face encoding
    try:
        img_array = face_engine.decode_base64_image(image_b64)
        encoding, err = face_engine.extract_face_encoding(img_array)
        if err:
            return JSONResponse({"error": err}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Image processing failed: {str(e)}"}, status_code=400)

    # Check if face already registered
    known_users = db.get_all_face_encodings()
    match = face_engine.find_matching_user(encoding, known_users)
    if match:
        return JSONResponse(
            {"error": f"Face already registered as '{match['name']}' (Group {match['group_number']})"},
            status_code=409,
        )

    # Save the face image to local disk
    image_path = None
    try:
        raw_b64 = image_b64.split(",")[1] if "," in image_b64 else image_b64
        img_bytes = base64.b64decode(raw_b64)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        filename = f"{safe_name}_{int(__import__('time').time())}.jpg"
        image_path = os.path.join(FACE_IMAGES_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        image_path = None  # Don't block registration if image save fails

    # Register user
    result, err = db.register_user(name, encoding, image_path)
    if err:
        return JSONResponse({"error": err}, status_code=400)

    return JSONResponse({
        "success": True,
        "user": result,
        "message": f"Registered '{name}' in Group {result['group_number']}",
    })


@app.get("/api/users")
async def api_users():
    """Get all registered users."""
    return JSONResponse({"users": db.get_all_users()})


@app.get("/api/groups")
async def api_groups():
    """Get group statistics."""
    return JSONResponse({
        "groups": db.get_group_stats(),
        "active_group": db.get_active_group(),
    })


@app.post("/api/set_active_group")
async def api_set_active_group(request: Request):
    """Set the currently active group. ADMIN ONLY."""
    auth_err = require_admin(request)
    if auth_err:
        return auth_err

    data = await request.json()
    group_number = data.get("group_number", 0)
    config = db.get_config()

    if not isinstance(group_number, int) or group_number < 0 or group_number > config["total_groups"]:
        return JSONResponse({"error": f"Invalid group number (0-{config['total_groups']})"}, status_code=400)

    db.set_active_group(group_number)
    return JSONResponse({
        "success": True,
        "active_group": group_number,
        "message": f"Group {group_number} is now active" if group_number > 0 else "No group active",
    })


@app.post("/api/verify")
async def api_verify(request: Request):
    """Verify a user at the gate via face recognition."""
    # Rate limit verifications
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip + "_verify", RATE_LIMIT_VERIFY):
        return JSONResponse({"error": "Too many scan attempts. Wait 1 minute."}, status_code=429)

    data = await request.json()
    image_b64 = data.get("image", "")

    if not image_b64:
        return JSONResponse({"error": "Face image is required"}, status_code=400)

    # Check image size
    if len(image_b64) > MAX_IMAGE_SIZE:
        return JSONResponse({"error": "Image too large"}, status_code=400)

    # Extract face encoding
    try:
        img_array = face_engine.decode_base64_image(image_b64)
        encoding, err = face_engine.extract_face_encoding(img_array)
        if err:
            return JSONResponse({
                "verified": False,
                "gate": "CLOSED",
                "reason": err,
            })
    except Exception as e:
        return JSONResponse({
            "verified": False,
            "gate": "CLOSED",
            "reason": f"Image processing failed: {str(e)}",
        })

    # Find matching user
    known_users = db.get_all_face_encodings()
    match = face_engine.find_matching_user(encoding, known_users)

    if not match:
        db.log_gate_event(None, "Unknown", None, "verify", "denied")
        return JSONResponse({
            "verified": False,
            "gate": "CLOSED",
            "reason": "Face not recognized. User not registered.",
        })

    # Check if user's group is active
    active_group = db.get_active_group()
    user_group = match["group_number"]

    if active_group == 0:
        db.log_gate_event(match["id"], match["name"], user_group, "verify", "denied")
        return JSONResponse({
            "verified": False,
            "gate": "CLOSED",
            "user": {"name": match["name"], "group": user_group},
            "reason": "No group is currently active. Please wait.",
        })

    if user_group == active_group:
        db.log_gate_event(match["id"], match["name"], user_group, "verify", "granted")
        return JSONResponse({
            "verified": True,
            "gate": "OPEN",
            "user": {"name": match["name"], "group": user_group},
            "message": f"Welcome {match['name']}! Group {user_group} is active. Gate OPEN.",
        })
    else:
        db.log_gate_event(match["id"], match["name"], user_group, "verify", "denied")
        return JSONResponse({
            "verified": False,
            "gate": "CLOSED",
            "user": {"name": match["name"], "group": user_group},
            "reason": f"Your group ({user_group}) is not active. Currently serving Group {active_group}.",
        })


@app.get("/api/stats")
async def api_stats():
    """Get system statistics."""
    stats = db.get_system_stats()
    stats["config"] = db.get_config()
    return JSONResponse(stats)


@app.get("/api/gate_logs")
async def api_gate_logs():
    """Get gate access logs."""
    return JSONResponse({"logs": db.get_gate_logs()})


@app.post("/api/configure")
async def api_configure(request: Request):
    """Configure the number of groups and max members per group. ADMIN ONLY."""
    auth_err = require_admin(request)
    if auth_err:
        return auth_err

    data = await request.json()
    total_groups = data.get("total_groups")
    max_members = data.get("max_members")

    if total_groups is not None:
        if not isinstance(total_groups, int) or total_groups < 1 or total_groups > 100:
            return JSONResponse({"error": "total_groups must be 1-100"}, status_code=400)
    if max_members is not None:
        if not isinstance(max_members, int) or max_members < 1 or max_members > 500:
            return JSONResponse({"error": "max_members must be 1-500"}, status_code=400)

    config = db.get_config()
    tg = total_groups if total_groups is not None else config["total_groups"]
    mm = max_members if max_members is not None else config["max_members"]
    db.update_config(tg, mm)

    return JSONResponse({
        "success": True,
        "config": {"total_groups": tg, "max_members": mm},
        "message": f"Updated: {tg} groups, {mm} members per group",
    })


@app.post("/api/reset")
async def api_reset(request: Request):
    """Reset the entire system. ADMIN ONLY."""
    auth_err = require_admin(request)
    if auth_err:
        return auth_err

    db.reset_system()
    return JSONResponse({"success": True, "message": "System reset complete"})


# ─────────────────────────────────────────────
# Run with: uvicorn server:app --host 0.0.0.0 --port 8000
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  Smart Virtual Queue - Crowd Control System")
    print("  Starting server on http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
