"""Service boundary tests. Requires the recognition worker dependencies."""
from io import BytesIO
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

TEMP = tempfile.TemporaryDirectory()
os.environ.update(PHOTO_ROOT=TEMP.name, INDEX_DB=str(Path(TEMP.name) / "faces.sqlite"),
                  RECOGNITION_TOKEN="test-token-" + "x" * 32)
import app as worker


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(worker.app)
        cls.client.__enter__()
        cls.headers = {"Authorization": f"Bearer {worker.TOKEN}"}
        for _ in range(100):
            if cls.client.get("/health", headers=cls.headers).json()["state"] == "ready":
                break
            time.sleep(.02)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def setUp(self):
        with worker.LOCK:
            worker.VISITORS.visitors = []
            worker.PREVIOUS.clear()

    def test_auth_required(self):
        for endpoint in ["/health", "/matches"]:
            self.assertEqual(self.client.get(endpoint).status_code, 401)

    def test_bad_frame_rejected(self):
        self.assertEqual(self.client.post("/match", headers=self.headers, content=b"bad").status_code, 400)

    def test_oversize_frame_rejected(self):
        self.assertEqual(self.client.post("/match", headers=self.headers, content=b"x" * 5_000_001).status_code, 413)

    def test_blank_frame_has_no_visitors(self):
        image = BytesIO()
        Image.new("RGB", (100, 100)).save(image, "JPEG")
        response = self.client.post("/match", headers=self.headers, content=image.getvalue())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["viewer_count"], 0)
        self.assertEqual(response.json()["matches"], [])

    def test_memory_expires_without_new_camera_frames(self):
        now = time.monotonic()
        with worker.LOCK:
            worker.VISITORS.observe([np.zeros(128)], now - 901)
        result = self.client.get("/matches", headers=self.headers).json()
        self.assertEqual(result["viewer_count"], 0)

    def test_index_reuses_cache_and_invalidates_changed_and_deleted_exports(self):
        photo = Path(TEMP.name) / "photo.jpg"
        Image.new("RGB", (100, 100)).save(photo)
        with patch.object(worker.face_recognition, "face_locations", return_value=[(0,80,80,0)]), patch.object(
            worker.face_recognition, "face_encodings", return_value=[np.zeros(128)]
        ) as encode:
            worker.scan()
            self.assertEqual(encode.call_count, 1)
            worker.scan()
            self.assertEqual(encode.call_count, 1)
            photo.write_bytes(b"broken jpeg export")
            worker.scan()
            self.assertNotIn("photo.jpg", worker.FACES)
            photo.unlink()
            worker.scan()
            self.assertNotIn("photo.jpg", worker.FACES)


if __name__ == "__main__":
    unittest.main()
