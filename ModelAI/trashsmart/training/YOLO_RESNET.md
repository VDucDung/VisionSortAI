# Train ResNet50 from the YOLO dataset

Run from the project root in PowerShell (activate your Python environment first):

```powershell
.\scripts\train-resnet-yolo.ps1
```

Or select an interpreter explicitly:

```powershell
.\scripts\train-resnet-yolo.ps1 -Python 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe'
```

The source defaults to `D:\thacsi\DOAN\HAUI-TRASH\data\data-yolo`.
Its original export `trash.v1i.yolov11 (2).zip` declares the class order
`glass, metal, paper, plastic`. All 1,826 annotation files were compared with
that archive and match. The current source `data.yaml` incorrectly declares
one class, Bottle; this workflow supplies the verified mapping explicitly and
does not edit the source dataset.

Conversion supports YOLO bounding boxes and segmentation polygons (using each
polygon's enclosing rectangle). One crop is written per annotation. Crops stay
in their original train/valid/test split. Empty background images do not
produce crops. Conversion validates annotations before writing and refuses
to overwrite a nonempty output directory.

Prepared images and the crop provenance manifest are in `outputs/data-resnet`.
Training uses ImageNet pretrained ResNet50, 10 frozen-backbone epochs and up
to 40 fine-tuning epochs with early stopping. Override these using
`-HeadEpochs`, `-FinetuneEpochs`, and `-BatchSize`. CUDA is used when available;
the currently installed PyTorch is CPU-only. Pretrained weights must already
be cached or be downloadable on the first run.

Each run uses a new `outputs/resnet-yolo-TIMESTAMP` directory containing:

- `config.json`: settings, split sizes, device, and class order.
- `best.pth`: best validation checkpoint across both stages.
- `history.json`: training and validation history after training completes.
- `test_metrics.json`: held-out test classification report and confusion matrix,
  generated using the best checkpoint after training completes.

Existing production checkpoints are not overwritten. This is a new training
run, not a resume from a previous trash classifier. The legacy flat ImageFolder
training path still supports its existing 90/10 split. The new split layout
uses the supplied train and valid directories without re-splitting.

For direct use:

```powershell
python -m trashsmart.training.prepare_yolo --source 'D:\thacsi\DOAN\HAUI-TRASH\data\data-yolo' --output outputs/data-resnet --classes glass metal paper plastic
python -u -m trashsmart.training.train_yolo_crops --dataset outputs/data-resnet --run-dir outputs/resnet-yolo-run1
```

The test split is excluded from fitting and checkpoint selection. Preserving
the provided split does not itself prove that the source dataset contains no
duplicate or near-duplicate images across splits.

## Continue from the trained checkpoint with bottle images

```powershell
.\scripts\finetune-resnet-chai.ps1 -Python 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe'
```

This builds `outputs/data-resnet-incremental-chai` by copying the existing
training data and adding the unique images from `dataset_new_chai`. Vietnamese
folder names map to the existing English class order. Validation and test files
are copied byte-for-byte, with no additional images inserted into those splits.
Duplicate detection compares decoded RGB pixels, including original images
behind validation/test crops when the original manifest is available. It does
not detect resized copies or near-duplicates. The incremental manifest records
the additions, exclusions, and counts. A prepared dataset is a snapshot; to
incorporate later source changes, generate another output directory with
`prepare_incremental` instead of reusing the existing snapshot.

`--init-checkpoint` loads all learned model weights and checks the class order.
This starts a new optimizer, not an interrupted-run resume. The starting model
is evaluated on validation and saved in the new run directory before training.
Fine-tuning opens layer3/layer4, uses learning rate 1e-5, and runs five epochs by
default. New weights replace that copy only on strictly better validation
accuracy. The original checkpoint and API configuration are never changed.
Selection does not use test metrics. After training, held-out test metrics are
written as usual. Retaining validation accuracy does not guarantee retaining
test or real-world accuracy, so compare the reports before deploying.

The additional set is too small to provide reliable separate held-out results
for every class (only one paper image). It is used for training only; scores
from the old test set do not measure generalization to new bottle photos.

Direct fine-tuning command after preparation:

```powershell
python -u -m trashsmart.training.train_yolo_crops --dataset outputs/data-resnet-incremental-chai --run-dir outputs/resnet-chai-run1 --init-checkpoint outputs/resnet-yolo-20261021-225037/best.pth --finetune-epochs 5 --learning-rate 0.00001
```
