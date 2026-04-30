"""
Smart Virtual Queue Crowd Control System - Face Recognition Module
Uses face_recognition library (dlib-based) for face detection & matching.
Falls back to OpenCV Haar cascades if face_recognition is unavailable.
"""

import base64
import io
import numpy as np
from PIL import Image

# Try to import face_recognition, fall back to OpenCV
try:
    import face_recognition
    FACE_ENGINE = "face_recognition"
except ImportError:
    FACE_ENGINE = "opencv"
    import cv2

print(f"[FaceEngine] Using engine: {FACE_ENGINE}")


def decode_base64_image(base64_str):
    """Decode a base64 image string to numpy array (RGB)."""
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    img_bytes = base64.b64decode(base64_str)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return np.array(img)


def extract_face_encoding(image_array):
    """Extract face encoding from an RGB image array.
    Returns (encoding_list, error_message).
    """
    if FACE_ENGINE == "face_recognition":
        face_locations = face_recognition.face_locations(image_array)
        if not face_locations:
            return None, "No face detected in image"
        encodings = face_recognition.face_encodings(image_array, face_locations)
        if not encodings:
            return None, "Could not extract face features"
        return encodings[0].tolist(), None
    else:
        # OpenCV fallback - uses Haar cascade for detection
        # Returns a pseudo-encoding based on face region pixel stats
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) == 0:
            return None, "No face detected in image"
        x, y, w, h = faces[0]
        face_region = gray[y : y + h, x : x + w]
        # Create a simple encoding from resized face region
        resized = cv2.resize(face_region, (16, 16))
        encoding = (resized.flatten().astype(float) / 255.0).tolist()
        return encoding, None


def compare_faces(known_encoding, unknown_encoding, tolerance=0.6):
    """Compare two face encodings. Returns True if they match."""
    if FACE_ENGINE == "face_recognition":
        known = np.array(known_encoding)
        unknown = np.array(unknown_encoding)
        distance = np.linalg.norm(known - unknown)
        return distance <= tolerance
    else:
        # OpenCV fallback - use cosine similarity
        known = np.array(known_encoding)
        unknown = np.array(unknown_encoding)
        if known.shape != unknown.shape:
            return False
        dot = np.dot(known, unknown)
        norm = np.linalg.norm(known) * np.linalg.norm(unknown)
        if norm == 0:
            return False
        similarity = dot / norm
        return similarity >= 0.85


def find_matching_user(unknown_encoding, known_users):
    """Find a matching user from the database.
    known_users: list of dicts with 'id', 'name', 'group_number', 'encoding'.
    Returns matching user dict or None.
    """
    best_match = None
    best_distance = float("inf")

    for user in known_users:
        known_enc = user["encoding"]
        if FACE_ENGINE == "face_recognition":
            distance = np.linalg.norm(
                np.array(known_enc) - np.array(unknown_encoding)
            )
            if distance < best_distance and distance <= 0.6:
                best_distance = distance
                best_match = user
        else:
            known = np.array(known_enc)
            unknown = np.array(unknown_encoding)
            if known.shape != unknown.shape:
                continue
            dot = np.dot(known, unknown)
            norm = np.linalg.norm(known) * np.linalg.norm(unknown)
            if norm == 0:
                continue
            similarity = dot / norm
            distance = 1.0 - similarity
            if distance < best_distance and similarity >= 0.85:
                best_distance = distance
                best_match = user

    return best_match
