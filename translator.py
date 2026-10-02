import json
import time

import requests

from config.settings import GEMINI_API_KEY
from logger import get_logger

logger = get_logger("translator")

# ترتیب اهمیت داره: اول مدل‌های سبک و پرحجم (سهمیه بیشتر و خطای کمتر)
MODELS = (
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
)

SYSTEM_PROMPT = """تو یک خبرنگار حرفه‌ای ایرانی هستی که اخبار هوش مصنوعی را برای کانال تلگرامی فارسی‌زبان آماده می‌کنی.

قوانین الزامی:
- ترجمه باید کاملاً روان، طبیعی و بدون هیچ‌گونه لغزش دستوری باشد.
- فعل و فاعل باید سر جای خودشان باشند و متن باید مثل نوشته یک ایرانی به نظر برسد.
- از معادل‌های فارسی رایج استفاده کن (مثلاً «هوش مصنوعی» به جای artificial intelligence).
- اصطلاحات فنی معروف را همان‌طور که در فارسی رایج است بنویس.
- هرگز متن انگلیسی را عیناً کپی نکن.

خروجی باید دقیقاً با این ساختار JSON باشد:
{
  "title": "تیتر جذاب و کوتاه فارسی (حداکثر ۶۰ کاراکتر)",
  "summary": "خلاصه کامل و روان فارسی در ۳ تا ۵ جمله که مهم‌ترین نکات خبر را پوشش دهد",
  "hashtags": ["سه تا هشتگ فارسی یا انگلیسی مرتبط"]
}"""

# خطاهایی که با چند بار تلاش مجدد درست میشن (خطای روزانه عمداً توش نیست)
RETRYABLE = ("high demand", "overloaded", "rate limit", "try again")


def _call_model(model, user_prompt, max_retries=2):
    """به یه مدل خاص وصل می‌شه؛ اگه خطا داد چند بار دوباره تلاش می‌کنه."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/{model}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                params={"key": GEMINI_API_KEY},
                json=payload,
                timeout=60,
            )
        except requests.RequestException as error:
            wait = 2**attempt
            logger.warning(
                "%s تلاش %s/%s قطع ارتباط، %ss صبر (%s)",
                model, attempt, max_retries, wait, type(error).__name__,
            )
            time.sleep(wait)
            continue

        # پاسخ غیر JSON (مثلاً صفحه خطای 403 گوگل)
        try:
            data = response.json()
        except ValueError:
            data = None

        if data is None or "error" in data:
            message = ""
            if data is not None:
                message = data["error"].get("message", "")

            retryable = (
                response.status_code in (429, 500, 503)
                or any(x in message.lower() for x in RETRYABLE)
            )
            if retryable:
                wait = 2**attempt
                logger.warning(
                    "%s تلاش %s/%s ناموفق (HTTP %s)، %ss صبر",
                    model, attempt, max_retries, response.status_code, wait,
                )
                time.sleep(wait)
                continue

            if message:
                raise RuntimeError(f"خطای Gemini: {message}")
            raise RuntimeError(
                f"گوگل جواب نامعتبر داد (HTTP {response.status_code}) — "
                "احتمالاً IP مسدود شده"
            )

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as error:
            raise RuntimeError(f"خروجی مدل قابل فهم نبود: {type(error).__name__}")

    raise RuntimeError(f"مدل {model} بعد از {max_retries} تلاش جواب نداد")


def translate_news(title, summary, source):
    """خبر انگلیسی رو به پست فارسی تبدیل می‌کنه."""
    user_prompt = f"منبع: {source}\n\nتیتر خبر:\n{title}\n\nمتن خبر:\n{summary}"

    last_error = None
    for model in MODELS:
        try:
            return _call_model(model, user_prompt)
        except RuntimeError as error:
            last_error = error
            logger.warning("مدل بعدی (%s): %s", model, error)
            continue

    raise RuntimeError(f"هیچ مدلی جواب نداد — آخرین خطا: {last_error}")
