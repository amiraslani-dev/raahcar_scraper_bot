import os
import sys
import logging

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURR_DIR not in sys.path:
    sys.path.insert(0, _CURR_DIR)

try:
    from celery_app import app
    from scraper import fetch_all_bama_ads, DEFAULT_FUEL_QUOTAS
    from publisher import publish_ad_with_processed_images
    from config import BOT_CONFIG_ENDPOINT, INGESTION_API_KEY
except ImportError:
    try:
        from scraper_bot.celery_app import app
        from scraper_bot.scraper import fetch_all_bama_ads, DEFAULT_FUEL_QUOTAS
        from scraper_bot.publisher import publish_ad_with_processed_images
        from scraper_bot.config import BOT_CONFIG_ENDPOINT, INGESTION_API_KEY
    except ImportError:
        raise

import requests

logger = logging.getLogger("RaahcarCeleryTasks")


def fetch_remote_bot_config():
    """
    Fetches dynamic scraping settings from main server Django admin.
    """
    try:
        headers = {"X-API-KEY": INGESTION_API_KEY}
        resp = requests.get(BOT_CONFIG_ENDPOINT, headers=headers, timeout=12)
        if resp.status_code == 200:
            logger.info("Successfully loaded remote bot configuration from main server.")
            return resp.json()
        else:
            logger.warning(f"Failed to fetch remote config (HTTP {resp.status_code}). Using local defaults.")
    except Exception as exc:
        logger.warning(f"Error connecting to main server for config: {exc}. Using local defaults.")
    return None


@app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    autoretry_for=(Exception,)
)
def publish_single_ad_task(self, ad_data):
    """
    Celery task to download images, detect/cover license plates,
    and post the ad to the main server API.
    Auto-retries up to 5 times on network failure.
    """
    source_id = ad_data.get("source_id", "unknown")
    brand = ad_data.get("brand_name", "")
    model = ad_data.get("model_name", "")
    logger.info(f"[Celery Worker] Starting task for ad {source_id} - {brand} {model}")

    try:
        from publisher import publish_ad_with_processed_images
        result = publish_ad_with_processed_images(ad_data)
        logger.info(f"[Celery Worker] Result for {source_id}: {result.get('status')}")
        return result
    except Exception as exc:
        logger.error(f"[Celery Worker] Failed to process {source_id}: {exc}. Retrying...")
        raise self.retry(exc=exc)


@app.task
def start_daily_scraping_batch_task(fuel_quotas=None, delay_seconds=None):
    """
    Celery task to fetch ads and schedule them into Redis queue based on Django Admin config.
    """
    # 1. Fetch live config from Django Admin
    remote_cfg = fetch_remote_bot_config()

    min_interval = 45
    max_interval = 150

    if remote_cfg:
        if not remote_cfg.get("is_active", True):
            logger.warning("⏸ [Scraper Task] Bot is disabled in Django Admin (is_active=False). Skipping execution.")
            return {"status": "skipped", "reason": "disabled_in_django_admin"}

        if fuel_quotas is None:
            fuel_quotas = remote_cfg.get("fuel_quotas", DEFAULT_FUEL_QUOTAS)

        min_interval = remote_cfg.get("min_interval_seconds", 45)
        max_interval = remote_cfg.get("max_interval_seconds", 150)
    else:
        if fuel_quotas is None:
            fuel_quotas = DEFAULT_FUEL_QUOTAS

    if delay_seconds is not None:
        min_interval = delay_seconds
        max_interval = delay_seconds
    elif min_interval > max_interval:
        min_interval, max_interval = max_interval, min_interval

    total_target = sum(fuel_quotas.values())
    logger.info(f"🚀 [Scraper Task] Fetching {total_target} ads across fuel quotas: {fuel_quotas}")

    ads = fetch_all_bama_ads(fuel_quotas=fuel_quotas, shuffle=True)
    logger.info(f"⚡ [Scraper Task] Fetched {len(ads)} ads. Enqueuing with randomized delays ({min_interval}s - {max_interval}s)...")

    import random
    scheduled_count = 0
    accumulated_delay = 0

    for ad in ads:
        random_step = random.randint(min_interval, max_interval)
        accumulated_delay += random_step
        publish_single_ad_task.apply_async(args=[ad], countdown=accumulated_delay)
        scheduled_count += 1

    total_hours = round(accumulated_delay / 3600, 2)
    logger.info(f"✅ [Scraper Task] Successfully enqueued {scheduled_count} ads randomly spread across ~{total_hours} hours.")
    return {
        "status": "enqueued",
        "total_ads": scheduled_count,
        "min_interval": min_interval,
        "max_interval": max_interval,
        "total_spread_hours": total_hours
    }


