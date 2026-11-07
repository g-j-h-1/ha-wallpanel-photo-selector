"""Anonymous face matching. Distances are not confidence probabilities."""
import numpy as np


def matched_paths(viewers, indexed, threshold=0.45, limit=200):
    """Return photos containing any accepted viewer, best distance first."""
    results = []
    for path, faces in indexed.items():
        if len(faces) and len(viewers):
            distance = min(float(np.linalg.norm(face - viewer))
                           for face in faces for viewer in viewers)
            if np.isfinite(distance) and distance <= threshold:
                results.append((distance, path))
    return [path for _, path in sorted(results)[:limit]]


def confirmed_viewers(current, previous, threshold=0.45):
    """Require the same face in successive frames before selecting photos."""
    return [face for face in current
            if any(np.linalg.norm(face - old) <= threshold for old in previous)]


class VisitorMemory:
    """Anonymous visitors, retained for 15 minutes after their last sighting."""
    def __init__(self, ttl=900, threshold=0.45):
        self.ttl = ttl
        self.threshold = threshold
        self.visitors = []

    def active(self, now):
        self.visitors = [(face, seen) for face, seen in self.visitors if now - seen < self.ttl]
        return self.visitors

    def observe(self, faces, now):
        self.active(now)
        for face in faces:
            distances = [float(np.linalg.norm(face - old)) for old, _ in self.visitors]
            if distances and min(distances) <= self.threshold:
                index = int(np.argmin(distances))
                old, _ = self.visitors[index]
                self.visitors[index] = (old, now)
            else:
                self.visitors.append((face.copy(), now))
        self.visitors = sorted(self.visitors, key=lambda v: v[1], reverse=True)[:100]


def group_matches(viewers, indexed, threshold=0.45, limit=200):
    """Maximum distinct visitor/photo-face matching; one face cannot count twice."""
    results = []
    for path, faces in indexed.items():
        edges = [[i for i, face in enumerate(faces) if np.linalg.norm(viewer - face) <= threshold]
                 for viewer in viewers]
        assigned = {}

        def assign(viewer, visited):
            for face in edges[viewer]:
                if face in visited:
                    continue
                visited.add(face)
                if face not in assigned or assign(assigned[face], visited):
                    assigned[face] = viewer
                    return True
            return False

        count = sum(assign(i, set()) for i in range(len(viewers)))
        if count:
            results.append({"path": path, "people": count})
    # Include every matched photo: the frontend applies ratings before group ranking.
    return sorted(results, key=lambda item: (-item["people"], item["path"]))[:limit]
