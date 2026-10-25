# scraper_bot/train_pipeline.py
import os
import sys
import json
import glob
import shutil
import random
import cv2

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUGS_DIR = os.path.join(BASE_DIR, "new-bugs-2")
JSON_PATH = os.path.join(BUGS_DIR, "labels_my-project-name_2026-09-22-08-48-52.json")
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
USER_LBL_DIR = os.path.join(DATASET_DIR, "user_labels")
USER_IMG_DIR = os.path.join(BASE_DIR, "images")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FINAL_PT_PATH = os.path.join(ASSETS_DIR, "plate_slot_yolov8n.pt")
FINAL_ONNX_PATH = os.path.join(ASSETS_DIR, "plate_slot_yolov8n.onnx")

os.makedirs(USER_LBL_DIR, exist_ok=True)
os.makedirs(USER_IMG_DIR, exist_ok=True)

print("=" * 60)
print("Step 1: Ingesting new-bugs-2 data...")
print("=" * 60)

with open(JSON_PATH, "r", encoding="utf-8") as f:
    coco = json.load(f)

img_map = {im["id"]: im for im in coco.get("images", [])}
ann_map = {}
for a in coco.get("annotations", []):
    ann_map.setdefault(a["image_id"], []).append(a)

all_jpgs = [f for f in os.listdir(BUGS_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
pos_count = 0
neg_count = 0

for fname in sorted(all_jpgs):
    src_img = os.path.join(BUGS_DIR, fname)
    dst_img = os.path.join(USER_IMG_DIR, fname)
    shutil.copy2(src_img, dst_img)

    cv_img = cv2.imread(src_img)
    if cv_img is None:
        continue
    H, W = cv_img.shape[:2]

    matched_ids = [iid for iid, im in img_map.items() if im["file_name"] == fname]
    yolo_lines = []

    if matched_ids:
        iid = matched_ids[0]
        anns = ann_map.get(iid, [])
        for ann in anns:
            bbox = ann.get("bbox", [])
            if len(bbox) == 4:
                bx, by, bw, bh = bbox
                cx = (bx + bw / 2.0) / float(W)
                cy = (by + bh / 2.0) / float(H)
                nw = bw / float(W)
                nh = bh / float(H)
                yolo_lines.append(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

    base_name = os.path.splitext(fname)[0]
    txt_path = os.path.join(USER_LBL_DIR, f"{base_name}.txt")

    if yolo_lines:
        pos_count += 1
        with open(txt_path, "w", encoding="utf-8") as tf:
            tf.write("\n".join(yolo_lines) + "\n")
        print(f"  [POSITIVE] {fname}: {len(yolo_lines)} box(es)")
    else:
        neg_count += 1
        with open(txt_path, "w", encoding="utf-8") as tf:
            tf.write("")  # empty file for true negative
        print(f"  [NEGATIVE] {fname}: (Empty label - false positive suppression)")

print(f"\nAdded {pos_count} positive plate images and {neg_count} negative images.")

# Step 2: Build Unified Dataset
print("\n" + "=" * 60)
print("Step 2: Rebuilding train/val splits...")
print("=" * 60)

TRAIN_IMG_DIR = os.path.join(DATASET_DIR, "images", "train")
VAL_IMG_DIR = os.path.join(DATASET_DIR, "images", "val")
TRAIN_LBL_DIR = os.path.join(DATASET_DIR, "labels", "train")
VAL_LBL_DIR = os.path.join(DATASET_DIR, "labels", "val")

# Copy all user labels into train/val
user_txts = sorted(glob.glob(os.path.join(USER_LBL_DIR, "*.txt")))
user_pairs = []
for txt_p in user_txts:
    bname = os.path.splitext(os.path.basename(txt_p))[0]
    img_p = os.path.join(USER_IMG_DIR, f"{bname}.jpg")
    if os.path.exists(img_p):
        user_pairs.append((img_p, txt_p))

random.seed(42)
random.shuffle(user_pairs)
u_split = int(len(user_pairs) * 0.85)
user_train = user_pairs[:u_split]
user_val = user_pairs[u_split:]

for img_p, txt_p in user_train:
    bname = os.path.basename(img_p)
    shutil.copy2(img_p, os.path.join(TRAIN_IMG_DIR, f"user_{bname}"))
    with open(txt_p, "r", encoding="utf-8") as f:
        content = f.read()
    with open(os.path.join(TRAIN_LBL_DIR, f"user_{os.path.splitext(bname)[0]}.txt"), "w", encoding="utf-8") as f:
        f.write(content)

for img_p, txt_p in user_val:
    bname = os.path.basename(img_p)
    shutil.copy2(img_p, os.path.join(VAL_IMG_DIR, f"user_{bname}"))
    with open(txt_p, "r", encoding="utf-8") as f:
        content = f.read()
    with open(os.path.join(VAL_LBL_DIR, f"user_{os.path.splitext(bname)[0]}.txt"), "w", encoding="utf-8") as f:
        f.write(content)

train_total = len(glob.glob(os.path.join(TRAIN_IMG_DIR, "*.jpg")))
val_total = len(glob.glob(os.path.join(VAL_IMG_DIR, "*.jpg")))
print(f"Total Train Images: {train_total}")
print(f"Total Val Images: {val_total}")

DATA_YAML = os.path.join(DATASET_DIR, "data.yaml")

# Step 3: Train YOLO
print("\n" + "=" * 60)
print("Step 3: Training YOLOv8n fine-tuning...")
print("=" * 60)

from ultralytics import YOLO

initial_weights = FINAL_PT_PATH if os.path.exists(FINAL_PT_PATH) else "yolov8n.pt"
print(f"Starting weights: {initial_weights}")
model = YOLO(initial_weights)

results = model.train(
    data=DATA_YAML,
    epochs=15,
    imgsz=640,
    batch=16,
    device="cpu",
    workers=2,
    verbose=True,
    project=os.path.join(BASE_DIR, "runs"),
    name="plate_slot_run",
    exist_ok=True
)

best_weights = os.path.join(BASE_DIR, "runs", "plate_slot_run", "weights", "best.pt")
if os.path.exists(best_weights):
    shutil.copy2(best_weights, FINAL_PT_PATH)
    print(f"Best trained weights saved to: {FINAL_PT_PATH}")
    try:
        print("Exporting to ONNX...")
        trained_model = YOLO(FINAL_PT_PATH)
        trained_model.export(format="onnx", imgsz=640, dynamic=False)
        print("ONNX successfully generated!")
    except Exception as e:
        print(f"ONNX export note: {e}")

# Step 4: Run evaluation on new-bugs-2
print("\n" + "=" * 60)
print("Step 4: Evaluating on all new-bugs-2 images...")
print("=" * 60)

import image_processor
image_processor._MODEL_INSTANCE = None
from image_processor import process_image_file

OUT_DIR = os.path.join(BASE_DIR, "new-bugs-2-output")
os.makedirs(OUT_DIR, exist_ok=True)

for fname in sorted(all_jpgs):
    inp = os.path.join(BUGS_DIR, fname)
    outp = os.path.join(OUT_DIR, fname)
    res = process_image_file(inp, outp)

print(f"\nAll {len(all_jpgs)} images processed and saved to {OUT_DIR}!")
print("Pipeline finished successfully!")
