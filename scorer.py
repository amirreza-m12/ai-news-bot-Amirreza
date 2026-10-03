"""رتبه‌بندی اخبار بر اساس اهمیت و دسته‌بندی — با یک فراخوانی مدل برای همه خبرها."""

from translator import call_gemini
from daily_log import day_key, load_day, previous_day
from logger import get_logger

logger = get_logger("scorer")

CATEGORIES = (
    "مدل‌های جدید",
    "پژوهش و تحقیقات",
    "محصولات و شرکت‌ها",
    "ابزارها و توسعه‌دهندگان",
    "قوانین و اخلاق",
    "کسب‌وکار و سرمایه‌گذاری",
    "کاربرد و زندگی روزمره",
)

DEFAULT_CATEGORY = "اخبار هوش مصنوعی"
DEFAULT_IMPORTANCE = 5

RANK_SYSTEM_PROMPT = """تو ویرایشگر خبر یک کانال تلگرامی فارسی‌زبان در حوزه هوش مصنوعی هستی.

به هر خبر «امتیاز اهمیت» از ۱ تا ۱۰ و یک «دسته» بده.

معیار اهمیت:
- ۱۰: بسیار مهم و تحول‌ساز (مدل جدید از شرکت بزرگ، تصمیم قانونی سرنوشت‌ساز، دستاورد پژوهشی بی‌سابقه)
- ۷ تا ۹: مهم و ارزشمند برای خواننده فنی (قابلیت جدید، همکاری جدی، تحلیل دقیق)
- ۴ تا ۶: متوسط (کاربردی ولی جزئی، خبر تکراری با زاویه نو)
- ۱ تا ۳: کم‌اهمیت (تبلیغاتی، حاشیه‌ای، شایعه، بی‌ربط)

دسته‌ها (دقیقاً یکی از همین‌ها):
«مدل‌های جدید»، «پژوهش و تحقیقات»، «محصولات و شرکت‌ها»، «ابزارها و توسعه‌دهندگان»، «قوانین و اخلاق»، «کسب‌وکار و سرمایه‌گذاری»، «کاربرد و زندگی روزمره»

تشخیص خبر تکراری (خیلی مهم):
- گاهی یک رویداد واحد را چند خبرگزاری مختلف پوشش می‌دهند. فقط باید یکی از آن‌ها پست شود.
- اگر خبر i درباره همان رویداد خبر j است (منبع یا زاویه فرق داشته باشد ولی رویداد یکی باشد)،
  «duplicate_of» خبری که باید حذف شود را شناسهٔ خبر نگه‌داشته‌شده بگذار.
- در هر گروه از یک رویداد دقیقاً یک خبر باید duplicate_of برابر null داشته باشد (ترجیحاً تازه‌ترین).
- اگر خبر i همان رویداد یکی از عناوین «قبلاً پست شده» در ابتدای پرامپت است، duplicate_of آن را -۱ بگذار.
- دو خبر کاملاً جداگانه را تکراری حساب نکن؛ فقط وقتی دقیقاً یک رویداد باشند.

خروجی باید دقیقاً یک آرایه JSON باشد:
- تعداد آیتم‌ها باید دقیقاً برابر تعداد اخبار ورودی باشد
- شناسه‌ها (id) باید دقیقاً همان‌هایی باشند که ورودی داده‌ای
- هیچ شناسه‌ای را جا نینداز و تکرار نکن

[
  {"id": 1, "category": "مدل‌های جدید", "importance": 9, "duplicate_of": null},
  {"id": 2, "category": "کسب‌وکار و سرمایه‌گذاری", "importance": 6, "duplicate_of": 1},
  {"id": 3, "category": "ابزارها و توسعه‌دهندگان", "importance": 7, "duplicate_of": -1}
]"""


def category_hashtag(category):
    """دسته رو تبدیل به هشتگ قابل جستجو می‌کنه: «مدل‌های جدید» ← «#مدل_های_جدید»"""
    text = (category or "").replace("\u200c", " ").strip()
    text = "_".join(text.split())
    return f"#{text}" if text else ""


def _clean_category(value):
    """دسته رو به یکی از دسته‌های معتبر نزدیک می‌کنه."""
    if not isinstance(value, str):
        return DEFAULT_CATEGORY
    value = value.strip()
    for category in CATEGORIES:
        if category in value or value in category:
            return category
    return DEFAULT_CATEGORY


def _clean_importance(value):
    """امتیاز رو به عدد صحیح ۱ تا ۱۰ تبدیل می‌کنه."""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return DEFAULT_IMPORTANCE
    return max(1, min(10, number))


