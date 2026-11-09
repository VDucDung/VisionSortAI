# Improving YOLO mAP50 and Recall on CPU

The current target is Precision >= 0.90 AND Recall >= 0.90 at the same operating
point, with mAP50 >= 0.90. See [OVERNIGHT_PR90.md](OVERNIGHT_PR90.md) for the
longer YOLO11s CPU workflow and strict validation/test publication conditions.
This is an experiment target,
not a guaranteed outcome. Use validation for selecting weights, confidence,
resolution and TTA; evaluate test only after selection. Keep the original split.

## Compare available checkpoints before retraining

```powershell
python -m trashsmart.yolo_training.search_accuracy --checkpoints trashsmart/models/best_new.pt runs/waste_detection_yolo11_roboflow/run_640/weights/best.pt runs/detect/runs/waste_detection_yolo11_finetune/run_640_lr0001/weights/best.pt --imgsz 640 --tta off --threads 4 --batch 8 --output outputs/yolo-checkpoints-new
```

Try TTA or image size 960 for the strongest checkpoint, rather than repeating the
entire grid. Each experiment directory must be new. Reports distinguish:

- Native mAP50 and Recall at the Ultralytics max-F1 operating point.
- Exact TP/GT Recall at a selected deployment confidence, with Precision >= 0.90
  by default (`--min-precision` changes this explicit constraint).
- Exact Precision/Recall at common fixed thresholds, plus inference timing.

`both_targets_met` applies to mAP50 and the explicitly selected operating point.
`summary_targets_met` requires the native max-F1 Recall to reach the target too.
The threshold search does not change AP: native validation always uses `conf=0.001`.
Lowering confidence can increase Recall while decreasing Precision; report both.

## Bounded fine-tuning on the current CPU

First prepare a detection-only snapshot. The original source contains two training
images that Ultralytics rejects because their label files mix boxes and polygons.
The snapshot converts polygons to enclosing boxes, merges material IDs for object
localization, preserves image bytes and original splits, and leaves source data
unchanged. Existing box coordinates are preserved.

```powershell
python -m trashsmart.yolo_training.prepare_detection --source D:/thacsi/DOAN/HAUI-TRASH/data/data-yolo --output outputs/yolo-detection-clean-new
```

```powershell
python -m trashsmart.yolo_training.train_accuracy --model runs/detect/runs/waste_detection_yolo11_finetune/run_640_lr0001/weights/best.pt --data outputs/yolo-detection-clean-new/data.yaml --run-dir outputs/yolo-cpu-finetune-new --minutes 30 --epochs 10 --imgsz 640 --batch 8 --threads 4
```

This is a new optimizer run, not an interrupted optimizer resume. The starting
checkpoint is evaluated and retained as the initial champion. Fine-tuning freezes
the first ten layers by default, uses gentle augmentation without Mosaic, and
selects `best_precision_recall.pt` by maximizing the smaller of validation
Precision and Recall, then F1 and mAP50. It does not replace API weights. A time cap covers the training
loop; initial/final validation and model loading add time. The explicit epoch cap
is enforced even when Ultralytics estimates epoch counts from the time budget.

Frozen layers and a small CPU budget are practical constraints, not evidence this
recipe will improve every run. Re-evaluate the selected weights with the same
settings as the baseline before deployment. Keep the baseline if results regress.

## Final evaluation and API settings

```powershell
python -m trashsmart.yolo_training.evaluate_yolo --split test --model path/to/selected.pt --imgsz 640 --conf 0.15 --iou 0.7 --tta --output outputs/yolo-final-test-new.json
```

The confidence above is an example: substitute the exact value chosen on
validation. Use `--no-tta` for a non-TTA selection. The command reports native
metrics and exact Precision/Recall at the supplied confidence separately.

API and ROI inference honor `YOLO_IMG_SIZE`, `YOLO_CONF_THRESHOLD`,
`YOLO_IOU_THRESHOLD`, `YOLO_TTA` (`0`/`1`) and `YOLO_AGNOSTIC_NMS` (`0`/`1`).
Class-agnostic NMS aligns a multi-material checkpoint with single-class object
localization. URL requests can still override confidence and NMS IoU. Preserve a
backup before updating `trashsmart/models/best_new.pt`; restart the API to reload
weights and environment settings. TTA and larger images increase CPU latency.

The source mixes a few polygon annotations with detection boxes and declares a
single Bottle class despite material IDs 0–3. Files containing only polygons can
be converted by Ultralytics, but mixed rows within one file are rejected. The clean
snapshot resolves that format issue. `single_cls=True` merges labels for detection. These scores measure
object localization, not bottle identity or material classification. No source
annotations are automatically relabeled or removed by this workflow.
