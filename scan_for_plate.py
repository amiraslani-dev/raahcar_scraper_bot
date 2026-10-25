import sys
import os
import urllib.request
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import fetch_ads_by_fuel
from image_processor import get_models, process_image_file

m_cars, m_cov, m_iran, m_det = get_models()
print("Fetching 15 ads from Bama...")
ads = fetch_ads_by_fuel("gasoline", target_count=15)

preview_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(preview_dir, exist_ok=True)

found = False
for ad in ads:
    source_id = ad["source_id"]
    brand = ad.get("brand_name", "")
    model = ad.get("model_name", "")
    print(f"Checking {brand} {model} ({source_id}) with {len(ad.get('image_urls', []))} images...")
    
    for idx, url in enumerate(ad.get("image_urls", [])[:5]):
        raw_path = os.path.join(preview_dir, f"scan_raw.jpg")
        proc_path = os.path.join(preview_dir, f"white_plate_covered_car.jpg")
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
            
        # Check Iranian plate model or covered plate model
        res_iran = m_iran(img, imgsz=960, conf=0.22, verbose=False)[0] if m_iran else None
        res_det = m_det(img, imgsz=640, conf=0.22, verbose=False)[0] if m_det else None
        
        plates_count = (len(res_iran.boxes) if res_iran else 0) + (len(res_det.boxes) if res_det else 0)
        if plates_count > 0:
            print(f"===> BINGO! Found {plates_count} plate(s) in {brand} {model} (image {idx})!")
            res = process_image_file(raw_path, proc_path)
            print("Successfully processed and saved at:", proc_path)
            found = True
            break
            
    if found:
        break

if not found:
    print("No plates detected in batch.")
