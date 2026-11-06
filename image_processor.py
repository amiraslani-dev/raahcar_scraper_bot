# scraper_bot/image_processor.py
import os
import logging
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from ultralytics import YOLO

try:
    from config import LOGO_PATH, WATERMARK_LOGO_PATH
except ImportError:
    try:
        from scraper_bot.config import LOGO_PATH, WATERMARK_LOGO_PATH
    except ImportError:
        LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        WATERMARK_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.webp")

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_CARS_PT = os.path.join(BASE_DIR, "assets", "cars_best_v26.pt")
MODEL_COVERED_PT = os.path.join(BASE_DIR, "assets", "plate_covered_yolov8n.pt")
MODEL_IRAN_ONNX = os.path.join(BASE_DIR, "assets", "plate_yolo_iran.onnx")
MODEL_DETECTOR_ONNX = os.path.join(BASE_DIR, "assets", "plate_detector.onnx")

_MODEL_CARS = None
_MODEL_COVERED = None
_MODEL_IRAN = None
_MODEL_DETECTOR = None


def get_models():
    """
    Returns cached ensemble instances of detectors:
    1. _MODEL_CARS (cars_best_v26.pt): Knows both Car and Plate context.
    2. _MODEL_COVERED (plate_covered_yolov8n.pt): Recognizes covered/censored/showroom plates.
    3. _MODEL_IRAN (plate_yolo_iran.onnx): High-precision Iranian plate detector.
    """
    global _MODEL_CARS, _MODEL_COVERED, _MODEL_IRAN, _MODEL_DETECTOR
    if _MODEL_CARS is None and os.path.exists(MODEL_CARS_PT):
        try:
            _MODEL_CARS = YOLO(MODEL_CARS_PT)
            logger.info("Loaded cars_best_v26 model")
        except Exception as e:
            logger.error(f"Failed to load cars model: {e}")

    if _MODEL_COVERED is None and os.path.exists(MODEL_COVERED_PT):
        try:
            _MODEL_COVERED = YOLO(MODEL_COVERED_PT)
            logger.info("Loaded covered plate model")
        except Exception as e:
            logger.error(f"Failed to load covered model: {e}")

    if _MODEL_IRAN is None and os.path.exists(MODEL_IRAN_ONNX):
        try:
            _MODEL_IRAN = YOLO(MODEL_IRAN_ONNX, task="detect")
            logger.info("Loaded Iranian plate model")
        except Exception as e:
            logger.error(f"Failed to load Iranian plate model: {e}")

    if _MODEL_DETECTOR is None and os.path.exists(MODEL_DETECTOR_ONNX):
        try:
            _MODEL_DETECTOR = YOLO(MODEL_DETECTOR_ONNX, task="detect")
            logger.info("Loaded general detector model")
        except Exception as e:
            logger.error(f"Failed to load general detector model: {e}")

    return _MODEL_CARS, _MODEL_COVERED, _MODEL_IRAN, _MODEL_DETECTOR


def get_model():
    """Returns primary model for backwards compatibility."""
    m_cars, m_cov, m_iran, m_det = get_models()
    return m_cars or m_cov or m_iran or m_det


