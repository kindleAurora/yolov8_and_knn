"""
动量修正定量评估脚本 —— 跑一次，直接输出论文表4-11和表4-12所需数据。

用法：
  conda activate yolov8
  python eval_motion.py
"""

from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Admin\Desktop\毕设")
sys.path.insert(0, str(PROJECT_ROOT / "code" / "yolov8" / "ultralytics"))
sys.path.insert(0, str(PROJECT_ROOT / "code" / "knn"))

from knn_utils import NumpyKNNClassifier, extract_hog_feature
from ultralytics import YOLO
import cv2

YOLO_MODEL = PROJECT_ROOT / "runs" / "detect" / "cow_120_on_basecommon" / "weights" / "best.pt"
KNN_MODEL = PROJECT_ROOT / "code" / "knn" / "knn_behavior_model.npz"
VIDEO = PROJECT_ROOT / "all_datasets" / "cow_video" / "一群奶牛在牧场草地上吃草.mp4"
MOTION_WINDOW = 6

THRESHOLD_GRID = [(0.008, 0.004), (0.01, 0.005), (0.012, 0.006), (0.014, 0.007)]


def clamp_box(x1, y1, x2, y2, w, h):
    return max(0, int(x1)), max(0, int(y1)), min(w, int(x2)), min(h, int(y2))


def get_center(x1, y1, x2, y2):
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def compute_motion_score(centers, box_w, box_h):
    if len(centers) < 2:
        return 0.0
    dists = [np.hypot(cx - px, cy - py) for (px, py), (cx, cy) in zip(centers[:-1], centers[1:])]
    return float(np.mean(dists)) / max(float(box_w), float(box_h), 1.0)


def refine_label(knn_label, centers, box_w, box_h, t_high, t_low):
    score = compute_motion_score(centers, box_w, box_h)
    if score >= t_high:
        return "walking", score, "motion-high"
    if score <= t_low:
        if knn_label == "lying":
            return "lying", score, "motion-low-lying"
        if knn_label == "walking":
            return "standing", score, "motion-low-corrected"
        return "standing", score, "motion-low-standing"
    return knn_label, score, "motion-middle"


def main():
    print("Loading models...")
    model = YOLO(str(YOLO_MODEL))
    classifier = NumpyKNNClassifier.load(str(KNN_MODEL))

    # ===== 第一遍：不开动量修正，纯 KNN =====
    print("Pass 1/5: KNN only (no motion correction)...")
    knn_log = []  # [(track_id, knn_label), ...]

    cap = cv2.VideoCapture(str(VIDEO))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    for frame_idx, result in enumerate(
        model.predict(source=str(VIDEO), conf=0.25, iou=0.45, stream=True, verbose=False), start=1
    ):
        if result.boxes is None:
            continue
        frame = result.orig_img
        h, w = frame.shape[:2]
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x1, y1, x2, y2 = clamp_box(x1, y1, x2, y2, w, h)
            if x2 <= x1 or y2 <= y1:
                continue
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            feature = extract_hog_feature(crop, image_size=classifier.image_size)
            pred = classifier.predict(feature)
            knn_log.append((frame_idx, pred.label_name))
        if frame_idx % 50 == 0:
            print(f"  ... frame {frame_idx}/{total}")

    # ===== 统计 KNN 分类混淆基线 =====
    total_s = sum(1 for _, l in knn_log if l == "standing")
    total_w = sum(1 for _, l in knn_log if l == "walking")
    print(f"\nKNN baseline: standing={total_s}, walking={total_w}")

    # ===== 第二到第五遍：不同阈值组合 =====
    for (t_high, t_low) in THRESHOLD_GRID:
        print(f"\nPass with (T_high={t_high}, T_low={t_low}):")
        track_history = defaultdict(list)  # track_id -> [(cx, cy, box_w, box_h, knn_label), ...]

        for frame_idx, result in enumerate(
            model.track(source=str(VIDEO), conf=0.25, iou=0.45, stream=True, persist=True, verbose=False), start=1
        ):
            if result.boxes is None:
                continue
            frame = result.orig_img
            h, w = frame.shape[:2]
            for box in result.boxes:
                raw_id = getattr(box, "id", None)
                if raw_id is None:
                    continue
                tid = int(raw_id[0].item() if hasattr(raw_id[0], "item") else raw_id[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = clamp_box(x1, y1, x2, y2, w, h)
                if x2 <= x1 or y2 <= y1:
                    continue
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                feature = extract_hog_feature(crop, image_size=classifier.image_size)
                pred = classifier.predict(feature)
                cx, cy = get_center(x1, y1, x2, y2)
                bw, bh = x2 - x1, y2 - y1
                track_history[tid].append((cx, cy, bw, bh, pred.label_name, frame_idx))
            if frame_idx % 50 == 0:
                print(f"  ... frame {frame_idx}/{total}")

        # ===== 统计修正后的误判 =====
        s2w = 0   # standing -> walking (KNN standing, motion corrects to walking)
        w2s = 0   # walking -> standing (KNN walking, motion corrects to standing)
        s_correct = 0
        s_total = 0
        w_correct = 0
        w_total = 0

        for tid, records in track_history.items():
            if len(records) < MOTION_WINDOW:
                continue
            for i, (cx, cy, bw, bh, knn_label, fidx) in enumerate(records):
                if knn_label not in ("standing", "walking"):
                    continue
                centers = [(r[0], r[1]) for r in records[max(0, i - MOTION_WINDOW + 1) : i + 1]]
                corrected, _, _ = refine_label(knn_label, centers, bw, bh, t_high, t_low)
                if knn_label == "standing":
                    s_total += 1
                    if corrected == "standing":
                        s_correct += 1
                    elif corrected == "walking":
                        s2w += 1
                elif knn_label == "walking":
                    w_total += 1
                    if corrected == "walking":
                        w_correct += 1
                    elif corrected == "standing":
                        w2s += 1

        s_acc = s_correct / s_total * 100 if s_total else 0
        w_acc = w_correct / w_total * 100 if w_total else 0
        print(f"  standing: {s_correct}/{s_total} = {s_acc:.2f}%  (KNN standing→walking 误修正: {s2w})")
        print(f"  walking:  {w_correct}/{w_total} = {w_acc:.2f}%  (KNN walking→standing 修正: {w2s})")

    print("\n===== 结果汇总 =====")
    print("前两列填表4-11(动量修正混淆对比)，standing/walking准确率改变填对应行，")
    print("后一列(s→w误修正、w→s修正)用于计算误判数变化。")
    print("四组阈值数据填表4-12(敏感性分析)。")


if __name__ == "__main__":
    main()
