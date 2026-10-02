from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from main import run_once
from config.settings import check_settings
from logger import get_logger

logger = get_logger("scheduler")


def safe_run():
    """اجرای امن: خطای یک دور، کل ربات رو نمی‌کُشه."""
    try:
        run_once()
    except Exception:
        logger.exception("خطای غیرمنتظره در اجرای دوره‌ای")


def start():
    missing = check_settings()
    if missing:
        logger.error("تنظیمات ناقصه: %s — فایل .env رو کامل کن", ", ".join(missing))
        return

    scheduler = BlockingScheduler(timezone="Asia/Tehran")
    scheduler.add_job(
        safe_run,
        trigger=IntervalTrigger(hours=1),
        id="hourly_news",
        next_run_time=datetime.now(),  # همین الان یک بار اجرا شه
        max_instances=1,  # اگه دوره قبل تموم نشده، دوره جدید شروع نشه
        coalesce=True,    # اجراهای عقب‌افتاده رو یکی کن
    )

    logger.info("ربات شروع شد. هر ساعت %s پست جدید می‌ذاره", 3)
    logger.info("برای توقف: Ctrl+C")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("ربات متوقف شد")


if __name__ == "__main__":
    start()
