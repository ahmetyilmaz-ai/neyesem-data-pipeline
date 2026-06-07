"""
Trendyol Go (tgoyemek) için tarayıcısız, tam otomatik scraper.

Eski Playwright + DOM yaklaşımı kırılgandı (captcha, "Detaylar" çöpü, her
restoranda manuel uğraş). Bu sürüm Trendyol'un kendi public API'sini doğrudan
kullanır (Getir scraper'ı ile aynı mantık):

  1. Restoran listesi:
     GET web-discovery-apidiscovery-santral/restaurants/filters
         ?latitude=..&longitude=..&page=..&pageSize=..
     -> data.restaurants (id, name, rating, kitchen), data.restaurantCount

  2. Restoran menüsü:
     GET web-restaurant-apirestaurant-santral/restaurants/{id}
         ?latitude=..&longitude=..
     -> data.restaurant.sections[].products[]  (name, price.salePrice, ...)

Menü ayrıştırma ortak scrapers/menu_parser üzerinden yapılır.

Kullanım:
    python scrape_trendyol_api.py                 # varsayılan limitle
    python scrape_trendyol_api.py --max 200       # 200 restoran
    python scrape_trendyol_api.py --max 0         # tüm restoranlar (~976)
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import requests

from scrapers.menu_parser import extract_menu_items


OUTPUT_PATH = Path("data/raw/trendyol_raw.json")

DISCOVERY_BASE = "https://api.tgoapis.com/web-discovery-apidiscovery-santral"
RESTAURANT_BASE = "https://api.tgoapis.com/web-restaurant-apirestaurant-santral"

# Bursa merkez koordinatları (proje tek şehir: Bursa).
CITY = "bursa"
LAT = 40.195
LON = 29.060

PAGE_SIZE = 20
REQUEST_DELAY = 0.6  # saniye; sunucuya yük bindirmemek için nazik gecikme

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Origin": "https://tgoyemek.com",
    "Referer": "https://tgoyemek.com/",
}


def get_json(session, url, params=None):
    response = session.get(url, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def list_restaurants(session, max_restaurants):
    """restaurants/filters üzerinden sayfa sayfa restoranları toplar."""
    restaurants = []
    page = 1

    while True:
        try:
            payload = get_json(
                session,
                f"{DISCOVERY_BASE}/restaurants/filters",
                params={
                    "latitude": LAT,
                    "longitude": LON,
                    "page": page,
                    "pageSize": PAGE_SIZE,
                },
            )
        except Exception as exc:
            print(f"  Restoran listesi sayfa {page} alınamadı: {exc}")
            break

        data = payload.get("data", payload)
        page_restaurants = data.get("restaurants", []) or []

        if not page_restaurants:
            break

        for raw in page_restaurants:
            restaurants.append(
                {
                    "id": raw.get("id"),
                    "name": raw.get("name"),
                    "rating": raw.get("rating") or raw.get("ratingText"),
                    "kitchen": raw.get("kitchen"),
                }
            )

        total = data.get("restaurantCount")
        print(f"  Sayfa {page}: +{len(page_restaurants)} restoran "
              f"(toplam toplanan: {len(restaurants)} / {total})")

        if max_restaurants and len(restaurants) >= max_restaurants:
            restaurants = restaurants[:max_restaurants]
            break

        if total is not None and len(restaurants) >= total:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return restaurants


def fetch_menu(session, restaurant_id):
    """Tek restoranın menü cevabını alır ve ortak parser ile ürünleri çıkarır."""
    payload = get_json(
        session,
        f"{RESTAURANT_BASE}/restaurants/{restaurant_id}",
        params={"latitude": LAT, "longitude": LON},
    )

    products = extract_menu_items(payload)

    # menü cevabındaki güvenilir restoran meta verisi (puan, ad)
    info = (
        payload.get("data", payload)
        .get("restaurant", {})
        .get("info", {})
        if isinstance(payload, dict) else {}
    )
    score = info.get("score") or {}
    rating = None
    if isinstance(score, dict):
        rating = score.get("averageScore") or score.get("score") or score.get("value")

    items = []
    for product in products:
        items.append(
            {
                "name": product["name"],
                "price": f"{product['price']:.2f} TL",
                "original_price": f"{product['original_price']:.2f} TL",
                "category": product.get("category"),
                "image_url": product.get("image_url"),
                "source": "api",
            }
        )

    return items, info.get("name"), rating


def save(results):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=40,
                        help="Çekilecek maksimum restoran (0 = tümü)")
    args = parser.parse_args()

    session = requests.Session()

    print("Trendyol restoran listesi alınıyor...")
    restaurants = list_restaurants(session, max_restaurants=args.max)
    print(f"\n{len(restaurants)} restoran bulundu. Menüler çekiliyor...\n")

    results = []

    for index, restaurant in enumerate(restaurants, start=1):
        rid = restaurant.get("id")
        if not rid:
            continue

        try:
            items, menu_name, rating = fetch_menu(session, rid)
        except Exception as exc:
            print(f"[{index}/{len(restaurants)}] {restaurant.get('name')}: HATA {exc}")
            continue

        results.append(
            {
                "restaurant_name": menu_name or restaurant.get("name"),
                "restaurant_rating": rating if rating is not None else restaurant.get("rating"),
                "restaurant_url": f"https://tgoyemek.com/restoranlar/{rid}",
                "city": CITY,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "extraction_source": "api",
                "items": items,
            }
        )

        print(f"[{index}/{len(restaurants)}] {restaurant.get('name')}: {len(items)} ürün")

        if index % 10 == 0:
            save(results)

        time.sleep(REQUEST_DELAY)

    save(results)

    total_items = sum(len(r["items"]) for r in results)
    print()
    print(f"Kaydedildi: {OUTPUT_PATH}")
    print(f"Restoran: {len(results)} | Toplam ürün: {total_items}")


if __name__ == "__main__":
    main()
