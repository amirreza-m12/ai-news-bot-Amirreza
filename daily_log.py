"""ثبت روزانه پست‌های ارسال‌شده — پایه ساخت خلاصه تک‌خطی پایان روز."""

import json
import os
from datetime import datetime, timedelta, timezone

from logger import get_logger

logger = get_logger("daily_log")

# ایران ساعت تابستانی ندارد؛ UTC+3:30 ثابت
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "daily")


def tehran_now():
    """حالا به وقت تهران."""
    return datetime.now(TEHRAN_TZ)


def day_key(moment=None):
    """تاریخ میلادی (YYYY-MM-DD) به وقت تهران."""
    return (moment or tehran_now()).strftime("%Y-%m-%d")


def previous_day(key):
    """یک روز قبل از یک تاریخ."""
    moment = datetime.strptime(key, "%Y-%m-%d")
    return (moment - timedelta(days=1)).strftime("%Y-%m-%d")


def log_path(key):
    return os.path.join(LOG_DIR, f"{key}.json")


def _empty(key):
    return {"date": key, "summary_sent": False, "items": []}


def load_day(key):
    """لاگ یک روز را می‌خواند؛ اگر نبود، لاگ خالی برمی‌گرداند."""
    path = log_path(key)
    if not os.path.exists(path):
        return _empty(key)
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError) as error:
        logger.warning("لاگ %s خوانده نشد: %s", key, type(error).__name__)
        return _empty(key)

    if not isinstance(data, dict):
        return _empty(key)
    data["date"] = key
    data.setdefault("items", [])
    data.setdefault("summary_sent", False)
    return data


def save_day(data):
    """لاگ یک روز را در فایل مخصوص خودش می‌نویسد."""
    os.makedirs(LOG_DIR, exist_ok=True)
    path = log_path(data["date"])
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    return path


def add_item(item, when=None):
    """یک پست ارسال‌شده را به لاگ همان روز اضافه می‌کند."""
    data = load_day(day_key(when))
    data["items"].append(item)
    save_day(data)
    return data
