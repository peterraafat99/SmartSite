"""
SmartSite Construction Video Generator.
Generates a realistic 1280x720 video sequence using authentic construction site
photographs from the Ultralytics Construction-PPE dataset.
"""
import os
import glob
import cv2
import numpy as np

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "videos")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sample_construction.mp4")
DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "datasets", "construction-ppe")

def generate_sample_video(num_scenes=25, frames_per_scene=24, fps=20):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    labels = glob.glob(os.path.join(DATASET_DIR, "labels", "train", "*.txt"))
    candidates = []

    for lf in labels:
        with open(lf) as f:
            lines = f.readlines()
        classes = [int(l.strip().split()[0]) for l in lines if len(l.strip().split()) >= 5]
        if 5 in classes:  # Person
            img_name = os.path.basename(lf).replace('.txt', '.jpg')
            img_path = os.path.join(DATASET_DIR, "images", "train", img_name)
            if os.path.exists(img_path):
                candidates.append((img_path, len(classes)))

    candidates.sort(key=lambda x: x[1], reverse=True)
    selected = [p for p, _ in candidates[:num_scenes]]

    w, h = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (w, h))
    total_frames = 0

    for idx, p in enumerate(selected):
        img = cv2.imread(p)
        if img is None:
            continue
        ih, iw = img.shape[:2]
        target_aspect = w / h
        img_aspect = iw / ih

        if img_aspect > target_aspect:
            new_w = int(ih * target_aspect)
            start_x = (iw - new_w) // 2
            crop = img[:, start_x:start_x + new_w]
        else:
            new_h = int(iw / target_aspect)
            start_y = (ih - new_h) // 2
            crop = img[start_y:start_y + new_h, :]

        resized = cv2.resize(crop, (w, h))

        for f in range(frames_per_scene):
            frame = resized.copy()
            cv2.putText(frame, f'SITE SURVEILLANCE CAM-0{idx%4 + 1} | LIVE FEED', (25, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, f'ZONE: SECTOR {chr(65 + idx%4)} | FRAME {total_frames:04d}', (25, h - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
            out.write(frame)
            total_frames += 1

    out.release()
    print(f"[SUCCESS] Real construction video generated:\n  {OUTPUT_PATH} ({total_frames} frames)")
    return OUTPUT_PATH

if __name__ == "__main__":
    generate_sample_video()
