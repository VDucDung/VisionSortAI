"""Dependency-free matching for end-to-end material detection evaluation."""
import math


def read_annotations(text, width, height, num_classes):
    objects = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5 and (len(parts) < 7 or len(parts) % 2 != 1):
            raise ValueError(f"Invalid box or polygon on line {number}")
        label = int(parts[0])
        coords = list(map(float, parts[1:]))
        if not 0 <= label < num_classes or not all(math.isfinite(x) and 0 <= x <= 1 for x in coords):
            raise ValueError(f"Invalid class or coordinates on line {number}")
        if len(coords) == 4:
            x, y, w, h = coords
            box = (x-w/2, y-h/2, x+w/2, y+h/2)
        else:
            xs, ys = coords[::2], coords[1::2]
            box = (min(xs), min(ys), max(xs), max(ys))
        box = tuple(max(0, min(1, v)) * size for v, size in zip(box, (width, height, width, height)))
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError(f"Empty box on line {number}")
        objects.append(dict(label=label, box=box))
    return objects


def box_iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area = lambda box: max(0, box[2]-box[0]) * max(0, box[3]-box[1])
    union = area(a) + area(b) - intersection
    return intersection / union if union else 0.0


def match_objects(truth, predictions, threshold=0.5):
    """Confidence-ordered, class-agnostic box matching; labels scored afterwards."""
    if not 0 < threshold <= 1:
        raise ValueError("IoU threshold must be in (0, 1]")
    unmatched = set(range(len(truth)))
    matches, false_positives = [], []
    for p in sorted(range(len(predictions)), key=lambda i: predictions[i]["confidence"], reverse=True):
        candidates = [(box_iou(truth[t]["box"], predictions[p]["box"]), t) for t in unmatched]
        overlap, t = max(candidates, default=(0, -1))
        if overlap >= threshold:
            unmatched.remove(t)
            matches.append((t, p))
        else:
            false_positives.append(p)
    return matches, sorted(unmatched), false_positives


def summarize_images(images, classes):
    totals = dict(objects=0, predictions=0, matched=0, correct_material=0,
                  missed=0, false_positives=0, wrong_material=0, unknown=0)
    per_class = {name: dict(objects=0, predictions=0, correct=0) for name in classes}
    for image in images:
        truth, predictions, matches = image["truth"], image["predictions"], image["matches"]
        totals["objects"] += len(truth)
        totals["predictions"] += len(predictions)
        totals["matched"] += len(matches)
        totals["missed"] += len(image["missed"])
        totals["false_positives"] += len(image["false_positives"])
        for obj in truth:
            per_class[classes[obj["label"]]]["objects"] += 1
        for obj in predictions:
            if obj["label"] >= 0:
                per_class[classes[obj["label"]]]["predictions"] += 1
        for t, p in matches:
            label = predictions[p]["label"]
            if label == truth[t]["label"]:
                totals["correct_material"] += 1
                per_class[classes[label]]["correct"] += 1
            elif label == -1:
                totals["unknown"] += 1
            else:
                totals["wrong_material"] += 1
    divide = lambda a, b: a / b if b else None
    totals.update(detection_recall=divide(totals["matched"], totals["objects"]),
                  detection_precision=divide(totals["matched"], totals["predictions"]),
                  material_accuracy_on_matched=divide(totals["correct_material"], totals["matched"]),
                  end_to_end_recall=divide(totals["correct_material"], totals["objects"]),
                  end_to_end_precision=divide(totals["correct_material"], totals["predictions"]))
    for values in per_class.values():
        values.update(recall=divide(values["correct"], values["objects"]),
                      precision=divide(values["correct"], values["predictions"]))
    return dict(totals=totals, per_class=per_class)
