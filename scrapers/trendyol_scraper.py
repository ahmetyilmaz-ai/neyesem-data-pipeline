import re
from playwright.sync_api import sync_playwright

from scrapers.utils import parse_price, normalize_text


PRICE_RE = re.compile(
    r"(?:₺\s*)?\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:TL|₺)?|"
    r"\d+,\d{2}\s*(?:TL|₺)?|"
    r"\d+\s*(?:TL|₺)",
    re.IGNORECASE,
)


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
]


def is_valid_name_candidate(text):
    if not text:
        return False

    text = text.strip()
    lowered = normalize_text(text)

    if len(text) < 3 or len(text) > 100:
        return False

    if PRICE_RE.search(text):
        return False

    if any(word in lowered for word in BAD_NAME_WORDS):
        return False

    return True


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

    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    print("Sayfa açıldı. Cookie/konum ekranı varsa tarayıcıda hallet.")
    input("Hazır olunca Enter'a bas: ")

    scroll_page(page)

    restaurant_name = extract_restaurant_name(page)
    body_text = page.locator("body").inner_text(timeout=10000)
    items = extract_items_from_page_text(body_text)

    print(f"{restaurant_name}: {len(items)} ürün bulundu.")

    return {
        "restaurant_name": restaurant_name,
        "restaurant_rating": None,
        "restaurant_url": url,
        "items": items,
    }


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