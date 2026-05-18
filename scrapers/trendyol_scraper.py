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
    "restoran",
    "anasayfa",
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

        # Bazı API'ler kuruş gönderir: 24990 -> 249.90
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
    """
    JSON/API response içinden ürün objesi yakalamaya çalışır.
    Restoran kartlarını ürün sanmamak için minBasketPrice gibi alanları fiyat kabul etmiyoruz.
    """

    name = get_value_by_keys(obj, NAME_KEYS)

    if not is_valid_name_candidate(name):
        return None

    # Restoran kartlarında gelen minBasketPrice, deliveryFee gibi alanları ürün fiyatı sanma.
    lowered_keys = {str(k).lower() for k in obj.keys()}
    restaurant_only_keys = {
        "minbasketprice",
        "deliveryfee",
        "averagedeliveryinterval",
        "kitchen",
        "kitchennameids",
        "rating",
        "ratingtext",
    }

    if lowered_keys.intersection(restaurant_only_keys) and not lowered_keys.intersection(
        {"price", "pricetext", "displayprice", "finalprice", "sellingprice", "discountedprice"}
    ):
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
        "source": "json",
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


def extract_items_from_dom_cards(page):
    """
    Text parser'dan daha kaliteli fallback.
    Fiyat ile ürün adını tüm sayfa metninden değil, aynı DOM kartının içinden eşleştirir.
    """

    return page.evaluate(
        r"""
        () => {
            const priceRegex = /(?:₺\s*)?\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:TL|₺)?|\d+,\d{2}\s*(?:TL|₺)?|\d+\s*(?:TL|₺)/gi;

            const badWords = [
                "sepet",
                "minimum",
                "teslimat",
                "kampanya",
                "indirim",
                "puan",
                "yorum",
                "dakika",
                "ara",
                "filtre",
                "sırala",
                "şu anda",
                "temsili",
                "cookie",
                "çerez",
                "restoran"
            ];

            function normalizeText(value) {
                return String(value || "")
                    .toLowerCase()
                    .replaceAll("ı", "i")
                    .replaceAll("ğ", "g")
                    .replaceAll("ü", "u")
                    .replaceAll("ş", "s")
                    .replaceAll("ö", "o")
                    .replaceAll("ç", "c")
                    .replace(/[^a-z0-9\s]/g, " ")
                    .replace(/\s+/g, " ")
                    .trim();
            }

            function parsePrice(value) {
                if (!value) return null;

                let text = String(value)
                    .replaceAll("₺", "")
                    .replaceAll("TL", "")
                    .trim();

                text = text.replace(/[^0-9,.]/g, "");

                if (!text) return null;

                if (text.includes(",")) {
                    text = text.replaceAll(".", "").replace(",", ".");
                }

                const number = Number.parseFloat(text);

                if (!Number.isFinite(number)) return null;
                if (number <= 0 || number > 5000) return null;

                return number;
            }

            function isValidName(value) {
                const raw = String(value || "").trim();
                const normalized = normalizeText(raw);

                if (raw.length < 2 || raw.length > 120) return false;
                if (priceRegex.test(raw)) {
                    priceRegex.lastIndex = 0;
                    return false;
                }

                priceRegex.lastIndex = 0;

                if (badWords.some(word => normalized.includes(normalizeText(word)))) return false;

                return true;
            }

            function getLeafTexts(root) {
                return Array.from(root.querySelectorAll("*"))
                    .filter(el => el.children.length === 0)
                    .map(el => ({
                        text: (el.textContent || "").trim(),
                        element: el
                    }))
                    .filter(x => x.text.length > 0);
            }

            const priceLeaves = Array.from(document.querySelectorAll("body *"))
                .filter(el => el.children.length === 0)
                .filter(el => {
                    const text = el.textContent || "";
                    const ok = priceRegex.test(text);
                    priceRegex.lastIndex = 0;
                    return ok;
                });

            const results = [];
            const seen = new Set();

            for (const priceEl of priceLeaves) {
                let card = priceEl;

                for (let depth = 0; depth < 8; depth++) {
                    card = card.parentElement;
                    if (!card) break;

                    const cardText = card.innerText || "";

                    if (cardText.length < 10 || cardText.length > 1200) continue;

                    const priceMatches = cardText.match(priceRegex) || [];
                    priceRegex.lastIndex = 0;

                    if (priceMatches.length === 0) continue;

                    const leafTexts = getLeafTexts(card);
                    const priceIndex = leafTexts.findIndex(x => x.element === priceEl || x.text.includes(priceEl.textContent.trim()));

                    let name = null;

                    for (let i = Math.max(0, priceIndex - 6); i < priceIndex; i++) {
                        const candidate = leafTexts[i]?.text;
                        if (isValidName(candidate)) {
                            name = candidate;
                            break;
                        }
                    }

                    if (!name) {
                        for (const leaf of leafTexts) {
                            if (isValidName(leaf.text)) {
                                name = leaf.text;
                                break;
                            }
                        }
                    }

                    if (!name) continue;

                    const prices = priceMatches
                        .map(parsePrice)
                        .filter(x => x !== null)
                        .sort((a, b) => a - b);

                    if (prices.length === 0) continue;

                    const currentPrice = prices[0];
                    const originalPrice = prices.length > 1 ? prices[prices.length - 1] : currentPrice;

                    const key = `${normalizeText(name)}|${currentPrice}|${originalPrice}`;

                    if (seen.has(key)) break;
                    seen.add(key);

                    results.push({
                        name,
                        price: `${currentPrice.toFixed(2)} TL`,
                        original_price: `${originalPrice.toFixed(2)} TL`,
                        source: "dom"
                    });

                    break;
                }
            }

            return results;
        }
        """
    )


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
                "source": "text",
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

        items = extract_items_from_json_payloads(captured_json_payloads)

        if items:
            print(f"{restaurant_name}: {len(items)} ürün JSON/API response üzerinden bulundu.")
            source = "json"
        else:
            items = extract_items_from_dom_cards(page)

            if items:
                print(f"{restaurant_name}: {len(items)} ürün DOM kart parser ile bulundu.")
                source = "dom"
            else:
                body_text = page.locator("body").inner_text(timeout=10000)
                items = extract_items_from_page_text(body_text)
                print(f"{restaurant_name}: {len(items)} ürün sayfa metni fallback ile bulundu.")
                source = "text"

        return {
            "restaurant_name": restaurant_name,
            "restaurant_rating": None,
            "restaurant_url": url,
            "items": items,
            "extraction_source": source,
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