def create_branded_plate_badge(width, height, logo_path=None):
    """
    Generates a sleek, metallic dark plate cover branded with Raahcar logo.
    Responsively adapts to plate dimensions:
    - Normal/large plates: Renders crisp Raahcar logo with double metallic borders.
    - Small/steep plates (<55px width or <18px height or steep AR): Renders a minimalist
      metallic showroom cover with subtle accent to prevent logo distortion or blurriness.
    """
    width = max(10, int(width))
    height = max(8, int(height))
    # Clean white background (matching Iranian license plates / showroom covers)
    badge = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(badge)
    radius = max(2, int(height * 0.12))
    border_w = 1 if (height < 26 or width < 60) else 2

    # Clean dark outer frame border (matching real plate frames)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, outline=(30, 41, 59, 255), width=border_w)

    # Subtle inner border for realistic showroom plate depth
    if width > 28 and height > 16:
        draw.rounded_rectangle(
            [border_w, border_w, width - 1 - border_w, height - 1 - border_w],
            radius=max(1, radius - 1),
            outline=(226, 232, 240, 255),
            width=1
        )

    # Check if box is large and wide enough for clean text logo rendering
    ar = width / float(max(1, height))
    is_small_or_steep = (width < 55 or height < 18 or ar < 1.4)

    target_logo = logo_path or LOGO_PATH
    if not is_small_or_steep and target_logo and os.path.exists(target_logo):
        try:
            logo = Image.open(target_logo).convert("RGBA")
            pad_y = max(1, int(height * 0.12))
            avail_h = max(1, height - (2 * pad_y))
            avail_w = max(1, width - int(width * 0.08))

            scale = min(avail_w / logo.width, avail_h / logo.height)
            new_w = max(1, int(logo.width * scale))
            new_h = max(1, int(logo.height * scale))

            logo_resized = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
            off_x = (width - new_w) // 2
            off_y = (height - new_h) // 2
            badge.paste(logo_resized, (off_x, off_y), mask=logo_resized)
        except Exception as e:
            logger.warning(f"Error applying logo to badge: {e}")
    elif is_small_or_steep and width >= 25 and height >= 12 and ar >= 1.2:
        # Minimalist showroom accent bar in center for small plates
        bar_w = int(width * 0.45)
        bar_h = max(2, int(height * 0.18))
        bx1 = (width - bar_w) // 2
        by1 = (height - bar_h) // 2
        draw.rounded_rectangle([bx1, by1, bx1 + bar_w, by1 + bar_h], radius=1, fill=(148, 163, 184, 255))

    return badge


def detect_plate_tilt_angle(cv_img, box):
    """
    Detects the perspective tilt angle of the license plate using Hough line transforms.
    Returns angle in degrees (-45.0 to +45.0) where 0 is perfectly horizontal.
    """
    x1, y1, x2, y2 = box
    H, W = cv_img.shape[:2]
    pad = 15
    cx1 = max(0, x1 - pad)
    cy1 = max(0, y1 - pad)
    cx2 = min(W, x2 + pad)
    cy2 = min(H, y2 + pad)
    crop = cv_img[cy1:cy2, cx1:cx2]
    if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 15:
        return 0.0

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=25, maxLineGap=10)

    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for line in lines:
        lx1, ly1, lx2, ly2 = line.reshape(4)
        dx = lx2 - lx1
        dy = ly2 - ly1
        if dx == 0:
            continue
        angle = np.degrees(np.arctan2(dy, dx))
        if -45.0 <= angle <= 45.0 and (dx ** 2 + dy ** 2) ** 0.5 >= 25:
            angles.append(angle)

    if not angles or len(angles) < 3:
        return 0.0

    return float(np.median(angles))


def overlay_rotated_plate_badge(cv_img, center, length, thickness, angle_deg, logo_path=None):
    """
    Overlays a metallic badge snugly rotated to match the vehicle's perspective angle.
    Prevents giant oversized overlays on tilted vehicles.
    """
    H, W = cv_img.shape[:2]
    cx, cy = center
    bw = max(24, int(length * 1.06))
    bh = max(12, int(thickness * 1.15))

    badge_pil = create_branded_plate_badge(bw, bh, logo_path=logo_path)
    badge_np = np.array(badge_pil)

    half_w = bw / 2.0
    half_h = bh / 2.0
    corners = np.array([
        [-half_w, -half_h],
        [ half_w, -half_h],
        [ half_w,  half_h],
        [-half_w,  half_h]
    ], dtype=np.float32)

    rad = np.radians(angle_deg)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    R = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)

    rot_corners = np.dot(corners, R.T) + np.array([cx, cy], dtype=np.float32)
    src_corners = np.array([[0, 0], [bw, 0], [bw, bh], [0, bh]], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src_corners, rot_corners)
    warped_bgr = cv2.warpPerspective(badge_np[:, :, :3], M, (W, H), flags=cv2.INTER_LANCZOS4)
    warped_alpha = cv2.warpPerspective(badge_np[:, :, 3], M, (W, H), flags=cv2.INTER_LANCZOS4)

    alpha = (warped_alpha / 255.0)[:, :, np.newaxis]
    result = (cv_img * (1.0 - alpha) + warped_bgr * alpha).astype(np.uint8)
    return result


