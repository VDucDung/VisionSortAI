"""Small CPU/GPU training jobs. Candidates never activate themselves in the API."""
import hashlib
import json
import time
from pathlib import Path

from . import PARTS, MATERIALS


def torch_device(value):
    import torch
    text = str(value)
    return torch.device("cuda:" + text if text.isdigit() else text)


def material_transform():
    from torchvision import transforms
    # Preserve the entire thin cap/label crop, identically during train and inference.
    return transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
                               transforms.Normalize([.485, .456, .406], [.229, .224, .225])])


def _job(args):
    import torch
    if args.epochs < 1 or args.batch < 1 or args.threads < 1 or args.workers < 0:
        raise ValueError("epochs, batch, threads must be positive; workers nonnegative")
    torch.set_num_threads(args.threads)
    if args.output.exists():
        if not args.resume:
            raise ValueError("Candidate directory exists; choose a new output or use --resume")
    args.output.mkdir(parents=True, exist_ok=True)
    report = json.loads((args.data / "dataset-report.json").read_text(encoding="utf-8"))
    if report.get("trainingScope") != "bottle-components":
        raise ValueError("Expected a validated component export")
    return report


def train_detector(args):
    report = _job(args)
    for split in ("train", "val", "test"):
        for part in PARTS:
            if report["counts"].get(f"detector/{split}/{part}", 0) < 1:
                raise ValueError(f"Missing detector/{split}/{part}; collect and review more groups")
    from ultralytics import YOLO
    model = YOLO(str(args.resume) if args.resume else args.weights)
    progress = getattr(args, "progress_callback", None)
    if callable(progress):
        model.add_callback("on_fit_epoch_end", progress)
    config = _detector_config(args)
    model.train(data=str(config),
                project=str(args.output.resolve()), name="detector", exist_ok=bool(args.resume),
                epochs=args.epochs, batch=args.batch, imgsz=args.imgsz, workers=args.workers,
                device=args.device, cache=False, seed=42, deterministic=True,
                resume=bool(args.resume), patience=10, plots=True, save=True, agnostic_nms=False)
    return {"candidate": str(args.output / "detector/weights/best.pt"), "activated": False}


def _detector_config(args):
    config = args.output / "dataset.yaml"
    config.write_text(json.dumps({"path": str((args.data / 'detector').resolve()), "train": "images/train", "val": "images/val", "test": "images/test", "names": dict(enumerate(PARTS))}), encoding="utf-8")
    return config.resolve()


def load_classifier(path, device="cpu"):
    import torch
    from torchvision.models import resnet18
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("training_scope") != "bottle-components" or checkpoint.get("architecture") != "resnet18":
        raise ValueError("Not a component material checkpoint")
    if checkpoint.get("class_names") != list(MATERIALS):
        raise ValueError("Material class order does not match the component contract")
    model = resnet18(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, len(MATERIALS))
    model.load_state_dict(checkpoint["model_state_dict"])
    return model.to(torch_device(device)).eval(), checkpoint


