import re
from playwright.sync_api import sync_playwright

from scrapers.utils import parse_price, normalize_text


PRICE_RE = re.compile(
    r"(?:₺\s*)?\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:TL|₺)?|"
    r"\d+,\d{2}\s*(?:TL|₺)?|"
    r"\d+\s*(?:TL|₺)",
    re.IGNORECASE,
)

NAME_KEYS = [
    "name",
    "title",
    "productName",
    "displayName",
]

PRICE_KEYS = [
    "price",
    "priceText",
    "displayPrice",
    "finalPrice",
    "sellingPrice",
    "discountedPrice",
    "discountPrice",
    "amount",
    "value",
]

ORIGINAL_PRICE_KEYS = [
    "originalPrice",
    "oldPrice",
    "strikeThroughPrice",
    "listPrice",
    "basePrice",
]

BAD_NAME_WORDS = [
    "sepet",
    "minimum",
    "teslimat",
    "kampanya",
    "indirim",
    "puan",
    "yorum",
    "dakika",
    "tl",
    "ara",
    "filtre",
    "sırala",
    "şu anda",
    "su anda",
    "temsili",
    "cookie",
    "çerez",
]


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)

    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def get_value_by_keys(obj, keys):
    lower_map = {str(k).lower(): v for k, v in obj.items()}

    for key in keys:
        value = lower_map.get(key.lower())

        if value is not None:
            return value

    return None


def parse_any_price(value):
    if value is None:
        return None

    if isinstance(value, dict):
        for key in PRICE_KEYS + ORIGINAL_PRICE_KEYS:
            if key in value:
                parsed = parse_any_price(value.get(key))
                if parsed is not None:
                    return parsed

        return None

    if isinstance(value, (int, float)):
        price = float(value)

        # Bazı API'ler fiyatı kuruş olarak gönderebilir: 24990 -> 249.90
        if price > 5000:
            price = price / 100

        return price

    return parse_price(value)


def is_valid_name_candidate(text):
    if not text:
        return False

    text = str(text).strip()
    lowered = normalize_text(text)

    if len(text) < 2 or len(text) > 120:
        return False

    if PRICE_RE.search(text):
        return False

    if any(word in lowered for word in BAD_NAME_WORDS):
        return False

    return True


def parse_product_object(obj):
    name = get_value_by_keys(obj, NAME_KEYS)

    if not is_valid_name_candidate(name):
        return None

    price_value = get_value_by_keys(obj, PRICE_KEYS)
    original_price_value = get_value_by_keys(obj, ORIGINAL_PRICE_KEYS)

    price = parse_any_price(price_value)
    original_price = parse_any_price(original_price_value)

    if price is None:
        return None

    if price <= 0 or price > 5000:
        return None

    if original_price is None:
        original_price = price

    if original_price < price:
        original_price = price

    return {
        "name": str(name).strip(),
        "price": f"{price:.2f} TL",
        "original_price": f"{original_price:.2f} TL",
    }


def extract_items_from_json_payloads(payloads):
    items = []
    seen = set()

    for payload in payloads:
        for obj in walk(payload):
            if not isinstance(obj, dict):
                continue

            item = parse_product_object(obj)

            if not item:
                continue

            key = (
                normalize_text(item["name"]),
                item["price"],
                item["original_price"],
            )

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

    return items


def extract_items_from_page_text(text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    items = []
    seen = set()

    for index, line in enumerate(lines):
        price_matches = PRICE_RE.findall(line)

        if not price_matches:
            continue

        prices = [
            parse_price(price_text)
            for price_text in price_matches
        ]
        prices = [price for price in prices if price is not None]

        if not prices:
            continue

        item_name = None

        for back_index in range(index - 1, max(index - 7, -1), -1):
            candidate = lines[back_index]

            if is_valid_name_candidate(candidate):
                item_name = candidate
                break

        if not item_name:
            continue

        current_price = min(prices)
        original_price = max(prices) if len(prices) > 1 else current_price

        if current_price <= 0 or current_price > 5000:
            continue

        key = (normalize_text(item_name), current_price)

        if key in seen:
            continue

        seen.add(key)

        items.append(
            {
                "name": item_name,
                "price": f"{current_price:.2f} TL",
                "original_price": f"{original_price:.2f} TL",
            }
        )

    return items


def extract_restaurant_name(page):
    selectors = ["h1", "[class*='restaurant']", "[class*='Restaurant']"]

    for selector in selectors:
        locator = page.locator(selector)

        if locator.count() == 0:
            continue

        for index in range(min(locator.count(), 5)):
            text = locator.nth(index).inner_text(timeout=2000).strip()

            if text and len(text) < 80:
                return text

    title = page.title()
    return title.split("|")[0].strip() if title else "Bilinmeyen Restoran"


def scroll_page(page):
    previous_height = 0

    for _ in range(8):
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(1200)

        current_height = page.evaluate("document.body.scrollHeight")

        if current_height == previous_height:
            break

        previous_height = current_height


def scrape_trendyol_url(page, url):
    print(f"Trendyol sayfası açılıyor: {url}")

    captured_json_payloads = []

    def on_response(response):
        response_url = response.url
        content_type = response.headers.get("content-type", "")

        if "application/json" not in content_type:
            return

        if "tgoyemek" not in response_url and "tgoapis" not in response_url:
            return

        try:
            captured_json_payloads.append(response.json())
        except Exception:
            return

    page.on("response", on_response)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        scroll_page(page)
        page.wait_for_timeout(2000)

        restaurant_name = extract_restaurant_name(page)

        # 1) Önce JSON/API response'larından ürün çıkar
        items = extract_items_from_json_payloads(captured_json_payloads)

        if items:
            print(f"{restaurant_name}: {len(items)} ürün JSON/API response üzerinden bulundu.")
        else:
            # 2) JSON'dan ürün bulunamazsa eski yöntem fallback
            body_text = page.locator("body").inner_text(timeout=10000)
            items = extract_items_from_page_text(body_text)
            print(f"{restaurant_name}: {len(items)} ürün sayfa metni fallback ile bulundu.")

        return {
            "restaurant_name": restaurant_name,
            "restaurant_rating": None,
            "restaurant_url": url,
            "items": items,
        }

    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


def scrape_trendyol_urls(urls, headless=False):
    results = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="tr-TR",
        )
        page = context.new_page()

        for url in urls:
            try:
                result = scrape_trendyol_url(page, url)
                results.append(result)
            except Exception as exc:
                print(f"Hata: {url} -> {exc}")

        browser.close()

    return results
