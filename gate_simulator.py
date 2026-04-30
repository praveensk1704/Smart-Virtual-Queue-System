"""
Gate Simulator - Standalone CLI Client
Simulates the embedded gate device in the terminal.
Captures face from webcam, sends to server for verification.

Usage: python gate_simulator.py [--server http://localhost:8000]
"""

import sys
import time
import json
import base64
import argparse
import io

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import Request, urlopen, URLError


SERVER_URL = "http://localhost:8000"

# ANSI colors for terminal
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"


def print_banner():
    print(f"""
{CYAN}{'='*60}
  🚪  SMART VIRTUAL QUEUE - GATE SIMULATOR
  📍  Simulated Embedded Gate Device
  🔗  Server: {SERVER_URL}
{'='*60}{RESET}
""")


def print_gate_open(user_name, group):
    print(f"""
{BG_GREEN}{BOLD}
  ╔══════════════════════════════════════╗
  ║         ✅  GATE OPEN  ✅            ║
  ║                                      ║
  ║   User:  {user_name:<28s} ║
  ║   Group: {str(group):<28s} ║
  ║                                      ║
  ║   GPIO23: HIGH → Relay ON            ║
  ║   GPIO24: HIGH → Green LED           ║
  ║   Buzzer: SHORT BEEP                 ║
  ╚══════════════════════════════════════╝
{RESET}
""")


def print_gate_denied(reason, user_name=None, group=None):
    info = ""
    if user_name:
        info = f"\n  ║   User:  {user_name:<28s} ║\n  ║   Group: {str(group):<28s} ║"
    print(f"""
{BG_RED}{BOLD}
  ╔══════════════════════════════════════╗
  ║         ❌  GATE CLOSED  ❌           ║
  ║                                      ║{info}
  ║   Reason: {reason:<27s}║
  ║                                      ║
  ║   GPIO23: LOW  → Relay OFF           ║
  ║   GPIO25: HIGH → Red LED             ║
  ║   Buzzer: LONG BEEP                  ║
  ╚══════════════════════════════════════╝
{RESET}
""")


def capture_from_webcam():
    """Capture a single frame from webcam, return as base64 JPEG."""
    if not HAS_CV2:
        print(f"{RED}OpenCV not installed. Install with: pip install opencv-python{RESET}")
        return None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print(f"{RED}Cannot open webcam{RESET}")
        return None

    print(f"{YELLOW}  📷 Camera active. Press SPACE to capture, Q to cancel...{RESET}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Draw guide rectangle
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.rectangle(frame, (cx - 120, cy - 150), (cx + 120, cy + 150), (0, 255, 255), 2)
        cv2.putText(frame, "GATE SCANNER", (cx - 80, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, "SPACE=Scan  Q=Cancel", (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("Gate Scanner", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):
            # Capture clean frame
            ret, clean_frame = cap.read()
            if ret:
                _, buffer = cv2.imencode('.jpg', clean_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                b64 = base64.b64encode(buffer).decode('utf-8')
                cap.release()
                cv2.destroyAllWindows()
                return f"data:image/jpeg;base64,{b64}"
        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return None


def verify_face(image_b64):
    """Send face image to server for verification."""
    data = json.dumps({"image": image_b64}).encode('utf-8')
    req = Request(
        f"{SERVER_URL}/api/verify",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        response = urlopen(req, timeout=10)
        return json.loads(response.read().decode('utf-8'))
    except URLError as e:
        return {"error": f"Server connection failed: {e}"}
    except Exception as e:
        return {"error": str(e)}


def get_stats():
    """Get current system stats from server."""
    try:
        req = Request(f"{SERVER_URL}/api/stats")
        response = urlopen(req, timeout=5)
        return json.loads(response.read().decode('utf-8'))
    except Exception:
        return None


def main():
    global SERVER_URL

    parser = argparse.ArgumentParser(description="Gate Simulator CLI")
    parser.add_argument("--server", default="http://localhost:8000", help="Server URL")
    args = parser.parse_args()
    SERVER_URL = args.server

    print_banner()

    # Check server connection
    stats = get_stats()
    if not stats:
        print(f"{RED}  ❌ Cannot connect to server at {SERVER_URL}")
        print(f"  Start the server first: python server.py{RESET}")
        sys.exit(1)

    print(f"{GREEN}  ✅ Connected to server{RESET}")
    print(f"  📊 Users: {stats['total_users']}  |  Active Group: {stats['active_group'] or 'None'}")
    print()

    while True:
        print(f"{CYAN}{'─'*50}")
        print(f"  Options: [S]can face  |  [R]efresh stats  |  [Q]uit")
        print(f"{'─'*50}{RESET}")

        choice = input("  > ").strip().lower()

        if choice == 'q':
            print(f"\n{YELLOW}  Gate simulator shutting down.{RESET}\n")
            break

        elif choice == 'r':
            stats = get_stats()
            if stats:
                active = stats['active_group'] if stats['active_group'] else 'None'
                print(f"\n  📊 Users: {stats['total_users']}  |  Active Group: {active}")
                print(f"     Entries: {stats['total_entries']}  |  Denied: {stats['total_denied']}\n")

        elif choice == 's':
            print(f"\n{YELLOW}  🔍 Initiating face scan...{RESET}")
            image = capture_from_webcam()
            if not image:
                print(f"{RED}  Scan cancelled or camera error.{RESET}\n")
                continue

            print(f"  ⏳ Verifying with server...")
            result = verify_face(image)

            if "error" in result:
                print(f"{RED}  Error: {result['error']}{RESET}\n")
            elif result.get("verified"):
                print_gate_open(result["user"]["name"], result["user"]["group"])
            else:
                user = result.get("user")
                if user:
                    print_gate_denied(
                        result.get("reason", "Denied")[:27],
                        user["name"],
                        user["group"],
                    )
                else:
                    print_gate_denied(result.get("reason", "Unknown user")[:27])
        else:
            print(f"  Invalid option. Use S, R, or Q.")


if __name__ == "__main__":
    main()
