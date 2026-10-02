from datetime import datetime

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_OWNER_ID,
    check_settings,
)
from main import run_once
from logger import get_logger

logger = get_logger("listener")

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
JOB_ID = "hourly_news"
POLL_TIMEOUT = 30  # ثانیه انتظار تلگرام برای پیام جدید

scheduler = BackgroundScheduler(timezone="Asia/Tehran")


def safe_run():
    try:
        run_once()
    except Exception:
        logger.exception("خطا در اجرای دوره‌ای")


def is_active():
    return scheduler.get_job(JOB_ID) is not None


def send(text, chat_id):
    """پیامی به چت فرستنده دستور برمی‌گردونه."""
    requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=30,
    )


def handle_command(command, chat_id):
    """دستور کاربر رو اجرا می‌کنه."""

    if command in ("/start", "/on"):
        if is_active():
            send("✅ از قبل فعال است.", chat_id)
            return
        scheduler.add_job(
            safe_run,
            trigger=IntervalTrigger(hours=1),
            id=JOB_ID,
            next_run_time=datetime.now(),
            max_instances=1,
            coalesce=True,
        )
        send(
            "🟢 <b>ربات فعال شد</b>\n"
            "همین الان یک دسته پست می‌فرستد و بعد هر ساعت تکرار می‌کند.\n\n"
            "دستورات:\n"
            "/stop — توقف\n"
            "/now — ارسال فوری\n"
            "/status — وضعیت",
            chat_id,
        )

    elif command == "/stop":
        if not is_active():
            send("⏸ از قبل متوقف است.", chat_id)
            return
        scheduler.remove_job(JOB_ID)
        send("🔴 <b>ربات متوقف شد.</b> دیگر پست خودکار نمی‌فرستد.", chat_id)

    elif command == "/now":
        if is_active():
            send("⏳ دوره ساعتی فعال است و خودش پست می‌فرستد. "
                 "برای اجرای دستی اول /stop بزن.", chat_id)
            return
        send("⏳ در حال جمع‌آوری و ارسال...", chat_id)
        posted = run_once()
        if posted:
            send(f"✅ {posted} پست ارسال شد.", chat_id)
        else:
            send("ℹ️ پست تازه‌ای برای ارسال نبود "
                 "(یا دوره دیگه‌ای در جریان بود).", chat_id)

    elif command == "/status":
        state = "🟢 فعال (هر ساعت)" if is_active() else "🔴 متوقف"
        send(f"وضعیت: {state}", chat_id)

    else:
        send(
            "دستور ناشناخته. دستورات:\n"
            "/start — فعال‌سازی\n"
            "/stop — توقف\n"
            "/now — ارسال فوری\n"
            "/status — وضعیت",
            chat_id,
        )


def process_update(update):
    """یه آپدیت دریافتی از تلگرام رو پردازش می‌کنه."""
    message = update.get("message")
    if not message:
        return

    sender_id = str(message.get("from", {}).get("id", ""))
    chat_id = message.get("chat", {}).get("id", "")
    text = (message.get("text") or "").strip()

    # امنیت: فقط صاحب ربات و فقط توی چت خصوصی
    if sender_id != TELEGRAM_OWNER_ID:
        logger.warning("دستور از کاربر غریبه نادیده گرفته شد: %s", sender_id)
        return
    if message.get("chat", {}).get("type") != "private":
        return

    logger.info("دستور دریافت شد: %s", text)
    handle_command(text.split()[0].lower() if text else "", chat_id)


def listen():
    """حلقه اصلی: گوش دادن به پیام‌های تلگرام."""
    offset = 0
    logger.info("گوش‌دهنده تلگرام روشن شد. منتظر دستور...")

    while True:
        try:
            response = requests.get(
                f"{API}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": ["message"],
                },
                timeout=POLL_TIMEOUT + 15,
            )
            data = response.json()
            if not data.get("ok"):
                logger.error("خطای getUpdates: %s", data.get("description"))
                continue

            for update in data["result"]:
                offset = update["update_id"] + 1
                process_update(update)

        except requests.RequestException as error:
            logger.warning("قطعی ارتباط (%s)، ۵ ثانیه بعد دوباره...", type(error).__name__)
            import time

            time.sleep(5)
        except Exception:
            logger.exception("خطای غیرمنتظره در حلقه گوش‌دهی")


def start():
    missing = check_settings()
    if missing:
        logger.error("تنظیمات ناقصه: %s — فایل .env رو کامل کن", ", ".join(missing))
        return

    scheduler.start()
    logger.info("ربات آماده است. با /start از تلگرام فعالش کن.")
    listen()


if __name__ == "__main__":
    start()
