"""Compare classifiers and preprocessing on one explicit split; never publish weights."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Prepared ImageFolder split dataset")
    parser.add_argument("--checkpoints", nargs="+", required=True)
    parser.add_argument("--split", choices=("valid", "test"), default="valid")
    parser.add_argument("--flat-validation", action="store_true",
                        help="Use the legacy seeded 10%% validation subset of a flat ImageFolder")
    parser.add_argument("--modes", nargs="+", choices=("letterbox_only", "letterbox_enhanced"),
                        default=["letterbox_enhanced"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if min(args.batch_size, args.threads) < 1:
        parser.error("Batch size and threads must be positive")
    if args.flat_validation and args.split != "valid":
        parser.error("Flat datasets have no independent test split")
    import torch
    from torchvision.datasets import ImageFolder
    from torch.utils.data import DataLoader, Subset
    from sklearn.metrics import classification_report, confusion_matrix
    from trashsmart.shared.classes import CLASS_NAMES, validate_class_order
    from trashsmart.shared.model import load_resnet_checkpoint
    from trashsmart.shared.preprocessing import ResNetEvalTransform
    from trashsmart.training.compare_preprocessing import LetterboxOnly
    from trashsmart.shared.resnet_config import FIX_LOW_LIGHT, FIX_MOTION_BLUR, RESNET_INPUT_SIZE

    torch.set_num_threads(args.threads)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    split_path = Path(args.dataset).resolve()
    if not args.flat_validation:
        split_path = split_path / args.split
    base_dataset = ImageFolder(split_path)
    validate_class_order(base_dataset.classes)
    if args.flat_validation:
        indices = torch.randperm(len(base_dataset), generator=torch.Generator().manual_seed(42)).tolist()
        indices = indices[int(0.9 * len(indices)):]
        dataset = Subset(base_dataset, indices)
        samples = [base_dataset.samples[i] for i in indices]
    else:
        dataset, samples = base_dataset, base_dataset.samples
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"Choose a new report path: {output}")
    result = dict(dataset=str(split_path), split=args.split, samples=len(dataset),
                  flat_validation=args.flat_validation, split_seed=42 if args.flat_validation else None,
                  classes=list(CLASS_NAMES), device=str(device), input_size=RESNET_INPUT_SIZE,
                  enhancement=dict(low_light=FIX_LOW_LIGHT, motion_blur=FIX_MOTION_BLUR),
                  scope="classification on annotated crops; excludes YOLO detection errors",
                  runs=[])
    for checkpoint in args.checkpoints:
        path = Path(checkpoint).resolve()
        model = load_resnet_checkpoint(path, len(CLASS_NAMES), device)
        for mode in args.modes:
            base_dataset.transform = LetterboxOnly() if mode == "letterbox_only" else ResNetEvalTransform()
            loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)
            truth, predicted, confidence = [], [], []
            with torch.inference_mode():
                for batch_index, (images, labels) in enumerate(loader):
                    probabilities = model(images.to(device)).softmax(1)
                    if not torch.isfinite(probabilities).all():
                        raise FloatingPointError(f"Non-finite model output: {path}")
                    scores, indices = probabilities.max(1)
                    truth.extend(labels.tolist())
                    predicted.extend(indices.cpu().tolist())
                    confidence.extend(scores.cpu().tolist())
                    if (batch_index + 1) % 10 == 0:
                        print(f"{path.name} / {mode}: {len(truth)}/{len(dataset)}", flush=True)
            thresholds = []
            for threshold in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
                accepted = [i for i, score in enumerate(confidence) if score >= threshold]
                correct = sum(truth[i] == predicted[i] for i in accepted)
                thresholds.append(dict(threshold=threshold, accepted=len(accepted),
                                       coverage=len(accepted) / len(truth),
                                       accepted_accuracy=correct / len(accepted) if accepted else None,
                                       correct_over_all=correct / len(truth)))
            report = classification_report(truth, predicted, labels=list(range(len(CLASS_NAMES))),
                                           target_names=CLASS_NAMES, output_dict=True, zero_division=0)
            result["runs"].append(dict(checkpoint=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), mode=mode, report=report,
                confusion_matrix=confusion_matrix(truth, predicted, labels=list(range(len(CLASS_NAMES)))).tolist(),
                thresholds=thresholds,
                predictions=[dict(path=filename, true=CLASS_NAMES[y], predicted=CLASS_NAMES[p],
                                  confidence=score) for (filename, _), y, p, score in
                             zip(samples, truth, predicted, confidence)]))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"{path.name} / {mode}: accuracy={report['accuracy']:.2%}; "
                  f"macro F1={report['macro avg']['f1-score']:.2%}", flush=True)
        del model
    print(f"Report: {output}", flush=True)


if __name__ == "__main__":
    main()
