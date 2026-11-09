import tempfile
import unittest
from pathlib import Path
from PIL import Image
from trashsmart.training.audit_splits import audit


class SplitAuditTests(unittest.TestCase):
    def test_decoded_duplicates_detected_across_file_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for split, color in (("train", "red"), ("valid", "red"), ("test", "blue")):
                path = root / split / "images"
                path.mkdir(parents=True)
                Image.new("RGB", (20, 30), color).save(path / ("a.png" if split == "train" else "b.bmp"))
            result = audit(root)
            self.assertEqual(len(result["exact_pixel_overlap"]), 1)
            self.assertEqual({r["split"] for r in result["exact_pixel_overlap"][0]}, {"train", "valid"})


class ObjectAugmentationTests(unittest.TestCase):
    def test_letterbox_keeps_top_and_bottom_of_tall_object(self):
        from trashsmart.shared.transforms import LetterboxTrainImage, get_train_transform
        import numpy as np
        image = Image.new("RGB", (20, 100), "red")
        image.paste("blue", (0, 90, 20, 100))
        array = np.asarray(LetterboxTrainImage(100)(image))
        self.assertEqual(array.shape, (100, 100, 3))
        self.assertEqual(array[0, 50].tolist(), [255, 0, 0])
        self.assertEqual(array[99, 50].tolist(), [0, 0, 255])
        tensor = get_train_transform(100, profile="object")(image)
        self.assertEqual(tuple(tensor.shape), (3, 100, 100))


if __name__ == "__main__":
    unittest.main()
