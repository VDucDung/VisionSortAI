import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from trashsmart.training.prepare_yolo import prepare_dataset


class YoloCropsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / "source", self.root / "output"
        self.names = ["glass", "metal", "paper", "plastic"]
        for split in ("train", "valid", "test"):
            for sub in ("images", "labels"):
                (self.source / split / sub).mkdir(parents=True)
            Image.new("RGB", (100, 80), "red").save(self.source / split / "images" / "sample.png")
            (self.source / split / "labels" / "sample.txt").write_text(
                "\n".join(f"{i} 0.5 0.5 0.4 0.5" for i in range(4)))

    def test_crops_keep_class_ids_geometry_and_original_splits(self):
        manifest = prepare_dataset(self.source, self.output, self.names)
        self.assertEqual(manifest["crop_count"], 12)
        for split in ("train", "valid", "test"):
            for name in self.names:
                with Image.open(self.output / split / name / f"sample__box{self.names.index(name):03d}.jpg") as image:
                    self.assertEqual(image.size, (40, 40))
        from trashsmart.training import data_utils
        with patch.multiple(data_utils, DIR_PATH=self.output, TRAIN_DIR=self.output / "train",
                            VAL_DIR=self.output / "valid", NUM_WORKERS=0, BATCH_SIZE=2):
            train, valid, names = data_utils.get_data_loaders()
        self.assertEqual(names, self.names)
        self.assertEqual(len(train.dataset), 4)
        self.assertEqual(len(valid.dataset), 4)
        self.assertTrue(all(Path(p).is_relative_to(self.output / "train") for p, _ in train.dataset.samples))
        self.assertTrue(all(Path(p).is_relative_to(self.output / "valid") for p, _ in valid.dataset.samples))

    def test_invalid_class_fails_before_creating_output(self):
        (self.source / "test" / "labels" / "sample.txt").write_text("9 0.5 0.5 0.4 0.5")
        with self.assertRaises(ValueError):
            prepare_dataset(self.source, self.output, self.names)
        self.assertFalse(self.output.exists())

    def test_polygon_is_converted_to_enclosing_box(self):
        label = self.source / "train" / "labels" / "sample.txt"
        label.write_text(label.read_text().replace("0 0.5 0.5 0.4 0.5",
                                                  "0 0.2 0.25 0.8 0.25 0.8 0.75 0.2 0.75"))
        prepare_dataset(self.source, self.output, self.names)
        with Image.open(self.output / "train/glass/sample__box000.jpg") as image:
            self.assertEqual(image.size, (60, 40))

    def test_existing_dataset_is_never_overwritten(self):
        self.output.mkdir()
        (self.output / "keep.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            prepare_dataset(self.source, self.output, self.names)
        self.assertEqual((self.output / "keep.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
