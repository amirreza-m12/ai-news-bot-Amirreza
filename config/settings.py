import os

from dotenv import load_dotenv

from logger import get_logger

logger = get_logger("settings")

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# آیدی عمومی کانال که داخل همه پست‌ها درج می‌شود (بخش HTML نیست، لینک خودکار تلگرام)
CHANNEL_HANDLE = "@eyaineUUs"

# ساعت کاری ربات به وقت ایران: فقط بین این دو ساعت پست عادی می‌رود
POSTING_START_HOUR = 9
POSTING_END_HOUR = 23  # آخرین پست ساعت ۲۳:۱۷

# خبرهای قدیمی‌تر از این تاریخ اصلاً بررسی نمی‌شوند (به وقت تهران)
NEWS_CUTOFF_DATE = "2026-10-01"

# اگر هر دوی اینها پر شوند، درخواست‌ها به جای API مستقیم گوگل به این سرویس
# OpenAI-compatible (مثلاً 9Router) می‌رود. خالی باشد = مستقیم گوگل.
ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL", "").rstrip("/")
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "")


def use_router():
    """آیا باید از روتر (9Router و غیره) استفاده کرد؟"""
    return bool(ROUTER_BASE_URL and ROUTER_MODEL)


# آیدی عددی صاحب ربات — فقط اون می‌تونه دستور بده
TELEGRAM_OWNER_ID = os.getenv("TELEGRAM_OWNER_ID")


def detect_windows_proxy():
    """پروکسی فعال ویندوز (VPN) رو پیدا می‌کنه و به پایتون معرفی می‌کنه."""
    if os.name != "nt":  # فقط ویندوز
        return
    if os.getenv("HTTPS_PROXY"):
        return
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if enabled and server:
            proxy = f"http://{server}"
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
            logger.info("پروکسی ویندوز فعال شد: %s", proxy)
    except Exception as error:
        logger.debug("پروکسی ویندوز پیدا نشد: %s", type(error).__name__)


detect_windows_proxy()


def check_settings():
    """بررسی می‌کنه همه تنظیمات لازم پر شدن یا نه."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID:
        missing.append("TELEGRAM_CHANNEL_ID")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not TELEGRAM_OWNER_ID:
        missing.append("TELEGRAM_OWNER_ID")
    return missing
