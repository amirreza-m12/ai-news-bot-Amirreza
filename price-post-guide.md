# راهنمای پست قیمت دلار، طلا و نفت

> **وضعیت فعلی: غیرفعال.** زمان‌بندی خودکار برداشته شده ولی کد و workflow
> دست‌نخورده سر جاشون هست. کافیه یه بلوک `cron` رو دوباره باز کنی.

---

## ۱) چطور دوباره فعالش کنیم

فایل `.github/workflows/prices.yml` رو باز کن و این بلوک رو به `on:` اضافه کن:

```yaml
on:
  schedule:
    # ۹ صبح، ۱۲ ظهر، ۱۸ عصر، ۲۲ شب به وقت ایران
    - cron: "30 5,8,14,18 * * *"
  workflow_dispatch:
```

بعد فقط کافیه فایل رو کامیت و پوش کنی. بقیه‌اش آماده‌ست.

---

## ۲) فایل‌های مرتبط

| فایل | کارش |
|---|---|
| `prices.py` | دریافت سه قیمت + ساخت متن پست + ارسال به تلگرام |
| `.github/workflows/prices.yml` | زمان‌بندی اجرا روی گیتهاب‌اکشنز |
| `telegram_bot.py` | تابع `send_message()` که هر دو ربات استفاده می‌کنن |

اجرا:
- دستی: `python prices.py`
- از پنل گیتهاب: Actions → Post Prices → Run workflow

---

## ۳) منابع قیمت (و اینکه چرا اینا انتخاب شدن)

### 💵 دلار — `alanchand.com`

```
GET https://alanchand.com/currencies-price
```

جدول HTML داره. ردیف «دلار آمریکا» این ساختار رو داره:

```html
<td class="currName"> ... دلار آمریکا </td>
<td class="buyPrice text-center">۲۵۷,۳۰۰</td>
<td class="sellPrice text-center">۲۵۹,۹۰۰<span ...></span></td>
```

regex استفاده‌شده در `prices.py`:

```python
r"دلار آمریکا.*?"
r"<td class=\"buyPrice[^>]*>(.*?)</td>.*?"
r"<td class=\"sellPrice[^>]*>(.*?)</td>"   # با re.S
```

### 🥇 طلای ۱۸ عیار — `alanchand.com`

```
GET https://alanchand.com/gold-price
```

```html
<td>گرم طلای 18 عیار</td>
<td data-label="قیمت (تومان) + تغییرات" class="priceTd">۲۵,۹۸۲,۲۷۰ تومان<span ...>۱.۰۲%</span></td>
```

regex:

```python
r"<td>\s*گرم طلای\s*18\s*عیار\s*</td>\s*<td[^>]*>(.*?)</td>"   # با re.S
```

> اولین عددِ اون سلول، قیمت واقعی بازاره. (ستون‌های بعدی «قیمت واقعی» و «حباب» هستن
> که استفاده نمی‌کنیم.)

### 🛢 نفت برنت — Yahoo Finance

```
GET https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?interval=1d&range=1d
```

```python
price = response.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
```

`BZ=F` نماد **Brent** هست. برای WTI باید `CL=F` رو بگیری.

---

## ۴) منابعی که تست شدن و رد شدن

| منبع | نتیجه |
|---|---|
| **TradingView** `FX_IDC:USDIRR` | ✅ کار می‌کنه ولی **نرخ مرجع بین‌المللیه (۱,۷۴۱,۸۱۰ ریال = ۱۷۴,۱۸۱ تومان)**، نه قیمت واقعی بازار. قیمت واقعی حدود **۲۶۰ هزار تومان** بود → رد شد |
| **TradingView** `TVC:GOLD` | ✅ ۴۲۱۷ دلار هر اونس (قیمت جهانی، به تومان نیست) |
| **TradingView** نماد نفت | ❌ `TVC:UKOIL` پیدا نشد؛ فقط `NYMEX:CL1!` (WTI) بود |
| **Nobitex / Bitpin / Wallex** | ❌ از IP خارج ایران بلاک یا DNS fail |
| **Binance P2P IRR** | ❌ از IP آمریکا (گیتهاب) ارتباط قطع می‌شه |
| **tgju.org** | ❌ endpoint هاش404 بود |
| **bonbast.com** | ❌ قطع ارتباط |
| **alanchand.com** | ✅ هم از ایران، هم از IP گیتهاب جواب داد |

