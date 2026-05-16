import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests


OUTPUT_PATH = Path("data/raw/getir_raw.json")
DEBUG_DIR = Path("data/debug/getir")

FOOD_API = "https://food-client-api-gateway.getirapi.com"
WEB_BASE = "https://getir.com"

CITY = "bursa"
LAT = 40.195
LON = 29.060
MAX_RESTAURANTS = 12

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_price(value):
    if value is None:
        return None

    if isinstance(value, dict):
        for key in ["value", "text", "price", "amount"]:
            if key in value:
                return parse_price(value.get(key))
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value)
    text = text.replace("₺", "").replace("TL", "").strip()
    text = re.sub(r"[^0-9,\.]", "", text)

    if not text:
        return None

    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def extract_next_data(html):
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )

    if not match:
        return None

    return json.loads(match.group(1))


def get_restaurants():
    response = requests.get(
        f"{FOOD_API}/restaurants",
        params={"lat": LAT, "lon": LON},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    restaurants = data.get("data", {}).get("items", [])

    return restaurants[:MAX_RESTAURANTS]


def get_slug(raw):
    for key in ["slug", "restaurantSlug", "seoName"]:
        value = raw.get(key)
        if value:
            return str(value).strip("/")

    return None


def parse_product(product, category_name=None):
    name = product.get("name") or product.get("title")
    price = (
        parse_price(product.get("price"))
        or parse_price(product.get("priceText"))
        or parse_price(product.get("displayPrice"))
        or parse_price(product.get("finalPrice"))
    )

    original_price = (
        parse_price(product.get("originalPrice"))
        or parse_price(product.get("strikeThroughPrice"))
        or parse_price(product.get("oldPrice"))
    )

    discount_percentage = (
        product.get("discountPercentage")
        or product.get("discount_percentage")
        or product.get("discountRate")
    )

    if not name or price is None:
        return None

    return {
        "name": name,
        "description": product.get("description"),
        "category": category_name,
        "price": price,
        "original_price": original_price,
        "discount_percentage": discount_percentage,
        "image_url": product.get("imageURL") or product.get("fullScreenImageURL"),
    }


def extract_menu_items(page_data):
    items = []
    seen = set()

    # 1) Önce kategori -> products yapısını dene
    for obj in walk(page_data):
        products = obj.get("products") if isinstance(obj, dict) else None

        if not isinstance(products, list):
            continue

        category_name = obj.get("name") or obj.get("title")

        for product in products:
            if not isinstance(product, dict):
                continue

            item = parse_product(product, category_name=category_name)

            if not item:
                continue

            key = (item["name"], item["price"])

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

    # 2) Kategori yapısı bulunamazsa generic product scan
    if items:
        return items

    for obj in walk(page_data):
        if not isinstance(obj, dict):
            continue

        item = parse_product(obj)

        if not item:
            continue

        key = (item["name"], item["price"])

        if key in seen:
            continue

        seen.add(key)
        items.append(item)

    return items


def fetch_menu(restaurant):
    slug = get_slug(restaurant)

    if not slug:
        return [], None

    url = f"{WEB_BASE}/yemek/restoran/{slug}/"

    response = requests.get(url, headers=HEADERS, timeout=30)

    if response.status_code != 200:
        print(f"  Menü sayfası alınamadı: HTTP {response.status_code}")
        return [], url

    page_data = extract_next_data(response.text)

    if not page_data:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        debug_path = DEBUG_DIR / f"{slug}.html"
        debug_path.write_text(response.text, encoding="utf-8")
        print(f"  __NEXT_DATA__ bulunamadı. Debug kaydedildi: {debug_path}")
        return [], url

    items = extract_menu_items(page_data)

    return items, url


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    restaurants = get_restaurants()
    output = []

    print(f"{len(restaurants)} Getir restoranı bulundu.")

    for index, restaurant in enumerate(restaurants, start=1):
        name = restaurant.get("name")
        rating = restaurant.get("ratingPoint")
        slug = get_slug(restaurant)

        print(f"[{index}/{len(restaurants)}] Menü çekiliyor: {name}")

        try:
            items, restaurant_url = fetch_menu(restaurant)
        except Exception as exc:
            print(f"  Hata: {exc}")
            items = []
            restaurant_url = None

        output.append(
            {
                "restaurant_id": restaurant.get("id"),
                "restaurant_name": name,
                "restaurant_rating": rating,
                "restaurant_slug": slug,
                "restaurant_url": restaurant_url,
                "city": CITY,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "items": items,
            }
        )

        print(f"  {len(items)} ürün")
        time.sleep(1)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    total_items = sum(len(r.get("items", [])) for r in output)

    print()
    print(f"{len(output)} restoran kaydedildi.")
    print(f"{total_items} ürün bulundu.")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