def train_material(args):
    import torch
    from torchvision.datasets import ImageFolder
    from torchvision.models import resnet18, ResNet18_Weights
    from torch.utils.data import DataLoader
    report = _job(args)
    for split in ("train", "val", "test"):
        for material in MATERIALS:
            minimum = 4 if split == "train" else 1
            if report["counts"].get(f"material/{split}/{material}", 0) < minimum:
                raise ValueError(f"Insufficient verified material/{split}/{material}: need at least {minimum} to run, not an accuracy guarantee")
    torch.manual_seed(42)
    device = torch_device(args.device)
    transform = material_transform()
    train = ImageFolder(args.data / "material/train", transform=transform)
    val = ImageFolder(args.data / "material/val", transform=transform)
    if train.classes != list(MATERIALS) or val.classes != list(MATERIALS):
        raise ValueError("Unexpected material folder order")
    if args.resume:
        model, previous = load_classifier(args.resume, device)
    else:
        model = resnet18(weights=ResNet18_Weights.DEFAULT)
        model.fc = torch.nn.Linear(model.fc.in_features, len(MATERIALS))
        model.to(device)
        previous = {}
    # CPU-friendly initial baseline: freeze backbone, train final layer.
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.fc.parameters():
        parameter.requires_grad = True
    optimizer = torch.optim.AdamW(model.fc.parameters(), lr=.001)
    if previous.get("optimizer_state_dict"):
        optimizer.load_state_dict(previous["optimizer_state_dict"])
    loss_fn = torch.nn.CrossEntropyLoss()
    generator = torch.Generator().manual_seed(42)
    train_loader = DataLoader(train, batch_size=args.batch, shuffle=True, num_workers=args.workers, generator=generator)
    val_loader = DataLoader(val, batch_size=args.batch, num_workers=args.workers)
    best = previous.get("best_val_accuracy", -1)
    first = previous.get("epoch", -1) + 1
    for epoch in range(first, args.epochs):
        started = time.monotonic()
        model.eval()  # Frozen backbone: do not change BatchNorm statistics.
        model.fc.train()
        total_loss = 0.
        for images, labels in train_loader:
            optimizer.zero_grad()
            logits = model(images.to(device))
            loss = loss_fn(logits, labels.to(device))
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(labels)
        model.eval()
        correct = 0
        with torch.inference_mode():
            for images, labels in val_loader:
                correct += (model(images.to(device)).argmax(1).cpu() == labels).sum().item()
        accuracy = correct / len(val)
        payload = {"training_scope": "bottle-components", "architecture": "resnet18", "class_names": list(MATERIALS),
                   "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(), "epoch": epoch,
                   "best_val_accuracy": max(best, accuracy), "dataset_sha256": report["sourceAnnotationsSha256"],
                   "training_mode": "frozen-backbone", "validated": False}
        temporary = args.output / "last.tmp"
        torch.save(payload, temporary)
        temporary.replace(args.output / "last.pth")
        if accuracy > best:
            torch.save(payload, args.output / "best.pth")
            best = accuracy
        progress = {"epoch": epoch + 1, "loss": total_loss / len(train), "val_accuracy": accuracy,
                    "seconds": round(time.monotonic() - started, 2)}
        print(json.dumps(progress), flush=True)
        with (args.output / "epochs.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(progress) + "\n")
    return {"candidate": str(args.output / "best.pth"), "activated": False, "epochsCompleted": args.epochs}


def evaluate(args):
    import torch
    from torch.utils.data import DataLoader
    from torchvision.datasets import ImageFolder
    from ultralytics import YOLO
    if args.output.exists():
        raise ValueError("Evaluation output exists; use a new directory")
    args.output.mkdir(parents=True)
    detector_path = Path(args.weights).resolve()
    if not args.resume:
        raise ValueError("--resume must point to the component material .pth checkpoint")
    detector = YOLO(str(detector_path))
    names = [detector.names[i] for i in range(len(detector.names))]
    if names != list(PARTS):
        raise ValueError("Detector does not have component class order cap/body/label")
    metrics = detector.val(data=str(_detector_config(args)), split=args.split,
                           device=args.device, batch=args.batch, imgsz=args.imgsz, workers=args.workers,
                           project=str(args.output), name="detector", agnostic_nms=False)
    model, _ = load_classifier(args.resume, args.device)
    device = torch_device(args.device)
    dataset = ImageFolder(args.data / "material" / args.split, transform=material_transform())
    if dataset.classes != list(MATERIALS):
        raise ValueError("Invalid material classes")
    confusion = torch.zeros((4, 4), dtype=torch.int64)
    with torch.inference_mode():
        for images, targets in DataLoader(dataset, batch_size=args.batch, num_workers=args.workers):
            predicted = model(images.to(device)).argmax(1).cpu()
            for truth, guess in zip(targets, predicted):
                confusion[truth, guess] += 1
    f1 = []
    for i in range(4):
        tp = confusion[i, i].item()
        denominator = confusion[i, :].sum().item() + confusion[:, i].sum().item()
        f1.append(2 * tp / denominator if denominator else 0)
    result = {"split": args.split, "detector": {k: float(v) for k, v in metrics.results_dict.items()},
              "materialClasses": list(MATERIALS), "materialConfusionMatrix": confusion.tolist(), "materialMacroF1": sum(f1) / 4,
              "detectorSha256": hashlib.sha256(detector_path.read_bytes()).hexdigest(),
              "materialSha256": hashlib.sha256(args.resume.read_bytes()).hexdigest(),
              "endToEndReviewed": False, "activated": False,
              "note": "Evaluate missed parts and parent association on independent real bottle photos before release."}
    (args.output / "evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
