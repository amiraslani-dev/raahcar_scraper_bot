# scraper_bot/scraper.py
import re
import time
import random
import logging
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://bama.ir/car",
    "Origin": "https://bama.ir"
}

# Fuel Type quotas requested by client
DEFAULT_FUEL_QUOTAS = {
    "gasoline": 260,       # بنزینی
    "cng_gasoline": 20,    # دوگانه‌سوز
    "electric": 10,        # برقی
    "hybrid": 10           # هیبریدی
}


def clean_mileage(mileage_str):
    if not mileage_str or "صفر" in mileage_str:
        return 0
    digits = re.sub(r"[^\d]", "", str(mileage_str))
    return int(digits) if digits else 0


def clean_price(price_dict):
    if not price_dict:
        return 0
    price_str = price_dict.get("price", "0")
    if not price_str or price_str in ["توافقی", "در توضیحات"]:
        return 0
    digits = re.sub(r"[^\d]", "", str(price_str))
    return int(digits) if digits else 0


def clean_city(location_str):
    if not location_str:
        return "تهران"
    parts = location_str.split("/")
    return parts[0].strip() if parts else "تهران"


def map_transmission(val):
    if not val:
        return "auto"
    if "دنده" in val or "دستی" in val:
        return "manual"
    return "auto"


def map_fuel(val):
    if not val:
        return "petrol"
    if "برق" in val or "electric" in val.lower():
        return "electric"
    if "هیبرید" in val or "hybrid" in val.lower():
        return "hybrid"
    if "دوگانه" in val or "cng" in val.lower():
        return "cng"
    if "دیزل" in val or "diesel" in val.lower():
        return "diesel"
    return "petrol"


def map_body_status(val):
    if not val:
        return "healthy"
    if "بدون رنگ" in val or "خط و خش" in val:
        return "healthy"
    if "یک لکه" in val:
        return "one_spot"
    if "دو لکه" in val:
        return "two_spots"
    if "چند لکه" in val:
        return "multi_spots"
    if "دور رنگ" in val:
        return "around_paint"
    if "تمام رنگ" in val:
        return "full_paint"
    if "تصادفی" in val:
        return "crashed"
    return "healthy"


def extract_model_name(title_str, brand_fa):
    if not title_str:
        return "نامشخص"
    if "،" in title_str:
        return title_str.split("،", 1)[1].strip()
    if brand_fa and title_str.startswith(brand_fa):
        return title_str.replace(brand_fa, "").strip()
    return title_str.strip()


def transform_bama_image_url(url):
    """
    Transforms Bama cropped/thumbnail image URLs into full-resolution uncropped 2560px URLs.
    Strips thumbnail dimensions (_thumb_900_600) and query parameters, appending 2560px resize query.
    """
    if not url:
        return url
    base = url.split("?")[0]
    base = re.sub(r"_thumb_\d+_\d+", "", base)
    return f"{base}?x-img=v1%2Fresize,w_2560"


def parse_bama_ad(raw_ad):
    """
    Parses a single raw ad from Bama API response into a normalized dictionary.
    """
    detail = raw_ad.get("detail", {})
    price_info = raw_ad.get("price", {})
    images_list = raw_ad.get("images", [])

    if not detail or not detail.get("code"):
        return None

    code = detail.get("code")
    raw_ad_url = detail.get("url")
    if raw_ad_url:
        ad_url = raw_ad_url if raw_ad_url.startswith("http") else f"https://bama.ir{raw_ad_url}"
    else:
        ad_url = f"https://bama.ir/car/detail-{code}"

    brand_fa = detail.get("brand_fa") or detail.get("brand") or "نامشخص"
    title = detail.get("title", "")
    model_name = extract_model_name(title, brand_fa)
    trim = detail.get("trim") or detail.get("subtitle") or "استاندارد"

    year_str = detail.get("year", "1402")
    digits_year = re.sub(r"[^\d]", "", str(year_str))
    year = int(digits_year) if digits_year else 1402

    image_urls = []
    for img_obj in images_list:
        raw_url = None
        if isinstance(img_obj, dict):
            raw_url = img_obj.get("large") or img_obj.get("url")
        elif isinstance(img_obj, str):
            raw_url = img_obj
        if raw_url:
            image_urls.append(transform_bama_image_url(raw_url))

    mileage = clean_mileage(detail.get("mileage"))
    condition = "new" if mileage == 0 else "used"
    description = detail.get("description") or ""

    return {
        "source_id": ad_url,
        "brand_name": brand_fa,
        "model_name": model_name,
        "tip_name": trim,
        "city_name": clean_city(detail.get("location")),
        "year": year,
        "mileage": mileage,
        "price": clean_price(price_info),
        "color": detail.get("body_color") or "سفید",
        "condition": condition,
        "fuel_type": map_fuel(detail.get("fuel")),
        "transmission": map_transmission(detail.get("transmission")),
        "body_status": map_body_status(detail.get("body_status")),
        "description": description.strip(),
        "status": "approved",
        "is_immediate": False,
        "sale_type": "custom",
        "image_urls": image_urls
    }


