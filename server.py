"""
Smart Virtual Queue Crowd Control System - Backend Server
FastAPI REST API Server

Endpoints:
  POST /api/register         - Register a user with face image
  GET  /api/users             - List all registered users
  GET  /api/groups            - Get group statistics
  POST /api/set_active_group  - Set the currently active group
  POST /api/verify            - Verify a face at the gate
  GET  /api/stats             - System statistics
  GET  /api/gate_logs         - Gate access logs
  POST /api/reset             - Reset the system
  GET  /                      - Web dashboard
"""

import os
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import database as db
import face_engine

app = FastAPI(title="Smart Virtual Queue - Crowd Control System")

# Static files & templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
# REST API Endpoints
# ─────────────────────────────────────────────

@app.post("/api/register")
async def api_register(request: Request):
    """Register a new user with face image (base64)."""
    data = await request.json()
    name = data.get("name", "").strip()
    image_b64 = data.get("image", "")

    if not name:
        return JSONResponse({"error": "Name is required"}, status_code=400)
    if not image_b64:
        return JSONResponse({"error": "Face image is required"}, status_code=400)

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

    # Register user
    result, err = db.register_user(name, encoding)
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
    """Set the currently active group."""
    data = await request.json()
    group_number = data.get("group_number", 0)

    if not isinstance(group_number, int) or group_number < 0 or group_number > 35:
        return JSONResponse({"error": "Invalid group number (0-35)"}, status_code=400)

    db.set_active_group(group_number)
    return JSONResponse({
        "success": True,
        "active_group": group_number,
        "message": f"Group {group_number} is now active" if group_number > 0 else "No group active",
    })


@app.post("/api/verify")
async def api_verify(request: Request):
    """Verify a user at the gate via face recognition."""
    data = await request.json()
    image_b64 = data.get("image", "")

    if not image_b64:
        return JSONResponse({"error": "Face image is required"}, status_code=400)

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
    return JSONResponse(db.get_system_stats())


@app.get("/api/gate_logs")
async def api_gate_logs():
    """Get gate access logs."""
    return JSONResponse({"logs": db.get_gate_logs()})


@app.post("/api/reset")
async def api_reset():
    """Reset the entire system."""
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
