import unittest
import numpy as np
from matching import VisitorMemory, confirmed_viewers, matched_paths, group_matches


class MatchingTests(unittest.TestCase):
    def test_threshold_and_multiple_people(self):
        viewer = np.zeros(128)
        near = viewer.copy()
        near[0] = 0.4
        far = viewer.copy()
        far[0] = 0.7
        self.assertEqual(matched_paths([viewer], {"yes.jpg": [far, near], "no.jpg": [far], "empty.jpg": []}), ["yes.jpg"])

    def test_no_faces_never_matches(self):
        self.assertEqual(matched_paths([], {"photo.jpg": [np.zeros(128)]}), [])

    def test_temporal_confirmation_rejects_a_different_viewer(self):
        first = np.zeros(128)
        second = np.ones(128)
        self.assertEqual(len(confirmed_viewers([first], [first])), 1)
        self.assertEqual(confirmed_viewers([second], [first]), [])
        self.assertEqual(confirmed_viewers([first], []), [])

    def test_limit_and_distance_order(self):
        self.assertEqual(matched_paths([np.zeros(128)], {"b": [np.full(128, .02)], "a": [np.zeros(128)]}, limit=1), ["a"])

    def test_visitor_memory_rolling_expiry_and_refresh(self):
        memory = VisitorMemory()
        first, second = np.zeros(128), np.ones(128)
        memory.observe([first], 0)
        memory.observe([second], 100)
        memory.observe([first], 800)
        self.assertEqual(len(memory.active(950)), 2)
        self.assertEqual(len(memory.active(1000)), 1)
        self.assertEqual(len(memory.active(1700)), 0)

    def test_group_counts_distinct_people_not_duplicate_faces(self):
        first, second = np.zeros(128), np.ones(128)
        result = group_matches([first, second], {"one": [first, first], "both": [second, first]})
        self.assertEqual(result, [{"path":"both","people":2},{"path":"one","people":1}])

    def test_one_photo_face_cannot_match_two_visitors(self):
        face = np.zeros(128)
        other = face.copy()
        other[0] = 0.5
        middle = face.copy()
        middle[0] = 0.25
        self.assertEqual(group_matches([face, other], {"photo": [middle]})[0]["people"], 1)


if __name__ == "__main__":
    unittest.main()
