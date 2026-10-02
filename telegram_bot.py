import requests

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from logger import get_logger

logger = get_logger("telegram")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text):
    """یه پیام متنی به کانال می‌فرسته."""
    response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"خطای تلگرام: {data.get('description')}")
    return data["result"]["message_id"]


if __name__ == "__main__":
    logger.info("پیام تست ارسال شد، شماره: %s", send_message("✅ اتصال برقرار است"))
