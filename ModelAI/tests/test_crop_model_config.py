"""Validate independent crop/full-image paths without importing torch or .env secrets."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch


class CropModelPathTests(unittest.TestCase):
    def resolve(self, settings):
        path = Path(__file__).resolve().parents[1] / "trashsmart/pipeline/config.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        nodes = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RESNET_MODEL_PATH"
                                                    for t in node.targets):
                nodes.append(node)
            elif isinstance(node, ast.If) and "RESNET_MODEL_PATH" in ast.unparse(node.test):
                nodes.append(node)
        root = Path("workspace").resolve()
        env = dict(Path=Path, os=os, PROJECT_ROOT=root, MODELS_DIR=root / "trashsmart/models")
        with patch.dict(os.environ, settings, clear=True):
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
        return env["RESNET_MODEL_PATH"], root

    def test_no_override_preserves_legacy(self):
        actual, root = self.resolve({})
        self.assertEqual(actual, root / "trashsmart/models/best_resnet50_model1.pth")

    def test_crop_override_takes_priority_and_resolves_relative_path(self):
        actual, root = self.resolve(dict(RESNET_MODEL_PATH="old.pth", RESNET_CROP_MODEL_PATH="models/crop.pth"))
        self.assertEqual(actual, root / "models/crop.pth")

    def test_generic_override_still_supported(self):
        actual, root = self.resolve(dict(RESNET_MODEL_PATH="models/full.pth"))
        self.assertEqual(actual, root / "models/full.pth")


if __name__ == "__main__":
    unittest.main()
