"""Train ResNet50 on prepared YOLO crops, then evaluate the held-out test split."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--head-epochs", type=int, default=10)
    parser.add_argument("--finetune-epochs", type=int, default=40)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--train-profile", choices=("legacy", "object"), default="legacy",
                        help="Explicit augmentation experiment; object preserves the full crop")
    parser.add_argument("--init-checkpoint", help="Continue learning from this trained checkpoint")
    parser.add_argument("--learning-rate", type=float, default=0.00001,
                        help="Learning rate for incremental fine-tuning")
    parser.add_argument("--threads", type=int, default=min(4, os.cpu_count() or 1))
    args = parser.parse_args()
    if not 0 < args.learning_rate < float("inf"):
        parser.error("Learning rate must be finite and positive.")
    if min(args.head_epochs, args.finetune_epochs, args.threads) < 1 or args.batch_size < 2 or args.workers < 0:
        parser.error("Epochs must be positive, batch size >= 2, workers >= 0.")
    dataset, run_dir = Path(args.dataset).resolve(), Path(args.run_dir).resolve()
    if args.init_checkpoint and not Path(args.init_checkpoint).is_file():
        raise FileNotFoundError(args.init_checkpoint)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Choose an empty run directory: {run_dir}")
    if not all((dataset / s).is_dir() for s in ("train", "valid", "test")):
        raise ValueError("Dataset must contain train, valid and test directories.")
    os.environ.update(DATASET_PATH=str(dataset), RESNET_MODEL_PATH=str(run_dir / "best.pth"),
                      BATCH_SIZE=str(args.batch_size), STAGE1_EPOCHS=str(args.head_epochs),
                      EPOCHS=str(args.finetune_epochs), LEARNING_RATE="0.0001",
                      NUM_WORKERS=str(args.workers), TRASHSMART_CLASSES="glass,metal,paper,plastic",
                      RESNET_TRAIN_PROFILE=args.train_profile)
    import random
    import numpy as np
    import torch
    from torchvision.datasets import ImageFolder
    from torch.utils.data import DataLoader
    from sklearn.metrics import classification_report, confusion_matrix
    from trashsmart.training.config import DEVICE
    from trashsmart.training.data_utils import get_data_loaders, get_class_weights
    from trashsmart.training.model_utils import build_model
    from trashsmart.training.train import train_two_stages, train_incremental
    from trashsmart.training.evaluate import evaluate_model
    from trashsmart.shared.classes import CLASS_NAMES, validate_class_order
    from trashsmart.shared.transforms import get_eval_transform
    from trashsmart.shared.resnet_config import RESNET_INPUT_SIZE, FIX_LOW_LIGHT, FIX_MOTION_BLUR

    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.set_num_threads(args.threads)
    train, valid, names = get_data_loaders()
    validate_class_order(names)
    test_ds = ImageFolder(dataset / "test", transform=get_eval_transform())
    validate_class_order(test_ds.classes)
    test = DataLoader(test_ds, batch_size=args.batch_size, num_workers=args.workers)
    run_dir.mkdir(parents=True, exist_ok=True)
    config = dict(vars(args), classes=CLASS_NAMES, device=str(DEVICE), seed=42,
                  train_samples=len(train.dataset), valid_samples=len(valid.dataset),
                  test_samples=len(test.dataset), torch_version=torch.__version__,
                  input_size=RESNET_INPUT_SIZE,
                  evaluation_preprocessing=dict(letterbox=True, low_light=FIX_LOW_LIGHT,
                                                motion_blur=FIX_MOTION_BLUR))
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps(config, indent=2), flush=True)
    if args.init_checkpoint:
        import hashlib
        from trashsmart.shared.model import load_resnet_checkpoint
        checkpoint_path = Path(args.init_checkpoint).resolve()
        config["init_checkpoint"] = str(checkpoint_path)
        config["init_checkpoint_sha256"] = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        model = load_resnet_checkpoint(checkpoint_path, len(names), DEVICE)
        history, baseline = train_incremental(
            model, train, valid, get_class_weights(train.dataset),
            lr=args.learning_rate, epochs=args.finetune_epochs)
        config["baseline_validation"] = baseline
        config["checkpoint_selection"] = "validation accuracy; starting checkpoint retained on ties"
        (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    else:
        model = build_model()
        history = train_two_stages(model, train, valid, get_class_weights(train.dataset))
    (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    _, predicted, labels = evaluate_model(test)
    report = classification_report(labels, predicted, labels=list(range(len(names))),
                                   target_names=names, output_dict=True, zero_division=0)
    metrics = {"split": "test", "report": report,
               "class_names": names, "confusion_matrix": confusion_matrix(
                   labels, predicted, labels=list(range(len(names)))).tolist()}
    (run_dir / "test_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Completed. Best checkpoint and test metrics: {run_dir}", flush=True)


if __name__ == "__main__":
    main()
