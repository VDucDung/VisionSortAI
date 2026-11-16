import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from trashsmart.yolo_training.benchmark import audit_snapshot, select_winner, training_options, verify_completed_run, verify_resume_state, verify_snapshot, write_json
from trashsmart.yolo_training.prepare_detection import normalize_annotations


class BenchmarkTests(unittest.TestCase):
    def test_resume_requires_same_recipe_optimizer_and_contiguous_epoch_history(self):
        recipe = dict(epochs=30, imgsz=640, lr0=.0005, resume=False)
        checkpoint = dict(epoch=1, optimizer={"state": {}}, train_args=dict(recipe))
        history = [dict(epoch=1), dict(epoch=2)]
        self.assertEqual(verify_resume_state(checkpoint, history, recipe), 2)
        with self.assertRaises(ValueError):
            verify_resume_state(dict(checkpoint, optimizer=None), history, recipe)
        with self.assertRaises(ValueError):
            verify_resume_state(checkpoint, [dict(epoch=1), dict(epoch=3)], recipe)
        with self.assertRaises(ValueError):
            verify_resume_state(checkpoint, history, dict(recipe, lr0=.001))

    def test_historical_checkpoint_cannot_win_controlled_comparison(self):
        rows = [dict(name="existing", role="historical_reference", map50_95=.99),
                dict(name="yolo11n", role="controlled", map50_95=.60),
                dict(name="yolov8n", role="controlled", map50_95=.65)]
        result = select_winner(rows)
        self.assertEqual(result["winner"], "yolov8n")
        self.assertAlmostEqual(result["difference_percentage_points"], 5)
        rows[-1]["map50_95"] = .60
        self.assertEqual(select_winner(rows)["winner"], "tie")

    def test_training_has_no_early_stop_or_inherited_checkpoint_advantage(self):
        args = SimpleNamespace(epochs=20, imgsz=416, batch=8, device="cpu", seed=42)
        recipe = training_options(args)
        self.assertGreater(recipe["patience"], recipe["epochs"])
        self.assertFalse(recipe["resume"])
        self.assertIsNone(recipe["freeze"])
        self.assertEqual(recipe["optimizer"], "AdamW")

    def test_material_ids_and_mixed_polygons_become_single_class_boxes(self):
        text, counts, polygons = normalize_annotations("3 .5 .5 .4 .4\n1 .2 .2 .8 .2 .8 .8 .2 .8\n")
        self.assertEqual([row.split()[0] for row in text.splitlines()], ["0", "0"])
        self.assertEqual(polygons, 1)
        self.assertEqual(sum(counts.values()), 2)
        self.assertEqual(len(text.splitlines()[1].split()), 5)

    def test_audit_detects_pixel_leakage_and_label_mutation(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for split in ("train", "valid", "test"):
                (root/split/"images").mkdir(parents=True)
                (root/split/"labels").mkdir()
                Image.new("RGB", (12, 12), "red" if split != "test" else "blue").save(root/split/"images/a.png")
                (root/split/"labels/a.txt").write_text("0 .5 .5 .4 .4\n")
            before = audit_snapshot(root)
            self.assertEqual(len(before["exact_pixel_cross_split"]), 1)
            self.assertEqual(before["counts"]["test"]["objects"], 1)
            (root/"data.yaml").write_text(json.dumps(dict(path=root.as_posix(), train="train/images", val="valid/images", test="test/images", nc=1, names=["item"])))
            verify_snapshot(root, before["sha256"])
            (root/"test/labels/a.txt").write_text("0 .5 .5 .6 .6\n")
            after = audit_snapshot(root)
            self.assertNotEqual(before["sha256"], after["sha256"])
            with self.assertRaises(ValueError):
                verify_snapshot(root, before["sha256"])
            (root/"data.yaml").write_text(json.dumps(dict(path=root.as_posix(), train="test/images", val="valid/images", test="test/images", nc=1, names=["item"])))
            with self.assertRaises(ValueError):
                verify_snapshot(root, after["sha256"])
            (root/"test/labels/a.txt").write_text("1 .5 .5 .6 .6\n")
            with self.assertRaises(ValueError):
                audit_snapshot(root)

    def test_report_replaces_atomically_without_pending_residue(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            write_json(path, {"status": "training"})
            write_json(path, {"status": "complete"})
            self.assertEqual(json.loads(path.read_text())["status"], "complete")
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_partial_or_skipped_epochs_cannot_be_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"results.csv"
            path.write_text("epoch,metrics/mAP50-95(B)\n1,.4\n")
            with self.assertRaises(ValueError):
                verify_completed_run(folder, 2)
            path.write_text("epoch,metrics/mAP50-95(B)\n1,.4\n3,.5\n")
            with self.assertRaises(ValueError):
                verify_completed_run(folder, 2)
            path.write_text("epoch,metrics/mAP50-95(B)\n1,.4\n2,.5\n")
            self.assertEqual(verify_completed_run(folder, 2)["completed_epochs"], 2)


if __name__ == "__main__":
    unittest.main()
