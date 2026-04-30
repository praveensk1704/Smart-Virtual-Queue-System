# 🚦 Smart Virtual Queue - Crowd Control System

## Hackathon Proof of Concept Demo

> Eliminate physical waiting lines using **face recognition + group-based access control**.  
> 500 people → 35 groups → One group enters at a time → No crowd congestion.

---

## Quick Start (One Command)

```bash
cd hackathon_demo
./run.sh
```

Then open **http://localhost:8000** in your browser.

---

## What This Demo Does

| Component | Description |
|-----------|-------------|
| **Backend Server** | FastAPI REST API with SQLite database |
| **Face Recognition** | Webcam-based face capture & matching (dlib or OpenCV fallback) |
| **Web Dashboard** | Real-time group control, user management, gate logs |
| **Gate Simulator** | Browser-based or CLI gate device simulation |

---

## Demo Flow (for Hackathon Presentation)

### Step 1: Start the Server
```bash
./run.sh
```

### Step 2: Register Users (http://localhost:8000/register)
- Open the Register page
- Allow camera access
- Enter user name → Capture face → Click Register
- System auto-assigns a group number
- Register 3-5 people for demo

### Step 3: Control Groups (http://localhost:8000/)
- Dashboard shows all registered users and their groups
- Click a group number or use Next/Previous to set the active group
- "Now Serving: Group X" updates in real-time

### Step 4: Gate Verification (http://localhost:8000/gate)
- Open the Gate Simulator page
- Start camera → Click "Scan & Verify"
- If the person's group is active → **GATE OPEN** (green, relay ON)
- If not → **GATE CLOSED** (red, access denied)
- Simulated GPIO/LED/Buzzer indicators show hardware behavior

### Step 5: Show Logs
- Dashboard shows real-time access logs (granted/denied)
- Statistics update automatically

---

## Project Architecture

```
          [ Registration ]                    [ Admin Dashboard ]
     (Webcam Face Capture)                   (Web Browser)
               ↓                                    ↓
        ┌──────────────────────────────────────────┐
        │         FastAPI Backend Server            │
        │  ┌─────────┐  ┌──────────┐  ┌─────────┐ │
        │  │ Face     │  │ Group    │  │ Gate    │ │
        │  │ Engine   │  │ Manager  │  │ Control │ │
        │  └─────────┘  └──────────┘  └─────────┘ │
        │         ↓           ↓            ↓       │
        │              [ SQLite DB ]               │
        └──────────────────────────────────────────┘
               ↓
        [ Gate Simulator ]
     (Browser / CLI Client)
        ┌─────────────────┐
        │ Simulated HW:   │
        │ • GPIO Relay     │
        │ • Green/Red LED  │
        │ • Buzzer         │
        │ • Door Latch     │
        └─────────────────┘
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web Dashboard |
| GET | `/register` | Registration Page |
| GET | `/gate` | Gate Simulator Page |
| POST | `/api/register` | Register user with face image |
| GET | `/api/users` | List all users |
| GET | `/api/groups` | Group statistics |
| POST | `/api/set_active_group` | Set active group |
| POST | `/api/verify` | Verify face at gate |
| GET | `/api/stats` | System statistics |
| GET | `/api/gate_logs` | Access logs |
| POST | `/api/reset` | Reset system |

---

## File Structure

```
hackathon_demo/
├── run.sh              # One-command setup & launch
├── server.py           # FastAPI backend server
├── database.py         # SQLite database models & logic
├── face_engine.py      # Face recognition module
├── gate_simulator.py   # CLI gate simulator client
├── requirements.txt    # Python dependencies
├── templates/
│   ├── dashboard.html  # Admin control panel
│   ├── register.html   # User registration page
│   └── gate.html       # Gate simulator UI
└── static/
    └── style.css       # UI stylesheet
```

---

## Requirements

- Python 3.8+
- Webcam (laptop camera works)
- Web browser (Chrome/Firefox)

### Dependencies (auto-installed by run.sh)
- FastAPI + Uvicorn (web server)
- OpenCV (face detection)
- face_recognition (optional, better accuracy)
- NumPy, Pillow, Jinja2

---

## Hardware Mapping (Proof of Concept → Real Device)

| Demo (PC Simulation) | Real Hardware (AM3352) |
|----------------------|----------------------|
| Webcam | USB/CSI Camera |
| Browser Gate UI | Qt GUI on touchscreen |
| LED indicators (CSS) | GPIO → Physical LEDs |
| Relay status (text) | GPIO23 → Door relay |
| Buzzer icon | GPIO → Piezo buzzer |
| SQLite database | SQLite/eMMC storage |
| FastAPI server | Embedded Linux daemon |
| Browser dashboard | HDMI display system |

---

## Tech Stack

- **Backend**: Python, FastAPI, SQLite
- **Face AI**: OpenCV / dlib / face_recognition
- **Frontend**: HTML5, CSS3, JavaScript
- **Target HW**: TI AM3352 (ARM Cortex-A8) with Linux
- **Products**: COSEC VEGA/ARGO/ATOM/ARCV2/PATH/PANEL_LITE_V2
