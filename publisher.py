import os
import sys
import re
import uuid
import shutil
import logging
import requests
import urllib.request

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURR_DIR not in sys.path:
    sys.path.insert(0, _CURR_DIR)

try:
    from config import INGEST_ENDPOINT, INGESTION_API_KEY, TEMP_IMAGE_DIR, LOGO_PATH, WATERMARK_LOGO_PATH
    from image_processor import process_image_file
except ImportError:
    try:
        from scraper_bot.config import INGEST_ENDPOINT, INGESTION_API_KEY, TEMP_IMAGE_DIR, LOGO_PATH, WATERMARK_LOGO_PATH
        from scraper_bot.image_processor import process_image_file
    except ImportError:
        raise

logger = logging.getLogger(__name__)


def download_image(img_url, dest_path):
    """
    Downloads image from URL with browser headers.
    Falls back to base URL if resize service returns an error.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://bama.ir"
    }
    try:
        req = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())
    except urllib.error.HTTPError:
        base_url = img_url.split("?")[0]
        if base_url != img_url:
            req = urllib.request.Request(base_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                with open(dest_path, "wb") as f:
                    f.write(resp.read())
        else:
            raise
    return dest_path


def publish_ad_with_processed_images(ad_data, logo_path=LOGO_PATH, watermark_path=WATERMARK_LOGO_PATH):
    """
    Downloads images, overlays logo on license plates, applies top-right Raahcar watermark
    to EVERY image, applies 5% SEO zoom, exports as optimized WebP with random filenames,
    and pushes ad to main server.
    """
    source_id = ad_data.get("source_id", "temp_ad")
    image_urls = ad_data.get("image_urls", [])

    safe_folder = re.sub(r'[^\w\-]', '_', str(source_id))[-35:] or uuid.uuid4().hex[:8]
    ad_temp_dir = os.path.join(TEMP_IMAGE_DIR, safe_folder)
    raw_dir = os.path.join(ad_temp_dir, "raw")
    proc_dir = os.path.join(ad_temp_dir, "processed")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(proc_dir, exist_ok=True)

    processed_file_paths = []

    try:
        # 1. Download & Process Images
        for idx, url in enumerate(image_urls):
            try:
                # Generate unique random filename (hiding any source website references)
                rand_id = uuid.uuid4().hex
                raw_path = os.path.join(raw_dir, f"raw_{idx}_{rand_id[:8]}.jpg")
                proc_path = os.path.join(proc_dir, f"{rand_id}.webp")

                download_image(url, raw_path)
                res_path = process_image_file(raw_path, proc_path, logo_path=logo_path, watermark_path=watermark_path)
                if res_path and os.path.exists(res_path):
                    processed_file_paths.append(res_path)
                else:
                    processed_file_paths.append(raw_path)

            except Exception as e:
                logger.warning(f"Error downloading/processing image {url}: {e}")

        # 2. Prepare payload without raw image_urls (since we send files)
        payload = {k: v for k, v in ad_data.items() if k != "image_urls"}

        headers = {
            "X-API-KEY": INGESTION_API_KEY
        }

        # 3. Open file handles for multipart upload
        files = []
        opened_handles = []
        try:
            for p in processed_file_paths:
                h = open(p, "rb")
                opened_handles.append(h)
                fname = os.path.basename(p)
                content_type = "image/webp" if fname.lower().endswith(".webp") else "image/jpeg"
                files.append(("images", (fname, h, content_type)))

            logger.info(f"Publishing {ad_data.get('brand_name')} {ad_data.get('model_name')} ({source_id}) with {len(files)} images...")
            response = requests.post(
                INGEST_ENDPOINT,
                data=payload,
                files=files,
                headers=headers,
                timeout=120
            )

            if response.status_code in [200, 201]:
                logger.info(f"Successfully published {source_id}: {response.json()}")
                return response.json()
            else:
                logger.error(f"Failed to publish {source_id}: Status {response.status_code} - {response.text}")
                return {"status": "error", "code": response.status_code, "text": response.text}

        finally:
            for h in opened_handles:
                h.close()

    finally:
        # Clean up temp folder for this ad
        if os.path.exists(ad_temp_dir):
            shutil.rmtree(ad_temp_dir, ignore_errors=True)
