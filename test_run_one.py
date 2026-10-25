import sys
import os
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import fetch_ads_by_fuel
from image_processor import process_image_file
from publisher import publish_ad_with_processed_images

print("1. Fetching 1 ad from Bama...")
ads = fetch_ads_by_fuel("gasoline", target_count=1)
if not ads:
    print("No ads returned!")
    sys.exit(1)

ad = ads[0]
print("Fetched ad:", ad.get("brand_name"), ad.get("model_name"), f"({ad.get('source_id')})")
print("Images count:", len(ad.get("image_urls", [])))

preview_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(preview_dir, exist_ok=True)

if ad.get("image_urls"):
    first_url = ad["image_urls"][0]
    raw_preview = os.path.join(preview_dir, "raw.jpg")
    proc_preview = os.path.join(preview_dir, "result_white_badge.jpg")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(first_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        with open(raw_preview, "wb") as f:
            f.write(resp.read())
    print("Processing first image with AI and white badge...")
    res = process_image_file(raw_preview, proc_preview)
    print("Processed preview saved at:", proc_preview)

print("Publishing to raahcar.com...")
pub_res = publish_ad_with_processed_images(ad)
print("Publish Result:", pub_res)
