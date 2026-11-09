import unittest
from trashsmart.training.detection_metrics import read_annotations, match_objects, summarize_images


class DetectionMetricsTests(unittest.TestCase):
    def test_boxes_and_polygons_preserve_material_ids(self):
        objects = read_annotations("2 .5 .5 .4 .8\n1 .1 .2 .4 .2 .4 .8 .1 .8", 100, 200, 4)
        self.assertEqual(objects[0]["label"], 2)
        self.assertAlmostEqual(objects[0]["box"][0], 30)
        self.assertEqual(objects[1]["box"], (10, 40, 40, 160))

    def test_invalid_annotations_fail(self):
        for line in ("4 .5 .5 .2 .2", "1 nan .5 .2 .2", "1 .5 .5 0 .2", "1 .2"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                read_annotations(line, 100, 100, 4)

    def test_duplicate_predictions_cannot_match_one_object_twice(self):
        truth = [dict(box=(0, 0, 10, 10), label=0)]
        predictions = [dict(box=(0, 0, 10, 10), confidence=0.6, label=0),
                       dict(box=(0, 0, 10, 10), confidence=0.9, label=1)]
        matches, missed, extras = match_objects(truth, predictions)
        self.assertEqual(matches, [(0, 1)])
        self.assertEqual(missed, [])
        self.assertEqual(extras, [0])
        report = summarize_images([dict(truth=truth, predictions=predictions, matches=matches,
                                       missed=missed, false_positives=extras)], ["glass", "metal"])
        self.assertEqual(report["totals"]["detection_recall"], 1)
        self.assertEqual(report["totals"]["end_to_end_recall"], 0)
        self.assertEqual(report["totals"]["wrong_material"], 1)

    def test_misses_unknown_and_background_false_positives_are_counted(self):
        truth = [dict(box=(0, 0, 10, 10), label=0), dict(box=(20, 20, 30, 30), label=1)]
        predictions = [dict(box=(0, 0, 10, 10), confidence=.9, label=-1)]
        matches, missed, extras = match_objects(truth, predictions)
        records = [dict(truth=truth, predictions=predictions, matches=matches,
                        missed=missed, false_positives=extras),
                   dict(truth=[], predictions=[dict(label=0)], matches=[], missed=[], false_positives=[0])]
        totals = summarize_images(records, ["glass", "metal"])["totals"]
        self.assertEqual(totals["missed"], 1)
        self.assertEqual(totals["unknown"], 1)
        self.assertEqual(totals["false_positives"], 1)
        self.assertEqual(totals["detection_recall"], .5)


if __name__ == "__main__":
    unittest.main()
