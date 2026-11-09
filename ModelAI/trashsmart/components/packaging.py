"""Create an explicit training-only bundle, excluding runtime secrets and history."""
import hashlib
import json
import zipfile
from pathlib import Path


def package_training(data, output):
    data, output = Path(data).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(data):
        raise ValueError("Choose a new bundle path outside the prepared export")
    report = json.loads((data / "dataset-report.json").read_text(encoding="utf-8"))
    if report.get("trainingScope") != "bottle-components":
        raise ValueError("Expected a validated prepared export")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trashsmart/__init__.py", "# Training-only bottle component package\n")
        source = Path(__file__).parent
        for name in ("__init__.py", "__main__.py", "data.py", "intake.py", "scope_review.py", "dedup_policy.py", "training.py", "packaging.py"):
            archive.write(source / name, "trashsmart/components/" + name)
        for file in data.rglob("*"):
            if not file.is_file():
                continue
            if file.is_symlink() or not file.resolve().is_relative_to(data):
                raise ValueError("Prepared export contains an external link")
            relative = file.relative_to(data)
            if relative.parts[0] in ("detector", "material") and file.suffix.lower() in (".jpg", ".txt", ".yaml") or relative.as_posix() in ("dataset-report.json", "source-acceptance.json", "accepted-source-annotations.jsonl"):
                archive.write(file, "dataset/" + relative.as_posix())
    return {"bundle": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "note": "Contains only prepared crops, labels and training code; no .env, accounts or scan history"}