def _clean_duplicate_of(value):
    """مقدار duplicate_of رو به شناسهٔ صحیح یا None تبدیل می‌کنه.

    -1 یعنی «این خبر قبلاً پست شده»، شناسهٔ مثبت یعنی «با این خبر هم‌رویداد است».
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def recent_posted_titles(days=2, limit=40):
    """تیتر پست‌های چند روز اخیر، از تازه‌ترین به قدیمی، برای تشخیص تکراری."""
    titles = []
    key = day_key()
    for _ in range(days):
        for item in load_day(key).get("items", []):
            title = (item.get("title") or "").strip()
            if title:
                titles.append(title)
        key = previous_day(key)
    return titles[:limit]


def drop_duplicate_stories(items):
    """خبرهای هم‌رویداد را حذف می‌کنه و فقط یکی از هر رویداد نگه می‌داره.

    باید بعد از rank_news صدا زده بشه، چون به مقدار duplicate_of نیاز داره.
    """
    if not items:
        return items

    count = len(items)
    refs = []
    for item in items:
        ref = item.get("duplicate_of")
        refs.append(ref if isinstance(ref, int) and not isinstance(ref, bool) else None)

    def root_of(start):
        """شناسهٔ خبری که باید نگه داشته بشه رو پیدا می‌کنه (زنجیره رو دنبال می‌کنه)."""
        path = []
        index = start
        while True:
            if index in path:  # مدل زنجیرهٔ حلقه‌ای ساخته؛ کوتاه‌ترین راه نگه می‌داریم
                return min(path)
            path.append(index)
            ref = refs[index]
            if ref is None:
                return index
            if ref == -1:  # قبلاً پست شده
                return None
            if not 0 <= ref < count:
                return index
            index = ref

    kept = []
    for index in range(count):
        if root_of(index) == index:
            kept.append(items[index])

    dropped = count - len(kept)
    if dropped:
        logger.info("%s خبر هم‌رویداد یا قبلاً پست‌شده کنار رفت", dropped)
    return kept


def rank_news(items, batch_size=20, recent_titles=()):
    """به همه اخبار امتیاز و دسته میده. آرایه‌ای با همان ترتیب برمی‌گردونه.

    هر آیتم خروجی: {"category": str, "importance": int, "duplicate_of": int|None}
    """
    if not items:
        return []

    scores = [None] * len(items)

    # دسته‌های ۲۰ تایی تا پرامپت خیلی بلند نشه
    for start in range(0, len(items), batch_size):
        chunk = items[start:start + batch_size]
        lines = []
        for offset, item in enumerate(chunk):
            item_id = offset + 1
            summary = (item.get("summary") or "")[:300]
            lines.append(
                f"{item_id}. [{item.get('source', '?')}] {item.get('title', '')}\n"
                f"   خلاصه: {summary}"
            )

        sections = []
        if recent_titles:
            posted_lines = "\n".join(f"- {title}" for title in recent_titles)
            sections.append(
                "عناوینی که قبلاً در کانال پست شده‌اند:\n" + posted_lines
            )
        sections.append(
            "اخبار زیر را امتیازدهی، دسته‌بندی و تشخیص تکراری کن:\n\n"
            + "\n".join(lines)
        )
        user_prompt = "\n\n".join(sections)

        try:
            result = call_gemini(RANK_SYSTEM_PROMPT, user_prompt, max_retries=2)
        except RuntimeError as error:
            logger.warning("امتیازدهی گروهی ناموفق؛ امتیاز پیش‌فرض می‌خوره: %s", error)
            continue

        if not isinstance(result, list):
            logger.warning("خروجی امتیازدهی لیست نبود؛ امتیاز پیش‌فرض می‌خوره")
            continue

        found = 0
        for entry in result:
            if not isinstance(entry, dict):
                continue
            try:
                item_id = int(entry.get("id"))
            except (TypeError, ValueError):
                continue

            index = start + item_id - 1
            if not 0 <= index < len(items):
                continue

            scores[index] = {
                "category": _clean_category(entry.get("category")),
                "importance": _clean_importance(entry.get("importance")),
                "duplicate_of": _clean_duplicate_of(entry.get("duplicate_of")),
            }
            found += 1

        logger.info("امتیازدهی گروهی: %s از %s خبر", found, len(chunk))

    # هر خبری که امتیاز نگرفت، امتیاز پیش‌فرض می‌گیره
    for index, item in enumerate(items):
        if scores[index] is None:
            scores[index] = {
                "category": DEFAULT_CATEGORY,
                "importance": DEFAULT_IMPORTANCE,
                "duplicate_of": None,
            }
        item["category"] = scores[index]["category"]
        item["importance"] = scores[index]["importance"]
        item["duplicate_of"] = scores[index]["duplicate_of"]

    return scores
