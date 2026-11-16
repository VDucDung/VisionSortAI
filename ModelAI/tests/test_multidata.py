import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from trashsmart.yolo_training.multidata import summarize
from trashsmart.yolo_training.public_datasets import annotation_box, capture_group, prepare, split_groups


class PublicDetectionDatasetTests(unittest.TestCase):
    def test_acquisition_frames_share_one_group(self):
        self.assertEqual(capture_group("uavvaste", "BATCH_s05_img_1260.jpg"), "batch_s05")
        self.assertEqual(capture_group("uavvaste", "batch_s05_img_9400.jpg"), "batch_s05")
        self.assertEqual(capture_group("uavvaste", "GOPR0038.JPG"), "gopro_photos")
        self.assertEqual(capture_group("taco", "batch_7/000001.jpg"), "batch_7")

    def test_group_allocation_is_reproducible_and_rejects_unsplittable_data(self):
        groups = {str(index): list(range(index * 10, index * 10 + 10)) for index in range(15)}
        assignment = split_groups(groups, 42)
        self.assertEqual(assignment, split_groups(groups, 42))
        self.assertEqual(set(assignment.values()), {"train", "valid", "test"})
        with self.assertRaises(ValueError):
            split_groups({"one_flight": [1, 2, 3]}, 42)

    def test_coco_geometry_and_all_original_images_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "sample.zip"
            images, annotations = [], []
            with zipfile.ZipFile(archive, "w") as stream:
                for index in range(15):
                    path = root / f"{index}.jpg"
                    photo = Image.new("RGB", (80, 100) if index == 0 else (100, 80),
                                      (index * 15, 20, 100))
                    exif = Image.Exif()
                    exif[274] = 6 if index == 0 else 1
                    photo.save(path, exif=exif)
                    filename = f"batch_{index + 1}/image.jpg"
                    stream.write(path, filename)
                    images.append(dict(id=index, width=100, height=80, file_name=filename))
                    annotations.append(dict(id=index, image_id=index, category_id=7,
                                            bbox=[20, 20, 40, 50], iscrowd=0,
                                            segmentation=[[20, 10, 60, 10, 60, 60, 20, 60]]))
                stream.writestr("annotations.json", json.dumps(dict(
                    images=images, annotations=annotations, categories=[dict(id=7, name="litter")],
                )))
            output = root / "prepared"
            prepare("taco", archive, output, 42)
            audit = json.loads((output / "data_audit.json").read_text())
            self.assertEqual(sum(split["images"] for split in audit["counts"].values()), 15)
            self.assertEqual(sum(split["objects"] for split in audit["counts"].values()), 15)
            self.assertEqual(audit["exact_pixel_cross_split"], [])
            source = json.loads((output / "source.json").read_text())
            self.assertEqual(source["records"][0]["applied_exif_orientation"], 6)
            for path in output.glob("*/labels/*.txt"):
                values = path.read_text().split()
                self.assertEqual(values[0], "0")
                self.assertEqual([float(value) for value in values[1:]], [.4, .4375, .4, .625])
            prepare("taco", archive, output, 42)

    def test_polygon_envelope_corrects_bottom_origin_source_bbox(self):
        annotation = dict(id=1, bbox=[517, 600, 447, 1322],
                          segmentation=[[517, 127, 964, 127, 964, 1449, 517, 1449]])
        self.assertEqual(annotation_box(annotation), (517, 127, 447, 1322))
        with self.assertRaises(ValueError):
            annotation_box(dict(id=2, bbox=[0, 0, 1, 1], segmentation=[]))


class HonestComparisonTests(unittest.TestCase):
    def test_one_regression_prevents_an_all_metrics_improvement_claim(self):
        rows = [dict(dataset="haui", model="yolo11n", precision=.9, recall=.7,
                     f1=.7875, map50=.95, map50_95=.7),
                dict(dataset="haui", model="yolov8n", precision=.8, recall=.8,
                     f1=.8, map50=.9, map50_95=.6)]
        summary = summarize(rows)[0]
        self.assertFalse(summary["yolo11n_higher_on_all_five"])
        self.assertLess(summary["metrics"]["recall"]["relative_change_percent"], 0)
        self.assertGreater(summary["metrics"]["map50_95"]["relative_change_percent"], 0)


if __name__ == "__main__":
    unittest.main()
