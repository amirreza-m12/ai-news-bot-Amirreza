import json
import time

import requests

from config.settings import GEMINI_API_KEY
from logger import get_logger

logger = get_logger("translator")

MODELS = ("gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.8-flash")

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


def _call_model(model, user_prompt, max_retries=2):
    """به یه مدل خاص وصل می‌شه؛ اگه خطا داد چند بار دوباره تلاش می‌کنه."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
            data = response.json()

            if "error" in data:
                message = data["error"]["message"]
                if "high demand" in message or response.status_code == 429:
                    raise ConnectionError(message)
                raise RuntimeError(f"خطای Gemini: {message}")

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)

        except (ConnectionError, requests.RequestException) as error:
            wait = 2**attempt
            logger.warning(
                "%s تلاش %s/%s ناموفق، %s ثانیه صبر",
                model, attempt, max_retries, wait,
            )
            time.sleep(wait)

    raise RuntimeError(f"مدل {model} بعد از {max_retries} تلاش جواب نداد")


def translate_news(title, summary, source):
    """خبر انگلیسی رو به پست فارسی تبدیل می‌کنه."""
    user_prompt = f"منبع: {source}\n\nتیتر خبر:\n{title}\n\nمتن خبر:\n{summary}"

    for model in MODELS:
        try:
            return _call_model(model, user_prompt)
        except RuntimeError as error:
            logger.warning("مدل بعدی: %s", error)
            continue

    raise RuntimeError("هیچ مدلی در دسترس نبود")
