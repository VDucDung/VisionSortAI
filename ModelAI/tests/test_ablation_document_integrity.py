"""Synthetic temporary fixtures test report guards; they are never research results."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_ablation_chapter import DATASETS, VARIANTS, QUALITY, verify_report


class DocumentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.rows = []
        for dataset in DATASETS:
            for variant in VARIANTS:
                directory = self.root / dataset / variant
                (directory / "weights").mkdir(parents=True)
                payload = (dataset + variant).encode()
                (directory / "weights/best.pt").write_bytes(payload)
                digest = hashlib.sha256(payload).hexdigest()
                (directory / "results.csv").write_text("epoch\n" + "".join(f"{epoch}\n" for epoch in range(1, 31)))
                row = dict(dataset=dataset, variant=variant, checkpoint_sha256=digest,
                           **{key: .5 for key in QUALITY})
                self.rows.append(row)
                raw = dict(checkpoint_sha256=digest, map50=.5, map50_95=.5,
                           fixed_confidence=dict(precision=.5, recall=.5, f1=.5))
                (directory / "test_results.json").write_text(json.dumps(raw))
        self.write(self.rows)

    def write(self, rows):
        (self.root / "comparison_original_improved.json").write_text(json.dumps(dict(results=rows)))

    def test_accepts_complete_consistent_report(self):
        self.assertEqual(len(verify_report(self.root)["results"]), 12)

    def test_missing_or_repeated_variant_cannot_look_complete(self):
        self.write(self.rows[:-1])
        with self.assertRaisesRegex(ValueError, "twelve"):
            verify_report(self.root)
        self.write(self.rows[:-1] + [self.rows[0]])
        with self.assertRaisesRegex(ValueError, "twelve"):
            verify_report(self.root)

    def test_changed_checkpoint_or_skipped_epoch_is_rejected(self):
        checkpoint = self.root / "haui/original/weights/best.pt"
        original = checkpoint.read_bytes()
        checkpoint.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checkpoint changed"):
            verify_report(self.root)
        checkpoint.write_bytes(original)
        (self.root / "haui/original/results.csv").write_text("epoch\n1\n3\n")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            verify_report(self.root)

    def test_non_finite_and_inflated_comparison_metrics_are_rejected(self):
        altered = copy.deepcopy(self.rows)
        altered[0]["map50_95"] = float("nan")
        self.write(altered)
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            verify_report(self.root)
        altered[0]["map50_95"] = .9
        self.write(altered)
        with self.assertRaisesRegex(ValueError, "raw evaluation"):
            verify_report(self.root)


if __name__ == "__main__":
    unittest.main()
