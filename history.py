import json
import os

# مسیر مطلق، تا فرقی نکنه از کدوم پوشه اجرا بشه
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posted_history.json")


def normalize_link(url):
    """لینک رو یکدست می‌کنه تا نسخه‌های مختلف یه خبر یکی حساب بشن."""
    url = url.split("#")[0].split("?")[0].strip()
    return url.rstrip("/")


def normalize_title(title):
    """تیتر رو برای مقایسه یکدست می‌کنه."""
    return " ".join(title.lower().split())


def load_history():
    """تاریخچه پست‌ها رو می‌خونه (از فرمت قدیمی هم پشتیبانی می‌کنه)."""
    if not os.path.exists(HISTORY_FILE):
        return {"links": set(), "titles": set()}

    with open(HISTORY_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    # فرمت قدیمی: صرفاً لیستی از لینک‌ها
    if isinstance(data, list):
        return {
            "links": {normalize_link(x) for x in data},
            "titles": set(),
        }

    return {
        "links": set(data.get("links", [])),
        "titles": set(data.get("titles", [])),
    }


def save_history(history):
    """تاریخچه رو توی فایل ذخیره می‌کنه."""
    data = {
        "links": sorted(history["links"]),
        "titles": sorted(history["titles"]),
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def is_posted(item, history):
    """بررسی می‌کنه این خبر قبلاً پست شده یا نه."""
    return (
        normalize_link(item["link"]) in history["links"]
        or normalize_title(item["title"]) in history["titles"]
    )


def mark_posted(item, history):
    """خبر رو به عنوان پست‌شده ثبت می‌کنه."""
    history["links"].add(normalize_link(item["link"]))
    history["titles"].add(normalize_title(item["title"]))


def filter_new_news(news, history):
    """فقط خبرهایی که هنوز پست نشدن رو نگه می‌داره."""
    return [item for item in news if not is_posted(item, history)]
