import threading
import time

from fetcher import get_latest_news
from history import load_history, save_history, filter_new_news, mark_posted
from translator import translate_news
from telegram_bot import send_message
from logger import get_logger

logger = get_logger("main")

# تعداد پست در هر اجرا
MAX_POSTS_PER_RUN = 3

# فاصله بین ترجمه‌ها تا به سهمیه دقیقه‌ای نخوریم
TRANSLATE_GAP = 15  # ثانیه

# قفل: جلوی اجرای همزمان دو دوره رو می‌گیره
_run_lock = threading.Lock()


def format_post(news, translated):
    """پست نهایی تلگرام رو می‌سازه."""
    tags = " ".join(translated["hashtags"])
    return (
        f"🔸 <b>{translated['title']}</b>\n\n"
        f"{translated['summary']}\n\n"
        f"📰 منبع: {news['source']}\n"
        f"🔗 <a href=\"{news['link']}\">متن کامل خبر</a>\n\n"
        f"{tags}"
    )


def run_once():
    """یک بار کل خط لوله رو اجرا می‌کنه. اگه دوره دیگه‌ای فعاله، رد می‌شه."""
    if not _run_lock.acquire(blocking=False):
        logger.info("دوره دیگه‌ای هنوز در جریانه؛ این اجرا رد شد")
        return 0

    try:
        return _run_pipeline()
    finally:
        _run_lock.release()


def _run_pipeline():
    history = load_history()
    logger.info("تاریخچه قبلی: %s لینک", len(history["links"]))

    news = get_latest_news(limit_per_feed=5)
    new_news = filter_new_news(news, history)
    logger.info("کل اخبار: %s | خبر تازه: %s", len(news), len(new_news))

    posted = 0
    for item in new_news[:MAX_POSTS_PER_RUN]:
        if not item["title"] or not item["link"]:
            continue

        logger.info("ترجمه: %s", item["title"][:70])
        try:
            translated = translate_news(
                title=item["title"],
                summary=item["summary"],
                source=item["source"],
            )
        except Exception as error:
            logger.error("ترجمه ناموفق: %s", error)
            continue

        try:
            send_message(format_post(item, translated))
        except Exception as error:
            logger.error("ارسال ناموفق: %s", error)
            continue

        # بلافاصله ذخیره کن تا با اجرای بعدی تکرار نشه
        mark_posted(item, history)
        save_history(history)

        posted += 1
        logger.info("ارسال شد: %s", translated["title"])

        time.sleep(TRANSLATE_GAP)

    logger.info("نتیجه این دوره: %s پست", posted)
    return posted


if __name__ == "__main__":
    run_once()
