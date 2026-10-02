import requests
import feedparser

from config.feeds import AI_FEEDS
from logger import get_logger

logger = get_logger("fetcher")

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_feed(url):
    """یک فید رو دانلود و خبرهاش رو برمی‌گردونه."""
    response = requests.get(url, timeout=15, headers=HEADERS)
    return feedparser.parse(response.content).entries


def get_latest_news(limit_per_feed=5):
    """از همه فیدها خبر جمع می‌کنه و یه لیست برمی‌گردونه."""
    all_news = []
    for url in AI_FEEDS:
        source = url.split("/")[2].replace("www.", "")
        try:
            entries = fetch_feed(url)
            logger.info("%s خبر از %s", len(entries), source)
            for entry in entries[:limit_per_feed]:
                all_news.append({
                    "title": (entry.get("title") or "").strip(),
                    "link": entry.get("link") or "",
                    "summary": entry.get("summary") or "",
                    "source": source,
                })
        except Exception as error:
            logger.warning("دریافت فید %s ناموفق: %s", source, type(error).__name__)
    return all_news
