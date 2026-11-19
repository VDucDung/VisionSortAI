import copy
import io
import unittest

import torch
from ultralytics import YOLO
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils.loss import BboxLoss

from trashsmart.yolo_training.improvements import (
    AttentionOutput, EIoUBboxLoss, PaperCBAM, add_improvements, eiou_loss, original_state_digest,
)


class ImprovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(4)
        cls.base = DetectionModel(YOLO("yolo11n.pt").model.yaml, nc=1, verbose=False)

    def test_eiou_matches_equation_and_has_finite_gradients(self):
        target = torch.tensor([[0., 0., 4., 2.]])
        self.assertEqual(eiou_loss(target, target).item(), 0.)
        predicted = torch.tensor([[0., 0., 2., 2.]], requires_grad=True)
        value = eiou_loss(predicted, target)
        self.assertAlmostEqual(value.item(), .8, places=6)
        value.backward()
        self.assertTrue(torch.isfinite(predicted.grad).all())
        self.assertTrue(torch.allclose(eiou_loss(predicted.detach() * 10, target * 10), value))

    def test_cbam_preserves_shape_and_learns_both_attention_branches(self):
        module = PaperCBAM(16)
        image = torch.rand(2, 16, 9, 7, requires_grad=True)
        result = module(image)
        self.assertEqual(result.shape, image.shape)
        result.sum().backward()
        for parameter in module.parameters():
            self.assertIsNotNone(parameter.grad)
            self.assertTrue(torch.isfinite(parameter.grad).all())

    def test_attachment_preserves_all_original_tensors_and_rng(self):
        model = copy.deepcopy(self.base)
        digest = original_state_digest(model)
        random_state = torch.random.get_rng_state().clone()
        add_improvements(model, cbam=True, eiou=True)
        self.assertEqual(original_state_digest(model), digest)
        self.assertTrue(torch.equal(random_state, torch.random.get_rng_state()))
        self.assertEqual([i for i, layer in enumerate(model.model) if isinstance(layer, AttentionOutput)], [16, 19, 22])
        with self.assertRaises(ValueError):
            add_improvements(model, cbam=True)
        buffer = io.BytesIO()
        torch.save(model, buffer)
        buffer.seek(0)
        restored = torch.load(buffer, weights_only=False)
        restored.eval()
        with torch.no_grad():
            output = restored(torch.rand(1, 3, 64, 64))
        self.assertIsNotNone(output)
        self.assertEqual(original_state_digest(restored), digest)

    def test_replacing_regression_keeps_dfl_and_does_not_patch_library(self):
        before = BboxLoss.forward
        stock, improved = BboxLoss(16), EIoUBboxLoss(16)
        pred_dist = torch.randn(1, 3, 64, requires_grad=True)
        pred = torch.tensor([[[0., 0., 2., 2.], [2., 2., 4., 4.], [4., 4., 6., 6.]]], requires_grad=True)
        target = pred.detach() + .25
        arguments = (pred_dist, pred, torch.tensor([[1., 1.], [3., 3.], [5., 5.]]), target,
                     torch.ones(1, 3, 1), torch.tensor(3.), torch.ones(1, 3, dtype=torch.bool),
                     torch.tensor([64, 64]), torch.ones(3, 1))
        original = stock(*arguments)
        changed = improved(*arguments)
        self.assertTrue(torch.equal(original[1], changed[1]))
        sum(changed).backward()
        self.assertTrue(torch.isfinite(pred.grad).all())
        self.assertIs(BboxLoss.forward, before)


if __name__ == "__main__":
    unittest.main()
