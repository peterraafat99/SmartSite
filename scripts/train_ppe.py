"""
SmartSite Construction-PPE Model Training Script.
Trains a lightweight YOLO model on the Construction-PPE dataset.
Evaluates precision, recall, mAP50, and mAP50-95, and saves best.pt to models/.
"""
import os
import sys
import shutil
import argparse
import numpy as np
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
DATASET_DIR = os.path.join(PROJECT_ROOT, "data", "datasets", "construction-ppe")

def check_dataset_ready(dataset_yaml_path: str) -> bool:
    """Verifies that dataset files and configuration exist."""
    if not os.path.exists(dataset_yaml_path):
        print(f"[ERROR] Dataset configuration file not found at:\n  {dataset_yaml_path}")
        print("Please run the downloader script first:")
        print("  python scripts/download_dataset.py")
        return False

    images_train = os.path.join(DATASET_DIR, "images", "train")
    if not os.path.exists(images_train) or len(os.listdir(images_train)) == 0:
        print(f"[ERROR] Dataset training images not found in:\n  {images_train}")
        print("Please run the downloader script first:")
        print("  python scripts/download_dataset.py")
        return False

    return True

def train(
    base_model: str = "yolo11n.pt",
    epochs: int = 25,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "cpu"
):
    print("=" * 65)
    print(" SmartSite — AI Construction PPE Model Training Pipeline")
    print(f" Base Model Architecture: {base_model}")
    print(f" Target Epochs:           {epochs}")
    print(f" Batch Size:              {batch}")
    print(f" Image Size:              {imgsz}x{imgsz}")
    print(f" Compute Device:          {device.upper()}")
    print("=" * 65)

    data_yaml = os.path.join(DATASET_DIR, "data.yaml")
    if not os.path.exists(data_yaml):
        # Fall back to Ultralytics built-in dataset spec if local yaml is missing
        data_yaml = "construction-ppe.yaml"

    # Verify dataset presence
    if not check_dataset_ready(data_yaml) and data_yaml != "construction-ppe.yaml":
        sys.exit(1)

    print(f"\n[1/4] Loading base architecture: {base_model}...")
    model = YOLO(base_model)

    print("\n[2/4] Starting training run (results saved in runs/detect/)...")
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        project=os.path.join(PROJECT_ROOT, "runs", "train_ppe"),
        name="smartsite_ppe",
        exist_ok=True,
        verbose=True
    )

    print("\n[3/4] Evaluating validation metrics on test split...")
    metrics = model.val()

    # Extract official metrics
    precision = getattr(metrics.box, "p", [])
    recall = getattr(metrics.box, "r", [])
    map50 = float(getattr(metrics.box, "map50", 0.0))
    map50_95 = float(getattr(metrics.box, "map", 0.0))

    mean_p = float(np.mean(precision)) if precision is not None and len(precision) > 0 else 0.0
    mean_r = float(np.mean(recall)) if recall is not None and len(recall) > 0 else 0.0

    print("\n" + "=" * 65)
    print(" SmartSite PPE Model Evaluation Results:")
    print(f" • Precision (mean):      {mean_p:.4f} ({mean_p*100:.1f}%)")
    print(f" • Recall (mean):         {mean_r:.4f} ({mean_r*100:.1f}%)")
    print(f" • mAP@0.50:              {map50:.4f} ({map50*100:.1f}%)")
    print(f" • mAP@0.50:0.95:         {map50_95:.4f} ({map50_95*100:.1f}%)")
    print("=" * 65)

    # Save best.pt to models/
    os.makedirs(MODELS_DIR, exist_ok=True)
    target_best_pt = os.path.join(MODELS_DIR, "best.pt")

    # Locate best.pt from run directory
    run_best = os.path.join(PROJECT_ROOT, "runs", "train_ppe", "smartsite_ppe", "weights", "best.pt")
    if os.path.exists(run_best):
        shutil.copy2(run_best, target_best_pt)
        print(f"\n[4/4] Successfully deployed best weights to:\n  {target_best_pt}")
    else:
        # Save current model weights directly
        model.save(target_best_pt)
        print(f"\n[4/4] Saved weights to:\n  {target_best_pt}")

    print("\n[COMPLETE] Model is now ready for live inference in SmartSite Dashboard.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train lightweight YOLO Construction-PPE model")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Base weights (e.g. yolo11n.pt or yolov8n.pt)")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu", help="Device (cpu or cuda)")
    args = parser.parse_args()

    train(
        base_model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device
    )
