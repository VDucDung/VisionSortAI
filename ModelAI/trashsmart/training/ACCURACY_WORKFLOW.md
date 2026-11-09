# Accuracy improvement workflow

Run commands from the repository root with the existing Python environment.
These evaluation commands write reports without replacing production weights or
uploading images. Use a new output filename for each evaluation.

## Compare checkpoints fairly

```powershell
python -m trashsmart.training.benchmark_resnet --dataset outputs/data-resnet --split valid --checkpoints trashsmart/models/best_resnet50_model1.pth outputs/resnet-yolo-20261021-225037/best.pth --modes letterbox_enhanced letterbox_only --output outputs/checkpoint-validation.json
```

Reports include checkpoint SHA256, classification report, confusion matrix,
per-image predictions and confidence thresholds with both coverage and accepted
accuracy. Rejecting more predictions must not be described as unconditional
accuracy improvement. Choose settings on validation; use test for final reporting.

For the legacy flat dataset, pass its root and `--flat-validation`. This uses the
same seeded 90/10 split as legacy training; it is not an independent new test set.
Compare both domains before changing the production classifier.

## Audit splits before interpreting scores

```powershell
python -m trashsmart.training.audit_splits --source D:/thacsi/DOAN/HAUI-TRASH/data/data-yolo --output outputs/split-audit.json
```

Exact decoded RGB duplicates across splits are reported. Roboflow source filename
overlap is only a review candidate. This does not detect all near-duplicates or
shared physical objects; review source identities and capture sessions manually.
Do not silently remove or re-split existing held-out data after seeing its errors.

## Measure the actual detection/classification chain

```powershell
python -m trashsmart.training.benchmark_pipeline --source D:/thacsi/DOAN/HAUI-TRASH/data/data-yolo --classes glass metal paper plastic --split valid --resnet outputs/resnet-yolo-20261021-225037/best.pth --output outputs/pipeline-validation.json
```

The supplied classes must be the verified **material annotation ID order**. The
source export currently says `Bottle` in data.yaml despite using IDs 0–3. YOLO
intentionally merges those IDs for localization; the benchmark uses the material
IDs for end-to-end scoring. A generic waste detection model cannot claim every
detected object is a bottle. Verify object scope separately if the product only
accepts bottles.

Matching uses confidence-ordered one-to-one boxes at evaluation IoU 0.5, then
scores material labels. It reports misses, extra detections, material errors,
unknowns, precision/recall and per-material results. This is a fixed operating
point benchmark, not COCO mAP. `--iou` controls NMS; `--match-iou` controls scoring.
Use exactly the same thresholds and checkpoints when comparing reports. All
images are included, including negative images and images with zero predictions.

## Run an isolated augmentation experiment

```powershell
python -m trashsmart.training.train_yolo_crops --dataset outputs/data-resnet --run-dir outputs/resnet-object-experiment --train-profile object
```

The `object` profile letterboxes the entire crop first, uses mild geometry and
color changes, and omits vertical flips and RandomResizedCrop. `legacy` remains
the default until the experiment demonstrates an improvement. Configuration is
recorded in each run. Start with the existing baseline and identical splits;
select on validation and compare macro-F1 and per-class recall, not accuracy alone.
The next fine-tuning stage now restores the best stage-1 accuracy checkpoint.

## Promotion and additional data

YOLO training compares the active and candidate models with identical validation
settings before replacing the active checkpoint. Publication requires strictly
higher mAP50–95 with no recall regression. A `promotion.json` report records the
decision, backup and candidate. Ties, invalid metrics and validation errors retain
the active model. This validation gate does not guarantee real camera performance.

ResNet evaluations never automatically publish. Preserve a rollback copy and check
both crop and full-image results. The API and ROI crop pipelines accept the optional
`RESNET_CROP_MODEL_PATH` override. Without it they retain the existing
`RESNET_MODEL_PATH`/legacy default. Relative paths resolve from the project root.
The crop override does not change legacy full-frame training/evaluation settings.
Restart the API after selecting a model: a running server keeps its loaded weights.
For Docker deployment include the selected weights in `trashsmart/models` and set
the crop override to the container-relative path, then rebuild/redeploy the image.

Collect new camera images for plastic/metal confusion, transparent and reflective
objects, partial occlusion and difficult lighting. Group by physical object and
capture session before splitting. Previously fine-tuned bottle images are training
data and cannot serve as independent held-out evidence.