def apply_top_right_watermark(cv_img, watermark_path=None, width_ratio=0.22, alpha_boost=2.5, pad_ratio=0.025):
    """
    Overlays the Raahcar logo (logo.webp) in the top-right corner of the image as a watermark.
    Scales responsively (~22% width) and boosts alpha for a clear, prominent watermark.
    """
    target_path = watermark_path or WATERMARK_LOGO_PATH
    if not target_path or not os.path.exists(target_path):
        return cv_img

    try:
        H, W = cv_img.shape[:2]
        wm_pil = Image.open(target_path).convert("RGBA")

        # Responsive scaling: ~22% of image width for crisp, bold visibility
        target_w = max(90, int(W * width_ratio))
        scale = target_w / float(wm_pil.width)
        target_h = max(30, int(wm_pil.height * scale))

        wm_resized = wm_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
        wm_np = np.array(wm_resized)

        # Top-right coordinates with responsive padding
        pad = max(14, int(W * pad_ratio))
        x2 = W - pad
        x1 = x2 - target_w
        y1 = pad
        y2 = y1 + target_h

        if x1 < 0 or y2 > H:
            return cv_img

        roi = cv_img[y1:y2, x1:x2].astype(float)
        wm_bgr = cv2.cvtColor(wm_np, cv2.COLOR_RGBA2BGR).astype(float)

        # Boost alpha channel for a richer, more prominent watermark
        raw_alpha = wm_np[:, :, 3].astype(float)
        boosted_alpha = np.clip(raw_alpha * alpha_boost, 0.0, 255.0)
        norm_alpha = (boosted_alpha / 255.0)[:, :, np.newaxis]

        blended = roi * (1.0 - norm_alpha) + wm_bgr * norm_alpha
        cv_img[y1:y2, x1:x2] = blended.astype(np.uint8)
    except Exception as e:
        logger.warning(f"Error applying watermark: {e}")

    return cv_img


