import copy
import tempfile
import unittest
import json
import shutil
from pathlib import Path

from trashsmart.yolo_training.pr90_policy import publication_allowed, strict_target_met, sha256
from trashsmart.yolo_training.overnight_pr90 import publish, dataset_fingerprint
from trashsmart.yolo_training.train_accuracy import precision_recall_score
from trashsmart.yolo_training.search_accuracy import best_balanced_point


def reports(digest):
    validation = dict(split="val", checkpoint_sha256=digest, data="fixed.yaml", imgsz=640,
                      tta=False, nms_iou=.7, map50=.95, precision_max_f1=.93, recall_max_f1=.92,
                      operating_point=dict(precision=.92, recall=.93, confidence=.4))
    test = copy.deepcopy(validation)
    test["split"] = "test"
    return validation, test


class StrictPRTests(unittest.TestCase):
    def test_continuation_skips_head_and_reduces_augmentation(self):
        from trashsmart.yolo_training.overnight_pr90 import stage_plan
        stages = stage_plan(True)
        self.assertEqual([stage[0] for stage in stages], ["finetune", "polish"])
        self.assertTrue(all(stage[2] == 0 for stage in stages))
        self.assertLess(stages[0][3], stage_plan()[1][3])
        self.assertLess(stages[0][4], stage_plan()[1][4])
        self.assertEqual(stages[-1][4], 0)
        self.assertAlmostEqual(sum(stage[-1] for stage in stages), 1)

    def test_high_recall_cannot_compensate_for_low_precision(self):
        validation, test = reports("weights")
        test["operating_point"]["precision"] = .8999
        self.assertFalse(publication_allowed(validation, test, "weights"))
        self.assertGreater(precision_recall_score(.91, .91, .94), precision_recall_score(.85, .99, .98))

    def test_both_summary_and_deployed_point_must_meet_target(self):
        validation, test = reports("weights")
        self.assertTrue(publication_allowed(validation, test, "weights"))
        test["recall_max_f1"] = .89
        self.assertFalse(publication_allowed(validation, test, "weights"))

    def test_no_test_threshold_retuning_or_checkpoint_mismatch(self):
        validation, test = reports("weights")
        test["operating_point"]["confidence"] = .3
        self.assertFalse(publication_allowed(validation, test, "weights"))
        validation, test = reports("weights")
        self.assertFalse(publication_allowed(validation, test, "other-weights"))

    def test_invalid_metrics_are_not_success(self):
        validation, _ = reports("weights")
        for value in (float("nan"), float("inf"), 1.1):
            validation["map50"] = value
            self.assertFalse(strict_target_met(validation))

    def test_balanced_selection_scores_precision_and_recall_together(self):
        point = best_balanced_point([.9, .8, .7, .6], [1, 1, 0, 1], 3)
        self.assertEqual(point["true_positives"], 3)
        self.assertEqual(point["precision"], .75)
        self.assertEqual(point["recall"], 1)


class PublicationTests(unittest.TestCase):
    def test_failed_goal_does_not_touch_active_weights_or_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active, candidate = root / "active.pt", root / "candidate.pt"
            active.write_bytes(b"old")
            candidate.write_bytes(b"new")
            (root / ".env").write_text("PRIVATE_SETTING=unchanged\nYOLO_CONF_THRESHOLD=.2\n")
            validation, test = reports(sha256(candidate))
            test["operating_point"]["recall"] = .89
            outcome = publish(candidate, validation, test, active, sha256(active), root, root / "run")
            self.assertEqual(outcome["status"], "not_published")
            self.assertEqual(active.read_bytes(), b"old")
            self.assertIn("YOLO_CONF_THRESHOLD=.2", (root / ".env").read_text())

    def test_verified_goal_preserves_backup_and_unrelated_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active, candidate = root / "active.pt", root / "candidate.pt"
            active.write_bytes(b"old")
            candidate.write_bytes(b"new")
            (root / ".env").write_text("PRIVATE_SETTING=unchanged\nYOLO_CONF_THRESHOLD=.2\n")
            validation, test = reports(sha256(candidate))
            outcome = publish(candidate, validation, test, active, sha256(active), root, root / "run")
            self.assertEqual(outcome["status"], "published")
            self.assertEqual(active.read_bytes(), b"new")
            self.assertEqual((root / "run/backup/best_new.pt").read_bytes(), b"old")
            self.assertIn("PRIVATE_SETTING=unchanged", (root / ".env").read_text())
            self.assertIn("YOLO_CONF_THRESHOLD=0.4", (root / ".env").read_text())


class DatasetIntegrityTests(unittest.TestCase):
    def create_data(self, root):
        for split in ("train", "valid", "test"):
            (root / split / "images").mkdir(parents=True)
            (root / split / "labels").mkdir()
            (root / split / "images/a.jpg").write_bytes(split.encode())
            (root / split / "labels/a.txt").write_text("0 .5 .5 .4 .4\n")
        data = root / "data.yaml"
        data.write_text(json.dumps(dict(path=root.as_posix(), train="train/images", val="valid/images", test="test/images")))
        return data

    def test_same_size_annotation_change_invalidates_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.create_data(root)
            before = dataset_fingerprint(data)
            (root / "valid/labels/a.txt").write_text("0 .6 .5 .4 .4\n")
            self.assertNotEqual(before, dataset_fingerprint(data))

    def test_exact_cross_split_duplicates_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.create_data(root)
            shutil.copy2(root / "train/images/a.jpg", root / "test/images/a.jpg")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                dataset_fingerprint(data)


if __name__ == "__main__":
    unittest.main()
