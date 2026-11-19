"""Paper-based YOLO11n ablations without modifying installed Ultralytics.

CBAM: Woo et al., ECCV 2018, equations 2-3 (r=16, spatial kernel 7).
EIoU: Zhang et al., Neurocomputing 506 (2022), equation 7, not Focal-EIoU.
"""
import hashlib

import torch
from torch import nn
from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils.loss import BboxLoss, v8DetectionLoss
from ultralytics.utils.tal import bbox2dist

from trashsmart.yolo_training.benchmark import write_json


class PaperCBAM(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        hidden = max(1, channels // reduction)
        self.shared_mlp = nn.Sequential(nn.Conv2d(channels, hidden, 1, bias=False),
                                        nn.ReLU(), nn.Conv2d(hidden, channels, 1, bias=False))
        self.spatial = nn.Conv2d(2, 1, 7, padding=3, bias=False)

    def forward(self, features):
        average = features.mean((2, 3), keepdim=True)
        maximum = features.amax((2, 3), keepdim=True)
        features = features * (self.shared_mlp(average) + self.shared_mlp(maximum)).sigmoid()
        spatial = torch.cat((features.mean(1, keepdim=True), features.amax(1, keepdim=True)), 1)
        return features * self.spatial(spatial).sigmoid()


class AttentionOutput(nn.Module):
    def __init__(self, base, channels):
        super().__init__()
        self.base = base
        self.attention = PaperCBAM(channels)
        self.i, self.f = base.i, base.f
        self.type = base.type + "+PaperCBAM"
        self.np = sum(parameter.numel() for parameter in self.parameters())

    def forward(self, inputs):
        return self.attention(self.base(inputs))


def eiou_loss(predicted, target, eps=1e-7):
    """Equation 7 for aligned xyxy boxes, returning one loss per pair."""
    pred_lt, pred_rb = predicted.chunk(2, -1)
    true_lt, true_rb = target.chunk(2, -1)
    pred_wh, true_wh = (pred_rb - pred_lt).clamp_min(0), (true_rb - true_lt).clamp_min(0)
    intersection_wh = (torch.minimum(pred_rb, true_rb) - torch.maximum(pred_lt, true_lt)).clamp_min(0)
    intersection = intersection_wh.prod(-1, keepdim=True)
    union = pred_wh.prod(-1, keepdim=True) + true_wh.prod(-1, keepdim=True) - intersection
    iou = intersection / union.clamp_min(eps)
    enclosing = (torch.maximum(pred_rb, true_rb) - torch.minimum(pred_lt, true_lt)).clamp_min(0)
    center_distance = (((pred_lt + pred_rb) - (true_lt + true_rb)) / 2).square().sum(-1, keepdim=True)
    center_penalty = center_distance / enclosing.square().sum(-1, keepdim=True).clamp_min(eps)
    side_penalty = ((pred_wh - true_wh).square() / enclosing.square().clamp_min(eps)).sum(-1, keepdim=True)
    return 1 - iou + center_penalty + side_penalty


class EIoUBboxLoss(BboxLoss):
    def forward(self, pred_dist, pred_bboxes, anchor_points, target_bboxes,
                target_scores, target_scores_sum, fg_mask, imgsz, stride):
        if self.dfl_loss is None:
            raise ValueError("This ablation requires the unchanged YOLO11 DFL head")
        foreground = fg_mask.nonzero(as_tuple=True)
        weight = target_scores[foreground].sum(-1, keepdim=True)
        regression = (eiou_loss(pred_bboxes[foreground], target_bboxes[foreground]) * weight).sum() / target_scores_sum
        target_ltrb = bbox2dist(anchor_points, target_bboxes, self.dfl_loss.reg_max - 1)
        distribution = self.dfl_loss(pred_dist[foreground].view(-1, self.dfl_loss.reg_max),
                                     target_ltrb[foreground]) * weight
        return regression, distribution.sum() / target_scores_sum


class AblationDetectionModel(DetectionModel):
    def init_criterion(self):
        criterion = super().init_criterion()
        if self.ablation_factors["eiou"]:
            if not isinstance(criterion, v8DetectionLoss):
                raise ValueError("EIoU ablation requires the standard YOLO11 detection criterion")
            criterion.bbox_loss = EIoUBboxLoss(criterion.reg_max).to(criterion.device)
        return criterion


def original_state_digest(model):
    """Hash all original tensors under canonical names, excluding only added CBAM tensors."""
    digest = hashlib.sha256()
    for index, block in enumerate(model.model):
        base = block.base if isinstance(block, AttentionOutput) else block
        for name, tensor in sorted(base.state_dict().items()):
            digest.update(f"model.{index}.{name}:{tensor.dtype}:{tuple(tensor.shape)}".encode())
            digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def add_improvements(model, cbam=False, eiou=False):
    if getattr(model, "ablation_factors", None) is not None:
        raise ValueError("Do not attach improvements twice")
    before = original_state_digest(model)
    if list(model.model[-1].f) != [16, 19, 22]:
        raise ValueError("Unexpected YOLO11n pyramid; review attachment points")
    # New modules must not alter the initial detector tensors or the global RNG stream.
    with torch.random.fork_rng(devices=[]):
        if cbam:
            for index in (16, 19, 22):
                base = model.model[index]
                if type(base).__name__ != "C3k2":
                    raise ValueError("Expected the YOLO11n neck C3k2 block")
                model.model[index] = AttentionOutput(base, base.cv2.conv.out_channels)
    model.ablation_factors = dict(cbam=cbam, eiou=eiou)
    if eiou:
        model.__class__ = AblationDetectionModel
    if original_state_digest(model) != before:
        raise ValueError("An original pretrained tensor changed while attaching an improvement")
    return model


class AblationTrainer(DetectionTrainer):
    cbam, eiou = False, False

    def get_model(self, cfg=None, weights=None, verbose=True):
        model = super().get_model(cfg, weights, verbose)
        model = add_improvements(model, self.cbam, self.eiou)
        write_json(self.save_dir / "initialization.json", dict(
            common_initial_sha256=original_state_digest(model), factors=model.ablation_factors,
            parameters=sum(parameter.numel() for parameter in model.parameters()),
            attention_locations=[16, 19, 22] if self.cbam else [],
        ))
        return model


class CBAMTrainer(AblationTrainer):
    cbam = True


class EIoUTrainer(AblationTrainer):
    eiou = True


class ImprovedTrainer(AblationTrainer):
    cbam, eiou = True, True


TRAINERS = dict(original=AblationTrainer, cbam=CBAMTrainer, eiou=EIoUTrainer, improved=ImprovedTrainer)
