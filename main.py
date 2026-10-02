import threading
import time

from fetcher import get_latest_news
from history import load_history, save_history, filter_new_news, mark_posted
from scorer import rank_news, category_hashtag
from translator import translate_news
from telegram_bot import send_message
from logger import get_logger

logger = get_logger("main")

# تعداد پست در هر اجرا (یک اجرا در هر ساعت)
MAX_POSTS_PER_RUN = 5

# حداکثر خبری که در هر اجرا امتیازدهی می‌شه
SCORING_LIMIT = 15

# فاصله بین فراخوانی‌ها تا به سهمیه دقیقه‌ای نخوریم
TRANSLATE_GAP = 10  # ثانیه

# قفل: جلوی اجرای همزمان دو دوره رو می‌گیره
_run_lock = threading.Lock()

# امتیازی که از این بالاتر باشه، نشان «خبر ویژه» می‌گیره
SPECIAL_THRESHOLD = 8


def format_post(news, translated):
    """پست نهایی تلگرام رو می‌سازه."""
    tags = " ".join(translated["hashtags"])
    category = news.get("category", "")
    special = " ⭐" if news.get("importance", 0) >= SPECIAL_THRESHOLD else ""
    hashtag = category_hashtag(news.get("category", ""))
    header = f"{hashtag}{special}\n\n" if hashtag else ""

    return (
        f"{header}"
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

    news = get_latest_news(limit_per_feed=8)
    new_news = filter_new_news(news, history)
    new_news = [item for item in new_news if item["title"] and item["link"]]
    logger.info("کل اخبار: %s | خبر تازه: %s", len(news), len(new_news))

    if not new_news:
        logger.info("خبر تازه‌ای نبود")
        return 0

    # اولویت با تازه‌ترین خبرهاست تا اخبار قدیمی از دست نرن
    new_news.sort(key=lambda item: item["published"], reverse=True)
    candidates = new_news[:SCORING_LIMIT]

    # مرحله ۱: امتیازدهی و دسته‌بندی همه کاندیداها با یک فراخوانی
    logger.info("امتیازدهی %s خبر...", len(candidates))
    rank_news(candidates)
    candidates.sort(key=lambda item: item["importance"], reverse=True)
    logger.info(
        "بالاترین امتیاز: %s | دسته: %s",
        candidates[0]["importance"],
        candidates[0]["category"],
    )

    selected = candidates[:MAX_POSTS_PER_RUN]
    skipped = candidates[MAX_POSTS_PER_RUN:]

    # اخباری که انتخاب نشدن دیگه امتیاز نمی‌گیرن
    for item in skipped:
        mark_posted(item, history)
    if skipped:
        save_history(history)
        logger.info("%s خبر کم‌اهمیت کنار گذاشته شد", len(skipped))

    # مرحله ۲: ترجمه و ارسال مهم‌ترین‌ها
    posted = 0
    for item in selected:
        logger.info(
            "ترجمه (امتیاز %s، %s): %s",
            item["importance"],
            item["category"],
            item["title"][:60],
        )
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
