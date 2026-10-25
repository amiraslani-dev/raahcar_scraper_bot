import sys
import os
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import fetch_ads_by_fuel
from image_processor import process_image_file, detect_plate_tilt_angle

print("Fetching ads to find a clear license plate...")
ads = fetch_ads_by_fuel("gasoline", target_count=5)

preview_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(preview_dir, exist_ok=True)

found = False
for ad in ads:
    print(f"Checking ad: {ad.get('brand_name')} {ad.get('model_name')} ({ad.get('source_id')}) with {len(ad.get('image_urls', []))} images")
    for idx, url in enumerate(ad.get("image_urls", [])):
        raw_path = os.path.join(preview_dir, f"raw_{ad.get('source_id')}_{idx}.jpg")
        proc_path = os.path.join(preview_dir, f"proc_{ad.get('source_id')}_{idx}.jpg")
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            with open(raw_path, "wb") as f:
                f.write(resp.read())
        res = process_image_file(raw_path, proc_path)
        # Check if proc_path was created and differs from raw (meaning plate was found and covered)
        if res and os.path.exists(proc_path):
            import cv2, numpy as np
            im1 = cv2.imread(raw_path)
            im2 = cv2.imread(proc_path)
            if im1 is not None and im2 is not None:
                diff = np.abs(im1.astype("float") - cv2.resize(im2, (im1.shape[1], im1.shape[0])).astype("float")).mean()
                if diff > 1.5:  # Significant badge was overlaid!
                    print(f"===> FOUND AND OVERLAID! Image index {idx} on {ad.get('brand_name')} {ad.get('model_name')}")
                    final_sample = os.path.join(preview_dir, "final_car_white_plate.jpg")
                    cv2.imwrite(final_sample, im2)
                    print(f"Saved final sample at: {final_sample}")
                    found = True
                    break
    if found:
        break