def process_image_file(input_path, output_path, logo_path=None, watermark_path=None, conf_threshold=0.25, zoom_percent=5, max_dimension=1280):
    """
    Production image processing pipeline:
    1. EXIF orientation correction.
    2. 5% SEO zoom (center crop & optional max dimension clamp for memory/storage savings).
    3. Multi-model ensemble plate detection (cars_best_v26 + plate_covered + plate_yolo_iran).
    4. Smart filtering (rejects odometers, dark cluster LCDs, corner watermarks, background cars).
    5. Automatic tilt detection and perspective badge alignment.
    6. Top-right corner watermark branding (logo.webp).
    7. WebP/JPEG optimized export.
    """
    try:
        # Step 1: Normalize EXIF orientation
        with Image.open(input_path) as pil_raw:
            pil_img = ImageOps.exif_transpose(pil_raw).convert("RGB")
            cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        H, W = cv_img.shape[:2]

        # Step 2: Safe SEO zoom without cutting off edge plates
        # We only apply center crop if no border plate would be mutilated,
        # or we detect plates first on full frame.
        # Clamp maximum dimension
        if max_dimension and max(H, W) > max_dimension:
            scale = max_dimension / float(max(H, W))
            new_w = int(W * scale)
            new_h = int(H * scale)
            cv_img = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            H, W = cv_img.shape[:2]

        result_img = cv_img.copy()

        try:
            m_cars, m_cov, m_iran, m_det = get_models()
            car_boxes = []
            candidates = []

            # 1. Primary Car Context Model (cars_best_v26)
            if m_cars is not None:
                try:
                    r_cars = m_cars(cv_img, imgsz=960, conf=0.18, verbose=False)[0]
                    for b in r_cars.boxes:
                        cls_name = r_cars.names[int(b.cls[0])]
                        conf = float(b.conf[0])
                        box = [int(v) for v in b.xyxy[0].tolist()]
                        if cls_name == "Car" and conf >= 0.35:
                            car_boxes.append((conf, box))
                        elif cls_name == "Plate" and conf >= 0.20:
                            candidates.append(("cars_v26", conf, box))
                except Exception as e:
                    logger.warning(f"Error in m_cars: {e}")

            # 2. Covered & Showroom Plate Model (Trained at 640)
            if m_cov is not None:
                try:
                    r_cov = m_cov(cv_img, imgsz=640, conf=0.18, verbose=False)[0]
                    for b in r_cov.boxes:
                        conf = float(b.conf[0])
                        box = [int(v) for v in b.xyxy[0].tolist()]
                        candidates.append(("covered", conf, box))
                except Exception as e:
                    logger.warning(f"Error in m_cov: {e}")

            # 3. General Plate Detector (Trained at 640)
            if m_det is not None:
                try:
                    r_det = m_det(cv_img, imgsz=640, conf=0.22, verbose=False)[0]
                    for b in r_det.boxes:
                        conf = float(b.conf[0])
                        box = [int(v) for v in b.xyxy[0].tolist()]
                        candidates.append(("detector", conf, box))
                except Exception as e:
                    logger.warning(f"Error in m_det: {e}")

            # 3. Specialized Iranian Plate Model
            if m_iran is not None:
                try:
                    r_iran = m_iran(cv_img, imgsz=960, conf=0.28, verbose=False)[0]
                    for b in r_iran.boxes:
                        conf = float(b.conf[0])
                        box = [int(v) for v in b.xyxy[0].tolist()]
                        candidates.append(("iran", conf, box))
                except Exception as e:
                    logger.warning(f"Error in m_iran: {e}")

            # Sort cars by area to identify primary foreground car
            car_boxes.sort(key=lambda c: (c[1][2] - c[1][0]) * (c[1][3] - c[1][1]), reverse=True)
            primary_car = car_boxes[0][1] if car_boxes else None

            valid_candidates = []
            for src, conf, box in candidates:
                x1, y1, x2, y2 = box
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(W, x2), min(H, y2)
                bw = x2 - x1
                bh = y2 - y1

                if bw < 20 or bh < 8:
                    continue

                # Reject camera watermark text at extreme bottom corner
                if y2 > 0.94 * H and (x2 < 0.24 * W or x1 > 0.76 * W) and bh < 0.05 * H:
                    continue

                # Reject absurd proportions (e.g. whole hood or side of car)
                if bw > 0.65 * W or bh > 0.25 * H:
                    continue

                # Aspect ratio check: Iranian plates and covers are horizontal (1.25 to 7.5).
                # Tilted plates reach 1.3 to 2.0; wide closeups reach 5.0 to 7.0.
                # Never allow ar < 1.25 (prevents vertical wheels/tires, headlights, or square gadgets).
                ar = bw / float(bh)
                if ar < 1.25 or ar > 7.5:
                    continue

                crop = cv_img[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # 1. Reject dark plastic / turned-off odometer LCD / AC vents:
                # Real Iranian plates and showroom covers have reflective white/yellow/silver backgrounds.
                # Hazard buttons, AC vents, and cluster plastic have median < 48 and mean < 58.
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                p80 = float(np.percentile(gray, 80))
                med_val = float(np.median(gray))
                mean_val = float(np.mean(gray))
                if p80 < 70 or (med_val < 48 and mean_val < 58):
                    continue

                # 2. Reject red digital 7-segment odometer displays (e.g. bama_fhwthfsj_img2)
                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                red_mask = ((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 100)
                if (red_mask.sum() / float(bw * bh)) > 0.035:
                    continue

                # 3. Reject cabin multimedia / GPS navigation screens with high color saturation:
                # Plates and dealer frames have neutral/monochrome centers (white, silver, black, yellow).
                # LCD monitors showing blue maps or media have saturation > 120 across the center.
                center_w = max(4, int(bw * 0.6))
                cx_start = int(bw * 0.2)
                center_hsv = hsv[:, cx_start:cx_start + center_w]
                if center_hsv.size > 0 and float(np.mean(center_hsv[:, :, 1])) > 120.0:
                    continue

                # 4. Detect tilt angle to filter out hood emblems (e.g. Peugeot lion, Mercedes star)
                # A horizontal plate (angle < 6 deg) must have AR >= 2.2. If AR < 2.2, it is an emblem/grille!
                candidate_tilt = detect_plate_tilt_angle(cv_img, (x1, y1, x2, y2))
                if abs(candidate_tilt) < 6.0 and ar < 2.2:
                    continue

                # 4. Score weighting: Prioritize primary foreground vehicle
                area_weight = (bw * bh) ** 0.25
                score = conf * area_weight

                if primary_car is not None:
                    cx1, cy1, cx2, cy2 = primary_car
                    pxc = (x1 + x2) // 2
                    pyc = (y1 + y2) // 2
                    # If plate is inside the primary foreground car, strongly prioritize
                    if cx1 <= pxc <= cx2 and cy1 <= pyc <= cy2:
                        score *= 2.5
                    else:
                        score *= 0.35

                valid_candidates.append({
                    "box": (x1, y1, x2, y2),
                    "conf": conf,
                    "score": score,
                    "src": src
                })

            # If plate detected, overlay branded plate badge
            if valid_candidates:
                # Select best candidate
                best = max(valid_candidates, key=lambda c: c["score"])
                x1, y1, x2, y2 = best["box"]
                bw = x2 - x1
                bh = y2 - y1
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Detect perspective tilt angle
                tilt_angle = detect_plate_tilt_angle(cv_img, (x1, y1, x2, y2))

                # If plate is tilted (angle >= 6°), overlay rotated metallic badge
                if abs(tilt_angle) >= 6.0:
                    plate_length = max(bw, bh)
                    plate_thickness = max(16, int(plate_length / 4.4))
                    result_img = overlay_rotated_plate_badge(
                        cv_img,
                        (cx, cy),
                        plate_length,
                        plate_thickness,
                        tilt_angle,
                        logo_path=logo_path
                    )
                else:
                    # Horizontal plate: Apply clean rectangular badge with strict height clamp
                    pad_x = max(2, int(bw * 0.05))
                    pad_y = max(2, int(bh * 0.08))
                    fx1 = max(0, x1 - pad_x)
                    fx2 = min(W, x2 + pad_x)
                    fy1 = max(0, y1 - pad_y)
                    fy2 = min(H, y2 + pad_y)
                    fbw = fx2 - fx1
                    fbh = fy2 - fy1

                    max_h = max(14, int(fbw / 3.8))
                    if fbh > max_h:
                        b_cy = (fy1 + fy2) // 2
                        fy1 = max(0, b_cy - max_h // 2)
                        fy2 = min(H, fy1 + max_h)
                        fbh = fy2 - fy1

                    badge_pil = create_branded_plate_badge(fbw, fbh, logo_path=logo_path)
                    badge_np = np.array(badge_pil)
                    badge_bgr = cv2.cvtColor(badge_np, cv2.COLOR_RGBA2BGR)
                    badge_alpha = (badge_np[:, :, 3] / 255.0)[:, :, np.newaxis]

                    roi = result_img[fy1:fy2, fx1:fx2]
                    result_img[fy1:fy2, fx1:fx2] = (roi * (1.0 - badge_alpha) + badge_bgr * badge_alpha).astype(np.uint8)

        except Exception as det_err:
            logger.warning(f"Plate detection skipped or encountered error on {input_path}: {det_err}")

        # Step 7: Top-right watermark branding (logo.webp)
        # Always applied on EVERY image of every ad (whether plate was detected or not)
        result_img = apply_top_right_watermark(result_img, watermark_path=watermark_path)

        # Step 8: Export WebP / JPEG
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if output_path.lower().endswith(".webp"):
            cv2.imwrite(output_path, result_img, [int(cv2.IMWRITE_WEBP_QUALITY), 80])
        elif output_path.lower().endswith((".jpg", ".jpeg")):
            cv2.imwrite(output_path, result_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        else:
            cv2.imwrite(output_path, result_img)

        return output_path

    except Exception as e:
        logger.exception(f"Error processing image {input_path}: {e}")
        return None
