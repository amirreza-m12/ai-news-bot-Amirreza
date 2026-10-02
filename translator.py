import json
import time

import requests

from config.settings import (
    GEMINI_API_KEY,
    ROUTER_API_KEY,
    ROUTER_BASE_URL,
    ROUTER_MODEL,
    use_router,
)
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

# خطاهایی که با چند بار تلاش مجدد درست میشن (خطای روزانه عمداً توش نیست)
RETRYABLE = ("high demand", "overloaded", "rate limit", "try again")

TRANSLATE_SYSTEM_PROMPT = """تو یک خبرنگار حرفه‌ای ایرانی هستی که اخبار هوش مصنوعی را برای کانال تلگرامی فارسی‌زبان آماده می‌کنی.

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


def call_gemini(system_prompt, user_prompt, max_retries=2):
    """یه درخواست به مدل می‌فرسته؛ اگر روتر تنظیم شده باشد از آن استفاده می‌کند."""
    if use_router():
        return _call_router(system_prompt, user_prompt, max_retries)

    last_error = None
    for model in MODELS:
        try:
            return _call_model(model, system_prompt, user_prompt, max_retries)
        except RuntimeError as error:
            last_error = error
            logger.warning("مدل بعدی (%s): %s", model, error)
            continue
    raise RuntimeError(f"هیچ مدلی جواب نداد — آخرین خطا: {last_error}")


def parse_json_text(text):
    """JSON را از خروجی مدل بیرون می‌کشد؛ با متن اضافه یا بلوک کد هم کنار می‌آید."""
    text = (text or "").strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise json.JSONDecodeError("no json", text, 0)

    start = min(starts)
    end = text.rfind("}" if text[start] == "{" else "]")
    if end <= start:
        raise json.JSONDecodeError("no json", text, start)
    return json.loads(text[start:end + 1])


def _call_router(system_prompt, user_prompt, max_retries=2):
    """درخواست به یک سرویس OpenAI-compatible مثل 9Router."""
    url = f"{ROUTER_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if ROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {ROUTER_API_KEY}"

    payload = {
        "model": ROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
        except requests.RequestException as error:
            wait = 2**attempt
            logger.warning(
                "روتر تلاش %s/%s قطع ارتباط، %ss صبر (%s)",
                attempt, max_retries, wait, type(error).__name__,
            )
            time.sleep(wait)
            continue

        if response.status_code in (401, 403):
            raise RuntimeError(f"روتر دسترسی را رد کرد (HTTP {response.status_code})")

        try:
            data = response.json()
        except ValueError:
            data = None

        if data is None or "error" in data:
            message = ""
            if data is not None and isinstance(data.get("error"), dict):
                message = data["error"].get("message", "")
            elif data is not None:
                message = str(data.get("error", ""))

            retryable = response.status_code in (408, 429, 500, 502, 503, 504) or any(
                x in message.lower() for x in RETRYABLE
            )
            if retryable:
                wait = 2**attempt
                logger.warning(
                    "روتر تلاش %s/%s ناموفق (HTTP %s)، %ss صبر",
                    attempt, max_retries, response.status_code, wait,
                )
                time.sleep(wait)
                continue

            raise RuntimeError(
                f"خطای روتر ({ROUTER_MODEL}): {message or f'HTTP {response.status_code}'}"
            )

        try:
            text = data["choices"][0]["message"]["content"]
            return parse_json_text(text)
        except (KeyError, IndexError, json.JSONDecodeError) as error:
            raise RuntimeError(f"خروجی روتر قابل فهم نبود: {type(error).__name__}")

    raise RuntimeError(f"روتر ({ROUTER_MODEL}) بعد از {max_retries} تلاش جواب نداد")


def _call_model(model, system_prompt, user_prompt, max_retries=2):
    """به یه مدل خاص وصل می‌شه؛ اگه خطا داد چند بار دوباره تلاش می‌کنه."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/{model}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
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
            return parse_json_text(text)
        except (KeyError, IndexError, json.JSONDecodeError) as error:
            raise RuntimeError(f"خروجی مدل قابل فهم نبود: {type(error).__name__}")

    raise RuntimeError(f"مدل {model} بعد از {max_retries} تلاش جواب نداد")


def translate_news(title, summary, source):
    """خبر انگلیسی رو به پست فارسی تبدیل می‌کنه."""
    user_prompt = f"منبع: {source}\n\nتیتر خبر:\n{title}\n\nمتن خبر:\n{summary}"
    return call_gemini(TRANSLATE_SYSTEM_PROMPT, user_prompt)
