"""دریافت قیمت دلار، طلا و نفت و پست کردن آن در کانال تلگرام."""

import re
from datetime import datetime, timedelta, timezone

import requests

from telegram_bot import send_message
from logger import get_logger

logger = get_logger("prices")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}

CURRENCY_URL = "https://alanchand.com/currencies-price"
GOLD_URL = "https://alanchand.com/gold-price"
BRENT_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
    "?interval=1d&range=1d"
)

# ایران ساعت ذخیره تابستانی نداره؛ همیشه UTC+3:30
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# تبدیل ارقام فارسی به لاتین
PERSIAN_TO_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ASCII_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _number(text):
    """اولین عدد داخل یه متن رو برمی‌گردونه (ارقام فارسی و لاتین رو هر دو می‌فهمه)."""
    if not text:
        return None
    cleaned = text.translate(PERSIAN_TO_ASCII)
    match = re.search(r"\d[\d,]*", cleaned)
    if not match:
        return None
    digits = match.group(0).replace(",", "")
    try:
        return float(digits)
    except ValueError:
        return None


def _fetch(url):
    """یه صفحه رو دانلود می‌کنه."""
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def get_dollar():
    """قیمت خرید و فروش دلار در بازار آزاد (تومان)."""
    html = _fetch(CURRENCY_URL)
    match = re.search(
        r"دلار آمریکا.*?"
        r"<td class=\"buyPrice[^>]*>(.*?)</td>.*?"
        r"<td class=\"sellPrice[^>]*>(.*?)</td>",
        html,
        re.S,
    )
    if not match:
        raise RuntimeError("قیمت دلار در صفحه پیدا نشد")
    buy, sell = _number(match.group(1)), _number(match.group(2))
    if not buy or not sell:
        raise RuntimeError("قیمت دلار قابل خواندن نبود")
    return buy, sell


def get_gold_18():
    """قیمت یک گرم طلای ۱۸ عیار در بازار آزاد (تومان)."""
    html = _fetch(GOLD_URL)
    match = re.search(
        r"<td>\s*گرم طلای\s*18\s*عیار\s*</td>\s*<td[^>]*>(.*?)</td>",
        html,
        re.S,
    )
    if not match:
        raise RuntimeError("قیمت طلای ۱۸ عیار در صفحه پیدا نشد")
    price = _number(match.group(1))
    if not price:
        raise RuntimeError("قیمت طلا قابل خواندن نبود")
    return price


def get_brent():
    """قیمت نفت برنت (دلار برای هر بشکه)."""
    response = requests.get(BRENT_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    meta = response.json()["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    if not price:
        raise RuntimeError("قیمت نفت برنت پیدا نشد")
    return float(price)


def fa(value, decimals=0):
    """عدد رو با ارقام فارسی و جداکننده هزارگان نشون میده."""
    return f"{value:,.{decimals}f}".translate(ASCII_TO_PERSIAN)


def build_post(dollar=None, gold=None, brent=None, now=None):
    """متن پست قیمت‌ها رو می‌سازه. هر کدوم نبود، از پست حذف می‌شه."""
    now = now or datetime.now(IRAN_TZ)
    lines = [f"🕐 نرخ‌ها — {now.strftime('%H:%M')}", ""]

    if dollar:
        lines.append(f"💵 دلار: خرید {fa(dollar[0])} | فروش {fa(dollar[1])} تومان")
    if gold:
        lines.append(f"🥇 طلای ۱۸ عیار (هر گرم): {fa(gold)} تومان")
    if brent:
        lines.append(f"🛢 نفت برنت (هر بشکه): {fa(brent, 2)} دلار")

    if not (dollar or gold or brent):
        return None
    return "\n".join(lines)


def collect_prices():
    """هر سه قیمت رو می‌گیره؛ اگه یکی خطا داد بقیه رو نگه می‌داره."""
    prices = {"dollar": None, "gold": None, "brent": None}

    for key, fetcher in (
        ("dollar", get_dollar),
        ("gold", get_gold_18),
        ("brent", get_brent),
    ):
        try:
            prices[key] = fetcher()
            logger.info("%s: %s", key, prices[key])
        except Exception as error:
            logger.error("دریافت %s ناموفق: %s", key, error)

    return prices


def run_once():
    prices = collect_prices()
    text = build_post(**prices)
    if not text:
        logger.error("هیچ قیمتی در دسترس نبود؛ پستی ارسال نشد")
        return 0

    logger.info("پست قیمت‌ها:\n%s", text)
    send_message(text)
    return 1


if __name__ == "__main__":
    run_once()
