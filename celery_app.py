import os
import sys
from celery import Celery

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURR_DIR not in sys.path:
    sys.path.insert(0, _CURR_DIR)

try:
    from config import REDIS_URL
except ImportError:
    try:
        from scraper_bot.config import REDIS_URL
    except ImportError:
        raise

app = Celery(
    "raahcar_scraper",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

from celery.schedules import crontab

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=300,        # 5 minutes max per ad
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1, # Fair task distribution
    broker_connection_retry_on_startup=True,
    worker_send_task_events=True,  # Enables real-time monitoring in Flower
    task_send_sent_event=True,     # Track when tasks are enqueued
    beat_schedule={
        "daily-car-scraping-batch": {
            "task": "tasks.start_daily_scraping_batch_task",
            "schedule": crontab(hour=8, minute=0),  # Runs every day at 08:00 AM Tehran time
        },
    }
)

if __name__ == "__main__":
    app.start()
