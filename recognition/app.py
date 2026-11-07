"""LAN-only photo recognition worker; never writes original photographs."""
from contextlib import asynccontextmanager
from io import BytesIO
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time

import face_recognition
import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from PIL import Image, ImageOps

from matching import VisitorMemory, confirmed_viewers, group_matches

LOG = logging.getLogger(__name__)
ROOT = Path(os.environ.get("PHOTO_ROOT", "/photos")).resolve()
TOKEN = os.environ.get("RECOGNITION_TOKEN", "")
THRESHOLD = float(os.environ.get("FACE_DISTANCE_THRESHOLD", "0.45"))
DB = os.environ.get("INDEX_DB", "/data/faces.sqlite")
LOCK = threading.Lock()
FACES = {}
PREVIOUS = {}
VISITORS = VisitorMemory(threshold=THRESHOLD)
STATUS = {"state": "starting", "photos": 0, "faces": 0, "errors": 0}
STOP = threading.Event()
Image.MAX_IMAGE_PIXELS = 30_000_000


def rgb_image(source, max_size=1600):
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        image.thumbnail((max_size, max_size))
        return np.asarray(image)


def scan():
    """Cache embeddings in SQLite, invalidating modified and deleted exports."""
    if not ROOT.is_dir():
        raise RuntimeError("Photo mount is missing")
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS faces (path TEXT PRIMARY KEY, mtime INTEGER, size INTEGER, vectors BLOB)")
        indexed, present, errors = {}, set(), 0
        for path in sorted(ROOT.rglob("*")):
            if STOP.is_set():
                return
            if path.suffix.lower() not in {".jpg", ".jpeg"}:
                continue
            relative = path.relative_to(ROOT).as_posix()
            present.add(relative)
            try:
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(ROOT) or not resolved.is_file():
                    raise ValueError("Photo is outside mounted directory")
                stat = resolved.stat()
                row = db.execute("SELECT mtime,size,vectors FROM faces WHERE path=?", (relative,)).fetchone()
                if row and row[:2] == (stat.st_mtime_ns, stat.st_size):
                    vectors = np.frombuffer(row[2], dtype=np.float64).reshape(-1, 128).copy()
                else:
                    pixels = rgb_image(resolved)
                    locations = face_recognition.face_locations(pixels, model="hog")
                    vectors = np.asarray(face_recognition.face_encodings(pixels, locations), dtype=np.float64).reshape(-1, 128)
                    after = resolved.stat()
                    if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
                        raise ValueError("Photo changed during indexing; retry next scan")
                    db.execute("INSERT OR REPLACE INTO faces VALUES (?,?,?,?)",
                               (relative, stat.st_mtime_ns, stat.st_size, vectors.tobytes()))
                indexed[relative] = vectors
            except Exception:
                errors += 1
                db.execute("DELETE FROM faces WHERE path=?", (relative,))
                LOG.warning("Could not index photo %s", relative)
        for (relative,) in db.execute("SELECT path FROM faces").fetchall():
            if relative not in present:
                db.execute("DELETE FROM faces WHERE path=?", (relative,))
        with LOCK:
            FACES.clear()
            FACES.update(indexed)
            STATUS.update(state="ready", photos=len(indexed),
                          faces=sum(len(v) for v in indexed.values()), errors=errors)


def index_loop():
    while not STOP.is_set():
        try:
            scan()
        except Exception:
            LOG.exception("Face index unavailable")
            with LOCK:
                FACES.clear()
                STATUS["state"] = "error"
        STOP.wait(60)


@asynccontextmanager
async def lifespan(app):
    if len(TOKEN) < 32:
        raise RuntimeError("Set RECOGNITION_TOKEN to at least 32 random characters")
    if not 0.2 <= THRESHOLD <= 0.6:
        raise RuntimeError("FACE_DISTANCE_THRESHOLD must be between 0.2 and 0.6")
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    STOP.clear()
    worker = threading.Thread(target=index_loop, daemon=True)
    worker.start()
    yield
    STOP.set()


def authorize(authorization: str = Header(default="")):
    if not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "Invalid recognition token")


app = FastAPI(lifespan=lifespan, dependencies=[Depends(authorize)])


@app.get("/health")
def health():
    with LOCK:
        return dict(STATUS)


def recognize(raw):
    pixels = rgb_image(BytesIO(raw), max_size=800)
    locations = face_recognition.face_locations(pixels, model="hog")
    landmarks = face_recognition.face_landmarks(pixels, locations)
    frontal = []
    for location, points in zip(locations, landmarks):
        top, right, bottom, left = location
        if right - left < 60:
            continue
        # A coarse frontal-pose gate, not eye tracking or proof of attention.
        left_eye = np.mean(points["left_eye"], axis=0)
        right_eye = np.mean(points["right_eye"], axis=0)
        nose = np.mean(points["nose_tip"], axis=0)
        span = right_eye[0] - left_eye[0]
        if span > 0 and 0.25 <= (nose[0] - left_eye[0]) / span <= 0.75:
            frontal.append(location)
    current = face_recognition.face_encodings(pixels, frontal)
    now = time.monotonic()
    with LOCK:
        previous = PREVIOUS.get("viewer", (0, []))
        confirmed = confirmed_viewers(current, previous[1], THRESHOLD) if now - previous[0] <= 15 else []
        PREVIOUS["viewer"] = (now, current)
        VISITORS.observe(confirmed, now)
    return recent_matches()


@app.get("/matches")
def recent_matches():
    now = time.monotonic()
    with LOCK:
        visitors = list(VISITORS.active(now))
        indexed = dict(FACES)
        state = STATUS["state"]
    return {"state": state, "viewer_count": len(visitors),
            "memory_seconds": 900,
            "next_expiry": time.time() + min((seen + 900 - now for _, seen in visitors), default=0),
            "matches": group_matches([face for face, _ in visitors], indexed, THRESHOLD)
            if state == "ready" else []}


@app.post("/match")
async def match(request: Request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 5_000_000:
            raise HTTPException(413, "Camera frame exceeds 5 MB")
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(recognize, bytes(raw))
    except (OSError, ValueError):
        raise HTTPException(400, "Invalid camera image") from None
