"""خلاصه تک‌خطی مهم‌ترین اخبار روز گذشته را برای کانال می‌فرستد.

این اسکریپت با زنگ جداگانه‌ای (ساعت ۰۰:۳۰ به وقت تهران) اجرا می‌شود.
"""

import sys

from config.settings import CHANNEL_HANDLE
from daily_log import day_key, load_day, previous_day, save_day
from logger import get_logger
from telegram_bot import send_message
from translator import call_gemini

logger = get_logger("summary")

# حد نصاب اهمیت برای «خبر مهم»؛ اگر هیچ‌کدام به این حد نرسیدند، مهم‌ترین‌ها انتخاب می‌شوند
MIN_IMPORTANCE = 8

# حداکثر تعداد خبری که داخل یک خط جا می‌شود
MAX_ITEMS = 10

SUMMARY_SYSTEM_PROMPT = """تو ویرایشگر خبر یک کانال تلگرامی فارسی‌زبان در حوزه هوش مصنوعی هستی.

فهرستی از مهم‌ترین اخبار یک روز را می‌گیری و باید دقیقاً یک خط خلاصه فارسی بنویسی.

قوانین الزامی:
- خروجی باید دقیقاً یک خط باشد و هیچ خط جدیدی (\\n) نداشته باشد.
- متن باید کاملاً روان و طبیعی و مثل نوشته یک ایرانی به نظر برسد.
- مهم‌ترین و جذاب‌ترین خبر را اول بیاور.
- اخبار را با « | » از هم جدا کن.
- هر خبر را در چند کلمه خلاصه کن؛ نه جمله کامل، نه توضیح اضافه.
- حداکثر ۴۰۰ کاراکتر.
- از نقل‌قول، ایموجی و شماره‌گذاری استفاده نکن.

خروجی باید دقیقاً با این ساختار JSON باشد:
{"line": "خلاصه تک‌خطی فارسی"}"""


def pick_items(items):
    """مهم‌ترین خبرها را برای خلاصه انتخاب می‌کند."""
    important = [x for x in items if x.get("importance", 0) >= MIN_IMPORTANCE]
    if not important:
        important = list(items)
    important.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return important[:MAX_ITEMS]


def build_prompt(day, items):
    lines = "\n".join(
        "- {title} ({category}، امتیاز {importance})".format(
            title=item.get("title", ""),
            category=item.get("category", ""),
            importance=item.get("importance", ""),
        )
        for item in items
    )
    return f"تاریخ میلادی: {day}\n\nمهم‌ترین اخبار آن روز:\n{lines}"


def format_summary(line):
    return (
        "📋 خلاصهٔ اخبار مهم روز\n\n"
        f"{line}\n\n"
        f"کانال: {CHANNEL_HANDLE}"
    )


def run(dry_run=False):
    """خلاصه دیروز را می‌سازد و می‌فرستد. تعداد پست‌های ارسال‌شده را برمی‌گرداند."""
    yesterday = previous_day(day_key())
    data = load_day(yesterday)

    if data.get("summary_sent"):
        logger.info("خلاصهٔ %s قبلاً ارسال شده بود", yesterday)
        return 0

    items = data.get("items", [])
    if not items:
        logger.info("روز %s هیچ پستی نداشت؛ خلاصه‌ای ارسال نشد", yesterday)
        return 0

    chosen = pick_items(items)
    logger.info(
        "ساخت خلاصهٔ روز %s از %s خبر (>%s مهم: %s)",
        yesterday, len(items), MIN_IMPORTANCE, len(chosen),
    )

    result = call_gemini(SUMMARY_SYSTEM_PROMPT, build_prompt(yesterday, chosen))
    line = ""
    if isinstance(result, dict):
        line = str(result.get("line", "")).strip()

    if not line:
        raise RuntimeError("مدل خلاصه‌ای برنگرداند")

    message = format_summary(line)

    if dry_run:
        print(message)
        return 1

    send_message(message)
    data["summary_sent"] = True
    save_day(data)
    logger.info("خلاصهٔ روز %s ارسال شد", yesterday)
    return 1


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
