import json
import re
from datetime import datetime
from pathlib import Path

import requests


OUTPUT_PATH = Path("data/raw/getir_raw.json")

FOOD_API = "https://food-client-api-gateway.getirapi.com"
WEB_BASE = "https://getir.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/html,*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Bursa merkez civarı
CITY = "bursa"
LAT = 40.195
LON = 29.060


def parse_price(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value)
    text = text.replace("₺", "").replace("TL", "").strip()
    text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def get_restaurants(limit=10):
    url = f"{FOOD_API}/restaurants"
    response = requests.get(
        url,
        params={"lat": LAT, "lon": LON},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    restaurants = data.get("data", {}).get("items", [])

    return restaurants[:limit]


def extract_next_data(html):
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )

    if not match:
        return None

    return json.loads(match.group(1))


def get_menu_from_slug(slug):
    if not slug:
        return []

    url = f"{WEB_BASE}/yemek/restoran/{slug}/"
    response = requests.get(url, headers=HEADERS, timeout=30)

    if response.status_code != 200:
        print(f"Menü alınamadı: {slug} | HTTP {response.status_code}")
        return []

    page_data = extract_next_data(response.text)

    if not page_data:
        print(f"__NEXT_DATA__ bulunamadı: {slug}")
        return []

    state = (
        page_data
        .get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
    )

    menu_data = state.get("restaurantDetail", {}).get("menu", {})
    categories = menu_data.get("productCategories", [])

    menu_items = []

    for category in categories:
        category_name = category.get("name")

        for product in category.get("products", []):
            price = parse_price(product.get("price"))

            if price is None:
                price = parse_price(product.get("priceText"))

            if not product.get("name") or price is None:
                continue

            menu_items.append(
                {
                    "name": product.get("name"),
                    "description": product.get("description"),
                    "category": category_name,
                    "price": price,
                    "original_price": None,
                    "discount_percentage": None,
                    "image_url": product.get("imageURL") or product.get("fullScreenImageURL"),
                }
            )

    return menu_items


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    restaurants = get_restaurants(limit=10)
    output = []

    print(f"{len(restaurants)} Getir restoranı bulundu.")

    for restaurant in restaurants:
        name = restaurant.get("name")
        slug = restaurant.get("slug")
        rating = restaurant.get("ratingPoint")

        print(f"Menü çekiliyor: {name}")

        menu_items = get_menu_from_slug(slug)

        output.append(
            {
                "restaurant_id": restaurant.get("id"),
                "restaurant_name": name,
                "restaurant_rating": rating,
                "restaurant_slug": slug,
                "restaurant_url": f"{WEB_BASE}/yemek/restoran/{slug}/" if slug else None,
                "city": CITY,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "items": menu_items,
            }
        )

        print(f"  {len(menu_items)} ürün")

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    total_items = sum(len(r.get("items", [])) for r in output)

    print(f"{len(output)} restoran kaydedildi.")
    print(f"{total_items} ürün bulundu.")
    print(f"Çıktı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
