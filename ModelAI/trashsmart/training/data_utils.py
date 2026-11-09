import sys
from pathlib import Path
import random

import torch
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, Subset
from torchvision import datasets
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trashsmart.shared.transforms import get_eval_transform, get_train_transform
from trashsmart.training.config import BATCH_SIZE, DEVICE, DIR_PATH, TARGET_SIZE, TRAIN_DIR, VAL_DIR, NUM_WORKERS


def get_transforms():
    return (
        get_train_transform(input_size=TARGET_SIZE[0]),
        get_eval_transform(input_size=TARGET_SIZE[0]),
    )
def _seed_worker(worker_id):
    seed = torch.initial_seed() % (2**32)
    np.random.seed(seed)
    random.seed(seed)

g = torch.Generator()
g.manual_seed(42)

def get_data_loaders():
    train_transform, val_transform = get_transforms()

    train_ds = datasets.ImageFolder(TRAIN_DIR, transform=train_transform)
    if VAL_DIR is not None:
        if not VAL_DIR.is_dir():
            raise ValueError(f"Split dataset requires a valid directory: {VAL_DIR}")
        val_ds = datasets.ImageFolder(VAL_DIR, transform=val_transform)
        if train_ds.class_to_idx != val_ds.class_to_idx:
            raise ValueError("Train and validation class mappings differ.")
        train_dataset, val_dataset = train_ds, val_ds
    else:
        val_ds = datasets.ImageFolder(DIR_PATH, transform=val_transform)
        total_size = len(train_ds)
        indices = torch.randperm(total_size, generator=torch.Generator().manual_seed(42)).tolist()
        train_size = int(0.9 * total_size)
        train_dataset = Subset(train_ds, indices[:train_size])
        val_dataset = Subset(val_ds, indices[train_size:])
    if len(train_dataset) < 2 or len(val_dataset) == 0:
        raise ValueError("Training requires at least two train images and one validation image.")
    if BATCH_SIZE < 2:
        raise ValueError("BATCH_SIZE must be at least 2 for the classifier BatchNorm layers.")

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        drop_last=len(train_dataset) % BATCH_SIZE == 1,
        pin_memory=torch.cuda.is_available(),
        worker_init_fn=_seed_worker,
        generator=g,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=torch.cuda.is_available(),
    )

    return train_loader, val_loader, train_ds.classes


def _extract_labels(dataset) -> np.ndarray:
    if isinstance(dataset, DataLoader):
        dataset = dataset.dataset

    if isinstance(dataset, Subset):
        parent = dataset.dataset
        return np.array([parent.targets[i] for i in dataset.indices])

    if hasattr(dataset, "targets"):
        return np.array(dataset.targets)

    labels = []
    for _, label in dataset:
        labels.append(int(label))
    return np.array(labels)


def get_class_weights(train_dataset):
    labels = _extract_labels(train_dataset)
    class_weights = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(labels),
        y=labels,
    )
    return torch.FloatTensor(class_weights).to(DEVICE)
