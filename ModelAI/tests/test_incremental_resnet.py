import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
from trashsmart.training.prepare_incremental import prepare_incremental, CLASSES, FOLDER_MAP


class ReplayDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.old, self.new, self.out = root / "old", root / "new", root / "output"
        for i, split in enumerate(("train", "valid", "test")):
            for j, name in enumerate(CLASSES):
                folder = self.old / split / name
                folder.mkdir(parents=True)
                Image.new("RGB", (8, 8), (i * 70, j * 50, 0)).save(folder / "old.png")
        for j, folder_name in enumerate(FOLDER_MAP):
            folder = self.new / folder_name
            folder.mkdir(parents=True)
            Image.new("RGB", (8, 8), (j * 30, 20, 200)).save(folder / "new.png")

    def test_replay_preserves_held_out_bytes_and_maps_new_labels(self):
        result = prepare_incremental(self.old, self.new, self.out)
        self.assertEqual(len(result["added"]), 4)
        for split in ("valid", "test"):
            for name in CLASSES:
                relative = Path(split) / name / "old.png"
                self.assertEqual((self.old / relative).read_bytes(), (self.out / relative).read_bytes())
                self.assertEqual(len(list((self.out / split / name).iterdir())), 1)
        for name in CLASSES:
            self.assertEqual(result["counts"]["train"][name], 2)

    def test_held_out_and_internal_duplicates_are_excluded(self):
        with Image.open(self.old / "test/plastic/old.png") as image:
            image.save(self.new / "nhua/test-copy.png")
        with Image.open(self.new / "nhua/new.png") as image:
            image.save(self.new / "nhua/duplicate.bmp")
        result = prepare_incremental(self.old, self.new, self.out)
        self.assertEqual(len(result["added"]), 4)
        self.assertEqual(len(result["skipped"]), 2)

    def test_conflicting_duplicate_labels_fail_before_writing(self):
        with Image.open(self.old / "test/metal/old.png") as image:
            image.save(self.new / "nhua/conflict.png")
        with self.assertRaises(ValueError):
            prepare_incremental(self.old, self.new, self.out)
        self.assertFalse(self.out.exists())


class FineTuneSelectionTests(unittest.TestCase):
    def test_baseline_is_saved_and_passed_to_checkpoint_selection(self):
        source = Path(__file__).resolve().parents[1] / "trashsmart/training/train.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "train_incremental")
        save, stage = Mock(), Mock(return_value={"loss": [0.3]})
        env = {"nn": SimpleNamespace(CrossEntropyLoss=Mock()), "DEVICE": "cpu",
               "validate_epoch": Mock(return_value=(0.2, 0.95, None, None)),
               "require_finite": Mock(), "require_accuracy": Mock(),
               "_save_if_best": save, "_run_stage": stage}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), env)
        model = Mock()
        history, baseline = env["train_incremental"](model, "train", "valid", None, lr=1e-5, epochs=5)
        save.assert_called_once_with(model, 0.95, float("-inf"))
        self.assertEqual(stage.call_args.kwargs["best_val_acc"], 0.95)
        self.assertTrue(stage.call_args.kwargs["unfreeze"])
        self.assertEqual(baseline["accuracy"], 0.95)


if __name__ == "__main__":
    unittest.main()