### نحوه فراخوانی TradingView (برای آینده)

```python
POST https://scanner.tradingview.com/forex/scan
{"symbols": {"tickers": ["FX_IDC:USDIRR"]}, "columns": ["close", "description"]}

POST https://scanner.tradingview.com/cfd/scan
{"symbols": {"tickers": ["TVC:GOLD"]}, "columns": ["close", "description"]}
```

---

## ۵) تریک‌های پیاده‌سازی

### ارقام فارسی ← لاتین

سایت‌های ایرانی با ارقام فارسی (`۲۵۷,۳۰۰`) جواب میدن:

```python
PERSIAN_TO_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
value = text.translate(PERSIAN_TO_ASCII)   # "۲۵۷,۳۰۰" → "257,300"
```

برای نمایش برعکس:

```python
ASCII_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
```

### تبدیل ساعت ایران ↔ UTC

ایران `UTC+3:30` هست و ساعت تابستانی نداره:

```python
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))
now = datetime.now(IRAN_TZ)
```

برای نوشتن `cron` (که به UTC هست):

| به وقت ایران | به وقت UTC |
|---|---|
| ۰۹:۰۰ | `30 5 * * *` |
| ۱۲:۰۰ | `30 8 * * *` |
| ۱۸:۰۰ | `30 14 * * *` |
| ۲۲:۰۰ | `30 18 * * *` |

فرمول: `UTC = ایران − ۳:۳۰`

---

## ۶) نتیجه تست (۲ آبان ۱۴۰۵ / ۲ اکتبر ۲۰۲۶)

هم محلی، هم روی گیتهاب‌اکشنز (IP آمریکا) جواب داد:

```
🕐 نرخ‌ها — ۱۶:۱۹

💵 دلار: خرید ۲۵۷,۳۰۰ | فروش ۲۵۹,۹۰۰ تومان
🥇 طلای ۱۸ عیار (هر گرم): ۲۵,۹۸۲,۲۷۰ تومان
🛢 نفت برنت (هر بشکه): ۹۹.۳۷ دلار
```

---

## ۷) نکات مهم

- **API رسمی alanchand**: `https://api.alanchand.com?type=currency&symbols=usd`
  نیاز به `Authorization: Bearer <TOKEN>` داره. رایگانش **فقط ۱ درخواست در ساعت**
  هست و توکن رو باید از ربات تلگرامشون گرفت (۳ روز تست). پلن ۶ ماهه ۶۵ تتر.
  ما چون روزی ۴ بار بیشتر نمی‌خوایم، **از HTML صفحه‌ها خوندیم** که رایگانه.
- **احتمال تغییر HTML**: اگه سایت تغییر کرد، regex ها باید به‌روز بشن. خطای
  `دریافت dollar ناموفق` توی لاگ یعنی این اتفاق افتاده.
- **روزهای تعطیل**: بازار ایران جمعه‌ها تعطیله ولی عددِ همون روز قبل رو نشون میده
  (سایت به‌صورت لحظه‌ای آپدیته، نه اینکه بیوفته).
- **نفت**: قیمت جهانیه و به دلاره؛ می‌شه با نرخ دلار تومانیش کرد:
  `بَرنت × نرخ فروش دلار`.

---

## ۸) نکته درباره زمان‌بند گیتهاب

زمان‌بند `schedule` گیتهاب برای این ریپو (تا تاریخ ۲ آبان ۱۴۰۵) **اجرا نمی‌شد** —
نه برای `*/20`، نه `* * * * *`، نه ساعتی. اجرای دستی (`workflow_dispatch`)
کاملاً سالم بود. قبل از فعال کردن دوباره این قیمت‌ها، باید این مشکل حل بشه.