def fetch_ads_by_fuel(fuel_key, target_count, page_size=24, seen_ids=None):
    """
    Fetches a specific count of ads for a given fuel type from Bama API.
    """
    if seen_ids is None:
        seen_ids = set()

    base_url = "https://bama.ir/cad/api/search"
    params = {
        "seller": "1",
        "status": ["no_paint", "scratches"],
        "region": ["tehran,tehran", "alborz,karaj"],
        "image": "1",
        "priced": "1",
        "yearFrom": "1398-2019",
        "fuel": fuel_key,
        "pageSize": page_size
    }

    collected = []
    page = 0
    max_pages = (target_count // page_size) + 5

    logger.info(f"Fetching {target_count} ads for fuel '{fuel_key}'...")

    while len(collected) < target_count and page <= max_pages:
        params["pageIndex"] = page
        try:
            response = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                logger.warning(f"Fuel [{fuel_key}] Page {page}: HTTP {response.status_code}")
                break

            res_json = response.json()
            ads = res_json.get("data", {}).get("ads", [])
            if not ads:
                logger.info(f"No more ads available for fuel '{fuel_key}'.")
                break

            for ad_item in ads:
                if ad_item.get("type") != "ad":
                    continue
                parsed = parse_bama_ad(ad_item)
                if parsed and parsed["source_id"] not in seen_ids:
                    seen_ids.add(parsed["source_id"])
                    collected.append(parsed)
                    if len(collected) >= target_count:
                        break

            page += 1
            time.sleep(0.3)

        except Exception as e:
            logger.exception(f"Error fetching fuel [{fuel_key}] page {page}: {e}")
            break

    logger.info(f"Collected {len(collected)}/{target_count} ads for fuel '{fuel_key}'.")
    return collected


FUEL_KEY_MAP = {
    "بنزینی": "gasoline",
    "دوگانه سوز": "cng_gasoline",
    "دوگانه‌سوز": "cng_gasoline",
    "گازسوز": "cng_gasoline",
    "برقی": "electric",
    "الکتریکی": "electric",
    "هیبرید": "hybrid",
    "هیبریدی": "hybrid",
    "دیزل": "diesel",
    "دیزلی": "diesel",
}


def fetch_all_bama_ads(fuel_quotas=None, shuffle=True):
    """
    Fetches ads based on specified fuel quotas (e.g. 260 petrol, 20 CNG, 10 electric, 10 hybrid)
    and mixes them for natural staggered publishing.
    """
    if fuel_quotas is None:
        fuel_quotas = DEFAULT_FUEL_QUOTAS

    all_ads = []
    seen_ids = set()

    for raw_fuel_key, count in fuel_quotas.items():
        if count <= 0:
            continue
        fuel_key = FUEL_KEY_MAP.get(str(raw_fuel_key).strip(), raw_fuel_key)
        ads = fetch_ads_by_fuel(fuel_key=fuel_key, target_count=count, seen_ids=seen_ids)
        all_ads.extend(ads)

    logger.info(f"Total collected ads across all fuel types: {len(all_ads)}")

    if shuffle:
        random.shuffle(all_ads)

    return all_ads
