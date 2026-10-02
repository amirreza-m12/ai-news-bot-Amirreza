"""رتبه‌بندی اخبار بر اساس اهمیت و دسته‌بندی — با یک فراخوانی مدل برای همه خبرها."""

from translator import call_gemini
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

خروجی باید دقیقاً یک آرایه JSON باشد:
- تعداد آیتم‌ها باید دقیقاً برابر تعداد اخبار ورودی باشد
- شناسه‌ها (id) باید دقیقاً همان‌هایی باشند که ورودی داده‌ای
- هیچ شناسه‌ای را جا نینداز و تکرار نکن

[
  {"id": 1, "category": "مدل‌های جدید", "importance": 9},
  {"id": 2, "category": "کاربرد و زندگی روزمره", "importance": 4}
]"""


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


def rank_news(items, batch_size=20):
    """به همه اخبار امتیاز و دسته میده. آرایه‌ای با همان ترتیب برمی‌گردونه.

    هر آیتم خروجی: {"category": str, "importance": int}
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

        user_prompt = (
            "اخبار زیر را امتیازدهی و دسته‌بندی کن:\n\n" + "\n".join(lines)
        )

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
            }
            found += 1

        logger.info("امتیازدهی گروهی: %s از %s خبر", found, len(chunk))

    # هر خبری که امتیاز نگرفت، امتیاز پیش‌فرض می‌گیره
    for index, item in enumerate(items):
        if scores[index] is None:
            scores[index] = {
                "category": DEFAULT_CATEGORY,
                "importance": DEFAULT_IMPORTANCE,
            }
        item["category"] = scores[index]["category"]
        item["importance"] = scores[index]["importance"]

    return scores
