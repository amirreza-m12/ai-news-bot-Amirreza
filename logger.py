import logging
import os
from logging.handlers import RotatingFileHandler

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

# مسیر مطلق، تا فرقی نکنه از کدوم پوشه اجرا بشه
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# فایل لاگ با حداکثر ۵ مگابایت؛ اگه پر شد، خودش قدیمی‌ها رو کنار می‌زنه
file_handler = RotatingFileHandler(
    os.path.join(BASE_DIR, "bot.log"),
    maxBytes=5_000_000,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(FORMAT))

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


def get_logger(name):
    """لاگر ماژول می‌سازه."""
    return logging.getLogger(name)
