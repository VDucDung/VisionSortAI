import tempfile
import unittest
from pathlib import Path
from PIL import Image
from trashsmart.yolo_training.prepare_detection import prepare, normalize_annotations


class DetectionSnapshotTests(unittest.TestCase):
    def test_mixed_box_polygon_converts_to_only_boxes_without_dropping_objects(self):
        text = "3 .5 .5 .4 .6\n1 .1 .2 .7 .2 .7 .8 .1 .8\n"
        converted, counts, polygons = normalize_annotations(text)
        rows = [line.split() for line in converted.splitlines()]
        self.assertEqual([len(row) for row in rows], [5, 5])
        self.assertEqual([row[0] for row in rows], ["0", "0"])
        self.assertAlmostEqual(float(rows[1][1]), .4)
        self.assertAlmostEqual(float(rows[1][3]), .6)
        self.assertEqual(sum(counts.values()), 2)
        self.assertEqual(polygons, 1)

    def test_snapshot_preserves_image_bytes_splits_and_source_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "snapshot"
            for split in ("train", "valid", "test"):
                (source / split / "images").mkdir(parents=True)
                (source / split / "labels").mkdir()
                Image.new("RGB", (20, 30), "red").save(source / split / "images/a.jpg")
                (source / split / "labels/a.txt").write_text("2 .5 .5 .4 .6\n")
            report = prepare(source, output)
            for split in report["counts"]:
                self.assertEqual(report["counts"][split]["objects"], 1)
                self.assertEqual((source / split / "images/a.jpg").read_bytes(),
                                 (output / split / "images/a.jpg").read_bytes())
                self.assertEqual((source / split / "labels/a.txt").read_text(), "2 .5 .5 .4 .6\n")
            with self.assertRaises(FileExistsError):
                prepare(source, output)


if __name__ == "__main__":
    unittest.main()
