"""
SmartSite Dataset Downloader for Ultralytics Construction-PPE.
Downloads and extracts the 1,000-image 12-class dataset into data/datasets/construction-ppe.
"""
import os
import sys
import zipfile
import urllib.request
import argparse

DATASET_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip"
TARGET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "datasets", "construction-ppe")

def download_progress_hook(count, block_size, total_size):
    if total_size > 0:
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\rDownloading dataset: {percent}% [{count * block_size / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB]")
        sys.stdout.flush()

def download_and_extract(force: bool = False):
    os.makedirs(TARGET_DIR, exist_ok=True)
    zip_path = os.path.join(TARGET_DIR, "construction-ppe.zip")

    # Check if already extracted
    images_dir = os.path.join(TARGET_DIR, "images")
    if os.path.exists(images_dir) and not force:
        print(f"[OK] Construction-PPE dataset already exists at:\n  {TARGET_DIR}")
        return True

    print("=" * 60)
    print(" SmartSite — Construction-PPE Dataset Downloader")
    print(f" Source: {DATASET_URL}")
    print(f" Target: {TARGET_DIR}")
    print("=" * 60)

    try:
        print("\nStarting download (approx 178 MB)...")
        urllib.request.urlretrieve(DATASET_URL, zip_path, reporthook=download_progress_hook)
        print("\nDownload complete. Extracting archive...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(TARGET_DIR)

        # Flatten nested directory if exists
        nested_dir = os.path.join(TARGET_DIR, "construction-ppe")
        if os.path.exists(nested_dir):
            for item in os.listdir(nested_dir):
                s = os.path.join(nested_dir, item)
                d = os.path.join(TARGET_DIR, item)
                if not os.path.exists(d):
                    os.rename(s, d)
            try:
                os.rmdir(nested_dir)
            except Exception:
                pass

        print(f"[SUCCESS] Dataset successfully extracted to:\n  {TARGET_DIR}")

        # Clean up zip
        if os.path.exists(zip_path):
            os.remove(zip_path)

        # Generate local data.yaml for training
        yaml_content = f"""# Ultralytics Construction-PPE Dataset Configuration
path: {TARGET_DIR.replace('\\\\', '/')}
train: images/train
val: images/val
test: images/test

names:
  0: helmet
  1: gloves
  2: vest
  3: boots
  4: goggles
  5: Person
  6: no_helmet
  7: no_goggle
  8: no_gloves
  9: no_boots
  10: forklift
  11: no_vest
"""
        yaml_path = os.path.join(TARGET_DIR, "data.yaml")
        with open(yaml_path, "w") as f:
            f.write(yaml_content)

        print(f"[OK] Training dataset configuration generated:\n  {yaml_path}")
        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to download or extract dataset: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Construction-PPE dataset")
    parser.add_argument("--force", action="store_true", help="Force redownload even if exists")
    args = parser.parse_args()

    download_and_extract(force=args.force)
