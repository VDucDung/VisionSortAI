"""Strict Precision/Recall publication policy; no lower-precision fallback."""
import hashlib
import math
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_target_met(report, target=.9):
    """Both native summary and the same deployed operating point must pass."""
    try:
        values = [report["precision_max_f1"], report["recall_max_f1"], report["map50"],
                  report["operating_point"]["precision"], report["operating_point"]["recall"]]
        return all(math.isfinite(value) and target <= value <= 1 for value in values)
    except (KeyError, TypeError, ValueError):
        return False


def publication_allowed(validation, test, candidate_sha, target=.9):
    if validation.get("split") != "val" or test.get("split") != "test":
        return False
    if not strict_target_met(validation, target) or not strict_target_met(test, target):
        return False
    if not all(report.get("checkpoint_sha256") == candidate_sha for report in (validation, test)):
        return False
    # A test measured at different settings cannot authorize the deployed settings.
    for key in ("data", "imgsz", "tta", "nms_iou"):
        if key not in validation or validation[key] != test.get(key):
            return False
    return validation["operating_point"]["confidence"] == test["operating_point"]["confidence"]
