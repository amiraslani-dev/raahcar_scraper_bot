# scraper_bot/main.py
import sys
import time
import argparse
import logging
try:
    from config import LOGO_PATH, REDIS_URL
    from scraper import fetch_all_bama_ads, DEFAULT_FUEL_QUOTAS
except ImportError:
    from scraper_bot.config import LOGO_PATH, REDIS_URL
    from scraper_bot.scraper import fetch_all_bama_ads, DEFAULT_FUEL_QUOTAS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RaahcarScraper")


def dispatch_to_celery(fuel_quotas=None, delay_seconds=72):
    """
    Enqueues the scraping and publishing batch into Celery + Redis.
    """
    try:
        from tasks import start_daily_scraping_batch_task
        logger.info("📡 Dispatching scraping job to Celery Worker & Redis Broker...")
        result = start_daily_scraping_batch_task.delay(fuel_quotas=fuel_quotas, delay_seconds=delay_seconds)
        logger.info(f"✅ Job successfully dispatched to Celery! Task ID: {result.id}")
        logger.info("   Celery Worker will handle the downloads, plate detection, and publishing in the background.")
    except Exception as e:
        logger.error(f"❌ Could not connect to Redis / Celery: {e}")
        logger.info("👉 Make sure Redis is running (e.g. 'docker compose up -d' or 'redis-server').")


def run_standalone_direct(fuel_quotas=None, delay_seconds=72, allowed_brands=None, brand_aliases=None):
    """
    Direct standalone execution without Celery/Redis.
    """
    if fuel_quotas is None:
        fuel_quotas = DEFAULT_FUEL_QUOTAS

    total_target = sum(fuel_quotas.values())
    logger.info("=" * 65)
    logger.info("🚀 Starting Direct Scraper & Publishing Pipeline (Standalone)")
    logger.info(f"Target Breakdown: {fuel_quotas}")
    logger.info(f"Total Target: {total_target} ads | Interval: {delay_seconds}s")
    logger.info("=" * 65)
    from publisher import publish_ad_with_processed_images

    start_time = time.time()
    ads = fetch_all_bama_ads(
        fuel_quotas=fuel_quotas,
        shuffle=True,
        allowed_brands=allowed_brands,
        brand_aliases=brand_aliases
    )
    fetch_duration = time.time() - start_time
    logger.info(f"⚡ Fetched {len(ads)} valid ads in {fetch_duration:.2f} seconds.")

    if not ads:
        logger.warning("No ads were fetched. Exiting.")
        return

    success_count = 0
    failed_count = 0

    for idx, ad in enumerate(ads, 1):
        logger.info(f"\n[{idx}/{len(ads)}] Publishing: {ad.get('brand_name')} {ad.get('model_name')} [{ad.get('fuel_type')}] ({ad.get('source_id')})")
        try:
            res = publish_ad_with_processed_images(ad, logo_path=LOGO_PATH)
            if res and res.get("status") in ["success", "already_exists"]:
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.exception(f"Error publishing {ad.get('source_id')}: {e}")
            failed_count += 1

        if idx < len(ads) and delay_seconds > 0:
            logger.info(f"⏳ Waiting {delay_seconds}s before next ad...")
            time.sleep(delay_seconds)

    logger.info("=" * 65)
    logger.info(f"✅ Pipeline finished! Published: {success_count} | Failed: {failed_count}")
    logger.info("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raahcar Car Ad Scraper & Publisher")
    parser.add_argument("--mode", choices=["celery", "direct"], default="celery", help="Execution mode (default: celery)")
    parser.add_argument("--delay", type=int, default=72, help="Delay between ads in seconds (default: 72s)")
    parser.add_argument("--test", action="store_true", help="Run quick test mode (1 of each fuel type)")

    args = parser.parse_args()

    if args.test:
        test_quotas = {"gasoline": 1, "cng_gasoline": 1, "electric": 1, "hybrid": 1}
        if args.mode == "celery":
            dispatch_to_celery(fuel_quotas=test_quotas, delay_seconds=5)
        else:
            run_standalone_direct(fuel_quotas=test_quotas, delay_seconds=2)
    else:
        if args.mode == "celery":
            dispatch_to_celery(fuel_quotas=None, delay_seconds=None)
        else:
            try:
                from tasks import fetch_remote_bot_config
                cfg = fetch_remote_bot_config()
                admin_quotas = cfg.get("fuel_quotas") if cfg else None
                admin_delay = cfg.get("interval_seconds") if cfg else args.delay
                admin_allowed_brands = cfg.get("allowed_brands") if cfg else None
                admin_brand_aliases = cfg.get("brand_aliases") if cfg else None
            except Exception:
                admin_quotas = None
                admin_delay = args.delay
                admin_allowed_brands = None
                admin_brand_aliases = None
            run_standalone_direct(
                fuel_quotas=admin_quotas,
                delay_seconds=admin_delay,
                allowed_brands=admin_allowed_brands,
                brand_aliases=admin_brand_aliases
            )
