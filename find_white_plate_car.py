import sys
import os
import urllib.request
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import fetch_ads_by_fuel
from image_processor import get_models, process_image_file

m_cars, m_cov, m_iran, m_det = get_models()
print("Searching Bama for ads with visible license plates...")
ads = fetch_ads_by_fuel("gasoline", target_count=20)

preview_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(preview_dir, exist_ok=True)

found_image = None
for ad in ads:
    source_id = ad["source_id"]
    brand = ad.get("brand_name", "")
    model = ad.get("model_name", "")
    print(f"Checking {brand} {model} ({source_id})...")
    
    for idx, url in enumerate(ad.get("image_urls", [])):
        raw_path = os.path.join(preview_dir, f"candidate_raw.jpg")
        proc_path = os.path.join(preview_dir, f"sample_car_white_plate.jpg")
        
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                with open(raw_path, "wb") as f:
                    f.write(resp.read())
        except Exception:
            continue
            
        img = cv2.imread(raw_path)
        if img is None:
            continue
            
        res_output = process_image_file(raw_path, proc_path)
        if res_output and os.path.exists(proc_path):
            im_proc = cv2.imread(proc_path)
            # Check if white badge was drawn: find pure white / near-white pixels of the badge
            # In our badge, background is (255, 255, 255)
            white_mask = (im_proc[:, :, 0] > 250) & (im_proc[:, :, 1] > 250) & (im_proc[:, :, 2] > 250)
            white_raw_mask = (img[:, :, 0] > 250) & (img[:, :, 1] > 250) & (img[:, :, 2] > 250)
            added_white = white_mask.sum() - cv2.resize(white_raw_mask.astype(np.uint8), (im_proc.shape[1], im_proc.shape[0])).sum()
            
            if added_white > 500:  # White badge was definitely placed!
                print(f"🎉 SUCCESS! Found and covered plate on {brand} {model} ({source_id}) image {idx}!")
                print(f"Result saved at: {proc_path}")
                found_image = proc_path
                break
                
    if found_image:
        break

if not found_image:
    print("Could not find suitable plate in this batch.")
